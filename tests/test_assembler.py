from __future__ import annotations

import unittest

from b8085.assembler import Assembler


class AssemblerTests(unittest.TestCase):
    def test_labels_and_directives(self) -> None:
        source = """
            ORG 0000H
START:      MVI A, 01H
            INR A
            JNZ START
            DB 'A', 00H
            DW 1234H
            END
        """
        image = Assembler().assemble(source)
        self.assertEqual(image.symbols["START"], 0x0000)
        bytes_out = b"".join(segment.data for segment in image.segments)
        self.assertEqual(bytes_out[:6], bytes([0x3E, 0x01, 0x3C, 0xC2, 0x00, 0x00]))
        self.assertEqual(bytes_out[6:], bytes([0x41, 0x00, 0x34, 0x12]))


if __name__ == "__main__":
    unittest.main()

