from importlib.metadata import version

__version__ = version("pynidm")

try:
    import etelemetry

    etelemetry.check_available_version("incf-nidash/pynidm", __version__)
except ImportError:
    pass


def my_isinstance(o, t):
    if (type(o) is t) != isinstance(o, t):
        #import pdb; pdb.set_trace()
        print(f"difference: o {o} is of type {type(o)}, t is {t}, isinstance(o, t): {isinstance(o, t)}")
    return isinstance(o, t)
