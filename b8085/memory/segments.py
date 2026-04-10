"""Memory segments for the emulator address space."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum


class MemoryAccessError(RuntimeError):
    """Raised when memory is accessed illegally."""


class SegmentType(str, Enum):
    """Supported memory segment kinds."""

    RAM = "ram"
    ROM = "rom"
    IO = "io"


Reader = Callable[[int], int]
Writer = Callable[[int, int], None]


@dataclass(slots=True)
class MemorySegment:
    """A contiguous region of the 8085 address space."""

    start: int
    end: int
    name: str
    segment_type: SegmentType
    readonly: bool = False
    initial_data: bytes | bytearray | None = None
    reader: Reader | None = None
    writer: Writer | None = None
    _storage: bytearray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not 0 <= self.start <= self.end <= 0xFFFF:
            raise ValueError("invalid memory segment bounds")
        size = self.size
        self._storage = bytearray(size)
        if self.initial_data is not None:
            data = bytes(self.initial_data)
            if len(data) > size:
                raise ValueError("initial data exceeds segment size")
            self._storage[: len(data)] = data
        if self.segment_type == SegmentType.ROM:
            self.readonly = True

    @property
    def size(self) -> int:
        """Return the size of the segment in bytes."""

        return self.end - self.start + 1

    def contains(self, address: int) -> bool:
        """Return whether the address belongs to this segment."""

        return self.start <= address <= self.end

    def _offset(self, address: int) -> int:
        if not self.contains(address):
            raise MemoryAccessError(f"address {address:04X} outside segment {self.name}")
        return address - self.start

    def read(self, address: int) -> int:
        """Read a byte from the segment."""

        if self.reader is not None:
            return self.reader(address) & 0xFF
        return self._storage[self._offset(address)]

    def write(self, address: int, value: int, force: bool = False) -> None:
        """Write a byte to the segment."""

        if self.readonly and not force:
            raise MemoryAccessError(f"segment {self.name} is read-only")
        value &= 0xFF
        if self.writer is not None:
            self.writer(address, value)
            return
        self._storage[self._offset(address)] = value

    def dump(self, start: int | None = None, length: int | None = None) -> bytes:
        """Return a raw view of data stored in the segment."""

        local_start = 0 if start is None else self._offset(start)
        local_end = self.size if length is None else local_start + length
        return bytes(self._storage[local_start:local_end])

