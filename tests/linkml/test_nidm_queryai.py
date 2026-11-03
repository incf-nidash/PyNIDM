"""Tests for nidm_queryai helpers that don't require an AI/API call.

Coverage boundary (intentional): ``nidm_queryai`` is an LLM-backed tool -- its
core question-answering path sends a prompt to an external model and cannot be
unit-tested deterministically (it is non-deterministic and needs a live API
key), so the module's overall line coverage is expected to stay low.  What *is*
tested is everything deterministic around that call: file/directory resolution
(``-nl`` recursion), data-element extraction from the graph (including coded
value levels), the ``_looks_analytical`` heuristic, and the deterministic SPARQL
builder.  The direct-predicate term registry -- the one piece genuinely
re-implemented from the legacy tool -- is covered separately in
``test_queryai_direct_predicates.py`` (and diffed against master by
``scripts/queryai_terms_parity.py``).  The remaining uncovered lines are the
LLM request/response handling, which is a known and accepted gap.
"""

from __future__ import annotations
from pathlib import Path
from click.testing import CliRunner
from rdflib import Graph
from nidm.linkml.experiment.tools import nidm_queryai as _qai
from nidm.linkml.experiment.tools.nidm_queryai import (
    _build_deterministic_sparql,
    _extract_data_elements,
    _looks_analytical,
    queryai,
)


def test_queryai_nl_expands_directory(tmp_path: Path, monkeypatch) -> None:
    """Regression: ``-nl <dir>`` must recurse for ``**/nidm.ttl`` (not error
    'File not found' by treating the directory as a literal file).  We stop
    right after file resolution so no AI/API call is made."""
    study = tmp_path / "CMU_a"
    study.mkdir()
    (study / "nidm.ttl").write_text("")

    captured = {}

    def _fake_extract(files):
        captured["files"] = list(files)
        raise SystemExit(0)  # short-circuit before Phase 1 / the AI call

    monkeypatch.setattr(_qai, "_extract_data_elements", _fake_extract)

    result = CliRunner().invoke(queryai, ["-nl", str(study), "-q", "x"])

    assert "File not found" not in result.output, result.output
    assert captured.get("files") == [str(study / "nidm.ttl")]


def test_extract_data_elements_captures_value_levels(tmp_path: Path) -> None:
    """A DataElement whose value levels are defined in the data (via
    reproschema:choices -> value/label) is captured as a coded->label dict;
    a DataElement with no level definitions has no 'levels' key.  This is what
    licenses queryai to translate coded values (and refuse when absent)."""
    ttl = """
@prefix niiri: <http://iri.nidash.org/> .
@prefix nidm: <http://purl.org/nidash/nidm#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix reproschema: <http://schema.repronim.org/> .

niiri:SEX_withlevels a nidm:PersonalDataElement ;
    rdfs:label "SEX" ;
    reproschema:choices [ reproschema:value "1" ; rdfs:label "Male" ] ,
                        [ reproschema:value "2" ; rdfs:label "Female" ] .

niiri:DX_nolevels a nidm:PersonalDataElement ;
    rdfs:label "diagnostic group" .
"""
    cde = tmp_path / "cde.ttl"
    cde.write_text(ttl, encoding="utf-8")

    data_elements, _g = _extract_data_elements([str(cde)])
    by_uri = {d["uri"]: d for d in data_elements}

    sex = by_uri["http://iri.nidash.org/SEX_withlevels"]
    dx = by_uri["http://iri.nidash.org/DX_nolevels"]

    assert sex.get("levels") == {"1": "Male", "2": "Female"}
    # No level definitions -> no 'levels' key -> queryai must not fabricate a mapping
    assert "levels" not in dx


def test_get_provider_selects_local_llama(monkeypatch) -> None:
    """A configured local LLaMA server (PYNIDM_LLAMA_URL) selects the 'llama'
    provider when no cloud key is present; an explicit PYNIDM_AI_PROVIDER wins."""
    from nidm.linkml.experiment.tools.nidm_queryai import _get_provider

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PYNIDM_AI_PROVIDER", raising=False)
    monkeypatch.setenv("PYNIDM_LLAMA_URL", "http://localhost:8080/v1")
    assert _get_provider() == "llama"

    monkeypatch.setenv("PYNIDM_AI_PROVIDER", "anthropic")
    assert _get_provider() == "anthropic"


def test_query_llama_posts_openai_format_and_parses(monkeypatch) -> None:
    """_query_llama POSTs an OpenAI chat payload to <url>/chat/completions and
    returns choices[0].message.content (no API key, no real server)."""
    from nidm.linkml.experiment.tools import nidm_queryai as q

    captured = {}

    class _FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "SELECT * WHERE {}"}}]}

    def _fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["payload"] = json
        captured["timeout"] = timeout
        return _FakeResp()

    monkeypatch.setattr(q.requests, "post", _fake_post)

    out = q._query_llama("SYS_PROMPT", "USER_QUESTION")
    assert out == "SELECT * WHERE {}"
    assert captured["url"].endswith("/chat/completions")
    msgs = captured["payload"]["messages"]
    assert msgs[0]["role"] == "system" and msgs[0]["content"] == "SYS_PROMPT"
    assert msgs[1]["role"] == "user" and msgs[1]["content"] == "USER_QUESTION"


def test_get_api_key_is_provider_aware(monkeypatch) -> None:
    """The provider-specific key is selected even when both are set, so
    PYNIDM_AI_PROVIDER=openai uses OPENAI_API_KEY (not the Anthropic key)."""
    from nidm.linkml.experiment.tools.nidm_queryai import _get_api_key

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xxx")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-oai-yyy")
    assert _get_api_key("openai") == "sk-oai-yyy"
    assert _get_api_key("anthropic") == "sk-ant-xxx"
    assert _get_api_key("llama") is None


