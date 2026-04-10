"""Port-space routing."""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import PortDevice


class NullDevice(PortDevice):
    """Fallback device returning zero."""

    def read_port(self, port: int) -> int:
        return 0

    def write_port(self, port: int, value: int) -> None:
        return None


@dataclass(slots=True)
class PortSpace:
    """Port-mapped I/O bus for 8-bit ports."""

    default_device: PortDevice = field(default_factory=NullDevice)
    _ports: dict[int, PortDevice] = field(default_factory=dict, init=False, repr=False)

    def map_device(self, device: PortDevice, ports: int | range | list[int] | tuple[int, ...]) -> None:
        """Map a device to one or more ports."""

        if isinstance(ports, int):
            self._ports[ports & 0xFF] = device
            return
        for port in ports:
            self._ports[port & 0xFF] = device

    def read(self, port: int) -> int:
        """Read a byte from a port."""

        device = self._ports.get(port & 0xFF, self.default_device)
        return device.read_port(port & 0xFF) & 0xFF

    def write(self, port: int, value: int) -> None:
        """Write a byte to a port."""

        device = self._ports.get(port & 0xFF, self.default_device)
        device.write_port(port & 0xFF, value & 0xFF)

