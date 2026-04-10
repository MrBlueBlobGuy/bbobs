"""Two-pass Intel 8085 assembler."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

from .exceptions import AssemblyError

REGISTER_CODES = {"B": 0, "C": 1, "D": 2, "E": 3, "H": 4, "L": 5, "M": 6, "A": 7}
PAIR_CODES = {"B": 0, "BC": 0, "D": 1, "DE": 1, "H": 2, "HL": 2, "SP": 3}
STACK_CODES = {"B": 0, "BC": 0, "D": 1, "DE": 1, "H": 2, "HL": 2, "PSW": 3}
CONDITION_CODES = {"NZ": 0, "Z": 1, "NC": 2, "C": 3, "PO": 4, "PE": 5, "P": 6, "M": 7}
DIRECTIVES = {"ORG", ".ORG", "DB", ".DB", "DW", ".DW", "DS", ".DS", "EQU", ".EQU", "END", ".END"}

NO_OPERAND_OPCODES = {
    "NOP": 0x00,
    "RIM": 0x20,
    "SIM": 0x30,
    "RLC": 0x07,
    "RRC": 0x0F,
    "RAL": 0x17,
    "RAR": 0x1F,
    "DAA": 0x27,
    "CMA": 0x2F,
    "STC": 0x37,
    "CMC": 0x3F,
    "HLT": 0x76,
    "RET": 0xC9,
    "RNZ": 0xC0,
    "RZ": 0xC8,
    "RNC": 0xD0,
    "RC": 0xD8,
    "RPO": 0xE0,
    "RPE": 0xE8,
    "RP": 0xF0,
    "RM": 0xF8,
    "XTHL": 0xE3,
    "PCHL": 0xE9,
    "XCHG": 0xEB,
    "DI": 0xF3,
    "SPHL": 0xF9,
    "EI": 0xFB,
}

IMMEDIATE_ALU = {
    "ADI": 0xC6,
    "ACI": 0xCE,
    "SUI": 0xD6,
    "SBI": 0xDE,
    "ANI": 0xE6,
    "XRI": 0xEE,
    "ORI": 0xF6,
    "CPI": 0xFE,
    "IN": 0xDB,
    "OUT": 0xD3,
}

DIRECT_16 = {
    "SHLD": 0x22,
    "LHLD": 0x2A,
    "STA": 0x32,
    "LDA": 0x3A,
    "JMP": 0xC3,
    "CALL": 0xCD,
}

LABEL_RE = re.compile(r"^(?P<label>[A-Za-z_.$?][\w.$?]*):?\s*(?P<body>.*)$")
NUMBER_HEX_RE = re.compile(r"\b([0-9A-F]+)H\b", re.IGNORECASE)
NUMBER_BIN_RE = re.compile(r"\b([01]+)B\b", re.IGNORECASE)
NUMBER_OCT_RE = re.compile(r"\b([0-7]+)[OQ]\b", re.IGNORECASE)
NUMBER_DEC_RE = re.compile(r"\b([0-9]+)D\b", re.IGNORECASE)
IDENTIFIER_RE = re.compile(r"\b[A-Za-z_.$?][\w.$?]*\b")


@dataclass(frozen=True, slots=True)
class ParsedLine:
    """A source line parsed into its structural pieces."""

    line_number: int
    original: str
    label: str | None
    opcode: str | None
    operands: tuple[str, ...]
    address: int


@dataclass(frozen=True, slots=True)
class ListingLine:
    """A rendered listing entry."""

    address: int
    bytes_: bytes
    source: str


@dataclass(frozen=True, slots=True)
class ProgramSegment:
    """A contiguous block of assembled bytes."""

    start: int
    data: bytes


@dataclass(frozen=True, slots=True)
class ProgramImage:
    """The fully assembled program."""

    segments: tuple[ProgramSegment, ...]
    symbols: dict[str, int]
    listing: tuple[ListingLine, ...]


class Assembler:
    """A small but practical two-pass 8085 assembler."""

    def assemble(self, source: str, origin: int = 0x0000) -> ProgramImage:
        """Assemble source code into loadable program segments."""

        symbols: dict[str, int] = {}
        lines = self._first_pass(source, origin, symbols)
        return self._second_pass(lines, symbols, origin)

    def _first_pass(self, source: str, origin: int, symbols: dict[str, int]) -> list[ParsedLine]:
        lines: list[ParsedLine] = []
        location = origin & 0xFFFF

        for line_number, raw_line in enumerate(source.splitlines(), start=1):
            original = raw_line.rstrip()
            code = original.split(";", 1)[0].strip()
            if not code:
                continue

            label, opcode, operands = self._parse_statement(code, line_number)
            upper_opcode = opcode.upper() if opcode else None

            if upper_opcode in {"EQU", ".EQU"}:
                if label is None:
                    raise AssemblyError(line_number, "EQU requires a label")
                symbols[label] = self._evaluate_expression(
                    operands[0], symbols=symbols, current_address=location, line_number=line_number
                )
                continue

            if label is not None:
                if label in symbols:
                    raise AssemblyError(line_number, f"duplicate label {label}")
                symbols[label] = location

            parsed = ParsedLine(
                line_number=line_number,
                original=original,
                label=label,
                opcode=upper_opcode,
                operands=operands,
                address=location,
            )
            lines.append(parsed)

            if upper_opcode in {"ORG", ".ORG"}:
                location = self._evaluate_expression(
                    operands[0], symbols=symbols, current_address=location, line_number=line_number
                )
                continue
            if upper_opcode in {"END", ".END"}:
                break

            location = (location + self._line_size(parsed, symbols)) & 0xFFFF

        return lines

    def _second_pass(
        self, lines: list[ParsedLine], symbols: dict[str, int], origin: int
    ) -> ProgramImage:
        listing: list[ListingLine] = []
        segments: list[ProgramSegment] = []
        current_bytes = bytearray()
        current_start: int | None = None
        location = origin & 0xFFFF

        for line in lines:
            opcode = line.opcode
            if opcode is None:
                continue

            if opcode in {"ORG", ".ORG"}:
                if current_start is not None and current_bytes:
                    segments.append(ProgramSegment(current_start, bytes(current_bytes)))
                    current_bytes.clear()
                current_start = None
                location = self._evaluate_expression(
                    line.operands[0], symbols=symbols, current_address=location, line_number=line.line_number
                )
                continue

            if opcode in {"END", ".END"}:
                break

            if opcode in {"EQU", ".EQU"}:
                continue

            encoded = self._encode_line(line, symbols)
            if encoded:
                if current_start is None:
                    current_start = line.address
                elif line.address != (current_start + len(current_bytes)) & 0xFFFF:
                    segments.append(ProgramSegment(current_start, bytes(current_bytes)))
                    current_bytes = bytearray()
                    current_start = line.address
                current_bytes.extend(encoded)
            listing.append(ListingLine(address=line.address, bytes_=bytes(encoded), source=line.original))
            location = (line.address + len(encoded)) & 0xFFFF

        if current_start is not None and current_bytes:
            segments.append(ProgramSegment(current_start, bytes(current_bytes)))

        return ProgramImage(tuple(segments), dict(symbols), tuple(listing))

    def _parse_statement(
        self, code: str, line_number: int
    ) -> tuple[str | None, str | None, tuple[str, ...]]:
        parts = code.split(None, 1)
        if not parts:
            return None, None, ()

        label: str | None = None
        opcode_text = code

        if ":" in code:
            label_part, opcode_text = code.split(":", 1)
            label = label_part.strip().upper()
            opcode_text = opcode_text.strip()
        else:
            head = parts[0].upper()
            if len(parts) > 1:
                next_token = parts[1].split(None, 1)[0].upper()
                if next_token in {"EQU", ".EQU"}:
                    label = head
                    opcode_text = parts[1]

        if not opcode_text:
            return label, None, ()

        pieces = opcode_text.split(None, 1)
        opcode = pieces[0].upper()
        operand_text = pieces[1] if len(pieces) > 1 else ""
        operands = tuple(self._split_operands(operand_text))

        if opcode not in DIRECTIVES and not re.fullmatch(r"[A-Z][A-Z0-9]*", opcode):
            raise AssemblyError(line_number, f"invalid opcode {opcode}")

        return label, opcode, operands

    def _split_operands(self, text: str) -> list[str]:
        if not text:
            return []
        operands: list[str] = []
        current: list[str] = []
        in_quote = False
        quote_char = ""
        for char in text:
            if char in {"'", '"'}:
                if in_quote and char == quote_char:
                    in_quote = False
                elif not in_quote:
                    in_quote = True
                    quote_char = char
                current.append(char)
            elif char == "," and not in_quote:
                operand = "".join(current).strip()
                if operand:
                    operands.append(operand)
                current = []
            else:
                current.append(char)
        tail = "".join(current).strip()
        if tail:
            operands.append(tail)
        return operands

    def _line_size(self, line: ParsedLine, symbols: dict[str, int]) -> int:
        opcode = line.opcode
        if opcode is None:
            return 0
        if opcode in {"ORG", ".ORG", "END", ".END", "EQU", ".EQU"}:
            return 0
        if opcode in {"DB", ".DB"}:
            return sum(self._db_operand_size(operand) for operand in line.operands)
        if opcode in {"DW", ".DW"}:
            return len(line.operands) * 2
        if opcode in {"DS", ".DS"}:
            return self._evaluate_expression(
                line.operands[0], symbols=symbols, current_address=line.address, line_number=line.line_number
            )
        return self._instruction_size(opcode, line.operands, line.line_number)

    def _instruction_size(self, opcode: str, operands: tuple[str, ...], line_number: int) -> int:
        if opcode in NO_OPERAND_OPCODES:
            return 1
        if opcode in IMMEDIATE_ALU:
            return 2
        if opcode in DIRECT_16:
            return 3
        if opcode == "RST":
            return 1
        if opcode == "MOV":
            self._require_operand_count(opcode, operands, 2, line_number)
            return 1
        if opcode == "MVI":
            self._require_operand_count(opcode, operands, 2, line_number)
            return 2
        if opcode in {"INR", "DCR"}:
            self._require_operand_count(opcode, operands, 1, line_number)
            return 1
        if opcode in {"LXI"}:
            self._require_operand_count(opcode, operands, 2, line_number)
            return 3
        if opcode in {"INX", "DCX", "DAD", "LDAX", "STAX", "PUSH", "POP"}:
            return 1
        if opcode in {
            "JNZ",
            "JZ",
            "JNC",
            "JC",
            "JPO",
            "JPE",
            "JP",
            "JM",
            "CNZ",
            "CZ",
            "CNC",
            "CC",
            "CPO",
            "CPE",
            "CP",
            "CM",
        }:
            return 3
        if opcode in {"ADD", "ADC", "SUB", "SBB", "ANA", "XRA", "ORA", "CMP"}:
            return 1
        raise AssemblyError(line_number, f"unsupported mnemonic {opcode}")

    def _encode_line(self, line: ParsedLine, symbols: dict[str, int]) -> bytes:
        opcode = line.opcode
        if opcode is None:
            return b""
        if opcode in {"DB", ".DB"}:
            data = bytearray()
            for operand in line.operands:
                data.extend(self._encode_db_operand(operand, symbols, line.address, line.line_number))
            return bytes(data)
        if opcode in {"DW", ".DW"}:
            data = bytearray()
            for operand in line.operands:
                value = self._evaluate_expression(
                    operand, symbols=symbols, current_address=line.address, line_number=line.line_number
                )
                data.append(value & 0xFF)
                data.append((value >> 8) & 0xFF)
            return bytes(data)
        if opcode in {"DS", ".DS"}:
            size = self._evaluate_expression(
                line.operands[0], symbols=symbols, current_address=line.address, line_number=line.line_number
            )
            return bytes([0x00] * size)
        return self._encode_instruction(line, symbols)

    def _encode_instruction(self, line: ParsedLine, symbols: dict[str, int]) -> bytes:
        opcode = line.opcode or ""
        operands = line.operands

        if opcode in NO_OPERAND_OPCODES:
            self._require_operand_count(opcode, operands, 0, line.line_number)
            return bytes([NO_OPERAND_OPCODES[opcode]])

        if opcode in IMMEDIATE_ALU:
            self._require_operand_count(opcode, operands, 1, line.line_number)
            value = self._eval_byte(operands[0], symbols, line)
            return bytes([IMMEDIATE_ALU[opcode], value])

        if opcode in DIRECT_16:
            self._require_operand_count(opcode, operands, 1, line.line_number)
            value = self._eval_word(operands[0], symbols, line)
            return bytes([DIRECT_16[opcode], value & 0xFF, (value >> 8) & 0xFF])

        if opcode == "RST":
            self._require_operand_count(opcode, operands, 1, line.line_number)
            value = self._evaluate_expression(
                operands[0], symbols=symbols, current_address=line.address, line_number=line.line_number
            )
            if not 0 <= value <= 7:
                raise AssemblyError(line.line_number, "RST expects a vector from 0 to 7")
            return bytes([0xC7 | (value << 3)])

        if opcode == "MOV":
            self._require_operand_count(opcode, operands, 2, line.line_number)
            dst = self._register_code(operands[0], line.line_number)
            src = self._register_code(operands[1], line.line_number)
            return bytes([0x40 | (dst << 3) | src])

        if opcode == "MVI":
            self._require_operand_count(opcode, operands, 2, line.line_number)
            reg = self._register_code(operands[0], line.line_number)
            value = self._eval_byte(operands[1], symbols, line)
            return bytes([0x06 | (reg << 3), value])

        if opcode in {"INR", "DCR"}:
            self._require_operand_count(opcode, operands, 1, line.line_number)
            reg = self._register_code(operands[0], line.line_number)
            base = 0x04 if opcode == "INR" else 0x05
            return bytes([base | (reg << 3)])

        if opcode == "LXI":
            self._require_operand_count(opcode, operands, 2, line.line_number)
            rp = self._pair_code(operands[0], line.line_number)
            value = self._eval_word(operands[1], symbols, line)
            return bytes([0x01 | (rp << 4), value & 0xFF, (value >> 8) & 0xFF])

        if opcode in {"INX", "DCX", "DAD"}:
            self._require_operand_count(opcode, operands, 1, line.line_number)
            rp = self._pair_code(operands[0], line.line_number)
            base = {"INX": 0x03, "DCX": 0x0B, "DAD": 0x09}[opcode]
            return bytes([base | (rp << 4)])

        if opcode in {"LDAX", "STAX"}:
            self._require_operand_count(opcode, operands, 1, line.line_number)
            pair_name = operands[0].strip().upper()
            if pair_name not in {"B", "BC", "D", "DE"}:
                raise AssemblyError(line.line_number, f"{opcode} expects B/BC or D/DE")
            rp = 0 if pair_name in {"B", "BC"} else 1
            base = 0x0A if opcode == "LDAX" else 0x02
            return bytes([base | (rp << 4)])

        if opcode in {"PUSH", "POP"}:
            self._require_operand_count(opcode, operands, 1, line.line_number)
            rp = self._stack_code(operands[0], line.line_number)
            base = 0xC5 if opcode == "PUSH" else 0xC1
            return bytes([base | (rp << 4)])

        if opcode in {"ADD", "ADC", "SUB", "SBB", "ANA", "XRA", "ORA", "CMP"}:
            self._require_operand_count(opcode, operands, 1, line.line_number)
            reg = self._register_code(operands[0], line.line_number)
            group = {"ADD": 0, "ADC": 1, "SUB": 2, "SBB": 3, "ANA": 4, "XRA": 5, "ORA": 6, "CMP": 7}[opcode]
            return bytes([0x80 | (group << 3) | reg])

        if opcode.startswith("J") and len(opcode) > 1:
            cond = opcode[1:]
            if cond in CONDITION_CODES:
                self._require_operand_count(opcode, operands, 1, line.line_number)
                value = self._eval_word(operands[0], symbols, line)
                return bytes([0xC2 | (CONDITION_CODES[cond] << 3), value & 0xFF, (value >> 8) & 0xFF])

        if opcode.startswith("C") and len(opcode) > 1:
            cond = opcode[1:]
            if cond in CONDITION_CODES:
                self._require_operand_count(opcode, operands, 1, line.line_number)
                value = self._eval_word(operands[0], symbols, line)
                return bytes([0xC4 | (CONDITION_CODES[cond] << 3), value & 0xFF, (value >> 8) & 0xFF])

        raise AssemblyError(line.line_number, f"unsupported mnemonic {opcode}")

    def _encode_db_operand(
        self, operand: str, symbols: dict[str, int], current_address: int, line_number: int
    ) -> bytes:
        operand = operand.strip()
        if (operand.startswith('"') and operand.endswith('"')) or (
            operand.startswith("'") and operand.endswith("'") and len(operand) > 2
        ):
            text = ast.literal_eval(operand)
            if not isinstance(text, str):
                raise AssemblyError(line_number, "DB string operand must be text")
            return text.encode("latin-1", errors="replace")
        value = self._evaluate_expression(
            operand, symbols=symbols, current_address=current_address, line_number=line_number
        )
        return bytes([value & 0xFF])

    def _db_operand_size(self, operand: str) -> int:
        operand = operand.strip()
        if (operand.startswith('"') and operand.endswith('"')) or (
            operand.startswith("'") and operand.endswith("'") and len(operand) > 2
        ):
            text = ast.literal_eval(operand)
            return len(text.encode("latin-1", errors="replace"))
        return 1

    def _evaluate_expression(
        self, expression: str, symbols: dict[str, int], current_address: int, line_number: int
    ) -> int:
        prepared = expression.strip().upper()
        if not prepared:
            raise AssemblyError(line_number, "empty expression")
        prepared = prepared.replace("$", str(current_address))
        prepared = NUMBER_HEX_RE.sub(lambda match: f"0x{match.group(1)}", prepared)
        prepared = NUMBER_BIN_RE.sub(lambda match: f"0b{match.group(1)}", prepared)
        prepared = NUMBER_OCT_RE.sub(lambda match: f"0o{match.group(1)}", prepared)
        prepared = NUMBER_DEC_RE.sub(lambda match: match.group(1), prepared)

        def replace_identifier(match: re.Match[str]) -> str:
            name = match.group(0)
            if name in symbols:
                return str(symbols[name])
            if name in {"X", "O", "B"}:
                return name
            raise AssemblyError(line_number, f"unknown symbol {name}")

        prepared = IDENTIFIER_RE.sub(replace_identifier, prepared)
        try:
            node = ast.parse(prepared, mode="eval")
        except SyntaxError as exc:
            raise AssemblyError(line_number, f"invalid expression {expression}") from exc
        return self._eval_ast(node.body, line_number) & 0xFFFF

    def _eval_ast(self, node: ast.AST, line_number: int) -> int:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return int(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Invert)):
            value = self._eval_ast(node.operand, line_number)
            if isinstance(node.op, ast.UAdd):
                return value
            if isinstance(node.op, ast.USub):
                return -value
            return ~value
        if isinstance(node, ast.BinOp):
            left = self._eval_ast(node.left, line_number)
            right = self._eval_ast(node.right, line_number)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.FloorDiv):
                return left // right
            if isinstance(node.op, ast.Div):
                return left // right
            if isinstance(node.op, ast.Mod):
                return left % right
            if isinstance(node.op, ast.BitOr):
                return left | right
            if isinstance(node.op, ast.BitAnd):
                return left & right
            if isinstance(node.op, ast.BitXor):
                return left ^ right
            if isinstance(node.op, ast.LShift):
                return left << right
            if isinstance(node.op, ast.RShift):
                return left >> right
        raise AssemblyError(line_number, "unsupported expression")

    def _register_code(self, operand: str, line_number: int) -> int:
        name = operand.strip().upper()
        if name not in REGISTER_CODES:
            raise AssemblyError(line_number, f"invalid register {operand}")
        return REGISTER_CODES[name]

    def _pair_code(self, operand: str, line_number: int) -> int:
        name = operand.strip().upper()
        if name not in PAIR_CODES:
            raise AssemblyError(line_number, f"invalid register pair {operand}")
        return PAIR_CODES[name]

    def _stack_code(self, operand: str, line_number: int) -> int:
        name = operand.strip().upper()
        if name not in STACK_CODES:
            raise AssemblyError(line_number, f"invalid stack pair {operand}")
        return STACK_CODES[name]

    def _eval_byte(self, operand: str, symbols: dict[str, int], line: ParsedLine) -> int:
        return self._evaluate_expression(
            operand, symbols=symbols, current_address=line.address, line_number=line.line_number
        ) & 0xFF

    def _eval_word(self, operand: str, symbols: dict[str, int], line: ParsedLine) -> int:
        return self._evaluate_expression(
            operand, symbols=symbols, current_address=line.address, line_number=line.line_number
        ) & 0xFFFF

    def _require_operand_count(
        self, opcode: str, operands: tuple[str, ...], expected: int, line_number: int
    ) -> None:
        if len(operands) != expected:
            raise AssemblyError(
                line_number, f"{opcode} expects {expected} operand(s), found {len(operands)}"
            )

