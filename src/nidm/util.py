from __future__ import annotations
from pathlib import Path
from uuid import UUID
import requests


def urlretrieve(url: str, filepath: str | Path) -> None:
    """`requests`-based alternative to `urllib.request.urlretrieve`"""
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(filepath, "wb") as fp:
            for chunk in r.iter_content(65535):
                fp.write(chunk)


def validate_uuid(uuid_string):
    """Validate that *uuid_string* is a well-formed UUID (uuid module does
    the checking).  Returns True/False."""
    try:
        UUID(uuid_string)
    except ValueError:
        return False
    return True
