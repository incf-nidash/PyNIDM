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
from rdflib import Graph, Literal, Namespace
import requests
from nidm.linkml.core.query_terms import resolve_query_term
from nidm.linkml.experiment.tools.click_base import cli
from nidm.linkml.experiment.tools.nidm_file_utils import expand_nidm_file_list

# ---------------------------------------------------------------------------
# Namespace constants
# ---------------------------------------------------------------------------

NIDM = Namespace("http://purl.org/nidash/nidm#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
DCT = Namespace("http://purl.org/dc/terms/")
RDF_NS = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
PROV = Namespace("http://www.w3.org/ns/prov#")
# Subjects are identified by ndar:src_subject_id.  The SAME human can appear
# under different Person nodes (one per source file) and with differently
# zero-padded ids ("50772" in demographics vs "0050772" in a FreeSurfer/FSL
# derivative); the deterministic builder normalizes by stripping leading zeros.
NDAR = Namespace("https://ndar.nih.gov/api/datadictionary/v2/dataelement/")
# NIDM encodes a DataElement's value levels (coded value -> human label) as
# reproschema:choices -> bnode(reproschema:value, rdfs:label).  Namespace is
# http://schema.repronim.org/ (NOT the ".../reproschema#" form models tend to
# guess).
REPROSCHEMA = Namespace("http://schema.repronim.org/")

_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent / "schema" / "nidm_schema.json"
)

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

        # Pipeline DataElements (fsl:, freesurfer:, ants:, ...) describe the
        # measured region/quantity with namespace-specific "structure" and
        # "measure" predicates rather than nidm:sourceVariable.  Capture them so
        # concept resolution can match phrasing like "left hippocampus volume"
        # (structure="Left-Hippocampus", measure="Volume").  Matched generically
        # by predicate local-name so it works across pipeline namespaces.
        for p, o in g.predicate_objects(de):
            plocal = str(p).rsplit("/", 1)[-1].rsplit("#", 1)[-1].lower()
            if plocal == "structure" and "structure" not in entry:
                entry["structure"] = str(o)
            elif plocal == "measure" and "measure" not in entry:
                entry["measure"] = str(o)

        # Value levels (coded value -> human label), when defined in the data.
        # NIDM stores these as reproschema:choices -> bnode(reproschema:value,
        # rdfs:label).  Only captured when BOTH a value and a label are present;
        # this is the ONLY thing that licenses queryai to translate coded values
        # (e.g. sex "1" -> "Male").  Absent here => no mapping is possible.
        levels = {}
        for choice in g.objects(de, REPROSCHEMA["choices"]):
            if isinstance(choice, Literal):
                continue  # bare enumerated value, no value->label pair
            val = next(g.objects(choice, REPROSCHEMA["value"]), None)
            lab = next(g.objects(choice, RDFS["label"]), None)
            if val is not None and lab is not None:
                levels[str(val)] = str(lab)
        if levels:
            entry["levels"] = levels

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
        # Pipeline DataElements carry the region/quantity in structure/measure
        # (e.g. "Left-Hippocampus" / "Volume") instead of a sourceVariable, so
        # include them so phrases like "left hippocampus volume" resolve.
        structure = de.get("structure", "").lower()
        measure = de.get("measure", "").lower()

        # Check label, source_variable, isAbout, structure and measure
        text = f"{label} {src_var} {is_about} {structure} {measure}"
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


def _parse_concepts_json(response):
    """Best-effort extraction of the concept JSON array from an AI response.

    Tolerates: a fenced block with or without a ``json`` language tag, prose
    around the JSON, and a bare array embedded in surrounding text.  Returns a
    list of concept dicts on success, or ``None`` if nothing parses.
    """
    if not response:
        return None

    candidates = []
    # 1. fenced code block(s), with or without a "json" language tag
    for m in re.finditer(r"```(?:json)?\s*(.*?)```", response, re.DOTALL):
        candidates.append(m.group(1).strip())
    # 2. the whole response, stripped
    candidates.append(response.strip())
    # 3. the first balanced [...] array embedded anywhere in the text
    start = response.find("[")
    if start != -1:
        depth = 0
        for i in range(start, len(response)):
            if response[i] == "[":
                depth += 1
            elif response[i] == "]":
                depth -= 1
                if depth == 0:
                    candidates.append(response[start : i + 1])
                    break

    for cand in candidates:
        if not cand:
            continue
        try:
            parsed = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    return None


