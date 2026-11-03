"""Attach the file converters to the ``pynidm`` command group.

``csv2nidm`` and ``bidsmri2nidm`` are argparse-based tools with their own
console-script entry points.  To give the toolset a uniform interface, this
module registers them on the shared ``pynidm`` click group as thin *passthrough*
subcommands -- ``pynidm csv2nidm`` and ``pynidm bids2nidm`` -- that forward every
argument unchanged to the existing ``main`` functions.  Flags and behavior are
identical to the standalone scripts (which remain available as
``csv2nidm`` / ``bidsmri2nidm``); only the invocation path is new.

Registration is an import side effect, matching the other tools (``click_main``
imports this module).  Because the arguments are forwarded verbatim, each
converter keeps its own argparse help -- ``pynidm csv2nidm -h`` shows the
converter's native usage.
"""
import click
from nidm.linkml.experiment.tools.bidsmri2nidm import main as _bids2nidm_main
from nidm.linkml.experiment.tools.click_base import cli
from nidm.linkml.experiment.tools.csv2nidm import csv2nidm_main as _csv2nidm_main

# ignore_unknown_options + an UNPROCESSED variadic argument = collect every token
# (including those starting with "-") and hand them to argparse untouched;
# help_option_names=[] disables click's own -h/--help so it passes through too.
_PASSTHROUGH = {"ignore_unknown_options": True, "help_option_names": []}


@cli.command(
    name="csv2nidm",
    context_settings=_PASSTHROUGH,
    short_help="Convert a CSV/TSV (+ optional JSON data dictionary) to NIDM.",
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def csv2nidm_cli(args):
    """Convert a CSV/TSV assessment file into a NIDM file.

    Thin wrapper over the standalone ``csv2nidm`` tool: every argument is
    forwarded unchanged.  Run ``pynidm csv2nidm -h`` for the full flag list.
    """
    raise SystemExit(_csv2nidm_main(list(args), prog="pynidm csv2nidm"))


@cli.command(
    name="bids2nidm",
    context_settings=_PASSTHROUGH,
    short_help="Convert a BIDS dataset to NIDM.",
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def bids2nidm_cli(args):
    """Convert a BIDS dataset into a NIDM file.

    Thin wrapper over the standalone ``bidsmri2nidm`` tool: every argument is
    forwarded unchanged.  Run ``pynidm bids2nidm -h`` for the full flag list.
    """
    raise SystemExit(_bids2nidm_main(list(args), prog="pynidm bids2nidm"))
