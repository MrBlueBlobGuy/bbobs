from __future__ import annotations

import unittest

from b8085.debugger import EmulatorSession


def run_until_halt(session: EmulatorSession, limit: int = 1000) -> None:
    for _ in range(limit):
        if session.cpu.halted:
            return
        session.cpu.step()
    raise AssertionError("program did not halt")


class CpuTests(unittest.TestCase):
    def test_arithmetic_and_cycles(self) -> None:
        source = """
            ORG 0000H
            MVI A, 02H
            ADI 03H
            HLT
            END
        """
        session = EmulatorSession()
        session.assemble_and_load(source)
        run_until_halt(session)
        self.assertEqual(session.cpu.registers.a, 0x05)
        self.assertEqual(session.cpu.cycles, 21)
        self.assertEqual(session.cpu.flags.z, 0)

    def test_branch_and_memory_store(self) -> None:
        source = """
            ORG 0000H
            MVI A, 00H
            CPI 00H
            JZ DONE
            MVI B, FFH
DONE:       INR B
            MOV A, B
            STA 2400H
            HLT
            END
        """
        session = EmulatorSession()
        session.assemble_and_load(source)
        run_until_halt(session)
        self.assertEqual(session.memory.read_byte(0x2400), 0x01)

    def test_rst7_5_interrupt_respects_ei_delay_and_exits_halt(self) -> None:
        source = """
            ORG 0000H
            EI
            HLT
            NOP
            HLT
            ORG 003CH
            INR A
            RET
            END
        """
        session = EmulatorSession()
        session.assemble_and_load(source)
        session.pulse_rst_7_5()

        result1 = session.cpu.step()
        self.assertIsNone(result1.interrupt_source)
        self.assertFalse(session.cpu.interrupts.enabled)

        result2 = session.cpu.step()
        self.assertIsNone(result2.interrupt_source)
        self.assertTrue(session.cpu.halted)
        self.assertTrue(session.cpu.interrupts.enabled)

        result3 = session.cpu.step()
        self.assertEqual(result3.interrupt_source, "RST7.5")
        self.assertEqual(session.cpu.registers.pc, 0x003C)
        self.assertFalse(session.cpu.halted)

        run_until_halt(session)
        self.assertEqual(session.cpu.registers.a, 0x01)

    def test_trap_is_non_maskable_and_first_rim_reports_previous_ie(self) -> None:
        source = """
            ORG 0000H
            EI
            NOP
            NOP
            HLT
            ORG 0024H
            RIM
            STA 2100H
            RIM
            STA 2101H
            HLT
            END
        """
        session = EmulatorSession()
        session.assemble_and_load(source)

        session.cpu.step()  # EI
        session.cpu.step()  # NOP, enables interrupts after completion
        self.assertTrue(session.cpu.interrupts.enabled)

        session.request_trap(True)
        result = session.cpu.step()
        self.assertEqual(result.interrupt_source, "TRAP")
        self.assertEqual(session.cpu.registers.pc, 0x0024)

        run_until_halt(session)
        self.assertEqual(session.memory.read_byte(0x2100) & 0x08, 0x08)
        self.assertEqual(session.memory.read_byte(0x2101) & 0x08, 0x00)

    def test_intr_accepts_supplied_call_instruction(self) -> None:
        source = """
            ORG 0000H
            EI
            NOP
            HLT
            ORG 0020H
            INR A
            HLT
            END
        """
        session = EmulatorSession()
        session.assemble_and_load(source)

        session.cpu.step()  # EI
        session.request_intr(0xCD, (0x20, 0x00))
        session.cpu.step()  # NOP, enables after completion
        result = session.cpu.step()

        self.assertEqual(result.interrupt_source, "INTR")
        self.assertEqual(session.cpu.registers.pc, 0x0020)

        run_until_halt(session)
        self.assertEqual(session.cpu.registers.a, 0x01)


if __name__ == "__main__":
    unittest.main()
