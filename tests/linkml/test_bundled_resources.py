"""
Guard tests for bundled resources and CLI entry points.

These exist because the LinkML strip + schema relocation moved files
(e.g. ``nidm_schema.json`` from ``experiment/schema/`` to
``linkml/schema/``) while some modules still pointed at the old
locations.  Those bugs are invisible to import-only smoke tests
(the bad path is a module-level constant that only fails when *read*),
so we resolve the actual resources here.
"""
from __future__ import annotations
import importlib
import json
import pytest

# Every module named in setup.cfg [options.entry_points] console_scripts,
# plus queryai/linreg, must import cleanly under the LinkML-only tree.
_CLI_MODULES = [
    "nidm.linkml.experiment.tools.bidsmri2nidm",
    "nidm.linkml.experiment.tools.csv2nidm",
    "nidm.linkml.experiment.tools.nidm_query",
    "nidm.linkml.experiment.tools.nidm_utils",
    "nidm.linkml.experiment.tools.click_main",
    "nidm.linkml.experiment.tools.nidm_queryai",
    "nidm.linkml.experiment.tools.nidm_linreg",
    "nidm.linkml.experiment.tools.nidm_file_utils",
]


@pytest.mark.parametrize("modname", _CLI_MODULES)
def test_cli_module_imports(modname: str) -> None:
    """Each CLI entry-point module imports without error."""
    importlib.import_module(modname)


def test_queryai_schema_json_resolves_and_loads() -> None:
    """nidm_queryai._SCHEMA_PATH must point at the relocated
    linkml/schema/nidm_schema.json and be valid JSON.  (Regression guard
    for the experiment/schema -> linkml/schema relocation.)"""
    mod = importlib.import_module("nidm.linkml.experiment.tools.nidm_queryai")
    assert mod._SCHEMA_PATH.exists(), f"missing bundled schema: {mod._SCHEMA_PATH}"
    data = json.loads(mod._SCHEMA_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, (dict, list)) and data


def test_bundled_cde_files_resolves_nonempty() -> None:
    """bundled_cde_files() always returns something (local paths if a
    CDE_DIR/cde_dir is present, else the canonical network URLs)."""
    from nidm.linkml.experiment.tools.nidm_file_utils import bundled_cde_files

    files = bundled_cde_files()
    assert isinstance(files, list) and len(files) >= 3
