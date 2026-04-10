"""Assembler-specific exceptions."""

from __future__ import annotations


class AssemblyError(Exception):
    """Raised for source parsing or encoding failures."""

    def __init__(self, line_number: int, message: str) -> None:
        super().__init__(f"line {line_number}: {message}")
        self.line_number = line_number
        self.message = message

