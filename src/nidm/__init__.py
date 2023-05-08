from importlib.metadata import version

__version__ = version("pynidm")

try:
    import etelemetry

    etelemetry.check_available_version("incf-nidash/pynidm", __version__)
except ImportError:
    pass
