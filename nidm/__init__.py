from __future__ import absolute_import, division, print_function
import __main__

__version__ = "3.9.7"

try:
    import etelemetry

    etelemetry.check_available_version("incf-nidash/pynidm", __version__)
except ImportError:
    pass
