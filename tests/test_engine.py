from __future__ import annotations

import time
import unittest

from b8085.debugger import EmulatorSession


class ExecutionEngineTests(unittest.TestCase):
    def test_run_stays_active_while_halted_waiting_for_interrupt(self) -> None:
        source = """
            ORG 0000H
            MVI A, 4EH
            OUT 11H
            MVI A, 37H
            OUT 11H
            EI
            HLT
            IN 10H
            OUT 10H
            HLT
            ORG 0034H
            RET
            END
        """
        session = EmulatorSession()
        session.assemble_and_load(source)

        try:
            session.engine.start()

            for _ in range(100):
                if session.cpu.halted and session.engine.is_running():
                    break
                time.sleep(0.01)
            else:
                self.fail("engine did not remain active while waiting at HLT")

            session.serial.push_input_text("A")

            for _ in range(200):
                if session.serial.pop_output_text() == "A":
                    break
                time.sleep(0.01)
            else:
                self.fail("interrupt-driven serial input did not resume execution")

            for _ in range(100):
                if session.cpu.halted and not session.engine.is_running():
                    break
                time.sleep(0.01)
            else:
                self.fail("engine did not stop after the final non-interruptible HLT")
        finally:
            session.engine.stop()


if __name__ == "__main__":
    unittest.main()
