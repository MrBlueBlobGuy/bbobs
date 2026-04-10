"""Breakpoint management."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class BreakpointManager:
    """Stores execution breakpoints."""

    _breakpoints: set[int] = field(default_factory=set, init=False, repr=False)

    def add(self, address: int) -> None:
        self._breakpoints.add(address & 0xFFFF)

    def remove(self, address: int) -> None:
        self._breakpoints.discard(address & 0xFFFF)

    def toggle(self, address: int) -> None:
        address &= 0xFFFF
        if address in self._breakpoints:
            self._breakpoints.remove(address)
        else:
            self._breakpoints.add(address)

    def contains(self, address: int) -> bool:
        return (address & 0xFFFF) in self._breakpoints

    def all(self) -> tuple[int, ...]:
        return tuple(sorted(self._breakpoints))

    def clear(self) -> None:
        self._breakpoints.clear()

