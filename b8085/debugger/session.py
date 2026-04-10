"""High-level composition root for the emulator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from b8085.assembler import Assembler, ProgramImage
from b8085.cpu import CPU8085
from b8085.cpu.opcodes import decode_instruction, instruction_size
from b8085.io import PortSpace, SerialDevice
from b8085.memory import AddressSpace, MemorySegment, SegmentType

from .breakpoints import BreakpointManager
from .engine import ExecutionEngine


@dataclass(frozen=True, slots=True)
class CpuSnapshot:
    """Debugger-friendly CPU state."""

    a: int
    b: int
    c: int
    d: int
    e: int
    h: int
    l: int
    sp: int
    pc: int
    flags: dict[str, int]
    cycles: int
    halted: bool
    interrupts_enabled: bool


@dataclass(frozen=True, slots=True)
class MemoryLine:
    """A formatted row in the memory viewer."""

    address: int
    hex_bytes: str
    ascii_text: str


class EmulatorSession:
    """Owns the emulator subsystems and exposes a clean façade."""

    def __init__(
        self,
        memory: AddressSpace | None = None,
        ports: PortSpace | None = None,
        serial: SerialDevice | None = None,
    ) -> None:
        self.memory = memory if memory is not None else AddressSpace.with_flat_ram()
        self.ports = ports if ports is not None else PortSpace()
        self.serial = serial if serial is not None else SerialDevice()
        mapped_ports = sorted({self.serial.data_port, self.serial.status_port, self.serial.control_port})
        self.ports.map_device(self.serial, mapped_ports)
        self.cpu = CPU8085(memory=self.memory, ports=self.ports, serial=self.serial)
        self.serial.bind_rx_ready_callback(self.cpu.set_rst_6_5)
        self.breakpoints = BreakpointManager()
        self.engine = ExecutionEngine(self.cpu, self.breakpoints)
        self.assembler = Assembler()

    @classmethod
    def with_default_segments(cls) -> "EmulatorSession":
        """Create a machine with default RAM/ROM segmentation."""

        memory = AddressSpace()
        memory.add_segment(MemorySegment(0x0000, 0x1FFF, "Monitor ROM", SegmentType.ROM))
        memory.add_segment(MemorySegment(0x2000, 0xFFFF, "RAM", SegmentType.RAM))
        return cls(memory=memory)

    def assemble(self, source: str, origin: int = 0x0000) -> ProgramImage:
        """Assemble source without loading it."""

        return self.assembler.assemble(source, origin=origin)

    def load_image(self, image: ProgramImage, force: bool = False) -> None:
        """Load an assembled image into memory."""

        for segment in image.segments:
            self.memory.load(segment.start, segment.data, force=force)

    def assemble_and_load(self, source: str, origin: int = 0x0000, force: bool = False) -> ProgramImage:
        """Assemble source code and load it into memory."""

        image = self.assemble(source, origin=origin)
        self.load_image(image, force=force)
        return image

    def load_binary(self, path: str | Path, address: int, force: bool = False) -> None:
        """Load a binary file into memory."""

        data = Path(path).read_bytes()
        self.memory.load(address, data, force=force)

    def clear_segments(self, segment_type: SegmentType, fill: int = 0x00) -> None:
        """Fill every segment of a given type with a byte value."""

        fill &= 0xFF
        for segment in self.memory.segments:
            if segment.segment_type != segment_type:
                continue
            for address in range(segment.start, segment.end + 1):
                self.memory.write_byte(address, fill, force=True)

    def flash_rom_image(self, image: ProgramImage, erase_value: int = 0x00) -> None:
        """Erase ROM and program a new image into it."""

        self.clear_segments(SegmentType.ROM, fill=erase_value)
        self.load_image(image, force=True)

    def reset(self, pc: int = 0x0000, sp: int = 0xFFFF) -> None:
        """Reset the CPU state."""

        self.serial.reset_device(clear_buffers=False)
        self.engine.reset(pc=pc, sp=sp)

    def snapshot(self) -> CpuSnapshot:
        """Return a live snapshot of CPU state."""

        registers = self.cpu.registers
        flags = self.cpu.flags
        return CpuSnapshot(
            a=registers.a,
            b=registers.b,
            c=registers.c,
            d=registers.d,
            e=registers.e,
            h=registers.h,
            l=registers.l,
            sp=registers.sp,
            pc=registers.pc,
            flags={"Z": flags.z, "S": flags.s, "P": flags.p, "CY": flags.cy, "AC": flags.ac},
            cycles=self.cpu.cycles,
            halted=self.cpu.halted,
            interrupts_enabled=self.cpu.interrupts.enabled,
        )

    def memory_lines(self, start: int, rows: int = 16, width: int = 16) -> list[MemoryLine]:
        """Return formatted rows for the memory viewer."""

        lines: list[MemoryLine] = []
        for row in range(rows):
            address = (start + row * width) & 0xFFFF
            data = self.memory.snapshot(address, width)
            ascii_text = "".join(chr(value) if 32 <= value <= 126 else "." for value in data)
            hex_bytes = " ".join(f"{value:02X}" for value in data)
            lines.append(MemoryLine(address=address, hex_bytes=hex_bytes, ascii_text=ascii_text))
        return lines

    def disassemble(self, start: int, lines: int = 24) -> list[str]:
        """Return a disassembly window."""

        output: list[str] = []
        address = start & 0xFFFF
        for _ in range(lines):
            opcode = self.memory.read_byte(address)
            size = instruction_size(opcode)
            operands = tuple(self.memory.read_byte((address + index) & 0xFFFF) for index in range(1, size))
            decoded = decode_instruction(address, opcode, operands)
            marker = "*" if self.breakpoints.contains(address) else " "
            output.append(f"{marker} {address:04X}: {decoded.text}")
            address = (address + size) & 0xFFFF
        return output

    def set_memory_byte(self, address: int, value: int, force: bool = False) -> None:
        """Write a byte into memory."""

        self.memory.write_byte(address, value, force=force)

    def request_trap(self, active: bool = True) -> None:
        """Drive the TRAP interrupt line."""

        self.cpu.request_trap(active=active)

    def pulse_rst_7_5(self) -> None:
        """Pulse the edge-triggered RST 7.5 interrupt."""

        self.cpu.request_rst_7_5()

    def set_rst_6_5(self, active: bool = True) -> None:
        """Drive the RST 6.5 interrupt line."""

        self.cpu.set_rst_6_5(active=active)

    def set_rst_5_5(self, active: bool = True) -> None:
        """Drive the RST 5.5 interrupt line."""

        self.cpu.set_rst_5_5(active=active)

    def request_intr(self, opcode: int = 0xC7, operands: tuple[int, ...] = (), active: bool = True) -> None:
        """Drive INTR with the instruction supplied during acknowledge."""

        self.cpu.request_intr(opcode=opcode, operands=operands, active=active)

    def clear_intr(self) -> None:
        """Lower the INTR line."""

        self.cpu.clear_intr()
