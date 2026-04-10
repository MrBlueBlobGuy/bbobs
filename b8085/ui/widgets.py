"""Reusable Tkinter widgets for the emulator UI."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from b8085.debugger import CpuSnapshot, MemoryLine
from b8085.io import SerialDevice


class RegisterPanel(ttk.LabelFrame):
    """Displays register values and execution status."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, text="Registers", padding=8)
        self._vars = {name: tk.StringVar(value="00") for name in ("A", "B", "C", "D", "E", "H", "L")}
        self._vars["SP"] = tk.StringVar(value="FFFF")
        self._vars["PC"] = tk.StringVar(value="0000")
        self._vars["Cycles"] = tk.StringVar(value="0")
        self._vars["State"] = tk.StringVar(value="Paused")

        row = 0
        for name in ("A", "B", "C", "D", "E", "H", "L", "SP", "PC", "Cycles", "State"):
            ttk.Label(self, text=name, width=8).grid(row=row, column=0, sticky="w")
            ttk.Label(self, textvariable=self._vars[name], width=12).grid(row=row, column=1, sticky="w")
            row += 1

    def update_from_snapshot(self, snapshot: CpuSnapshot, running: bool) -> None:
        self._vars["A"].set(f"{snapshot.a:02X}")
        self._vars["B"].set(f"{snapshot.b:02X}")
        self._vars["C"].set(f"{snapshot.c:02X}")
        self._vars["D"].set(f"{snapshot.d:02X}")
        self._vars["E"].set(f"{snapshot.e:02X}")
        self._vars["H"].set(f"{snapshot.h:02X}")
        self._vars["L"].set(f"{snapshot.l:02X}")
        self._vars["SP"].set(f"{snapshot.sp:04X}")
        self._vars["PC"].set(f"{snapshot.pc:04X}")
        self._vars["Cycles"].set(str(snapshot.cycles))
        state = "Running" if running else "Halted" if snapshot.halted else "Paused"
        self._vars["State"].set(state)


