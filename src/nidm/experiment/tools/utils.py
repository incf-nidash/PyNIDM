from __future__ import annotations
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from types import TracebackType
from typing import IO, Any, Optional


@dataclass
class Reporter:
    output: Optional[IO[str]] = field(init=False)
    output_file: InitVar[str | Path | None]

    def __post_init__(self, output_file: str | Path | None) -> None:
        if output_file is not None:
            self.output = open(output_file, "w", encoding="utf-8")
        else:
            self.output = None

    def __enter__(self) -> Reporter:
        return self

    def __exit__(
        self,
        _exc_type: Optional[type[BaseException]],
        _exc_val: Optional[BaseException],
        _exc_tb: Optional[TracebackType],
    ) -> None:
        if self.output is not None:
            self.output.close()

    def print(self, *args: Any, end: str = "\n", sep: str = "") -> None:
        print(*args, end=end, sep=sep)
        if self.output is not None:
            print(*args, end=end, sep=sep, file=self.output)

    def print_file(self, *args: Any, end: str = "\n", sep: str = "") -> None:
        if self.output is not None:
            print(*args, end=end, sep=sep, file=self.output)
