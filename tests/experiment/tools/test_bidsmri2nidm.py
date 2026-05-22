"""
Tests for bidsmri2nidm.py

Focuses on edge cases in how participants.tsv (and phenotype/*.tsv) column
headers are handled.  These tests do not require network access and run
entirely from a synthetic BIDS directory built in a pytest tmp_path.
"""

from __future__ import annotations
import argparse
from io import StringIO
import json
from pathlib import Path
from rdflib import Graph
from rdflib.namespace import Namespace
from nidm.experiment.tools.bidsmri2nidm import bidsmri2project

# ---------------------------------------------------------------------------
# Shared BIDS sidecar annotations (no interactive prompts, no network calls)
# ---------------------------------------------------------------------------

_PARTICIPANTS_SIDECAR = {
    "age_at_scan": {
        "description": "Age at anatomical scan in years",
        "source_variable": "age_at_scan",
        "associatedWith": "NIDM",
        "valueType": "http://www.w3.org/2001/XMLSchema#float",
        "minValue": "0",
        "maxValue": "120",
    },
    "sex": {
        "description": "Biological sex of participant",
        "source_variable": "sex",
        "associatedWith": "NIDM",
        "valueType": "http://www.w3.org/2001/XMLSchema#complexType",
    },
}


def _make_minimal_bids(root: Path, participants_tsv_text: str) -> None:
    """Write the minimal files needed by bidsmri2project."""
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "TSV whitespace test", "BIDSVersion": "1.8.0"}),
        encoding="utf-8",
    )
    (root / "participants.tsv").write_text(participants_tsv_text, encoding="utf-8")
    # Pre-written BIDS sidecar so map_variables_to_terms needs no user input.
    # Keys here intentionally use the *clean* (stripped) variable names.
    (root / "participants.json").write_text(
        json.dumps(_PARTICIPANTS_SIDECAR), encoding="utf-8"
    )


def _default_args(directory: str) -> argparse.Namespace:
    return argparse.Namespace(
        directory=directory,
        json_map=False,
        no_concepts=True,  # no network calls / interactive mapping
        bidsignore=False,
        outputfile="nidm.ttl",
        logfile=None,
    )


def _to_rdflib(project, cde: Graph) -> Graph:
    """Merge the prov project graph and CDE graph into a single rdflib Graph."""
    g = Graph()
    g.parse(source=StringIO(project.serializeTurtle()), format="turtle")
    return g + cde


