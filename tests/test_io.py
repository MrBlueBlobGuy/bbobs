from __future__ import annotations

import unittest

from b8085.debugger import EmulatorSession


def run_until_halt(session: EmulatorSession, limit: int = 1000) -> None:
    for _ in range(limit):
        if session.cpu.halted:
            return
        session.cpu.step()
    raise AssertionError("program did not halt")


class IoTests(unittest.TestCase):
    def test_8251_transmit_after_mode_and_command_setup(self) -> None:
        source = """
            ORG 0000H
            MVI A, 4EH
            OUT 11H
            MVI A, 37H
            OUT 11H
            MVI A, 41H
            OUT 10H
            HLT
            END
        """
        session = EmulatorSession()
        session.assemble_and_load(source)
        run_until_halt(session)
        self.assertEqual(session.serial.pop_output_text(), "A")

    def test_8251_status_reflects_receive_ready(self) -> None:
        session = EmulatorSession()
        session.serial.write_port(0x11, 0x4E)
        session.serial.write_port(0x11, 0x37)
        session.serial.push_input_text("Z")
        self.assertEqual(session.serial.status_byte() & 0x87, 0x87)
        self.assertEqual(session.serial.read_port(0x10), ord("Z"))
        self.assertEqual(session.serial.status_byte() & 0x02, 0x00)

    def test_sim_updates_serial_output_line(self) -> None:
        source = """
            ORG 0000H
            MVI A, 0C0H
            SIM
            HLT
            END
        """
        session = EmulatorSession()
        session.assemble_and_load(source)
        run_until_halt(session)
        self.assertEqual(session.serial.sod_line, 1)


if __name__ == "__main__":
    unittest.main()
