"""Intel 8251-compatible serial terminal device."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from .base import PortDevice


@dataclass(slots=True)
class SerialDevice(PortDevice):
    """A small Intel 8251 USART model backed by a terminal-like host buffer.

    The device exposes the classic two-port 8251 layout:

    - `data_port`: transmit/receive data register
    - `status_port` / `control_port`: read status, write mode/command

    SID/SOD helper methods are also kept so the CPU's `RIM`/`SIM` support can
    interact with the same terminal abstraction.
    """

    data_port: int = 0x10
    status_port: int = 0x11
    control_port: int = 0x11
    _rx_buffer: deque[int] = field(default_factory=deque, init=False, repr=False)
    _tx_buffer: deque[int] = field(default_factory=deque, init=False, repr=False)
    sid_line: int = 0
    sod_line: int = 0
    mode_instruction: int = 0
    command_instruction: int = 0
    sync_chars: list[int] = field(default_factory=list, init=False, repr=False)
    _awaiting_mode: bool = field(default=True, init=False, repr=False)
    _pending_sync_chars: int = field(default=0, init=False, repr=False)
    parity_error: int = 0
    overrun_error: int = 0
    framing_error: int = 0
    syn_det_brk: int = 0
    dsr: int = 1
    _rx_ready_callback: Callable[[bool], None] | None = field(default=None, init=False, repr=False)
    _rx_ready_state: bool = field(default=False, init=False, repr=False)

    def read_port(self, port: int) -> int:
        port &= 0xFF
        if port == self.data_port:
            return self._read_data()
        if port == self.status_port:
            return self.status_byte()
        return 0

    def write_port(self, port: int, value: int) -> None:
        port &= 0xFF
        value &= 0xFF
        if port == self.data_port:
            self._write_data(value)
        elif port == self.control_port:
            self._write_control(value)

    def _read_data(self) -> int:
        if not self.rx_enabled or not self._rx_buffer:
            return 0
        value = self._rx_buffer.popleft()
        self.sid_line = value & 0x01
        self._update_rx_ready_line()
        return value

    def _write_data(self, value: int) -> None:
        if not self.tx_enabled:
            return
        self._tx_buffer.append(value)
        self.sod_line = value & 0x01

    def _write_control(self, value: int) -> None:
        if self._awaiting_mode:
            self.mode_instruction = value
            self.sync_chars.clear()
            self._pending_sync_chars = self._expected_sync_chars(value)
            self._awaiting_mode = False
            return

        if self._pending_sync_chars:
            self.sync_chars.append(value)
            self._pending_sync_chars -= 1
            self._awaiting_mode = self._pending_sync_chars > 0
            return

        if value & 0x40:
            self.reset_device(clear_buffers=False)
            return

        if value & 0x10:
            self.parity_error = 0
            self.overrun_error = 0
            self.framing_error = 0
        self.command_instruction = value
        if value & 0x08:
            self.sod_line = 0

    def reset_device(self, clear_buffers: bool = False) -> None:
        """Reset the USART state machine."""

        self.mode_instruction = 0
        self.command_instruction = 0
        self.sync_chars.clear()
        self._awaiting_mode = True
        self._pending_sync_chars = 0
        self.parity_error = 0
        self.overrun_error = 0
        self.framing_error = 0
        self.syn_det_brk = 0
        self.sod_line = 0
        if clear_buffers:
            self._rx_buffer.clear()
            self._tx_buffer.clear()
        self._update_rx_ready_line()

    def status_byte(self) -> int:
        """Return the 8251 status register."""

        tx_ready = 1 if self.tx_enabled else 0
        rx_ready = 1 if self.rx_enabled and self._rx_buffer else 0
        tx_empty = 1 if self.tx_enabled else 0
        return (
            tx_ready
            | (rx_ready << 1)
            | (tx_empty << 2)
            | (self.parity_error << 3)
            | (self.overrun_error << 4)
            | (self.framing_error << 5)
            | (self.syn_det_brk << 6)
            | (self.dsr << 7)
        ) & 0xFF

    @property
    def configured(self) -> bool:
        """Return whether a mode word has been accepted."""

        return not self._awaiting_mode and self._pending_sync_chars == 0

    @property
    def tx_enabled(self) -> bool:
        """Return whether the transmitter is enabled."""

        return self.configured and bool(self.command_instruction & 0x01)

    @property
    def rx_enabled(self) -> bool:
        """Return whether the receiver is enabled."""

        return self.configured and bool(self.command_instruction & 0x04)

    def push_input_bytes(self, data: bytes | bytearray) -> None:
        """Queue incoming terminal data for the guest to read."""

        for value in data:
            self._rx_buffer.append(value & 0xFF)
        if data:
            self.sid_line = data[0] & 0x01
        self._update_rx_ready_line()

    def push_input_text(self, text: str) -> None:
        """Queue incoming UTF-8 text."""

        self.push_input_bytes(text.encode("utf-8"))

    def pop_output_bytes(self) -> bytes:
        """Drain transmitted bytes."""

        data = bytes(self._tx_buffer)
        self._tx_buffer.clear()
        return data

    def pop_output_text(self) -> str:
        """Drain transmitted terminal text."""

        return self.pop_output_bytes().decode("utf-8", errors="replace")

    def read_sid(self) -> int:
        """Expose the current serial input line to `RIM`."""

        return 1 if self.sid_line else 0

    def write_sod(self, value: int) -> None:
        """Drive the serial output line through the shared terminal buffer."""

        self.sod_line = 1 if value else 0
        self._tx_buffer.append(ord("1") if self.sod_line else ord("0"))

    def mode_summary(self) -> str:
        """Return a short textual summary of the current mode."""

        if not self.configured and self.mode_instruction == 0:
            return "Reset"
        if (self.mode_instruction & 0x03) == 0:
            chars = 5 + ((self.mode_instruction >> 2) & 0x03)
            sync = "2-sync" if self.mode_instruction & 0x80 else "1-sync"
            return f"Sync {chars}-bit {sync}"

        baud_factor = {1: "x1", 2: "x16", 3: "x64"}.get(self.mode_instruction & 0x03, "x?")
        chars = 5 + ((self.mode_instruction >> 2) & 0x03)
        parity_enabled = bool(self.mode_instruction & 0x10)
        parity = "N"
        if parity_enabled:
            parity = "E" if self.mode_instruction & 0x20 else "O"
        stop_bits = {0: "invalid", 1: "1", 2: "1.5", 3: "2"}[(self.mode_instruction >> 6) & 0x03]
        return f"Async {chars}{parity}{stop_bits} {baud_factor}"

    @staticmethod
    def _expected_sync_chars(mode_instruction: int) -> int:
        if (mode_instruction & 0x03) != 0:
            return 0
        return 2 if mode_instruction & 0x80 else 1

    def bind_rx_ready_callback(self, callback: Callable[[bool], None]) -> None:
        """Bind a callback that tracks whether receive data is pending."""

        self._rx_ready_callback = callback
        self._update_rx_ready_line()

    def _update_rx_ready_line(self) -> None:
        ready = bool(self._rx_buffer)
        if ready == self._rx_ready_state:
            return
        self._rx_ready_state = ready
        if self._rx_ready_callback is not None:
            self._rx_ready_callback(ready)
