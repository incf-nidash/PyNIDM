from __future__ import absolute_import, division, print_function
from .version import __version__
import __main__

if not hasattr(__main__, "__file__"):
    import etelemetry
    etelemetry.check_available_version("incf-nidash/pynidm", __version__)
