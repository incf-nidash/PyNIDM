import os
import subprocess

try:
    from importlib.metadata import PackageNotFoundError, version
except ImportError:  # pragma: no cover
    from importlib_metadata import PackageNotFoundError, version  # type: ignore


def _get_version_from_git() -> str:
    """Derive the package version from git tags when package metadata is unavailable."""
    try:
        _here = os.path.dirname(os.path.abspath(__file__))
        result = subprocess.run(
            ["git", "describe", "--tags", "--always"],
            cwd=_here,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode == 0:
            tag = result.stdout.decode().strip()
            # Strip leading 'v' from tags like 'v4.2.4' or 'v4.2.4-8-gabcdef0'
            return tag.lstrip("v")
    except Exception:
        pass
    return "0+unknown"


try:
    __version__ = version("pynidm")
    if __version__ == "0+unknown":
        __version__ = _get_version_from_git()
except PackageNotFoundError:
    __version__ = _get_version_from_git()


try:
    import etelemetry

    etelemetry.check_available_version("incf-nidash/pynidm", __version__)
except ImportError:
    pass
