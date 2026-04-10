"""Shared instruction metadata and disassembly helpers."""

from __future__ import annotations

from dataclasses import dataclass

REGISTERS = ("B", "C", "D", "E", "H", "L", "M", "A")
REGISTER_PAIRS = ("B", "D", "H", "SP")
STACK_PAIRS = ("B", "D", "H", "PSW")
CONDITIONS = ("NZ", "Z", "NC", "C", "PO", "PE", "P", "M")
ALU_GROUP = ("ADD", "ADC", "SUB", "SBB", "ANA", "XRA", "ORA", "CMP")
IMMEDIATE_ALU = {
    0xC6: "ADI",
    0xCE: "ACI",
    0xD6: "SUI",
    0xDE: "SBI",
    0xE6: "ANI",
    0xEE: "XRI",
    0xF6: "ORI",
    0xFE: "CPI",
}

NO_OPERAND_SPECS: dict[int, tuple[str, int, int | tuple[int, int]]] = {
    0x00: ("NOP", 1, 4),
    0x08: ("NOP", 1, 4),
    0x10: ("NOP", 1, 4),
    0x18: ("NOP", 1, 4),
    0x20: ("NOP", 1, 4),
    0x28: ("NOP", 1, 4),
    0x30: ("NOP", 1, 4),
    0x38: ("NOP", 1, 4),
    0x07: ("RLC", 1, 4),
    0x0F: ("RRC", 1, 4),
    0x17: ("RAL", 1, 4),
    0x1F: ("RAR", 1, 4),
    0x27: ("DAA", 1, 4),
    0x2F: ("CMA", 1, 4),
    0x37: ("STC", 1, 4),
    0x3F: ("CMC", 1, 4),
    0x76: ("HLT", 1, 7),
    0xC9: ("RET", 1, 10),
    0xD9: ("RET", 1, 10),
    0xE3: ("XTHL", 1, 16),
    0xE9: ("PCHL", 1, 6),
    0xEB: ("XCHG", 1, 4),
    0xF3: ("DI", 1, 4),
    0xF9: ("SPHL", 1, 6),
    0xFB: ("EI", 1, 4),
    0x20: ("NOP", 1, 4),
    0xE7: ("RST 4", 1, 12),
    0xF7: ("RST 6", 1, 12),
    0xEF: ("RST 5", 1, 12),
    0xDF: ("RST 3", 1, 12),
    0xCF: ("RST 1", 1, 12),
    0xC7: ("RST 0", 1, 12),
    0xD7: ("RST 2", 1, 12),
    0xFF: ("RST 7", 1, 12),
    0xF5: ("PUSH PSW", 1, 12),
    0xF1: ("POP PSW", 1, 10),
    0xE6: ("ANI", 2, 7),
    0xE7: ("RST 4", 1, 12),
    0xF6: ("ORI", 2, 7),
    0xF7: ("RST 6", 1, 12),
    0xE8: ("RPE", 1, (6, 12)),
    0xF8: ("RM", 1, (6, 12)),
    0xE0: ("RPO", 1, (6, 12)),
    0xF0: ("RP", 1, (6, 12)),
    0xC0: ("RNZ", 1, (6, 12)),
    0xC8: ("RZ", 1, (6, 12)),
    0xD0: ("RNC", 1, (6, 12)),
    0xD8: ("RC", 1, (6, 12)),
    0xE3: ("XTHL", 1, 16),
    0xF3: ("DI", 1, 4),
    0xDB: ("IN", 2, 10),
    0xD3: ("OUT", 2, 10),
    0xE3: ("XTHL", 1, 16),
    0xEB: ("XCHG", 1, 4),
    0xE9: ("PCHL", 1, 6),
    0xF9: ("SPHL", 1, 6),
    0xE3: ("XTHL", 1, 16),
    0xF3: ("DI", 1, 4),
    0xFB: ("EI", 1, 4),
    0x20: ("RIM", 1, 4),
    0x30: ("SIM", 1, 4),
}

