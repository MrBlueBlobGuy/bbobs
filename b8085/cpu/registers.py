"""Register and flag state."""

from __future__ import annotations

from dataclasses import dataclass


def even_parity(value: int) -> bool:
    """Return True when the value has even parity."""

    return (value & 0xFF).bit_count() % 2 == 0


@dataclass(slots=True)
class Flags:
    """8085 flag register."""

    z: int = 0
    s: int = 0
    p: int = 0
    cy: int = 0
    ac: int = 0

    def as_byte(self) -> int:
        """Pack flags into the PSW representation."""

        return (
            (self.s << 7)
            | (self.z << 6)
            | (self.ac << 4)
            | (self.p << 2)
            | 0x02
            | self.cy
        )

    def from_byte(self, value: int) -> None:
        """Load flags from a PSW byte."""

        self.s = 1 if value & 0x80 else 0
        self.z = 1 if value & 0x40 else 0
        self.ac = 1 if value & 0x10 else 0
        self.p = 1 if value & 0x04 else 0
        self.cy = 1 if value & 0x01 else 0

    def set_szp(self, value: int) -> None:
        """Update sign, zero, and parity flags from an 8-bit value."""

        value &= 0xFF
        self.z = 1 if value == 0 else 0
        self.s = 1 if value & 0x80 else 0
        self.p = 1 if even_parity(value) else 0


@dataclass(slots=True)
class Registers:
    """8085 general register file."""

    a: int = 0
    b: int = 0
    c: int = 0
    d: int = 0
    e: int = 0
    h: int = 0
    l: int = 0
    sp: int = 0xFFFF
    pc: int = 0x0000

    def bc(self) -> int:
        return ((self.b & 0xFF) << 8) | (self.c & 0xFF)

    def de(self) -> int:
        return ((self.d & 0xFF) << 8) | (self.e & 0xFF)

    def hl(self) -> int:
        return ((self.h & 0xFF) << 8) | (self.l & 0xFF)

    def set_bc(self, value: int) -> None:
        self.b = (value >> 8) & 0xFF
        self.c = value & 0xFF

    def set_de(self, value: int) -> None:
        self.d = (value >> 8) & 0xFF
        self.e = value & 0xFF

    def set_hl(self, value: int) -> None:
        self.h = (value >> 8) & 0xFF
        self.l = value & 0xFF

    def get_register(self, code: int) -> int:
        """Return register value for standard 8085 register encoding."""

        return {
            0: self.b,
            1: self.c,
            2: self.d,
            3: self.e,
            4: self.h,
            5: self.l,
            7: self.a,
        }[code]

    def set_register(self, code: int, value: int) -> None:
        """Write register value for standard 8085 register encoding."""

        value &= 0xFF
        if code == 0:
            self.b = value
        elif code == 1:
            self.c = value
        elif code == 2:
            self.d = value
        elif code == 3:
            self.e = value
        elif code == 4:
            self.h = value
        elif code == 5:
            self.l = value
        elif code == 7:
            self.a = value
        else:
            raise KeyError(f"invalid register code {code}")