def _extract_concepts_from_question(question):
    """Use AI to extract variable concepts from the user's question.

    Returns a list of concept dicts.
    """
    concepts = _parse_concepts_json(_send_to_ai(_CONCEPT_EXTRACTION_PROMPT, question))
    if concepts is None:
        # Model formatting is non-deterministic; a single retry usually
        # returns clean, parseable JSON.
        concepts = _parse_concepts_json(
            _send_to_ai(_CONCEPT_EXTRACTION_PROMPT, question)
        )
    if concepts is None:
        click.echo(
            "Warning: Could not parse concept extraction response. "
            "Proceeding with basic keyword matching.",
            err=True,
        )
        return []
    return concepts


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
        if v.get("levels"):
            var_block += (
                f"    Value levels (coded -> label, the ONLY permitted "
                f"mapping for this variable): {v['levels']}\n"
            )
        else:
            var_block += (
                "    Value levels: NONE in the data — do NOT translate this "
                "variable's coded values; return them raw.\n"
            )

    return f"""\
You are a SPARQL query generator for NIDM (Neuroimaging Data Model) RDF graphs.

The variables have ALREADY been resolved to exact DataElement URIs.
You MUST use the exact URIs listed below — do NOT substitute or invent URIs.

## RESOLVED VARIABLES

{var_block}

## NIDM GRAPH STRUCTURE (from schema)

{schema_context}

## CRITICAL QUERY RULES

1. **Anchor EVERY value to a subject — a floating value block is the #1 bug.**
   Each value's carrying entity MUST be tied back to a subject; an entity
   variable that appears in a value triple but is not connected to a subject
   ranges over ALL subjects and produces a cartesian product (e.g. one
   subject's age paired with every subject's left x right volumes).
   - Values from the SAME source file share one `?person`:
     `?person ndar:src_subject_id ?subject_id .` then join each block to that
     shared `?person` node (do not re-derive it per block).
   - Values from DIFFERENT source files (e.g. demographics in one file,
     FreeSurfer/FSL volumes in another) have DIFFERENT Person nodes AND the
     `src_subject_id` may be zero-padded differently ("50772" vs "0050772").
     Join those by the leading-zero-stripped id, NOT by the same person node:
     `FILTER(REPLACE(STR(?id_a), "^0+", "") = REPLACE(STR(?id_b), "^0+", ""))`.

2. **Locate each value via the PROV backbone + its resolved DE URI:**
   ```
   ?act prov:qualifiedAssociation/prov:agent ?person .
   ?ent prov:wasGeneratedBy ?act ;
        <RESOLVED_DE_URI> ?value .
   ```
   Group DE predicates that live on the SAME entity (e.g. all
   participants.tsv columns such as age, sex, diagnosis, VIQ, PIQ, FIQ)
   into ONE such block.  Put values that live on a DIFFERENT entity
   (e.g. FreeSurfer / FSL / ANTS volumes) in their OWN person-anchored block.

3. **Do NOT constrain the carrying entity's rdf:type.**  The entity type
   varies across NIDM versions (nidm:AcquisitionObject, nidm:AssessmentObject,
   nidm:FSStatsCollection, nidm:DerivativeObject, ...).  The resolved DE URI
   alone uniquely identifies the value, so typing the entity is unnecessary
   and silently breaks older files.

4. **Edge direction & paths:** the entity is generated by the activity —
   write `?ent prov:wasGeneratedBy ?act` (entity is the subject).  Reuse
   `?person`; do not build long multi-hop property-path chains just to
   re-derive the subject id.

5. **SoftwareAgents:** Use `a prov:SoftwareAgent` (rdf:type), NEVER
   `prov:type`. They have `nidm:NIDM_0000164` for the tool namespace URI.

6. **Numeric values:** Values are often xsd:string. For numeric ops cast
   with `xsd:float(?val)`.
   Filter: `FILTER(?val != "n/a" && ?val != "" && BOUND(?val))`

7. **Use EXACT URIs from RESOLVED VARIABLES as predicates.**
   Do NOT invent, guess, or modify any URI. If a variable has no resolved
   URI (role is identifier/aggregate/software), follow the schema patterns
   instead.  NEVER use placeholders like <YOUR_URI_HERE>.

8. **NEVER invent value mappings — this is critical.**
   A coded value (e.g. sex "1"/"2", diagnosis "1"/"2") may be translated to a
   human-readable label ONLY when that variable lists "Value levels" in
   RESOLVED VARIABLES above.
   - If levels ARE listed: map using EXACTLY those coded->label pairs (a BIND
     or inline VALUES table), and nothing else.
   - If a variable's "Value levels" is NONE: return its RAW value unchanged.
     Do NOT translate it from outside/domain knowledge (dataset conventions,
     ABIDE coding, "1 usually means male", etc.), and do NOT emit a no-op
     `reproschema:choices` (or similar) triple to disguise a hardcoded guess.
   It is far better to return the raw coded value than a fabricated label.
   When the user asked for a mapping you cannot perform (no levels in the
   data), add a top-level SPARQL comment line for each such variable:
   `# NOTE: no value-level definitions for <var> in the data; returning raw values`
   and select the raw value.

9. **Valid SPARQL syntax only (not SQL).**
   - SPARQL has NO `CASE`/`WHEN`/`END`.  For conditionals use the function
     form `IF(condition, then_value, else_value)` (nestable), or a `VALUES`
     table.  Example: `BIND(IF(?x = "1", "yes", "no") AS ?label)`.
   - Never `BIND(... AS ?v)` to a variable `?v` that is already bound elsewhere
     in the query — that is illegal.  Read the raw value into one variable
     (e.g. `?sex_code`) and BIND the derived value into a NEW variable
     (e.g. `?sex`).
   - Use only SPARQL 1.1 built-ins (IF, COALESCE, BIND, FILTER, COUNT, etc.).

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
# Phase 2 (deterministic):  build the SPARQL ourselves from resolved URIs
# ---------------------------------------------------------------------------
#
# For the common "retrieve these variables per subject (optionally mapping a
# coded value via its data-element levels)" intent, the correct query is fully
# determined once Phase 1 has resolved the DataElement URIs.  Generating it in
# code -- instead of asking an LLM -- makes the result identical regardless of
# which model (Claude, GPT, a local Qwen, ...) ran Phase 1, and eliminates by
# construction the two failure modes an LLM-authored join keeps hitting:
#
#   1. Cartesian products: a value block whose carrying entity is not tied back
#      to the subject ranges over EVERY subject's entity (e.g. one subject's
#      age paired with all N subjects' left x right hippocampus volumes).
#   2. Cross-file no-matches: joining on the raw subject-id string silently
#      matches nothing across files because of zero-padding ("50772"/"0050772").
#
# Every variable is placed in its own OPTIONAL block, anchored through the
# universal NIDM provenance path
#   entity -> prov:wasGeneratedBy -> activity
#          -> prov:qualifiedAssociation -> prov:agent -> Person(src_subject_id)
# back to the SAME leading-zero-stripped subject id.  OPTIONAL (left join) keeps
# a subject in the output even when one variable is missing, rather than
# dropping the row.


def _sparql_var_name(name, used):
    """Turn a concept name into a unique, valid SPARQL variable name."""
    base = re.sub(r"[^0-9a-zA-Z]+", "_", str(name).strip().lower()).strip("_")
    if not base or base[0].isdigit():
        base = "v_" + base
    candidate = base
    i = 2
    while candidate in used:
        candidate = f"{base}_{i}"
        i += 1
    used.add(candidate)
    return candidate


def _sparql_escape(s):
    """Escape a string for use inside a double-quoted SPARQL literal."""
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


def _value_map_if_chain(code_var, levels):
    """Build a nested SPARQL IF() that maps a coded value to its label.

    Falls back to the raw code for any value not present in *levels*, so an
    unexpected code is surfaced rather than silently dropped.  *levels* is the
    coded->label dict captured from reproschema:choices (the ONLY licensed
    source of a mapping).
    """
    expr = code_var
    for val, lab in reversed(list(levels.items())):
        expr = (
            f'IF({code_var} = "{_sparql_escape(val)}", "{_sparql_escape(lab)}", {expr})'
        )
    return expr


def _build_deterministic_sparql(resolved_vars):
    """Build a person-anchored, zero-pad-tolerant SELECT from resolved DE URIs.

    *resolved_vars* is a list of dicts each with at least ``uri`` and ``name``;
    an optional ``levels`` dict triggers coded->label mapping for that column.
    Returns the SPARQL string (one row per subject, ordered by subject id).
    """
    used = {"subject_id", "sid_raw", "p"}
    select_cols = ["?subject_id"]
    blocks = []
    for i, v in enumerate(resolved_vars):
        col = _sparql_var_name(v.get("name", f"var_{i}"), used)
        ent, per, sid = f"e_{i}", f"p_{i}", f"s_{i}"
        levels = v.get("levels")
        if levels:
            code_var = f"?{col}_code"
            obj = code_var
            map_line = f"    BIND({_value_map_if_chain(code_var, levels)} AS ?{col})\n"
        else:
            obj = f"?{col}"
            map_line = ""
        blocks.append(
            "  OPTIONAL {\n"
            f"    ?{ent} <{v['uri']}> {obj} ;\n"
            f"         prov:wasGeneratedBy/prov:qualifiedAssociation/prov:agent ?{per} .\n"
            f"    ?{per} ndar:src_subject_id ?{sid} .\n"
            f'    FILTER(REPLACE(STR(?{sid}), "^0+", "") = ?subject_id)\n'
            f"{map_line}"
            "  }"
        )
        select_cols.append(f"?{col}")

    return (
        "PREFIX prov: <http://www.w3.org/ns/prov#>\n"
        "PREFIX ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/>\n\n"
        f"SELECT {' '.join(select_cols)}\n"
        "WHERE {\n"
        "  # one row per distinct (leading-zero-stripped) subject id\n"
        "  {\n"
        "    SELECT DISTINCT ?subject_id WHERE {\n"
        "      ?p ndar:src_subject_id ?sid_raw .\n"
        '      BIND(REPLACE(STR(?sid_raw), "^0+", "") AS ?subject_id)\n'
        "    }\n"
        "  }\n\n" + "\n".join(blocks) + "\n}\nORDER BY ?subject_id\n"
    )


def _build_direct_predicate_sparql(direct_vars):
    """Build a DISTINCT-values SELECT over NIDM/BIDS predicates stored directly
    on entities (e.g. ``nidm:Task``, ``bids:session_number``, ``nfo:filename``).

    Answers "what tasks / sessions / runs / files are in this data?" -- one
    column per resolved predicate, distinct rows.  Unlike the person-anchored
    :func:`_build_deterministic_sparql`, these facts are properties of the
    acquisition/derivative objects themselves and are not joined to a subject.

    *direct_vars* is a list of dicts each with at least ``uri`` and ``name``.
    Returns the SPARQL query string.
    """
    used = set()
    select_cols = []
    blocks = []
    for i, v in enumerate(direct_vars):
        col = _sparql_var_name(v.get("name", f"var_{i}"), used)
        select_cols.append(f"?{col}")
        # each predicate is matched on its own entity variable so the columns
        # are independent (a distinct list per predicate)
        blocks.append(f"  ?e_{i} <{v['uri']}> ?{col} .")
    return (
        f"SELECT DISTINCT {' '.join(select_cols)}\n"
        "WHERE {\n" + "\n".join(blocks) + "\n}\n"
        f"ORDER BY {' '.join(select_cols)}\n"
    )


# Words/phrases that signal an analytical question (aggregation, filtering,
# grouping) the deterministic per-subject retrieval builder does NOT handle --
# those are routed to the LLM Phase-2 path instead.
_ANALYTIC_RE = re.compile(
    r"(?i)("
    # whole words
    r"\b(?:count|how many|number of|mean|median|sum|total|min|minimum|max|"
    r"maximum|ratio|stdev|std dev|standard deviation|older|younger|greater|"
    r"less than|fewer than|more than|at least|at most|between|filter|exclude|"
    r"having|only)\b"
    # stems (match plurals/derivations: average(s), correlation, distribution)
    r"|\baverag\w*|\bcorrelat\w*|\bdistribut\w*|\bproportion\w*|\bpercent\w*"
    # grouping / per-X / inline comparisons
    r"|group(?:ed)?\s+by|\bper\s+\w+|where\s+\w+\s*[<>=]"
    r")"
)


def _looks_analytical(question):
    """True if the question implies aggregation/filtering/grouping (-> LLM).

    A plain "retrieve / list / show these variables" question returns False and
    is handled by the deterministic builder.
    """
    return bool(_ANALYTIC_RE.search(question or ""))


# ---------------------------------------------------------------------------
# AI provider interface
# ---------------------------------------------------------------------------


def _get_api_key(provider=None):
    """Get the API key for *provider* from the environment or config file.

    When the provider is known, the provider-specific env var is used so the
    correct key is selected even if both ANTHROPIC_API_KEY and OPENAI_API_KEY
    are set:
      - "openai"    -> OPENAI_API_KEY
      - "anthropic" -> ANTHROPIC_API_KEY
      - "llama"     -> None (a local server needs no key)
    With no provider, falls back to whichever key is present (Anthropic first).
    """
    if provider == "llama":
        return None
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY")
    elif provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY")
    else:
        key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    config_path = Path.home() / ".pynidm" / "config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())
        return config.get("api_key")
    return None


def _get_provider():
    """Determine which AI provider to use.

    Precedence: explicit PYNIDM_AI_PROVIDER env var, then a cloud API key in the
    environment, then a configured local LLaMA server (PYNIDM_LLAMA_URL), then
    ~/.pynidm/config.json.  Valid providers: "anthropic", "openai", "llama"
    (a local OpenAI-compatible server such as llama.cpp's llama-server or
    Ollama).
    """
    explicit = os.environ.get("PYNIDM_AI_PROVIDER")
    if explicit:
        return explicit.strip().lower()
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("PYNIDM_LLAMA_URL"):
        return "llama"
    config_path = Path.home() / ".pynidm" / "config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())
        return config.get("provider", "anthropic")
    return None


# Anthropic model used for queryai.  Defaults to the current Claude
# Sonnet (4.6); override via the PYNIDM_ANTHROPIC_MODEL env var so a
# model deprecation doesn't require a code change.  (The previous
# hard-coded "claude-sonnet-4-20250514" was retired and now 404s.)
_ANTHROPIC_MODEL = os.environ.get("PYNIDM_ANTHROPIC_MODEL", "claude-sonnet-4-6")

# Local LLaMA / OpenAI-compatible server (llama.cpp's llama-server, Ollama, ...).
# No API key required.  PYNIDM_LLAMA_URL is the OpenAI-compatible base URL
# (default = llama.cpp's llama-server on :8080); set to e.g.
# http://localhost:11434/v1 for Ollama.  PYNIDM_LLAMA_MODEL is the model name to
# request (llama.cpp serves whatever model it was started with and ignores it;
# Ollama requires the model tag, e.g. "llama3").
_LLAMA_URL = os.environ.get("PYNIDM_LLAMA_URL", "http://localhost:8080/v1")
_LLAMA_MODEL = os.environ.get("PYNIDM_LLAMA_MODEL", "local-model")


def _query_anthropic(system_prompt, user_question, api_key):
    """Send a query to the Anthropic API and return the response text."""
    try:
        import anthropic
    except ImportError:
        click.echo(
            "Error: anthropic package not installed. "
            'Install the queryai backends with: pip install "pynidm[queryai]"',
            err=True,
        )
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=_ANTHROPIC_MODEL,
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
            "Error: openai package not installed. "
            'Install the queryai backends with: pip install "pynidm[queryai]"',
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


def _query_llama(system_prompt, user_question):
    """Send a query to a local OpenAI-compatible LLM server (llama.cpp's
    llama-server, Ollama, etc.).  No API key is required; the endpoint is
    configured via PYNIDM_LLAMA_URL / PYNIDM_LLAMA_MODEL.
    """
    url = _LLAMA_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": _LLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question},
        ],
        "max_tokens": 4096,
        # deterministic generation for SPARQL/concept extraction
        "temperature": 0,
        "stream": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=600)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        click.echo(
            f"Error: could not connect to a local LLM server at {_LLAMA_URL}. "
            "Start one (e.g. `llama-server -m <model>.gguf` on :8080, or "
            "`ollama serve`) and/or set PYNIDM_LLAMA_URL.",
            err=True,
        )
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        click.echo(f"Error querying local LLM server at {url}: {e}", err=True)
        sys.exit(1)

    try:
        return resp.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError) as e:
        click.echo(
            f"Error: unexpected response from local LLM server at {url}: {e}",
            err=True,
        )
        sys.exit(1)


def _send_to_ai(system_prompt, user_question):
    """Send a question to the configured AI provider."""
    provider = _get_provider()

    # Local LLaMA / OpenAI-compatible server: no API key required.
    if provider == "llama":
        return _query_llama(system_prompt, user_question)

    api_key = _get_api_key(provider)
    if not api_key:
        click.echo(
            "Error: No AI provider configured. Set one of:\n"
            "  - ANTHROPIC_API_KEY environment variable\n"
            "  - OPENAI_API_KEY environment variable\n"
            "  - PYNIDM_AI_PROVIDER=llama (+ optional PYNIDM_LLAMA_URL / "
            "PYNIDM_LLAMA_MODEL) for a local OpenAI-compatible LLM server\n"
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


def _ensure_prefixes(sparql_query, prefixes):
    """Prepend ``PREFIX`` declarations for any prefix used in
    *sparql_query* but not already declared, so the query is
    self-contained / portable to external SPARQL engines (e.g. Stardog).

    rdflib resolves undeclared prefixes from the graph's namespace
    bindings at execution time, so queries run inside pynidm even without
    a PREFIX block -- but they aren't portable.  *prefixes* is the
    ``{prefix: uri}`` map from :func:`_extract_namespace_prefixes`.
    """
    declared = set(
        re.findall(r"(?im)^\s*PREFIX\s+([A-Za-z][\w.\-]*)\s*:", sparql_query)
    )
    missing = [
        p
        for p, uri in prefixes.items()
        if p not in declared and re.search(rf"(?<![<\w]){re.escape(p)}:", sparql_query)
    ]
    if not missing:
        return sparql_query
    header = "\n".join(f"PREFIX {p}: <{prefixes[p]}>" for p in sorted(missing))
    return header + "\n\n" + sparql_query


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


def _resolve_concepts_to_vars(concepts, data_elements):
    """Resolve extracted *concepts* to query-variable descriptors.

    For each concept: identifier/aggregate/software roles pass through without
    DataElement resolution; otherwise resolve to a DataElement URI (by name,
    then keywords), falling back to the direct-predicate registry
    (task/session/run/filename/...).  Multiple matches prompt the user to pick,
    and multiple chosen DEs for one concept get distinct names.  Returns the
    list of resolved-variable dicts.
    """
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
            # Not a DataElement -- try the direct-predicate registry.  Terms
            # like task / session / run / filename / scan metadata are stored
            # as predicates on the acquisition object (nidm:Task,
            # bids:session_number, ...), not as DataElement nodes, so they
            # never appear in `data_elements`.
            direct = resolve_query_term(name)
            if direct is None:
                for kw in concept.get("keywords", []):
                    direct = resolve_query_term(kw)
                    if direct:
                        break
            if direct is not None:
                click.echo(
                    f"  Found direct NIDM predicate: {direct['qname']}",
                    err=True,
                )
                resolved_vars.append(
                    {
                        "name": name,
                        "role": role,
                        "qname": direct["qname"],
                        "uri": direct["uri"],
                        "label": None,
                        # marks this as a predicate on an entity (queried
                        # directly) rather than a DataElement value.
                        "direct_predicate": True,
                    }
                )
                continue

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
            # When multiple DEs are chosen for the same concept, give each a
            # distinct name so the AI creates separate SPARQL variables
            # (e.g. left_hippocampus_volume_fs, left_hippocampus_volume_ants).
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
                    # value levels (coded -> label), if defined in the data;
                    # the ONLY licensed source for a coded-value mapping
                    "levels": selected.get("levels"),
                }
            )
    return resolved_vars


@cli.command()
@click.option(
    "--nidm_file_list",
    "-nl",
    required=True,
    help="Comma-separated list of NIDM inputs.  Each entry may be a NIDM file "
    "with full path, a directory (recursed for **/nidm.ttl), a manifest text "
    "file (.txt/.list, one entry per line, # comments allowed), a glob, or an "
    "http(s) URL.",
)
@click.option(
    "--with_cdes",
    "-wc",
    is_flag=True,
    default=False,
    help="Also load the bundled FreeSurfer/FSL/ANTS CDE files (local copy if "
    "present, else downloaded) so brain-volume concepts resolve without "
    "listing them by hand.",
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
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["auto", "deterministic", "llm"]),
    default="auto",
    help="How Phase 2 builds the SPARQL.  'deterministic' assembles a "
    "person-anchored, zero-pad-tolerant query in code from the resolved URIs "
    "(identical output on any model, no cartesian products).  'llm' always "
    "asks the AI.  'auto' (default) uses the deterministic builder for plain "
    "'retrieve these variables' questions and the AI for analytical ones "
    "(counts, averages, group-by, filtering).",
)
def queryai(nidm_file_list, with_cdes, question, output_file, show_query, mode):
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

    # Expand -nl entries (files, directories recursed for **/nidm.ttl, manifest
    # text files, globs, http(s) URLs) into a concrete file list; append the
    # bundled CDE files when -wc is given so they are parsed for concepts.
    nidm_files = expand_nidm_file_list(nidm_file_list, include_cdes=with_cdes)
    if not nidm_files:
        click.echo(
            f"Error: no NIDM files found from -nl '{nidm_file_list}' "
            "(check the path, directory, or manifest).",
            err=True,
        )
        sys.exit(1)
    for f in nidm_files:
        # URLs are fetched by rdflib at parse time; only validate local paths.
        if f.startswith(("http://", "https://")):
            continue
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

        # Resolve each extracted concept to a query variable.
        resolved_vars = _resolve_concepts_to_vars(concepts, data_elements)

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
        # Only resolved vars that have URIs can be queried as predicates.
        vars_with_uris = [v for v in resolved_vars if v.get("uri")]
        # Direct predicates (nidm:Task, bids:session_number, ...) are queried as
        # properties of the acquisition/derivative object itself; DataElement
        # vars are person-anchored.
        direct_vars = [v for v in vars_with_uris if v.get("direct_predicate")]
        de_vars = [v for v in vars_with_uris if not v.get("direct_predicate")]

        # Decide how to build the query.  The direct builder lists distinct
        # values of direct predicates; the deterministic builder handles the
        # common per-subject DataElement retrieval reproducibly; the AI handles
        # analytical questions (counts/averages/group-by/filtering) and any
        # case where no variable resolved to a URI.
        use_direct = (
            mode in ("auto", "deterministic")
            and direct_vars
            and not de_vars
            and not _looks_analytical(q)
        )
        use_deterministic = (not use_direct) and (
            mode == "deterministic"
            or (mode == "auto" and de_vars and not _looks_analytical(q))
        )
        if mode == "deterministic" and not vars_with_uris:
            click.echo(
                "  No variables resolved to URIs; cannot build a deterministic "
                "query.  Falling back to the AI.",
                err=True,
            )
            use_deterministic = False

        if use_direct:
            click.echo(
                "\nPhase 2: Building direct-predicate SPARQL (no LLM)...",
                err=True,
            )
            sparql_query = _build_direct_predicate_sparql(direct_vars)
        elif use_deterministic:
            click.echo(
                "\nPhase 2: Building deterministic SPARQL (person-anchored, "
                "no LLM)...",
                err=True,
            )
            sparql_query = _build_deterministic_sparql(de_vars or vars_with_uris)
            mapped = [v["name"] for v in vars_with_uris if v.get("levels")]
            raw = [v["name"] for v in vars_with_uris if not v.get("levels")]
            if mapped:
                click.echo(
                    f"  Mapped coded values using data-element levels: "
                    f"{', '.join(mapped)}",
                    err=True,
                )
            if raw:
                click.echo(
                    f"  Returned raw (no value-level definitions in the data): "
                    f"{', '.join(raw)}",
                    err=True,
                )
        else:
            click.echo("\nPhase 2: Generating SPARQL query (AI)...", err=True)
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

        # Make the query self-contained: prepend any PREFIX declarations
        # that may be missing, so the shown/executed SPARQL is portable.
        sparql_query = _ensure_prefixes(sparql_query, prefixes)

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
