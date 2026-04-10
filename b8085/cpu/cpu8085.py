"""Core Intel 8085 CPU implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from b8085.io import PortSpace, SerialDevice
from b8085.memory import AddressSpace

from .opcodes import IMMEDIATE_ALU, instruction_cycles, instruction_size
from .registers import Flags, Registers

InterruptSource = Literal["TRAP", "RST7.5", "RST6.5", "RST5.5", "INTR"]


@dataclass(frozen=True, slots=True)
class InterruptInstruction:
    """An instruction inserted during INTR acknowledge."""

    opcode: int
    operands: tuple[int, ...] = ()

    @property
    def size(self) -> int:
        """Return the encoded instruction size."""

        return instruction_size(self.opcode)


@dataclass(slots=True)
class InterruptState:
    """State for the 8085 interrupt system."""

    enabled: bool = False
    enable_after_next: int = 0
    mask_5_5: int = 0
    mask_6_5: int = 0
    mask_7_5: int = 0
    line_5_5: int = 0
    line_6_5: int = 0
    line_7_5: int = 0
    line_intr: int = 0
    trap_line: int = 0
    trap_pending: int = 0
    trap_rearm_required: bool = False
    saved_ie_before_trap: int | None = None
    report_saved_ie_on_next_rim: bool = False
    pending_7_5: int = 0
    intr_instruction: InterruptInstruction = field(
        default_factory=lambda: InterruptInstruction(0xC7, ())
    )


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Information about a single executed instruction."""

    pc: int
    opcode: int
    size: int
    cycles: int
    halted: bool
    interrupt_source: InterruptSource | None = None