class FlagPanel(ttk.LabelFrame):
    """Displays CPU flags."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, text="Flags", padding=8)
        self._vars = {name: tk.StringVar(value="0") for name in ("Z", "S", "P", "CY", "AC", "INT")}
        for column, name in enumerate(self._vars):
            ttk.Label(self, text=name).grid(row=0, column=column, padx=4, sticky="w")
            ttk.Label(self, textvariable=self._vars[name], width=3).grid(row=1, column=column, padx=4, sticky="w")

    def update_from_snapshot(self, snapshot: CpuSnapshot) -> None:
        for name in ("Z", "S", "P", "CY", "AC"):
            self._vars[name].set(str(snapshot.flags[name]))
        self._vars["INT"].set("1" if snapshot.interrupts_enabled else "0")


class MemoryViewer(ttk.LabelFrame):
    """Scrollable memory view with optional edit controls."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        title: str = "Memory",
        default_base: str = "0000",
        write_button_text: str = "Write",
    ) -> None:
        super().__init__(master, text=title, padding=8)
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 6))

        ttk.Label(header, text="Base").pack(side="left")
        self.base_var = tk.StringVar(value=default_base)
        ttk.Entry(header, textvariable=self.base_var, width=8).pack(side="left", padx=(4, 8))
        self.refresh_button = ttk.Button(header, text="Refresh")
        self.refresh_button.pack(side="left")

        ttk.Label(header, text="Edit").pack(side="left", padx=(12, 4))
        self.edit_address_var = tk.StringVar(value="0000")
        ttk.Entry(header, textvariable=self.edit_address_var, width=8).pack(side="left")
        self.edit_value_var = tk.StringVar(value="00")
        ttk.Entry(header, textvariable=self.edit_value_var, width=6).pack(side="left", padx=4)
        self.write_button = ttk.Button(header, text=write_button_text)
        self.write_button.pack(side="left")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self.text = tk.Text(body, width=72, height=16, wrap="none", font=("Courier New", 10))
        scroll = ttk.Scrollbar(body, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def render(self, lines: list[MemoryLine]) -> None:
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        for line in lines:
            self.text.insert("end", f"{line.address:04X}: {line.hex_bytes:<47}  {line.ascii_text}\n")
        self.text.config(state="disabled")


class DisassemblyView(ttk.LabelFrame):
    """Displays disassembled code and highlights the current instruction."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, text="Disassembly", padding=8)
        self.text = tk.Text(self, width=48, height=18, wrap="none", font=("Courier New", 10))
        self.text.pack(fill="both", expand=True)
        self.text.tag_configure("current", background="#ffe082")

    def render(self, lines: list[str], current_pc: int) -> None:
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.tag_remove("current", "1.0", "end")
        for index, line in enumerate(lines, start=1):
            self.text.insert("end", line + "\n")
            if line[2:6] == f"{current_pc:04X}":
                self.text.tag_add("current", f"{index}.0", f"{index}.end")
        self.text.config(state="disabled")


class BreakpointPanel(ttk.LabelFrame):
    """Controls and lists breakpoints."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, text="Breakpoints", padding=8)
        row = ttk.Frame(self)
        row.pack(fill="x")
        self.address_var = tk.StringVar(value="0000")
        ttk.Entry(row, textvariable=self.address_var, width=8).pack(side="left")
        self.toggle_button = ttk.Button(row, text="Toggle")
        self.toggle_button.pack(side="left", padx=4)
        self.clear_button = ttk.Button(row, text="Clear")
        self.clear_button.pack(side="left")
        self.listbox = tk.Listbox(self, height=6)
        self.listbox.pack(fill="both", expand=True, pady=(6, 0))

    def render(self, addresses: tuple[int, ...]) -> None:
        self.listbox.delete(0, "end")
        for address in addresses:
            self.listbox.insert("end", f"{address:04X}")


class EditorPanel(ttk.LabelFrame):
    """Source editor and file actions."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, text="Program Editor", padding=8)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 6))
        self.open_button = ttk.Button(toolbar, text="Open")
        self.open_button.pack(side="left")
        ttk.Label(toolbar, text="Example").pack(side="left", padx=(12, 4))
        self.example_var = tk.StringVar()
        self.example_combo = ttk.Combobox(toolbar, textvariable=self.example_var, width=24, state="readonly")
        self.example_combo.pack(side="left")
        self.load_example_button = ttk.Button(toolbar, text="Load Example")
        self.load_example_button.pack(side="left", padx=(4, 0))
        self.load_rom_button = ttk.Button(toolbar, text="Load ROM File")
        self.load_rom_button.pack(side="left", padx=(8, 0))
        self.load_button = ttk.Button(toolbar, text="Assemble + Load")
        self.load_button.pack(side="left", padx=4)
        ttk.Label(toolbar, text="Origin").pack(side="left", padx=(12, 4))
        self.origin_var = tk.StringVar(value="0000")
        ttk.Entry(toolbar, textvariable=self.origin_var, width=8).pack(side="left")
        self.text = tk.Text(self, width=64, height=18, wrap="none", font=("Courier New", 10))
        self.text.pack(fill="both", expand=True)

    def get_source(self) -> str:
        return self.text.get("1.0", "end-1c")

    def set_source(self, source: str) -> None:
        self.text.delete("1.0", "end")
        self.text.insert("1.0", source)


class SerialTerminal(ttk.LabelFrame):
    """Virtual terminal backed by the 8251 USART device."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, text="8251 Terminal Console", padding=10)
        self._input_callback: Callable[[str], None] | None = None
        status_row = ttk.Frame(self)
        status_row.pack(fill="x", pady=(0, 6))
        self.mode_var = tk.StringVar(value="Reset")
        self.status_var = tk.StringVar(value="00")
        self.command_var = tk.StringVar(value="00")
        self.keyboard_var = tk.StringVar(value="Keyboard I/O Ready")
        ttk.Label(status_row, text="Mode").pack(side="left")
        ttk.Label(status_row, textvariable=self.mode_var, width=22).pack(side="left", padx=(4, 12))
        ttk.Label(status_row, text="Status").pack(side="left")
        ttk.Label(status_row, textvariable=self.status_var, width=6).pack(side="left", padx=(4, 12))
        ttk.Label(status_row, text="Cmd").pack(side="left")
        ttk.Label(status_row, textvariable=self.command_var, width=6).pack(side="left", padx=(4, 0))
        ttk.Label(status_row, textvariable=self.keyboard_var).pack(side="right")

        hint_row = ttk.Frame(self)
        hint_row.pack(fill="x", pady=(0, 8))
        ttk.Label(
            hint_row,
            text="CLICK THE SCREEN OR PRESS F6, THEN TYPE DIRECTLY TO SEND SERIAL INPUT",
        ).pack(side="left")

        self.output = tk.Text(
            self,
            width=108,
            height=24,
            wrap="char",
            font=("Courier New", 12, "bold"),
            background="#020402",
            foreground="#7dff93",
            insertbackground="#b8ffb8",
            selectbackground="#165f28",
            relief="sunken",
            bd=2,
            padx=14,
            pady=14,
        )
        self.output.pack(fill="both", expand=True)
        self.output.config(state="disabled")
        self.output.bind("<KeyPress>", self._on_key_press)
        self.output.bind("<Button-1>", self._focus_output)
        self.output.bind("<Control-c>", self._copy_selection)
        self.output.bind("<Control-C>", self._copy_selection)
        self.output.bind("<Control-v>", self._paste_clipboard)
        self.output.bind("<Control-V>", self._paste_clipboard)
        self.output.bind("<Shift-Insert>", self._paste_clipboard)
        self.output.bind("<<Paste>>", self._paste_clipboard)

        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=(6, 0))
        self.input_var = tk.StringVar()
        ttk.Label(controls, text="Send").pack(side="left", padx=(0, 6))
        ttk.Entry(controls, textvariable=self.input_var).pack(side="left", fill="x", expand=True)
        self.send_button = ttk.Button(controls, text="Send")
        self.send_button.pack(side="left", padx=4)
        self.paste_button = ttk.Button(controls, text="Paste")
        self.paste_button.pack(side="left", padx=(0, 4))
        self.copy_button = ttk.Button(controls, text="Copy")
        self.copy_button.pack(side="left")
        self.clear_button = ttk.Button(controls, text="Clear")
        self.clear_button.pack(side="left", padx=(4, 0))
        self.focus_button = ttk.Button(controls, text="Focus Terminal")
        self.focus_button.pack(side="left", padx=(4, 0))

    def append_output(self, text: str) -> None:
        if not text:
            return
        self.output.config(state="normal")
        for char in text:
            if char == "\r":
                self._carriage_return()
            elif char == "\n":
                self.output.insert("end", "\n")
            elif char == "\b":
                self._backspace()
            elif char == "\t":
                self.output.insert("end", "    ")
            else:
                self.output.insert("end", char)
        self.output.see("end")
        self.output.config(state="disabled")

    def clear(self) -> None:
        self.output.config(state="normal")
        self.output.delete("1.0", "end")
        self.output.config(state="disabled")

    def update_device_state(self, device: SerialDevice) -> None:
        """Refresh terminal metadata from the USART."""

        self.mode_var.set(device.mode_summary())
        self.status_var.set(f"{device.status_byte():02X}")
        self.command_var.set(f"{device.command_instruction:02X}")

    def bind_input_handler(self, callback: Callable[[str], None]) -> None:
        """Bind a callback used for keyboard-driven serial input."""

        self._input_callback = callback
        self.focus_button.configure(command=self.focus_screen)
        self.paste_button.configure(command=self.paste_clipboard)
        self.copy_button.configure(command=self.copy_selection)
        self.keyboard_var.set("Keyboard I/O Active")

    def focus_screen(self) -> None:
        """Focus the terminal display for live typing."""

        self.output.focus_set()

    def _focus_output(self, _event: tk.Event[tk.Text]) -> None:
        self.focus_screen()

    def _on_key_press(self, event: tk.Event[tk.Text]) -> str:
        if self._input_callback is None:
            return "break"
        if event.state & 0x4 and event.keysym.lower() in {"c", "v"}:
            return "break"
        if event.keysym == "Return":
            self._input_callback("\r\n")
            return "break"
        if event.keysym == "BackSpace":
            self._input_callback("\b")
            return "break"
        if event.keysym == "Tab":
            self._input_callback("\t")
            return "break"
        if event.char and event.char >= " ":
            self._input_callback(event.char)
            return "break"
        return "break"

    def copy_selection(self) -> None:
        """Copy the selected terminal text to the host clipboard."""

        try:
            selection = self.output.get("sel.first", "sel.last")
        except tk.TclError:
            return
        self.output.clipboard_clear()
        self.output.clipboard_append(selection)

    def paste_clipboard(self) -> None:
        """Paste host clipboard text into the emulated serial input."""

        if self._input_callback is None:
            return
        try:
            text = self.output.clipboard_get()
        except tk.TclError:
            return
        if not text:
            return
        normalized = text.replace("\r\n", "\r").replace("\n", "\r")
        self._input_callback(normalized)
        self.focus_screen()

    def _copy_selection(self, _event: tk.Event[tk.Text]) -> str:
        self.copy_selection()
        return "break"

    def _paste_clipboard(self, _event: tk.Event[tk.Text]) -> str:
        self.paste_clipboard()
        return "break"

    def _carriage_return(self) -> None:
        # Most guest software emits CRLF for line endings, so treating CR as a
        # non-destructive cursor return keeps the terminal readable without
        # needing a full screen-buffer emulator.
        return None

    def _backspace(self) -> None:
        end_index = self.output.index("end-1c")
        if self.output.compare(end_index, ">", "1.0"):
            self.output.delete(f"{end_index} -1 chars", end_index)
