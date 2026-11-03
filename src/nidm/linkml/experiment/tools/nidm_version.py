"""``pynidm version`` -- print the installed PyNIDM version."""
from nidm import __version__
from nidm.linkml.experiment.tools.click_base import cli


# adding click argument parsing
@cli.command()
def version():
    """
    This function will print the version of pynidm.
    """
    print(f"PyNIDM Version: {__version__}")


if __name__ == "__main__":
    version()
