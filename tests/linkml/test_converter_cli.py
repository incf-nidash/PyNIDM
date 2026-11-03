"""Tests for the converter passthrough subcommands.

``pynidm csv2nidm`` and ``pynidm bids2nidm`` (``converter_cli.py``) are thin
click wrappers that forward all arguments to the standalone argparse tools, so
the two converters share the uniform ``pynidm <verb>`` interface of the other
tools.  These tests confirm the wrappers are registered and that arguments
really reach the underlying argparse parser (via ``-h`` and an unknown-flag
probe).  The converters' actual conversion behavior is covered by
``test_csv2nidm.py`` / ``test_bidsmri2nidm_slim.py`` -- the wrapper only forwards.
"""
from __future__ import annotations
from click.testing import CliRunner
import pytest
from nidm.linkml.experiment.tools.click_main import cli


def test_converters_registered_on_group() -> None:
    """Both converters attach to the pynidm group as subcommands."""
    assert "csv2nidm" in cli.commands
    assert "bids2nidm" in cli.commands


@pytest.mark.parametrize("verb", ["csv2nidm", "bids2nidm"])
def test_passthrough_forwards_help(verb: str) -> None:
    """``pynidm <verb> -h`` forwards to argparse, which prints usage and exits 0.

    Proves click's own help is disabled and the token reaches the underlying
    parser (a click-native help would not say "usage:" the argparse way).
    """
    result = CliRunner().invoke(cli, [verb, "-h"])
    assert result.exit_code == 0, result.output
    assert "usage" in result.output.lower()
    # the wrapper threads prog through, so the usage line names the subcommand
    assert f"pynidm {verb}" in result.output


def test_passthrough_forwards_unknown_flag_to_argparse() -> None:
    """An unrecognized flag is forwarded and rejected by argparse (exit 2),
    confirming arguments are passed through rather than swallowed by click."""
    result = CliRunner().invoke(cli, ["csv2nidm", "--definitely-not-a-flag"])
    assert result.exit_code != 0
    # argparse emits its error/usage to stderr, which CliRunner folds into output
    assert "usage" in result.output.lower() or "unrecognized" in result.output.lower()