@dataclass(slots=True)
class CPU8085:
    """Cycle-counting Intel 8085 CPU emulator."""

    memory: AddressSpace
    ports: PortSpace = field(default_factory=PortSpace)
    serial: SerialDevice | None = None
    registers: Registers = field(default_factory=Registers)
    flags: Flags = field(default_factory=Flags)
    cycles: int = 0
    halted: bool = False
    interrupts: InterruptState = field(default_factory=InterruptState)

    def reset(self, pc: int = 0x0000, sp: int = 0xFFFF) -> None:
        """Reset registers, flags, and internal state."""

        self.registers = Registers(sp=sp, pc=pc)
        self.flags = Flags()
        self.cycles = 0
        self.halted = False
        self.interrupts = InterruptState()

    def step(self) -> ExecutionResult:
        """Execute a single instruction."""

        interrupt_result = self._service_pending_interrupt()
        if interrupt_result is not None:
            return interrupt_result

        if self.halted:
            return ExecutionResult(self.registers.pc, 0x76, 1, 0, True)

        start_pc = self.registers.pc
        opcode = self._next_byte()
        size = instruction_size(opcode)
        operands: list[int] = []
        for _ in range(size - 1):
            operands.append(self._next_byte())

        branch_taken = False

        if 0x40 <= opcode <= 0x7F:
            if opcode == 0x76:
                self.halted = True
            else:
                dst = (opcode >> 3) & 0x07
                src = opcode & 0x07
                self._write_reg(dst, self._read_reg(src))
        elif 0x80 <= opcode <= 0xBF:
            group = (opcode - 0x80) >> 3
            operand = self._read_reg(opcode & 0x07)
            self._execute_alu(group, operand)
        elif opcode in IMMEDIATE_ALU:
            self._execute_immediate_alu(opcode, operands[0])
        elif (opcode & 0xC7) == 0x04:
            reg = (opcode >> 3) & 0x07
            value = self._read_reg(reg)
            result = (value + 1) & 0xFF
            carry = self.flags.cy
            self.flags.ac = 1 if ((value & 0x0F) + 1) > 0x0F else 0
            self.flags.set_szp(result)
            self.flags.cy = carry
            self._write_reg(reg, result)
        elif (opcode & 0xC7) == 0x05:
            reg = (opcode >> 3) & 0x07
            value = self._read_reg(reg)
            result = (value - 1) & 0xFF
            carry = self.flags.cy
            self.flags.ac = 1 if (value & 0x0F) == 0 else 0
            self.flags.set_szp(result)
            self.flags.cy = carry
            self._write_reg(reg, result)
        elif (opcode & 0xC7) == 0x06:
            self._write_reg((opcode >> 3) & 0x07, operands[0])
        elif (opcode & 0xCF) == 0x01:
            self._set_rp((opcode >> 4) & 0x03, self._word_from_bytes(operands))
        elif (opcode & 0xCF) == 0x03:
            index = (opcode >> 4) & 0x03
            self._set_rp(index, (self._get_rp(index) + 1) & 0xFFFF)
        elif (opcode & 0xCF) == 0x0B:
            index = (opcode >> 4) & 0x03
            self._set_rp(index, (self._get_rp(index) - 1) & 0xFFFF)
        elif (opcode & 0xCF) == 0x09:
            left = self.registers.hl()
            right = self._get_rp((opcode >> 4) & 0x03)
            result = left + right
            self.flags.cy = 1 if result > 0xFFFF else 0
            self.registers.set_hl(result & 0xFFFF)
        elif (opcode & 0xCF) == 0xC1:
            self._pop_stack_pair((opcode >> 4) & 0x03)
        elif (opcode & 0xCF) == 0xC5:
            self._push_stack_pair((opcode >> 4) & 0x03)
        elif opcode in {0xC2, 0xCA, 0xD2, 0xDA, 0xE2, 0xEA, 0xF2, 0xFA}:
            branch_taken = self._condition((opcode >> 3) & 0x07)
            if branch_taken:
                self.registers.pc = self._word_from_bytes(operands)
        elif opcode in {0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC}:
            branch_taken = self._condition((opcode >> 3) & 0x07)
            if branch_taken:
                self._push(self.registers.pc)
                self.registers.pc = self._word_from_bytes(operands)
        elif opcode in {0xC0, 0xC8, 0xD0, 0xD8, 0xE0, 0xE8, 0xF0, 0xF8}:
            branch_taken = self._condition((opcode >> 3) & 0x07)
            if branch_taken:
                self.registers.pc = self._pop()
        elif (opcode & 0xC7) == 0xC7:
            self._push(self.registers.pc)
            self.registers.pc = ((opcode >> 3) & 0x07) * 8
        else:
            branch_taken = self._execute_misc(opcode, operands)

        cycles = instruction_cycles(opcode, branch_taken)
        self.cycles += cycles
        self._complete_instruction(opcode)
        return ExecutionResult(start_pc, opcode, size, cycles, self.halted)

    def _execute_misc(self, opcode: int, operands: list[int]) -> bool:
        branch_taken = False

        if opcode in {0x00, 0x08, 0x10, 0x18}:
            return False
        if opcode == 0x20:
            self.registers.a = self._rim()
            return False
        if opcode == 0x30:
            self._sim(self.registers.a)
            return False
        if opcode == 0x07:
            bit7 = (self.registers.a >> 7) & 0x01
            self.registers.a = ((self.registers.a << 1) | bit7) & 0xFF
            self.flags.cy = bit7
            return False
        if opcode == 0x0F:
            bit0 = self.registers.a & 0x01
            self.registers.a = ((bit0 << 7) | (self.registers.a >> 1)) & 0xFF
            self.flags.cy = bit0
            return False
        if opcode == 0x17:
            carry = self.flags.cy
            bit7 = (self.registers.a >> 7) & 0x01
            self.registers.a = ((self.registers.a << 1) | carry) & 0xFF
            self.flags.cy = bit7
            return False
        if opcode == 0x1F:
            carry = self.flags.cy
            bit0 = self.registers.a & 0x01
            self.registers.a = ((carry << 7) | (self.registers.a >> 1)) & 0xFF
            self.flags.cy = bit0
            return False
        if opcode == 0x02:
            self.memory.write_byte(self.registers.bc(), self.registers.a)
            return False
        if opcode == 0x12:
            self.memory.write_byte(self.registers.de(), self.registers.a)
            return False
        if opcode == 0x0A:
            self.registers.a = self.memory.read_byte(self.registers.bc())
            return False
        if opcode == 0x1A:
            self.registers.a = self.memory.read_byte(self.registers.de())
            return False
        if opcode == 0x22:
            address = self._word_from_bytes(operands)
            self.memory.write_byte(address, self.registers.l)
            self.memory.write_byte((address + 1) & 0xFFFF, self.registers.h)
            return False
        if opcode == 0x2A:
            address = self._word_from_bytes(operands)
            self.registers.l = self.memory.read_byte(address)
            self.registers.h = self.memory.read_byte((address + 1) & 0xFFFF)
            return False
        if opcode == 0x27:
            self._daa()
            return False
        if opcode == 0x2F:
            self.registers.a ^= 0xFF
            return False
        if opcode == 0x32:
            self.memory.write_byte(self._word_from_bytes(operands), self.registers.a)
            return False
        if opcode == 0x3A:
            self.registers.a = self.memory.read_byte(self._word_from_bytes(operands))
            return False
        if opcode == 0x37:
            self.flags.cy = 1
            return False
        if opcode == 0x3F:
            self.flags.cy ^= 0x01
            return False
        if opcode == 0xC3:
            self.registers.pc = self._word_from_bytes(operands)
            return True
        if opcode == 0xC9 or opcode == 0xD9:
            self.registers.pc = self._pop()
            return True
        if opcode == 0xCD:
            self._push(self.registers.pc)
            self.registers.pc = self._word_from_bytes(operands)
            return True
        if opcode == 0xD3:
            self.ports.write(operands[0], self.registers.a)
            return False
        if opcode == 0xDB:
            self.registers.a = self.ports.read(operands[0])
            return False
        if opcode == 0xE3:
            stack_low = self.memory.read_byte(self.registers.sp)
            stack_high = self.memory.read_byte((self.registers.sp + 1) & 0xFFFF)
            self.memory.write_byte(self.registers.sp, self.registers.l)
            self.memory.write_byte((self.registers.sp + 1) & 0xFFFF, self.registers.h)
            self.registers.l = stack_low
            self.registers.h = stack_high
            return False
        if opcode == 0xE9:
            self.registers.pc = self.registers.hl()
            return True
        if opcode == 0xEB:
            self.registers.d, self.registers.h = self.registers.h, self.registers.d
            self.registers.e, self.registers.l = self.registers.l, self.registers.e
            return False
        if opcode == 0xF3:
            self.interrupts.enabled = False
            self.interrupts.enable_after_next = 0
            return False
        if opcode == 0xF9:
            self.registers.sp = self.registers.hl()
            return False
        if opcode == 0xFB:
            self.interrupts.enabled = False
            self.interrupts.enable_after_next = 1
            return False
        return False

    def request_trap(self, active: bool = True) -> None:
        """Drive the TRAP line."""

        if active:
            if not self.interrupts.trap_line and not self.interrupts.trap_rearm_required:
                self.interrupts.trap_pending = 1
            self.interrupts.trap_line = 1
            return
        self.interrupts.trap_line = 0
        self.interrupts.trap_rearm_required = False

    def request_rst_7_5(self) -> None:
        """Pulse the edge-triggered RST 7.5 line."""

        self.interrupts.line_7_5 = 1
        self.interrupts.pending_7_5 = 1
        self.interrupts.line_7_5 = 0

    def set_rst_6_5(self, active: bool = True) -> None:
        """Drive the level-sensitive RST 6.5 line."""

        self.interrupts.line_6_5 = 1 if active else 0

    def set_rst_5_5(self, active: bool = True) -> None:
        """Drive the level-sensitive RST 5.5 line."""

        self.interrupts.line_5_5 = 1 if active else 0

    def request_intr(self, opcode: int = 0xC7, operands: tuple[int, ...] = (), active: bool = True) -> None:
        """Drive the INTR line and provide the acknowledge instruction."""

        if active:
            self.interrupts.line_intr = 1
            self.interrupts.intr_instruction = InterruptInstruction(opcode & 0xFF, tuple(operands))
            return
        self.interrupts.line_intr = 0

    def clear_intr(self) -> None:
        """Lower the INTR line."""

        self.interrupts.line_intr = 0

    def _execute_alu(self, group: int, operand: int) -> None:
        if group == 0:
            self._add(operand, carry=0)
        elif group == 1:
            self._add(operand, carry=self.flags.cy)
        elif group == 2:
            self._sub(operand, borrow=0)
        elif group == 3:
            self._sub(operand, borrow=self.flags.cy)
        elif group == 4:
            self.registers.a &= operand
            self.registers.a &= 0xFF
            self.flags.cy = 0
            self.flags.ac = 1
            self.flags.set_szp(self.registers.a)
        elif group == 5:
            self.registers.a ^= operand
            self.flags.cy = 0
            self.flags.ac = 0
            self.flags.set_szp(self.registers.a)
        elif group == 6:
            self.registers.a |= operand
            self.flags.cy = 0
            self.flags.ac = 0
            self.flags.set_szp(self.registers.a)
        elif group == 7:
            self._compare(operand)

    def _execute_immediate_alu(self, opcode: int, operand: int) -> None:
        if opcode == 0xC6:
            self._add(operand, carry=0)
        elif opcode == 0xCE:
            self._add(operand, carry=self.flags.cy)
        elif opcode == 0xD6:
            self._sub(operand, borrow=0)
        elif opcode == 0xDE:
            self._sub(operand, borrow=self.flags.cy)
        elif opcode == 0xE6:
            self.registers.a &= operand
            self.flags.cy = 0
            self.flags.ac = 1
            self.flags.set_szp(self.registers.a)
        elif opcode == 0xEE:
            self.registers.a ^= operand
            self.flags.cy = 0
            self.flags.ac = 0
            self.flags.set_szp(self.registers.a)
        elif opcode == 0xF6:
            self.registers.a |= operand
            self.flags.cy = 0
            self.flags.ac = 0
            self.flags.set_szp(self.registers.a)
        elif opcode == 0xFE:
            self._compare(operand)

    def _add(self, operand: int, carry: int) -> None:
        acc = self.registers.a
        result = acc + operand + carry
        self.flags.cy = 1 if result > 0xFF else 0
        self.flags.ac = 1 if ((acc & 0x0F) + (operand & 0x0F) + carry) > 0x0F else 0
        self.registers.a = result & 0xFF
        self.flags.set_szp(self.registers.a)

    def _sub(self, operand: int, borrow: int) -> None:
        acc = self.registers.a
        result = acc - operand - borrow
        self.flags.cy = 1 if result < 0 else 0
        self.flags.ac = 1 if ((acc & 0x0F) - (operand & 0x0F) - borrow) < 0 else 0
        self.registers.a = result & 0xFF
        self.flags.set_szp(self.registers.a)

    def _compare(self, operand: int) -> None:
        acc = self.registers.a
        result = acc - operand
        self.flags.cy = 1 if result < 0 else 0
        self.flags.ac = 1 if ((acc & 0x0F) - (operand & 0x0F)) < 0 else 0
        self.flags.set_szp(result & 0xFF)

    def _daa(self) -> None:
        correction = 0
        carry_out = self.flags.cy
        acc = self.registers.a
        if (acc & 0x0F) > 9 or self.flags.ac:
            correction |= 0x06
        if acc > 0x99 or self.flags.cy:
            correction |= 0x60
            carry_out = 1
        result = acc + correction
        self.flags.ac = 1 if ((acc & 0x0F) + (correction & 0x0F)) > 0x0F else 0
        self.registers.a = result & 0xFF
        self.flags.cy = carry_out if correction & 0x60 else self.flags.cy
        self.flags.set_szp(self.registers.a)

    def _condition(self, code: int) -> bool:
        return {
            0: self.flags.z == 0,
            1: self.flags.z == 1,
            2: self.flags.cy == 0,
            3: self.flags.cy == 1,
            4: self.flags.p == 0,
            5: self.flags.p == 1,
            6: self.flags.s == 0,
            7: self.flags.s == 1,
        }[code]

    def _read_reg(self, code: int) -> int:
        if code == 6:
            return self.memory.read_byte(self.registers.hl())
        return self.registers.get_register(code)

    def _write_reg(self, code: int, value: int) -> None:
        if code == 6:
            self.memory.write_byte(self.registers.hl(), value)
            return
        self.registers.set_register(code, value)

    def _get_rp(self, index: int) -> int:
        if index == 0:
            return self.registers.bc()
        if index == 1:
            return self.registers.de()
        if index == 2:
            return self.registers.hl()
        return self.registers.sp

    def _set_rp(self, index: int, value: int) -> None:
        value &= 0xFFFF
        if index == 0:
            self.registers.set_bc(value)
        elif index == 1:
            self.registers.set_de(value)
        elif index == 2:
            self.registers.set_hl(value)
        else:
            self.registers.sp = value

    def _push_stack_pair(self, index: int) -> None:
        if index == 0:
            self._push(self.registers.bc())
        elif index == 1:
            self._push(self.registers.de())
        elif index == 2:
            self._push(self.registers.hl())
        else:
            self._push((self.registers.a << 8) | self.flags.as_byte())

    def _pop_stack_pair(self, index: int) -> None:
        value = self._pop()
        if index == 0:
            self.registers.set_bc(value)
        elif index == 1:
            self.registers.set_de(value)
        elif index == 2:
            self.registers.set_hl(value)
        else:
            self.registers.a = (value >> 8) & 0xFF
            self.flags.from_byte(value & 0xFF)

    def _push(self, value: int) -> None:
        self.registers.sp = (self.registers.sp - 1) & 0xFFFF
        self.memory.write_byte(self.registers.sp, (value >> 8) & 0xFF)
        self.registers.sp = (self.registers.sp - 1) & 0xFFFF
        self.memory.write_byte(self.registers.sp, value & 0xFF)

    def _pop(self) -> int:
        low = self.memory.read_byte(self.registers.sp)
        self.registers.sp = (self.registers.sp + 1) & 0xFFFF
        high = self.memory.read_byte(self.registers.sp)
        self.registers.sp = (self.registers.sp + 1) & 0xFFFF
        return low | (high << 8)

    def _rim(self) -> int:
        sid = self.serial.read_sid() if self.serial is not None else 0
        interrupt_enable = self._rim_interrupt_enable_bit()
        return (
            (sid << 7)
            | (self.interrupts.pending_7_5 << 6)
            | (self.interrupts.line_6_5 << 5)
            | (self.interrupts.line_5_5 << 4)
            | (interrupt_enable << 3)
            | (self.interrupts.mask_7_5 << 2)
            | (self.interrupts.mask_6_5 << 1)
            | self.interrupts.mask_5_5
        )

    def _sim(self, accumulator: int) -> None:
        if accumulator & 0x08:
            self.interrupts.mask_5_5 = accumulator & 0x01
            self.interrupts.mask_6_5 = 1 if accumulator & 0x02 else 0
            self.interrupts.mask_7_5 = 1 if accumulator & 0x04 else 0
        if accumulator & 0x10:
            self.interrupts.pending_7_5 = 0
        if accumulator & 0x40 and self.serial is not None:
            self.serial.write_sod(1 if accumulator & 0x80 else 0)

    def _next_byte(self) -> int:
        value = self.memory.read_byte(self.registers.pc)
        self.registers.pc = (self.registers.pc + 1) & 0xFFFF
        return value

    @staticmethod
    def _word_from_bytes(operands: list[int] | tuple[int, ...]) -> int:
        low = operands[0] if operands else 0
        high = operands[1] if len(operands) > 1 else 0
        return low | (high << 8)

    def _service_pending_interrupt(self) -> ExecutionResult | None:
        source = self._next_interrupt_source()
        if source is None:
            return None

        start_pc = self.registers.pc
        self.halted = False

        if source == "TRAP":
            previous_enabled = 1 if self.interrupts.enabled else 0
            self._disable_interrupts_for_service()
            self.interrupts.trap_pending = 0
            self.interrupts.trap_rearm_required = True
            self.interrupts.saved_ie_before_trap = previous_enabled
            self.interrupts.report_saved_ie_on_next_rim = True
            self._push(self.registers.pc)
            self.registers.pc = 0x0024
            cycles = 12
            opcode = 0x00
        elif source == "RST7.5":
            self._disable_interrupts_for_service()
            self.interrupts.pending_7_5 = 0
            self._push(self.registers.pc)
            self.registers.pc = 0x003C
            cycles = 12
            opcode = 0x00
        elif source == "RST6.5":
            self._disable_interrupts_for_service()
            self._push(self.registers.pc)
            self.registers.pc = 0x0034
            cycles = 12
            opcode = 0x00
        elif source == "RST5.5":
            self._disable_interrupts_for_service()
            self._push(self.registers.pc)
            self.registers.pc = 0x002C
            cycles = 12
            opcode = 0x00
        else:
            instruction = self.interrupts.intr_instruction
            self._disable_interrupts_for_service()
            opcode, cycles = self._execute_intr_instruction(instruction)

        self.cycles += cycles
        return ExecutionResult(start_pc, opcode, 0, cycles, self.halted, interrupt_source=source)

    def _next_interrupt_source(self) -> InterruptSource | None:
        if self.interrupts.trap_pending:
            return "TRAP"
        if not self.interrupts.enabled:
            return None
        if self.interrupts.pending_7_5 and not self.interrupts.mask_7_5:
            return "RST7.5"
        if self.interrupts.line_6_5 and not self.interrupts.mask_6_5:
            return "RST6.5"
        if self.interrupts.line_5_5 and not self.interrupts.mask_5_5:
            return "RST5.5"
        if self.interrupts.line_intr:
            return "INTR"
        return None

    def _disable_interrupts_for_service(self) -> None:
        self.interrupts.enabled = False
        self.interrupts.enable_after_next = 0

    def _execute_intr_instruction(self, instruction: InterruptInstruction) -> tuple[int, int]:
        opcode = instruction.opcode & 0xFF
        if (opcode & 0xC7) == 0xC7:
            self._push(self.registers.pc)
            self.registers.pc = ((opcode >> 3) & 0x07) * 8
            return opcode, 12
        if opcode == 0xCD and len(instruction.operands) >= 2:
            self._push(self.registers.pc)
            self.registers.pc = instruction.operands[0] | (instruction.operands[1] << 8)
            return opcode, 18
        raise ValueError("INTR currently supports RST n and CALL acknowledge instructions")

    def _rim_interrupt_enable_bit(self) -> int:
        if self.interrupts.report_saved_ie_on_next_rim:
            self.interrupts.report_saved_ie_on_next_rim = False
            return self.interrupts.saved_ie_before_trap or 0
        return 1 if self.interrupts.enabled else 0

    def _complete_instruction(self, opcode: int) -> None:
        if opcode == 0xFB:
            return
        if self.interrupts.enable_after_next > 0:
            self.interrupts.enable_after_next -= 1
            if self.interrupts.enable_after_next == 0:
                self.interrupts.enabled = True