DIRECT_SPECS: dict[int, tuple[str, int, int]] = {
    0x01: ("LXI B", 3, 10),
    0x11: ("LXI D", 3, 10),
    0x21: ("LXI H", 3, 10),
    0x31: ("LXI SP", 3, 10),
    0x02: ("STAX B", 1, 7),
    0x12: ("STAX D", 1, 7),
    0x0A: ("LDAX B", 1, 7),
    0x1A: ("LDAX D", 1, 7),
    0x22: ("SHLD", 3, 16),
    0x2A: ("LHLD", 3, 16),
    0x32: ("STA", 3, 13),
    0x3A: ("LDA", 3, 13),
    0x03: ("INX B", 1, 6),
    0x13: ("INX D", 1, 6),
    0x23: ("INX H", 1, 6),
    0x33: ("INX SP", 1, 6),
    0x0B: ("DCX B", 1, 6),
    0x1B: ("DCX D", 1, 6),
    0x2B: ("DCX H", 1, 6),
    0x3B: ("DCX SP", 1, 6),
    0x09: ("DAD B", 1, 10),
    0x19: ("DAD D", 1, 10),
    0x29: ("DAD H", 1, 10),
    0x39: ("DAD SP", 1, 10),
    0xC3: ("JMP", 3, 10),
    0xCD: ("CALL", 3, 18),
    0xC1: ("POP B", 1, 10),
    0xD1: ("POP D", 1, 10),
    0xE1: ("POP H", 1, 10),
    0xC5: ("PUSH B", 1, 12),
    0xD5: ("PUSH D", 1, 12),
    0xE5: ("PUSH H", 1, 12),
}

JUMP_CONDITIONAL_BASE = {0xC2, 0xCA, 0xD2, 0xDA, 0xE2, 0xEA, 0xF2, 0xFA}
CALL_CONDITIONAL_BASE = {0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC}


@dataclass(frozen=True, slots=True)
class DecodedInstruction:
    """A decoded instruction ready for display."""

    address: int
    opcode: int
    mnemonic: str
    operands: tuple[int, ...]
    size: int
    cycles: int | tuple[int, int]

    @property
    def text(self) -> str:
        """Return a human-readable assembly string."""

        if not self.operands:
            return self.mnemonic
        if self.size == 2:
            return f"{self.mnemonic} {self.operands[0]:02X}H"
        operand = self.operands[0] | (self.operands[1] << 8)
        return f"{self.mnemonic} {operand:04X}H"


def instruction_size(opcode: int) -> int:
    """Return the size of an opcode in bytes."""

    opcode &= 0xFF
    if 0x40 <= opcode <= 0x7F:
        return 1
    if 0x80 <= opcode <= 0xBF:
        return 1
    if opcode in NO_OPERAND_SPECS:
        return NO_OPERAND_SPECS[opcode][1]
    if opcode in DIRECT_SPECS:
        return DIRECT_SPECS[opcode][1]
    if opcode in IMMEDIATE_ALU:
        return 2
    if opcode in JUMP_CONDITIONAL_BASE or opcode in CALL_CONDITIONAL_BASE:
        return 3
    if opcode in {0xC6, 0xCE, 0xD6, 0xDE, 0xE6, 0xEE, 0xF6, 0xFE, 0xD3, 0xDB}:
        return 2
    if (opcode & 0xC7) in {0x04, 0x05}:
        return 1
    if (opcode & 0xC7) == 0x06:
        return 2
    if (opcode & 0xCF) in {0x01}:
        return 3
    if (opcode & 0xCF) in {0x03, 0x09, 0x0B}:
        return 1
    if (opcode & 0xCF) in {0xC1, 0xC5}:
        return 1
    if (opcode & 0xC7) == 0xC7:
        return 1
    return 1


def instruction_cycles(opcode: int, branch_taken: bool | None = None) -> int:
    """Return the cycle count for an opcode."""

    opcode &= 0xFF
    if 0x40 <= opcode <= 0x7F:
        if opcode == 0x76:
            return 7
        return 7 if ((opcode >> 3) & 0x07) == 6 or (opcode & 0x07) == 6 else 5
    if 0x80 <= opcode <= 0xBF:
        return 7 if (opcode & 0x07) == 6 else 4
    if opcode in NO_OPERAND_SPECS:
        cycles = NO_OPERAND_SPECS[opcode][2]
        if isinstance(cycles, tuple):
            return cycles[1] if branch_taken else cycles[0]
        return cycles
    if opcode in DIRECT_SPECS:
        return DIRECT_SPECS[opcode][2]
    if opcode in IMMEDIATE_ALU:
        return 7
    if opcode in JUMP_CONDITIONAL_BASE:
        return 10
    if opcode in CALL_CONDITIONAL_BASE:
        return 18 if branch_taken else 9
    if (opcode & 0xC7) == 0x04:
        return 10 if ((opcode >> 3) & 0x07) == 6 else 5
    if (opcode & 0xC7) == 0x05:
        return 10 if ((opcode >> 3) & 0x07) == 6 else 5
    if (opcode & 0xC7) == 0x06:
        return 10 if ((opcode >> 3) & 0x07) == 6 else 7
    if (opcode & 0xCF) == 0x01:
        return 10
    if (opcode & 0xCF) in {0x03, 0x0B}:
        return 6
    if (opcode & 0xCF) == 0x09:
        return 10
    if (opcode & 0xCF) == 0xC1:
        return 10
    if (opcode & 0xCF) == 0xC5:
        return 12
    if (opcode & 0xC7) == 0xC7:
        return 12
    return 4


