"""Regression guard for the prov-toolbox removal (cutover step 5).

The shipped LinkML surface -- the ``pynidm`` CLI group, the query/navigate/CDE/
REST layers, and the queryai/linreg tools -- must import and run with ``prov``
NOT installed.  We enforce that here by installing an import blocker that makes
any ``import prov`` (or ``prov.*``) fail, purging cached ``prov``/``nidm``
modules, and then importing the shipped modules.
"""
from __future__ import annotations
import importlib
import sys


class _ProvBlocker:
    """meta_path finder that refuses to import ``prov`` / ``prov.*``."""

    def find_spec(self, fullname, path=None, target=None):  # noqa: U100
        if fullname == "prov" or fullname.startswith("prov."):
            raise ImportError("prov is blocked (test_prov_free)")
        return None


def _purge(prefixes):
    for name in list(sys.modules):
        if any(name == p or name.startswith(p + ".") for p in prefixes):
            del sys.modules[name]


def _run_without_prov(fn):
    """Run *fn* with prov import-blocked and prov/nidm caches purged, then
    restore the original module state so other tests are unaffected."""
    blocker = _ProvBlocker()
    saved = dict(sys.modules)
    sys.meta_path.insert(0, blocker)
    _purge(["prov", "nidm"])
    try:
        return fn()
    finally:
        sys.meta_path.remove(blocker)
        sys.modules.clear()
        sys.modules.update(saved)


def test_shipped_linkml_cli_imports_without_prov():
    def _imp():
        importlib.import_module("nidm.linkml.experiment.tools.click_main")
        importlib.import_module("nidm.linkml.experiment.query")
        importlib.import_module("nidm.linkml.experiment.navigate")
        importlib.import_module("nidm.linkml.experiment.cde")
        importlib.import_module("nidm.linkml.experiment.tools.rest")
        importlib.import_module("nidm.linkml.experiment.tools.nidm_queryai")
        importlib.import_module("nidm.linkml.experiment.tools.nidm_linreg")
        importlib.import_module("nidm.linkml.experiment.tools.nidm_file_utils")
        # prov must not have been pulled in transitively
        assert "prov" not in sys.modules
        return True

    assert _run_without_prov(_imp) is True
