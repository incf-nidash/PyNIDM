"""
AI-assisted SPARQL query tool for NIDM files.

This tool uses a two-phase approach:
  Phase 1: AI extracts concepts from the user's question, then the tool
           resolves them to DataElement URIs using isAbout/sourceVariable
           properties.  If multiple matches are found the user picks.
  Phase 2: AI generates a SPARQL query using the resolved, exact URIs.
"""

import json
import os
from pathlib import Path
import re
import sys
import click
from rdflib import Graph, Namespace
from nidm.experiment.tools.click_base import cli

# ---------------------------------------------------------------------------
# Namespace constants
# ---------------------------------------------------------------------------

NIDM = Namespace("http://purl.org/nidash/nidm#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
DCT = Namespace("http://purl.org/dc/terms/")
RDF_NS = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "nidm_schema.json"

# ---------------------------------------------------------------------------
# DataElement extraction
# ---------------------------------------------------------------------------


def _extract_data_elements(nidm_files):
    """Extract DataElement summaries from the supplied NIDM files.

    Returns a list of dicts with keys: uri, qname, label, description,
    is_about, source_variable, value_type, measure_of, laterality, unit,
    datum_type.
    """
    g = Graph()
    for f in nidm_files:
        g.parse(f, format="turtle")

    # Collect all DataElement URIs
    de_uris = set()
    for de_type in (NIDM["DataElement"], NIDM["PersonalDataElement"]):
        for s in g.subjects(RDF_NS["type"], de_type):
            de_uris.add(s)
    # Pipeline-specific types (fsl:DataElement, freesurfer:DataElement, etc.)
    for s, _p, o in g.triples((None, RDF_NS["type"], None)):
        if str(o).endswith("DataElement") and s not in de_uris:
            de_uris.add(s)

    data_elements = []
    for de in sorted(de_uris, key=str):
        entry = {"uri": str(de)}
        try:
            prefix, namespace, local = g.compute_qname(str(de))
            entry["qname"] = f"{prefix}:{local}"
        except Exception:
            entry["qname"] = str(de)

        for label in g.objects(de, RDFS["label"]):
            entry["label"] = str(label)
        for desc in g.objects(de, DCT["description"]):
            entry["description"] = str(desc)
        for isa in g.objects(de, NIDM["isAbout"]):
            entry["is_about"] = str(isa)
        for sv in g.objects(de, NIDM["sourceVariable"]):
            entry["source_variable"] = str(sv)
        for vt in g.objects(de, NIDM["valueType"]):
            entry["value_type"] = str(vt)
        for mo in g.objects(de, NIDM["measureOf"]):
            entry["measure_of"] = str(mo)
        for lat in g.objects(de, NIDM["hasLaterality"]):
            entry["laterality"] = str(lat)
        for unit in g.objects(de, NIDM["hasUnit"]):
            entry["unit"] = str(unit)
        for dt in g.objects(de, NIDM["datumType"]):
            entry["datum_type"] = str(dt)

        data_elements.append(entry)

    return data_elements, g


def _extract_projects(g):
    """Extract project titles from a loaded graph."""
    DCTYPES = Namespace("http://purl.org/dc/dcmitype/")
    projects = []
    for proj in g.subjects(RDF_NS["type"], NIDM["Project"]):
        entry = {"uri": str(proj)}
        for title in g.objects(proj, DCTYPES["title"]):
            entry["title"] = str(title)
        projects.append(entry)
    return projects


def _extract_namespace_prefixes(g):
    """Extract all namespace prefix bindings from a loaded graph."""
    return {prefix: str(ns) for prefix, ns in g.namespaces() if prefix}


# ---------------------------------------------------------------------------
# Phase 1:  Concept extraction  +  DataElement resolution
# ---------------------------------------------------------------------------

# Well-known isAbout URIs for common concepts
_KNOWN_CONCEPTS = {
    "age": [
        "http://uri.interlex.org/ilx_0100400",
        "http://uri.interlex.org/base/ilx_0100400",
    ],
    "sex": [
        "http://uri.interlex.org/base/ilx_0101292",
        "http://uri.interlex.org/ilx_0101292",
    ],
    "gender": [
        "http://uri.interlex.org/base/ilx_0101292",
        "http://uri.interlex.org/ilx_0101292",
    ],
    "diagnosis": [
        "http://ncitt.ncit.nih.gov/Diagnosis",
        "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#Diagnosis",
    ],
    "handedness": [
        "http://uri.interlex.org/base/ilx_0104886",
        "http://uri.interlex.org/ilx_0104886",
    ],
}


def _resolve_concept(concept_name, data_elements, concept_hints=None):
    """Resolve a concept name to matching DataElement(s).

    Strategy:
      1. If concept_hints provides an isAbout URI, match on that.
      2. Try well-known isAbout URIs for common concepts (age, sex, etc.)
      3. Fall back to substring match on sourceVariable and label.

    Returns a list of matching DE dicts.
    """
    matches = []
    concept_lower = concept_name.lower().strip()

    # --- Strategy 1: Explicit isAbout hint from the AI -----------------
    if concept_hints and concept_hints.get("is_about"):
        hint_uri = concept_hints["is_about"]
        for de in data_elements:
            if de.get("is_about") == hint_uri:
                matches.append(de)
        if matches:
            return matches

    # --- Strategy 2: Well-known isAbout URIs ---------------------------
    known_uris = _KNOWN_CONCEPTS.get(concept_lower, [])
    for uri in known_uris:
        for de in data_elements:
            if de.get("is_about") == uri:
                matches.append(de)
    if matches:
        return matches

    # --- Strategy 3: Match on label containing concept keywords --------
    # For brain regions, also check measureOf and laterality
    laterality = concept_hints.get("laterality") if concept_hints else None
    keywords = [w.lower() for w in concept_lower.split() if len(w) > 2]

    for de in data_elements:
        label = de.get("label", "").lower()
        src_var = de.get("source_variable", "").lower()
        is_about = de.get("is_about", "").lower()

        # Check label and source_variable for keyword matches
        text = f"{label} {src_var} {is_about}"
        if all(kw in text for kw in keywords):
            # If laterality is specified, filter on it
            if laterality:
                if de.get("laterality", "").lower() != laterality.lower():
                    continue
            matches.append(de)

    # --- Strategy 3b: Looser match on sourceVariable -------------------
    # Use word boundary matching to avoid "ant" matching "stimulants"
    if not matches:
        for de in data_elements:
            sv = de.get("source_variable", "").lower()
            if sv and concept_lower in sv:
                matches.append(de)
            elif sv and any(
                re.search(r"\b" + re.escape(kw) + r"\b", sv) for kw in keywords
            ):
                matches.append(de)

    return matches


def _format_de_for_display(de, index=None):
    """Format a DE for display to the user during disambiguation."""
    prefix = f"  [{index}] " if index is not None else "  "
    parts = [de.get("qname", de["uri"])]
    if "label" in de:
        parts.append(f'label="{de["label"]}"')
    if "source_variable" in de:
        parts.append(f'sourceVariable="{de["source_variable"]}"')
    if "is_about" in de:
        parts.append(f"isAbout={de['is_about']}")
    if "measure_of" in de:
        parts.append(f"measureOf={de['measure_of']}")
    if "laterality" in de:
        parts.append(f"laterality={de['laterality']}")
    if "unit" in de:
        parts.append(f"unit={de['unit']}")
    if "description" in de:
        desc = de["description"]
        if len(desc) > 60:
            desc = desc[:57] + "..."
        parts.append(f'desc="{desc}"')
    return prefix + " | ".join(parts)


def _ask_user_to_pick(concept_name, matches):
    """Present multiple DE matches and let the user choose one, several, or all.

    Returns a list of selected DE dicts (may contain multiple entries),
    or None if the user wants to skip.
    """
    n = len(matches)
    click.echo(
        f"\nMultiple DataElements match '{concept_name}':",
        err=True,
    )
    for i, de in enumerate(matches):
        click.echo(_format_de_for_display(de, index=i + 1), err=True)
    click.echo("  [a] Select all", err=True)
    click.echo("  [0] Skip this variable", err=True)
    click.echo(
        "\nEnter one number, multiple numbers separated by commas "
        "(e.g. 2,3), 'a' for all, or 0 to skip.",
        err=True,
    )

    while True:
        try:
            raw = input("Your choice: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if raw == "0":
            return None
        if raw.lower() == "a":
            return list(matches)
        # Parse comma-separated indices
        try:
            indices = [int(x.strip()) - 1 for x in raw.split(",")]
            if all(0 <= idx < n for idx in indices):
                return [matches[idx] for idx in indices]
        except ValueError:
            pass
        click.echo(
            f"  Please enter numbers between 1 and {n} "
            f"(comma-separated), 'a' for all, or 0 to skip.",
            err=True,
        )


# ---------------------------------------------------------------------------
# Phase 1 AI call:  extract concepts from the user's question
# ---------------------------------------------------------------------------

_CONCEPT_EXTRACTION_PROMPT = """\
You are a helper that extracts variable concepts from natural-language
questions about neuroimaging datasets.

Given a question, return a JSON array of objects, one per variable/concept
the user wants.  Each object should have:
  - "name": short concept name (e.g. "age", "sex", "left hippocampus volume")
  - "role": one of "demographic", "measurement", "identifier", "software",
            "aggregate", or "other"
  - "laterality": "Left" or "Right" if applicable, otherwise null
  - "is_about": an ontology URI if you know the standard one, otherwise null
  - "keywords": list of search keywords to find the variable

Only return the JSON array, no other text.  Wrap it in a ```json block.

Example for "What is the average age of male subjects?":
```json
[
  {"name": "age", "role": "demographic", "laterality": null,
   "is_about": "http://uri.interlex.org/ilx_0100400",
   "keywords": ["age"]},
  {"name": "sex", "role": "demographic", "laterality": null,
   "is_about": "http://uri.interlex.org/base/ilx_0101292",
   "keywords": ["sex", "gender", "male", "female"]}
]
```
"""


def _extract_concepts_from_question(question):
    """Use AI to extract variable concepts from the user's question.

    Returns a list of concept dicts.
    """
    response = _send_to_ai(_CONCEPT_EXTRACTION_PROMPT, question)

    # Parse JSON from response
    match = re.search(r"```json\s*\n(.*?)```", response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Fallback: try parsing entire response as JSON
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        click.echo(
            "Warning: Could not parse concept extraction response. "
            "Proceeding with basic keyword matching.",
            err=True,
        )
        return []


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------


def _load_schema_context():
    """Load the NIDM LinkML schema and extract structural context for the AI.

    Returns a string describing the graph hierarchy, class relationships,
    example SPARQL patterns, and important notes — all derived from the schema
    rather than hardcoded.
    """
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

    sections = []

    # 1. Graph hierarchy (from annotations)
    annotations = schema.get("annotations", {})
    if "graph_hierarchy" in annotations:
        sections.append(
            "### Graph Hierarchy\n```\n" + annotations["graph_hierarchy"] + "\n```"
        )

    # 2. Class descriptions and relationships
    classes = schema.get("classes", {})
    class_lines = []
    for cls_name, cls_def in classes.items():
        desc = cls_def.get("description", "")
        uri = cls_def.get("class_uri", "")
        comments = cls_def.get("comments", [])
        parent = cls_def.get("is_a", "")

        line = f"**{cls_name}** (`{uri}`)"
        if parent:
            line += f" — subclass of {parent}"
        line += f"\n  {desc}"
        for c in comments:
            line += f"\n  - {c}"

        # List key attributes with their slot_uri
        attrs = cls_def.get("attributes", {})
        if attrs:
            attr_lines = []
            for attr_name, attr_def in attrs.items():
                slot_uri = attr_def.get("slot_uri", "")
                attr_desc = attr_def.get("description", "")
                attr_range = attr_def.get("range", "")
                if slot_uri:
                    attr_lines.append(
                        f"    {attr_name}: `{slot_uri}` "
                        f"-> {attr_range} — {attr_desc}"
                    )
            if attr_lines:
                line += "\n  Attributes:\n" + "\n".join(attr_lines)

        class_lines.append(line)

    sections.append("### Classes\n\n" + "\n\n".join(class_lines))

    # 3. Example SPARQL patterns
    sparql_examples = []
    for key, val in annotations.items():
        if key.startswith("sparql_"):
            label = key.replace("sparql_", "").replace("_", " ").title()
            sparql_examples.append(f"**{label}:**\n```sparql\n{val}\n```")
    if sparql_examples:
        sections.append(
            "### Example SPARQL Patterns\n\n" + "\n\n".join(sparql_examples)
        )

    # 4. Important notes
    if "important_notes" in annotations:
        sections.append("### Important Notes\n" + annotations["important_notes"])

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Phase 2:  SPARQL generation with resolved URIs
# ---------------------------------------------------------------------------


def _build_sparql_prompt(resolved_vars, prefixes, projects):
    """Build the system prompt for SPARQL generation.

    Loads the NIDM schema to teach the AI about graph structure, then adds
    the resolved variable URIs.  *resolved_vars* is a list of dicts, each
    with: name, role, qname, uri, label, laterality, ...
    """
    # Load structural context from the schema document
    schema_context = _load_schema_context()

    prefix_block = "\n".join(
        f"PREFIX {p}: <{uri}>" for p, uri in sorted(prefixes.items())
    )

    proj_block = "\n".join(
        f"  - {p['uri']}" + (f"  title: {p['title']}" if "title" in p else "")
        for p in projects
    )

    # Format the resolved variables
    var_block = ""
    for v in resolved_vars:
        var_block += f"  - Concept: {v['name']}\n"
        var_block += f"    Role: {v['role']}\n"
        if v.get("qname"):
            var_block += f"    USE THIS EXACT URI AS PREDICATE: {v['qname']}\n"
            var_block += f"    Full URI: <{v['uri']}>\n"
        if v.get("label"):
            var_block += f"    Label: {v['label']}\n"
        if v.get("laterality"):
            var_block += f"    Laterality: {v['laterality']}\n"
        if v.get("unit"):
            var_block += f"    Unit: {v['unit']}\n"

    return f"""\
You are a SPARQL query generator for NIDM (Neuroimaging Data Model) RDF graphs.

The variables have ALREADY been resolved to exact DataElement URIs.
You MUST use the exact URIs listed below — do NOT substitute or invent URIs.

## RESOLVED VARIABLES

{var_block}

## NIDM GRAPH STRUCTURE (from schema)

{schema_context}

## CRITICAL QUERY RULES

1. **Demographics (age, sex, diagnosis) are ALL on ONE entity.**
   Use a single ?demo_ent with multiple DE predicates.

2. **Brain measurements are on SEPARATE entities from demographics.**
   Join demographics and measurements by matching subject ID (?ID).

3. **SoftwareAgents:** Use `a prov:SoftwareAgent` (rdf:type), NEVER
   `prov:type`. They have `nidm:NIDM_0000164` for the tool namespace URI.

4. **Numeric values:** Values are often xsd:string. For numeric ops cast
   with `xsd:float(?val)`.
   Filter: `FILTER(?val != "n/a" && ?val != "" && BOUND(?val))`

5. **Use EXACT URIs from RESOLVED VARIABLES as predicates.**
   Do NOT invent, guess, or modify any URI. If a variable has no resolved
   URI (role is identifier/aggregate/software), follow the schema patterns
   instead.  NEVER use placeholders like <YOUR_URI_HERE>.

## Available Prefixes
```sparql
{prefix_block}
```

## Projects
{proj_block}

## Instructions
1. Use the EXACT URIs from RESOLVED VARIABLES above as predicates.
2. Refer to the NIDM GRAPH STRUCTURE for how to traverse the graph.
3. Include a PREFIX declaration for EVERY namespace prefix you use.
4. Return ONLY the SPARQL in a ```sparql block.
"""


# ---------------------------------------------------------------------------
# AI provider interface
# ---------------------------------------------------------------------------


def _get_api_key():
    """Get the API key from environment or config file."""
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    config_path = Path.home() / ".pynidm" / "config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())
        return config.get("api_key")
    return None


def _get_provider():
    """Determine which AI provider to use based on available API key."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    config_path = Path.home() / ".pynidm" / "config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())
        return config.get("provider", "anthropic")
    return None


def _query_anthropic(system_prompt, user_question, api_key):
    """Send a query to the Anthropic API and return the response text."""
    try:
        import anthropic
    except ImportError:
        click.echo(
            "Error: anthropic package not installed. "
            "Install with: pip install anthropic",
            err=True,
        )
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_question}],
    )
    return message.content[0].text


def _query_openai(system_prompt, user_question, api_key):
    """Send a query to the OpenAI API and return the response text."""
    try:
        import openai
    except ImportError:
        click.echo(
            "Error: openai package not installed. " "Install with: pip install openai",
            err=True,
        )
        sys.exit(1)

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question},
        ],
        max_tokens=4096,
    )
    return response.choices[0].message.content


def _send_to_ai(system_prompt, user_question):
    """Send a question to the configured AI provider."""
    provider = _get_provider()
    api_key = _get_api_key()

    if not api_key:
        click.echo(
            "Error: No API key found. Set one of:\n"
            "  - ANTHROPIC_API_KEY environment variable\n"
            "  - OPENAI_API_KEY environment variable\n"
            "  - ~/.pynidm/config.json with "
            '{"provider": "anthropic", "api_key": "sk-ant-..."}',
            err=True,
        )
        sys.exit(1)

    if provider == "openai":
        return _query_openai(system_prompt, user_question, api_key)
    else:
        return _query_anthropic(system_prompt, user_question, api_key)


# ---------------------------------------------------------------------------
# SPARQL extraction and execution
# ---------------------------------------------------------------------------


def _extract_sparql(ai_response):
    """Extract a SPARQL query from the AI response text."""
    match = re.search(r"```sparql\s*\n(.*?)```", ai_response, re.DOTALL)
    if match:
        return match.group(1).strip()

    match = re.search(r"```\s*\n(.*?)```", ai_response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Fallback: lines starting with PREFIX or SELECT
    lines = ai_response.strip().split("\n")
    sparql_lines = []
    in_query = False
    for line in lines:
        stripped = line.strip().upper()
        if stripped.startswith("PREFIX") or stripped.startswith("SELECT"):
            in_query = True
        if in_query:
            sparql_lines.append(line)
    if sparql_lines:
        return "\n".join(sparql_lines).strip()

    return None


def _execute_sparql(nidm_files, sparql_query):
    """Execute a SPARQL query against the loaded NIDM files."""
    g = Graph()
    for f in nidm_files:
        g.parse(f, format="turtle")
    return g.query(sparql_query)


def _format_results(results):
    """Format SPARQL query results as a readable table."""
    if not results:
        return "No results found."

    rows = list(results)
    if not rows:
        return "No results found."

    vars_ = [str(v) for v in results.vars]
    header = "\t".join(vars_)
    lines = [header, "-" * len(header)]

    for row in rows:
        values = []
        for v in results.vars:
            val = row[v]
            if val is not None:
                val_str = str(val)
                for prefix, ns in [
                    ("niiri:", "http://iri.nidash.org/"),
                    ("nidm:", "http://purl.org/nidash/nidm#"),
                    ("prov:", "http://www.w3.org/ns/prov#"),
                ]:
                    if val_str.startswith(ns):
                        val_str = prefix + val_str[len(ns) :]
                        break
                values.append(val_str)
            else:
                values.append("")
        lines.append("\t".join(values))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--nidm_file_list",
    "-nl",
    required=True,
    help="A comma-separated list of NIDM files with full path.",
)
@click.option(
    "--question",
    "-q",
    required=False,
    default=None,
    help="Natural-language question to ask about the NIDM data. "
    "If not provided, enters interactive mode.",
)
@click.option(
    "--output_file",
    "-o",
    required=False,
    default=None,
    type=click.Path(),
    help="Optional output file for results (TSV format).",
)
@click.option(
    "--show_query",
    "-s",
    is_flag=True,
    default=False,
    help="Show the generated SPARQL query before executing it.",
)
def queryai(nidm_file_list, question, output_file, show_query):
    """AI-assisted natural-language query of NIDM files.

    Uses a two-phase approach:
      1. Extracts concepts from your question, resolves them to DataElement
         URIs using isAbout / sourceVariable properties.  If multiple matches
         are found you can pick the right one.
      2. Generates and executes a SPARQL query using the resolved URIs.

    \b
    Requires an API key for either Anthropic or OpenAI.  Set one of:
      export ANTHROPIC_API_KEY=sk-ant-...
      export OPENAI_API_KEY=sk-...
    Or create ~/.pynidm/config.json:
      {"provider": "anthropic", "api_key": "sk-ant-..."}

    \b
    Examples:
      pynidm queryai -nl data/nidm.ttl -q "How many subjects are there?"
      pynidm queryai -nl data/nidm.ttl -q "What is the average age?" -s
      pynidm queryai -nl data/nidm.ttl   (interactive mode)
    """

    # Parse file list
    nidm_files = [f.strip() for f in nidm_file_list.split(",") if f.strip()]
    for f in nidm_files:
        if not os.path.isfile(f):
            click.echo(f"Error: File not found: {f}", err=True)
            sys.exit(1)

    # Extract metadata from files (single parse)
    click.echo("Loading NIDM files and extracting metadata...", err=True)
    data_elements, g = _extract_data_elements(nidm_files)
    projects = _extract_projects(g)
    prefixes = _extract_namespace_prefixes(g)

    click.echo(
        f"Found {len(projects)} project(s), " f"{len(data_elements)} data element(s).",
        err=True,
    )

    def _ask(q):
        """Process a single question through both phases."""

        click.echo(f"\nQuestion: {q}", err=True)

        # ---- Phase 1: concept extraction + resolution ----
        click.echo("Phase 1: Identifying variables in your question...", err=True)
        concepts = _extract_concepts_from_question(q)

        if not concepts:
            click.echo(
                "Could not identify any variables. Trying direct SPARQL generation...",
                err=True,
            )
            # Fall back to a simple prompt with all personal DEs listed
            concepts = []

        # Resolve each concept to a DataElement URI
        resolved_vars = []
        for concept in concepts:
            name = concept.get("name", "unknown")
            role = concept.get("role", "other")

            # Roles that never need DataElement resolution:
            #  - "identifier": subject ID, handled by ndar:src_subject_id
            #  - "aggregate": COUNT/AVG/etc. — operations, not data variables
            #  - "software": tools (FreeSurfer, FSL, ANTs) are SoftwareAgents
            #    identified via nidm:NIDM_0000164, not DataElements
            if role in ("identifier", "aggregate", "software"):
                if role == "software":
                    click.echo(
                        f"  '{name}' is a software tool; handled by "
                        f"SoftwareAgent query pattern.",
                        err=True,
                    )
                resolved_vars.append(
                    {
                        "name": name,
                        "role": role,
                        "qname": None,
                        "uri": None,
                    }
                )
                continue

            click.echo(f"  Resolving '{name}'...", err=True)
            matches = _resolve_concept(name, data_elements, concept_hints=concept)

            if not matches:
                # Try with individual keywords
                for kw in concept.get("keywords", []):
                    matches = _resolve_concept(kw, data_elements)
                    if matches:
                        break

            if not matches:
                click.echo(
                    f"  WARNING: No DataElement found for '{name}'. "
                    f"This variable will be omitted from the query.",
                    err=True,
                )
                continue
            elif len(matches) == 1:
                selected_list = [matches[0]]
                click.echo(
                    f"  Found: {matches[0].get('qname', matches[0]['uri'])} "
                    f"(label=\"{matches[0].get('label', 'N/A')}\")",
                    err=True,
                )
            else:
                selected_list = _ask_user_to_pick(name, matches)
                if selected_list is None:
                    click.echo(f"  Skipping '{name}'.", err=True)
                    continue

            for selected in selected_list:
                # When multiple DEs are chosen for the same concept,
                # give each a distinct name so the AI creates separate
                # SPARQL variables (e.g. left_hippocampus_volume_fs,
                # left_hippocampus_volume_ants).
                if len(selected_list) > 1:
                    suffix = selected.get("qname", "").split(":")[0]
                    var_name = f"{name} ({suffix})"
                else:
                    var_name = name

                resolved_vars.append(
                    {
                        "name": var_name,
                        "role": role,
                        "qname": selected.get("qname", selected["uri"]),
                        "uri": selected["uri"],
                        "label": selected.get("label"),
                        "laterality": selected.get("laterality"),
                        "unit": selected.get("unit"),
                    }
                )

        # Show resolved variables
        click.echo("\nResolved variables:", err=True)
        for v in resolved_vars:
            if v.get("uri"):
                click.echo(
                    f"  {v['name']} -> {v['qname']} "
                    f"(label=\"{v.get('label', 'N/A')}\")",
                    err=True,
                )
            else:
                click.echo(f"  {v['name']} -> (handled by query pattern)", err=True)

        # ---- Phase 2: SPARQL generation ----
        click.echo("\nPhase 2: Generating SPARQL query...", err=True)

        # Only pass resolved vars that have URIs to the SPARQL prompt
        vars_with_uris = [v for v in resolved_vars if v.get("uri")]

        system_prompt = _build_sparql_prompt(vars_with_uris, prefixes, projects)
        ai_response = _send_to_ai(system_prompt, q)
        sparql_query = _extract_sparql(ai_response)

        if not sparql_query:
            click.echo(
                "Error: Could not extract a SPARQL query from the AI response.",
                err=True,
            )
            click.echo(f"AI response:\n{ai_response}", err=True)
            return

        if show_query:
            click.echo(f"\nGenerated SPARQL:\n{sparql_query}\n", err=True)

        click.echo("Executing query...", err=True)
        try:
            results = _execute_sparql(nidm_files, sparql_query)
            formatted = _format_results(results)
            click.echo(f"\nResults:\n{formatted}")

            if output_file:
                with open(output_file, "w", encoding="utf-8") as fout:
                    fout.write(formatted)
                click.echo(f"\nResults written to {output_file}", err=True)

        except Exception as e:
            click.echo(f"\nSPARQL execution error: {e}", err=True)
            click.echo(
                "The AI-generated query may have a syntax error. "
                "Try rephrasing your question.",
                err=True,
            )
            if show_query:
                click.echo(f"\nFailed query:\n{sparql_query}", err=True)

    if question:
        _ask(question)
    else:
        # Interactive mode
        click.echo(
            "\nNIDM AI Query - Interactive Mode\n"
            "Type your question and press Enter. Type 'quit' to exit.\n",
            err=True,
        )
        while True:
            try:
                q = input("Question: ").strip()
            except (EOFError, KeyboardInterrupt):
                click.echo("\nGoodbye!", err=True)
                break
            if not q or q.lower() in ("quit", "exit", "q"):
                click.echo("Goodbye!", err=True)
                break
            _ask(q)


if __name__ == "__main__":
    queryai()
