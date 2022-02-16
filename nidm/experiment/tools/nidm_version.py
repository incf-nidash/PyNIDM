import os,sys

import click
from nidm.experiment.tools.click_base import cli
from nidm.version import __version__

# adding click argument parsing
@cli.command()

def version():
    '''
    This function will print the version of pynidm.
    '''
    print("PyNIDM Version: %s" %__version__)


if __name__ == "__main__":
   version()