from __future__ import annotations

from pathlib import Path
import unittest

from b8085.assembler import Assembler
from b8085.debugger import EmulatorSession


class ExampleTests(unittest.TestCase):
    WOZMON_WAIT_PC = 0x005E

    def test_all_examples_assemble(self) -> None:
        assembler = Assembler()
        for path in sorted(Path("examples").glob("*.asm")):
            with self.subTest(example=path.name):
                image = assembler.assemble(path.read_text())
                self.assertGreater(len(image.segments), 0)

    def test_wozmon_clone_example_assembles(self) -> None:
        source = Path("examples/wozmon_clone.asm").read_text()
        image = Assembler().assemble(source)
        self.assertEqual([segment.start for segment in image.segments], [0x0000, 0x0034, 0x0040])
        self.assertEqual(image.segments[1].data[0], 0xC3)
        self.assertGreater(len(image.segments[2].data), 256)
        self.assertIn("START", image.symbols)
        self.assertIn("CMD_READ", image.symbols)
        self.assertIn("SERIAL_RX_ISR", image.symbols)

    def test_wozmon_clone_handles_interrupt_driven_help_command(self) -> None:
        source = Path("examples/wozmon_clone.asm").read_text()
        session = EmulatorSession()
        session.assemble_and_load(source)

        for _ in range(5_000):
            session.cpu.step()
            if session.cpu.halted:
                break

        self.assertTrue(session.cpu.halted)
        self.assertEqual(session.cpu.registers.pc, self.WOZMON_WAIT_PC)
        self.assertIn("BLUMON", session.serial.pop_output_text())

        session.serial.push_input_text("H\r")

        for _ in range(50_000):
            session.cpu.step()
            if (
                session.cpu.halted
                and session.cpu.registers.pc == self.WOZMON_WAIT_PC
                and not session.serial._rx_buffer
                and session.memory.read_byte(0x2403) == 0
            ):
                break

        output = session.serial.pop_output_text()
        self.assertIn("R HHHH      READ 16 BYTES", output)
        self.assertIn("W HHHH BB   WRITE BYTES", output)
        self.assertIn("G HHHH      GO", output)
        self.assertIn("C HHHH      CALL / RET", output)
        self.assertIn("H           HELP", output)
        self.assertTrue(session.cpu.halted)
        self.assertEqual(session.cpu.registers.pc, self.WOZMON_WAIT_PC)

    def test_wozmon_clone_can_call_program_and_return_via_ret(self) -> None:
        source = Path("examples/wozmon_clone.asm").read_text()
        session = EmulatorSession()
        session.assemble_and_load(source)

        for _ in range(5_000):
            session.cpu.step()
            if session.cpu.halted:
                break

        session.serial.pop_output_text()
        session.serial.push_input_text("W 2210 3E 42 D3 10 C9\rC 2210\r")

        for _ in range(100_000):
            session.cpu.step()
            if (
                session.cpu.halted
                and session.cpu.registers.pc == self.WOZMON_WAIT_PC
                and not session.serial._rx_buffer
                and session.memory.read_byte(0x2403) == 0
            ):
                break

        output = session.serial.pop_output_text()
        self.assertIn("OK", output)
        self.assertIn("B", output)
        self.assertTrue(output.endswith("\\ "))
        self.assertTrue(session.cpu.halted)
        self.assertEqual(session.cpu.registers.pc, self.WOZMON_WAIT_PC)


if __name__ == "__main__":
    unittest.main()
