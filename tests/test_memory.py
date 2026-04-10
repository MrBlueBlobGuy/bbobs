from __future__ import annotations

import unittest

from b8085.debugger import EmulatorSession
from b8085.memory import AddressSpace, MemoryAccessError, MemorySegment, SegmentType


class MemoryTests(unittest.TestCase):
    def test_flat_ram_reads_and_writes(self) -> None:
        memory = AddressSpace.with_flat_ram()
        memory.write_byte(0x1234, 0xAB)
        self.assertEqual(memory.read_byte(0x1234), 0xAB)
        memory.write_word(0x2000, 0xBEEF)
        self.assertEqual(memory.read_word(0x2000), 0xBEEF)

    def test_rom_segment_rejects_runtime_writes(self) -> None:
        memory = AddressSpace()
        memory.add_segment(MemorySegment(0x0000, 0x00FF, "ROM", SegmentType.ROM, initial_data=b"\xAA"))
        with self.assertRaises(MemoryAccessError):
            memory.write_byte(0x0000, 0x55)
        memory.write_byte(0x0000, 0x55, force=True)
        self.assertEqual(memory.read_byte(0x0000), 0x55)

    def test_flashing_new_rom_image_erases_old_bytes(self) -> None:
        session = EmulatorSession.with_default_segments()
        first = session.assemble(
            """
            ORG 0000H
            MVI A, 12H
            HLT
            END
            """
        )
        second = session.assemble(
            """
            ORG 0000H
            HLT
            END
            """
        )

        session.flash_rom_image(first)
        self.assertEqual(session.memory.read_byte(0x0001), 0x12)

        session.flash_rom_image(second)
        self.assertEqual(session.memory.read_byte(0x0000), 0x76)
        self.assertEqual(session.memory.read_byte(0x0001), 0x00)
        self.assertEqual(session.memory.read_byte(0x0002), 0x00)


if __name__ == "__main__":
    unittest.main()