def decode_instruction(address: int, opcode: int, operands: tuple[int, ...] = ()) -> DecodedInstruction:
    """Decode an opcode into a display-friendly structure."""

    opcode &= 0xFF
    if 0x40 <= opcode <= 0x7F:
        if opcode == 0x76:
            return DecodedInstruction(address, opcode, "HLT", (), 1, 7)
        dst = REGISTERS[(opcode >> 3) & 0x07]
        src = REGISTERS[opcode & 0x07]
        return DecodedInstruction(address, opcode, f"MOV {dst}, {src}", (), 1, instruction_cycles(opcode))
    if 0x80 <= opcode <= 0xBF:
        mnemonic = ALU_GROUP[(opcode - 0x80) >> 3]
        src = REGISTERS[opcode & 0x07]
        return DecodedInstruction(address, opcode, f"{mnemonic} {src}", (), 1, instruction_cycles(opcode))
    if opcode in IMMEDIATE_ALU:
        return DecodedInstruction(address, opcode, IMMEDIATE_ALU[opcode], operands, 2, 7)
    if opcode in DIRECT_SPECS:
        mnemonic, size, cycles = DIRECT_SPECS[opcode]
        return DecodedInstruction(address, opcode, mnemonic, operands, size, cycles)
    if opcode in NO_OPERAND_SPECS:
        mnemonic, size, cycles = NO_OPERAND_SPECS[opcode]
        return DecodedInstruction(address, opcode, mnemonic, operands, size, cycles)
    if (opcode & 0xC7) == 0x04:
        reg = REGISTERS[(opcode >> 3) & 0x07]
        return DecodedInstruction(address, opcode, f"INR {reg}", (), 1, instruction_cycles(opcode))
    if (opcode & 0xC7) == 0x05:
        reg = REGISTERS[(opcode >> 3) & 0x07]
        return DecodedInstruction(address, opcode, f"DCR {reg}", (), 1, instruction_cycles(opcode))
    if (opcode & 0xC7) == 0x06:
        reg = REGISTERS[(opcode >> 3) & 0x07]
        return DecodedInstruction(address, opcode, f"MVI {reg}", operands, 2, instruction_cycles(opcode))
    if (opcode & 0xCF) == 0x01:
        rp = REGISTER_PAIRS[(opcode >> 4) & 0x03]
        return DecodedInstruction(address, opcode, f"LXI {rp}", operands, 3, 10)
    if (opcode & 0xCF) == 0x03:
        rp = REGISTER_PAIRS[(opcode >> 4) & 0x03]
        return DecodedInstruction(address, opcode, f"INX {rp}", (), 1, 6)
    if (opcode & 0xCF) == 0x0B:
        rp = REGISTER_PAIRS[(opcode >> 4) & 0x03]
        return DecodedInstruction(address, opcode, f"DCX {rp}", (), 1, 6)
    if (opcode & 0xCF) == 0x09:
        rp = REGISTER_PAIRS[(opcode >> 4) & 0x03]
        return DecodedInstruction(address, opcode, f"DAD {rp}", (), 1, 10)
    if (opcode & 0xCF) == 0xC1:
        rp = STACK_PAIRS[(opcode >> 4) & 0x03]
        return DecodedInstruction(address, opcode, f"POP {rp}", (), 1, 10)
    if (opcode & 0xCF) == 0xC5:
        rp = STACK_PAIRS[(opcode >> 4) & 0x03]
        return DecodedInstruction(address, opcode, f"PUSH {rp}", (), 1, 12)
    if opcode in JUMP_CONDITIONAL_BASE:
        cond = CONDITIONS[(opcode >> 3) & 0x07]
        return DecodedInstruction(address, opcode, f"J{cond}", operands, 3, 10)
    if opcode in CALL_CONDITIONAL_BASE:
        cond = CONDITIONS[(opcode >> 3) & 0x07]
        return DecodedInstruction(address, opcode, f"C{cond}", operands, 3, (9, 18))
    if opcode in {0xC0, 0xC8, 0xD0, 0xD8, 0xE0, 0xE8, 0xF0, 0xF8}:
        cond = CONDITIONS[(opcode >> 3) & 0x07]
        return DecodedInstruction(address, opcode, f"R{cond}", (), 1, (6, 12))
    if (opcode & 0xC7) == 0xC7:
        rst = (opcode >> 3) & 0x07
        return DecodedInstruction(address, opcode, f"RST {rst}", (), 1, 12)
    return DecodedInstruction(address, opcode, "NOP", (), 1, 4)

