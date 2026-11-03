"""Regression test for ``_bids_filename`` on datalad/git-annex symlinks.

datalad stores BIDS image files as symlinks pointing into
``.git/annex/objects/...``.  A previous revision of ``_bids_filename`` called
``Path.resolve()`` on the file, which followed that symlink and recorded the
opaque annex-object key (``.git/annex/objects/.../MD5E-...nii.gz``) as
``nfo:filename`` instead of the meaningful ``sub-XX_..._bold.nii.gz`` name.

The legacy ``getRelPathToBIDS`` never resolved the file symlink, so the two
tools diverged on datalad datasets.  These tests pin the fixed behavior:
the *logical* BIDS path is recorded, symlink or not -- which also keeps the
LinkML tool byte-identical to the legacy tool (bidsmri2nidm parity).
"""
from __future__ import annotations
from pathlib import Path
from nidm.linkml.experiment.tools.bidsmri2nidm import _bids_filename


def _make_bids_tree(root: Path) -> Path:
    """Create ``root/sub-01/func/sub-01_task-rest_bold.nii.gz`` and return root."""
    func = root / "sub-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-01_task-rest_bold.nii.gz").write_bytes(b"\x00")
    return root


def test_plain_file_returns_logical_bids_path(tmp_path):
    """A normal (non-symlink) image yields the logical bids:: path."""
    root = _make_bids_tree(tmp_path)
    img = root / "sub-01" / "func" / "sub-01_task-rest_bold.nii.gz"

    assert _bids_filename(img, root) == "bids::sub-01/func/sub-01_task-rest_bold.nii.gz"


def test_annex_symlink_keeps_logical_name_not_resolved_target(tmp_path):
    """An annex-style symlink must record its BIDS name, not the target.

    We emulate datalad: the BIDS file is a symlink whose target lives under
    ``.git/annex/objects``.  ``_bids_filename`` must NOT follow the symlink.
    """
    root = tmp_path
    # the "annex object" the symlink points at
    annex = root / ".git" / "annex" / "objects" / "9P" / "29"
    annex.mkdir(parents=True)
    target = annex / "MD5E-s123--deadbeef.nii.gz"
    target.write_bytes(b"\x00")

    func = root / "sub-01" / "func"
    func.mkdir(parents=True)
    link = func / "sub-01_task-rest_run-1_bold.nii.gz"
    # relative symlink into the annex, exactly like datalad creates
    link.symlink_to(Path("../../.git/annex/objects/9P/29/MD5E-s123--deadbeef.nii.gz"))

    result = _bids_filename(link, root)

    assert result == "bids::sub-01/func/sub-01_task-rest_run-1_bold.nii.gz"
    assert "annex" not in result  # never leak the annex object path
    assert "MD5E" not in result


def test_macos_tmp_parent_symlink_is_normalized(tmp_path):
    """Resolving the *parent* still normalizes dir-level symlinks.

    (On macOS ``/tmp`` is itself a symlink to ``/private/tmp``; the fix
    resolves the parent dir so ``relative_to`` still succeeds.)
    """
    root = _make_bids_tree(tmp_path)
    # a directory symlink standing in for the /tmp -> /private/tmp case
    alias = tmp_path.parent / (tmp_path.name + "_alias")
    try:
        alias.symlink_to(tmp_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        return  # symlinks unsupported on this platform; nothing to assert
    aliased_img = alias / "sub-01" / "func" / "sub-01_task-rest_bold.nii.gz"

    # passing the aliased path + real root still yields the logical rel path
    assert (
        _bids_filename(aliased_img, root)
        == "bids::sub-01/func/sub-01_task-rest_bold.nii.gz"
    )
    alias.unlink()