NIDM = Namespace("http://purl.org/nidash/nidm#")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParticipantsTsvWhitespaceStripping:
    """
    Regression tests for the fix that strips leading/trailing whitespace from
    TSV column headers.  Prior to the fix, a header like 'age_at_scan ' (with
    a trailing space) would silently fail to match the pre-written sidecar
    entry 'age_at_scan', causing subject data to be lost.
    """

    def test_trailing_space_column_has_source_variable_stripped(
        self, tmp_path: Path
    ) -> None:
        """
        A column header with a trailing space ('age_at_scan ') must be stored
        in the NIDM graph as nidm:sourceVariable "age_at_scan" (no space).
        """
        _make_minimal_bids(
            tmp_path,
            "participant_id\tage_at_scan \tsex\n"  # <-- trailing space in header
            "sub-01\t25\t1\n"
            "sub-02\t30\t2\n",
        )
        project, _, cde, _ = bidsmri2project(
            str(tmp_path), _default_args(str(tmp_path))
        )
        g = _to_rdflib(project, cde)
        ttl = g.serialize(format="turtle")

        assert 'nidm:sourceVariable "age_at_scan"' in ttl, (
            "Expected nidm:sourceVariable to be 'age_at_scan' (stripped), "
            "but it was missing or still had the trailing space."
        )
        assert (
            'nidm:sourceVariable "age_at_scan "' not in ttl
        ), "nidm:sourceVariable should NOT contain the raw spaced name 'age_at_scan '."

    def test_trailing_space_column_data_written_not_lost(self, tmp_path: Path) -> None:
        """
        When the header has a trailing space, subject data must still be
        written into the NIDM graph (i.e. the value must not be silently
        dropped or appear only as 'n/a').
        """
        _make_minimal_bids(
            tmp_path,
            "participant_id\tage_at_scan \tsex\n"  # <-- trailing space in header
            "sub-01\t25\t1\n"
            "sub-02\t30\t2\n",
        )
        project, _, cde, _ = bidsmri2project(
            str(tmp_path), _default_args(str(tmp_path))
        )
        g = _to_rdflib(project, cde)
        ttl = g.serialize(format="turtle")

        # At least one of the age values must be present in the output.
        assert '"25"' in ttl or '"25.0"' in ttl or '"30"' in ttl or '"30.0"' in ttl, (
            "Expected age values (25 or 30) to appear in the NIDM output.  "
            "This would be absent if the spaced column header caused a mismatch "
            "against the sidecar and silently dropped the data."
        )

    def test_leading_space_column_stripped(self, tmp_path: Path) -> None:
        """
        A column header with a *leading* space (' age_at_scan') is also stripped.
        """
        _make_minimal_bids(
            tmp_path,
            "participant_id\t age_at_scan\tsex\n"  # <-- leading space in header
            "sub-01\t25\t1\n"
            "sub-02\t30\t2\n",
        )
        project, _, cde, _ = bidsmri2project(
            str(tmp_path), _default_args(str(tmp_path))
        )
        g = _to_rdflib(project, cde)
        ttl = g.serialize(format="turtle")

        assert (
            'nidm:sourceVariable "age_at_scan"' in ttl
        ), "Leading-space column header should be stripped to 'age_at_scan'."
        assert 'nidm:sourceVariable " age_at_scan"' not in ttl

    def test_clean_column_unaffected(self, tmp_path: Path) -> None:
        """
        Columns without surrounding whitespace continue to work correctly
        (non-regression guard).
        """
        _make_minimal_bids(
            tmp_path,
            "participant_id\tage_at_scan\tsex\n"  # clean header, no spaces
            "sub-01\t25\t1\n"
            "sub-02\t30\t2\n",
        )
        project, _, cde, _ = bidsmri2project(
            str(tmp_path), _default_args(str(tmp_path))
        )
        g = _to_rdflib(project, cde)
        ttl = g.serialize(format="turtle")

        assert (
            'nidm:sourceVariable "age_at_scan"' in ttl
        ), "Clean column name should still produce the correct sourceVariable."


class TestPhenotypeTsvWhitespaceStripping:
    """
    The same whitespace stripping applies to phenotype/*.tsv files.
    """

    def test_phenotype_tsv_trailing_space_stripped(self, tmp_path: Path) -> None:
        """
        A phenotype TSV column with a trailing space must be stripped before
        the column name is stored as nidm:sourceVariable in the CDE graph.
        """
        _make_minimal_bids(
            tmp_path,
            # participants.tsv intentionally minimal; phenotype has the spaced col
            "participant_id\n" "sub-01\n" "sub-02\n",
        )
        # Remove participants.json so map_variables_to_terms gets an empty list
        (tmp_path / "participants.json").unlink(missing_ok=True)

        # Build phenotype directory with spaced header
        pheno_dir = tmp_path / "phenotype"
        pheno_dir.mkdir()
        (pheno_dir / "cognitive.tsv").write_text(
            "participant_id\tiq_score \n"  # <-- trailing space in header
            "sub-01\t110\n"
            "sub-02\t95\n",
            encoding="utf-8",
        )
        (pheno_dir / "cognitive.json").write_text(
            json.dumps(
                {
                    "iq_score": {
                        "description": "Full-scale IQ score",
                        "source_variable": "iq_score",
                        "associatedWith": "NIDM",
                        "valueType": "http://www.w3.org/2001/XMLSchema#float",
                        "minValue": "0",
                        "maxValue": "200",
                    }
                }
            ),
            encoding="utf-8",
        )

        project, _, cde, cde_pheno = bidsmri2project(
            str(tmp_path), _default_args(str(tmp_path))
        )

        # Merge all CDE graphs
        g = _to_rdflib(project, cde)
        for cde_p in cde_pheno:
            g = g + cde_p
        ttl = g.serialize(format="turtle")

        assert 'nidm:sourceVariable "iq_score"' in ttl, (
            "Phenotype column 'iq_score ' (trailing space) should be stripped to "
            "'iq_score' in the NIDM output."
        )
        assert (
            'nidm:sourceVariable "iq_score "' not in ttl
        ), "Spaced phenotype column name should not appear in the NIDM output."
