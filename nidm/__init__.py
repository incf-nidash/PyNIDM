from __future__ import absolute_import, division, print_function
from .version import __version__
import __main__

try:
    import etelemetry
    etelemetry.check_available_version("incf-nidash/pynidm", __version__)
except ImportError:
    pass