# ---------------------------------------------------------------------------
# Deterministic Phase-2 SPARQL builder
# ---------------------------------------------------------------------------


def test_looks_analytical_routing() -> None:
    """Plain 'retrieve these variables' questions are NOT analytical (they use
    the deterministic builder); aggregation/filter/group-by questions ARE (they
    fall back to the LLM)."""
    retrieval = [
        "Retrieve age, sex, diagnosis, VIQ, PIQ, FIQ, and hippocampus volume",
        "Map sex to 'M' and 'F' using the data element properties",
        "show age and sex for all subjects",
        "list every subject's diagnosis and FIQ",
    ]
    analytical = [
        "What is the average age of male subjects?",
        "How many subjects are there?",
        "average hippocampus volume per diagnosis",
        "count subjects by sex",
        "subjects older than 10",
        "distribution of FIQ",
        "correlation between age and hippocampus volume",
    ]
    for q in retrieval:
        assert _looks_analytical(q) is False, q
    for q in analytical:
        assert _looks_analytical(q) is True, q


def test_build_deterministic_sparql_anchors_each_var_and_maps_only_from_levels() -> (
    None
):
    """Each variable gets its own OPTIONAL block anchored back to the SAME
    zero-stripped subject id (no floating entities -> no cartesian product),
    and a coded->label mapping is emitted ONLY for a variable that carries
    value levels."""
    q = _build_deterministic_sparql(
        [
            {"name": "age", "uri": "http://x/AGE"},
            {
                "name": "sex",
                "uri": "http://x/SEX",
                "levels": {"1": "Male", "2": "Female"},
            },
            {"name": "left hippocampus volume", "uri": "http://x/fs_LH"},
        ]
    )
    # one anchored OPTIONAL per variable
    assert q.count("OPTIONAL {") == 3
    # every block re-anchors to the shared subject id (driver + 3 blocks = 4)
    assert q.count("REPLACE(STR(") == 4
    assert q.count("prov:wasGeneratedBy/prov:qualifiedAssociation/prov:agent") == 3
    # value mapping ONLY where levels exist
    assert 'IF(?sex_code = "1", "Male"' in q
    assert "?age_code" not in q and "?left_hippocampus_volume_code" not in q
    # full URIs used as predicates (portable, no prefix guessing)
    assert "<http://x/AGE>" in q and "<http://x/fs_LH>" in q


def test_deterministic_query_joins_across_zero_padding_without_cartesian(
    tmp_path: Path,
) -> None:
    """End-to-end: a demographics file (id '50772') and a derivative file
    (id '0050772', different Person node) with a left+right measure pair on ONE
    entity must yield exactly ONE row per subject -- the volumes joined to the
    right demographics despite the padding mismatch, and NO left x right
    explosion."""
    ns = (
        "@prefix prov: <http://www.w3.org/ns/prov#> .\n"
        "@prefix ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/> .\n"
        "@prefix niiri: <http://iri.nidash.org/> .\n"
        "@prefix x: <http://x/> .\n"
    )

    def subj(person, sid, ent, act, triples):
        return (
            f'niiri:{person} a prov:Agent, prov:Person ; ndar:src_subject_id "{sid}" .\n'
            f"niiri:{act} a prov:Activity ; "
            f"prov:qualifiedAssociation [ a prov:Association ; prov:agent niiri:{person} ] .\n"
            f"niiri:{ent} a prov:Entity ; prov:wasGeneratedBy niiri:{act} ; {triples} .\n"
        )

    # demographics: ids are zero-stripped
    demo = (
        ns
        + subj("pA", "50772", "eA", "aA", 'x:AGE "11" ; x:SEX "1"')
        + subj("pB", "50773", "eB", "aB", 'x:AGE "12" ; x:SEX "2"')
    )
    # derivatives: ids are zero-padded; LH+RH live on ONE entity per subject
    deriv = (
        ns
        + subj("pC", "0050772", "eC", "aC", 'x:fs_LH "100.0" ; x:fs_RH "200.0"')
        + subj("pD", "0050773", "eD", "aD", 'x:fs_LH "300.0" ; x:fs_RH "400.0"')
    )

    (tmp_path / "demo.ttl").write_text(demo, encoding="utf-8")
    (tmp_path / "deriv.ttl").write_text(deriv, encoding="utf-8")

    g = Graph()
    g.parse(tmp_path / "demo.ttl", format="turtle")
    g.parse(tmp_path / "deriv.ttl", format="turtle")

    query = _build_deterministic_sparql(
        [
            {"name": "age", "uri": "http://x/AGE"},
            {
                "name": "sex",
                "uri": "http://x/SEX",
                "levels": {"1": "Male", "2": "Female"},
            },
            {"name": "lh", "uri": "http://x/fs_LH"},
            {"name": "rh", "uri": "http://x/fs_RH"},
        ]
    )
    rows = list(g.query(query))
    by_sid = {str(r["subject_id"]): r for r in rows}

    # exactly one row per subject (no cartesian, no duplicate Person-node rows)
    assert len(rows) == 2, [tuple(map(str, r)) for r in rows]
    assert set(by_sid) == {"50772", "50773"}

    # cross-file join is correct AND the LH/RH pair did not explode
    r = by_sid["50772"]
    assert str(r["age"]) == "11"
    assert str(r["sex"]) == "Male"  # mapped from levels
    assert str(r["lh"]) == "100.0" and str(r["rh"]) == "200.0"

    r = by_sid["50773"]
    assert str(r["sex"]) == "Female"
    assert str(r["lh"]) == "300.0" and str(r["rh"]) == "400.0"
