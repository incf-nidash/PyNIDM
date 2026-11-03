"""The ``pynidm`` click command group for the LinkML toolset.

Mirrors ``nidm.experiment.tools.click_base``: every LinkML CLI tool
registers its subcommand on this shared :data:`cli` group via
``@cli.command()``.  ``click_main`` imports the tool modules so the
registration side effects run and ``pynidm <subcommand>`` resolves.
"""
import click


@click.group()
def cli():
    """Root ``pynidm`` command group; subcommands attach here via ``@cli.command()``."""
    pass
