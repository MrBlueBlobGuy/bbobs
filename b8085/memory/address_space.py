"""Address-space composition for memory segments."""

from __future__ import annotations

from dataclasses import dataclass, field

from .segments import MemoryAccessError, MemorySegment


@dataclass(slots=True)
class AddressSpace:
    """The full 64KB 8085 address space."""

    segments: list[MemorySegment] = field(default_factory=list)
    _pages: list[list[MemorySegment]] = field(
        default_factory=lambda: [[] for _ in range(256)], init=False, repr=False
    )

    def add_segment(self, segment: MemorySegment) -> None:
        """Add a memory segment and update the lookup table."""

        for existing in self.segments:
            if not (segment.end < existing.start or segment.start > existing.end):
                raise ValueError(
                    f"segment overlap between {segment.name} and {existing.name}"
                )
        for page in range(segment.start >> 8, (segment.end >> 8) + 1):
            self._pages[page].append(segment)
        self.segments.append(segment)

    def resolve(self, address: int) -> MemorySegment:
        """Resolve an address to its backing segment."""

        address &= 0xFFFF
        for segment in self._pages[address >> 8]:
            if segment.contains(address):
                return segment
        raise MemoryAccessError(f"unmapped address {address:04X}")

    def read_byte(self, address: int) -> int:
        """Read a byte from memory."""

        return self.resolve(address).read(address)

    def write_byte(self, address: int, value: int, force: bool = False) -> None:
        """Write a byte to memory."""

        self.resolve(address).write(address, value, force=force)

    def read_word(self, address: int) -> int:
        """Read a 16-bit little-endian word."""

        low = self.read_byte(address)
        high = self.read_byte((address + 1) & 0xFFFF)
        return low | (high << 8)

    def write_word(self, address: int, value: int, force: bool = False) -> None:
        """Write a 16-bit little-endian word."""

        self.write_byte(address, value & 0xFF, force=force)
        self.write_byte((address + 1) & 0xFFFF, (value >> 8) & 0xFF, force=force)

    def load(self, start: int, data: bytes | bytearray, force: bool = False) -> None:
        """Load bytes into memory."""

        for offset, value in enumerate(data):
            self.write_byte((start + offset) & 0xFFFF, value, force=force)

    def snapshot(self, start: int, length: int) -> bytes:
        """Return a memory snapshot."""

        return bytes(self.read_byte((start + index) & 0xFFFF) for index in range(length))

    @classmethod
    def with_flat_ram(cls) -> "AddressSpace":
        """Create a default flat 64KB RAM address space."""

        from .segments import MemorySegment, SegmentType

        address_space = cls()
        address_space.add_segment(
            MemorySegment(0x0000, 0xFFFF, "RAM", SegmentType.RAM, readonly=False)
        )
        return address_space
