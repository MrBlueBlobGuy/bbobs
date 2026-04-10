"""Base interfaces for port-mapped devices."""

from __future__ import annotations

from abc import ABC, abstractmethod


class PortDevice(ABC):
    """Base class for port-mapped devices."""

    @abstractmethod
    def read_port(self, port: int) -> int:
        """Read a byte from a port."""

    @abstractmethod
    def write_port(self, port: int, value: int) -> None:
        """Write a byte to a port."""

