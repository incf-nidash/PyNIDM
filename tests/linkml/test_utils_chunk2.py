"""
Tests for chunk 15.2 of the Utils.py port:
``add_git_annex_sources`` and ``add_datalad_dataset_uuid``.

The git-annex helper is exercised against a mocked ``AnnexRepo`` so
the tests don't require a real annex on disk.  The datalad UUID
helper is currently a no-op stub (matching the legacy empty
implementation).
"""
from __future__ import annotations
from unittest.mock import patch
from rdflib import Graph, Literal
from rdflib.namespace import XSD
from nidm.linkml.core.namespaces import PROV
from nidm.linkml.experiment import utils
from nidm.linkml.experiment.core import Core

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockAnnexRepo:
    """Stand-in for datalad.support.annexrepo.AnnexRepo used in tests."""

    def __init__(
        self,
        bids_root,
        create=False,  # noqa: U100 -- matches AnnexRepo signature
        urls=None,
    ):
        # Stored for inspection by tests
        self.bids_root = bids_root
        self._urls = urls or []

    def get_urls(self, path):  # noqa: U100 -- matches AnnexRepo.get_urls signature
        # Mirrors AnnexRepo.get_urls signature: returns a list of URLs
        return list(self._urls)


# ---------------------------------------------------------------------------
# add_datalad_dataset_uuid -- stub matches legacy
# ---------------------------------------------------------------------------


def test_add_datalad_dataset_uuid_is_a_no_op():
    """Legacy implementation is empty; our port preserves the no-op."""
    g = Graph()
    result = utils.add_datalad_dataset_uuid("any-uuid", "/no/such/dir", g)
    assert result is None
    assert len(g) == 0


def test_add_datalad_dataset_uuid_legacy_alias():
    assert utils.addDataladDatasetUUID is utils.add_datalad_dataset_uuid


# ---------------------------------------------------------------------------
# add_git_annex_sources -- happy path with a mocked AnnexRepo
# ---------------------------------------------------------------------------


def test_add_git_annex_sources_emits_prov_location_per_match():
    obj = Core()  # gives us a graph and identifier

    fake_urls = [
        "https://datasets.datalad.org/foo/bar/sub-01_T1w.nii.gz",
        "https://example.org/other/sub-01_T1w.nii.gz",
        "https://unrelated.org/other/sub-02_T1w.nii.gz",  # should NOT match
    ]

    with patch(
        "datalad.support.annexrepo.AnnexRepo",
        lambda root, create=False: _MockAnnexRepo(root, urls=fake_urls),  # noqa: U100
    ):
        count = utils.add_git_annex_sources(
            obj,
            bids_root="/fake/bids",
            filepath="/fake/bids/sub-01/anat/sub-01_T1w.nii.gz",
        )

    # All three URLs were returned by get_urls; that's the count.
    assert count == 3

    # But only the two containing 'sub-01_T1w.nii.gz' become triples.
    # prov:Location is emitted as an xsd:string literal to match the legacy
    # (prov-toolbox) serialization -- i.e. `"<url>"^^xsd:string`, not an IRI.
    locations = list(obj.graph.objects(obj.identifier, PROV["Location"]))
    assert len(locations) == 2
    assert Literal(fake_urls[0], datatype=XSD.string) in locations
    assert Literal(fake_urls[1], datatype=XSD.string) in locations
    assert Literal(fake_urls[2], datatype=XSD.string) not in locations


def test_add_git_annex_sources_with_no_filepath_adds_all_sources():
    """
    With filepath=None, all sources for bids_root are emitted -- this
    is the bug-fix path vs. the legacy (which crashed because
    os.path.basename(None) raises TypeError).
    """
    obj = Core()

    fake_urls = [
        "https://datasets.datalad.org/foo/bar/manifest.txt",
        "https://datasets.datalad.org/foo/bar/sub-01_T1w.nii.gz",
    ]

    with patch(
        "datalad.support.annexrepo.AnnexRepo",
        lambda root, create=False: _MockAnnexRepo(root, urls=fake_urls),  # noqa: U100
    ):
        count = utils.add_git_annex_sources(obj, bids_root="/fake/bids", filepath=None)

    assert count == 2
    locations = list(obj.graph.objects(obj.identifier, PROV["Location"]))
    assert len(locations) == 2


def test_add_git_annex_sources_returns_zero_when_no_annex():
    """The 'No annex found at' branch is a quiet failure -> 0."""
    obj = Core()

    def _raise_no_annex(root, create=False):  # noqa: U100
        raise RuntimeError(f"No annex found at {root}")

    with patch("datalad.support.annexrepo.AnnexRepo", _raise_no_annex):
        count = utils.add_git_annex_sources(
            obj, bids_root="/no/annex/here", filepath="anything"
        )

    assert count == 0
    assert len(list(obj.graph.objects(obj.identifier, PROV["Location"]))) == 0


def test_add_git_annex_sources_returns_zero_on_other_errors(capsys):
    """Other AnnexRepo errors are caught, printed as warnings, return 0."""
    obj = Core()

    def _raise_other(root, create=False):  # noqa: U100
        raise RuntimeError("something else broke")

    with patch("datalad.support.annexrepo.AnnexRepo", _raise_other):
        count = utils.add_git_annex_sources(
            obj, bids_root="/some/dir", filepath="anything"
        )

    assert count == 0
    captured = capsys.readouterr()
    assert "Warning, error with AnnexRepo" in captured.out
    assert "something else broke" in captured.out


def test_add_git_annex_sources_legacy_alias():
    assert utils.addGitAnnexSources is utils.add_git_annex_sources


# ---------------------------------------------------------------------------
# Module surface check
# ---------------------------------------------------------------------------


def test_chunk2_names_in_all():
    """The new functions are exported from __all__."""
    for name in (
        "add_git_annex_sources",
        "addGitAnnexSources",
        "add_datalad_dataset_uuid",
        "addDataladDatasetUUID",
    ):
        assert name in utils.__all__
