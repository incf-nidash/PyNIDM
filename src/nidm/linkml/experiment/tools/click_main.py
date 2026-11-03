"""Aggregator for the LinkML ``pynidm`` CLI.

Importing each tool module runs its ``@cli.command()`` registration as a
side effect, so by the time :data:`cli` is exposed every subcommand is
attached.  This mirrors ``nidm.experiment.tools.click_main`` and is the
entry point the ``pynidm`` console_script points at after cutover.

Subcommands are added here as each legacy tool is ported to the LinkML
toolset (task 8).
"""
from nidm.linkml.experiment.tools import (  # noqa: F401
    converter_cli,
    nidm_concat,
    nidm_convert,
    nidm_linreg,
    nidm_merge,
    nidm_query,
    nidm_queryai,
    nidm_version,
    nidm_visualize,
)
from nidm.linkml.experiment.tools.click_base import cli

__all__ = ["cli"]
