"""Shared helpers for the LinkML CLI tools (currently the :class:`Reporter`)."""
from __future__ import annotations
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from types import TracebackType
from typing import IO, Any, Optional


@dataclass
class Reporter:
    """Tee output to stdout and, optionally, to a file.

    Used as a context manager so the output file is opened on entry and
    closed on exit.  ``print`` writes to both destinations; ``print_file``
    writes only to the file.
    """

    output: Optional[IO[str]] = field(init=False)
    output_file: InitVar[str | Path | None]

    def __post_init__(self, output_file: str | Path | None) -> None:
        """Open *output_file* for writing when supplied, else disable file output."""
        if output_file is not None:
            self.output = open(output_file, "w", encoding="utf-8")
        else:
            self.output = None

    def __enter__(self) -> Reporter:
        """Enter the context manager, returning self."""
        return self

    def __exit__(
        self,
        _exc_type: Optional[type[BaseException]],
        _exc_val: Optional[BaseException],
        _exc_tb: Optional[TracebackType],
    ) -> None:
        """Close the output file on context-manager exit, if one was opened."""
        if self.output is not None:
            self.output.close()

    def print(self, *args: Any, end: str = "\n", sep: str = "") -> None:
        """Print to stdout and (if configured) also to the output file."""
        print(*args, end=end, sep=sep)
        if self.output is not None:
            print(*args, end=end, sep=sep, file=self.output)

    def print_file(self, *args: Any, end: str = "\n", sep: str = "") -> None:
        """Print only to the output file (no-op when no file is configured)."""
        if self.output is not None:
            print(*args, end=end, sep=sep, file=self.output)
