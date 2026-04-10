"""Tkinter application shell."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from b8085.assembler import AssemblyError, ProgramImage
from b8085.debugger import EmulatorSession
from b8085.memory import SegmentType

from .widgets import BreakpointPanel, DisassemblyView, EditorPanel, FlagPanel, MemoryViewer, RegisterPanel, SerialTerminal


class EmulatorApp(tk.Tk):
    """Main Tkinter window."""

    def __init__(self, session: EmulatorSession | None = None) -> None:
        super().__init__()
        self.title("b8085 Emulator")
        self.geometry("1560x980")
        self.session = session if session is not None else EmulatorSession.with_default_segments()
        self._theme_mode = "light"
        self._style = ttk.Style(self)
        self._style.theme_use("clam")
        self._examples_dir = Path(__file__).resolve().parents[2] / "examples"
        self._example_paths: dict[str, Path] = {}

        self._build_layout()
        self._wire_actions()
        self._populate_examples()
        self._load_default_example()
        self._apply_theme()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._schedule_refresh()

    def _build_layout(self) -> None:
        controls = ttk.Frame(self, padding=8)
        controls.pack(fill="x")
        self.run_button = ttk.Button(controls, text="Run")
        self.run_button.pack(side="left")
        self.step_button = ttk.Button(controls, text="Step")
        self.step_button.pack(side="left", padx=4)
        self.pause_button = ttk.Button(controls, text="Pause")
        self.pause_button.pack(side="left")
        self.reset_button = ttk.Button(controls, text="Reset")
        self.reset_button.pack(side="left", padx=4)
        self.theme_button = ttk.Button(controls, text="Toggle Theme")
        self.theme_button.pack(side="left", padx=(12, 0))
        ttk.Label(
            controls,
            text="F6 focuses the terminal screen for keyboard I/O",
        ).pack(side="right")

        scroll_host = ttk.Frame(self)
        scroll_host.pack(fill="both", expand=True)
        self.workspace_canvas = tk.Canvas(scroll_host, highlightthickness=0)
        workspace_scrollbar = ttk.Scrollbar(scroll_host, orient="vertical", command=self.workspace_canvas.yview)
        self.workspace_canvas.configure(yscrollcommand=workspace_scrollbar.set)
        workspace_scrollbar.pack(side="right", fill="y")
        self.workspace_canvas.pack(side="left", fill="both", expand=True)

        self.workspace = ttk.Frame(self.workspace_canvas)
        self.workspace_window = self.workspace_canvas.create_window((0, 0), window=self.workspace, anchor="nw")
        self.workspace.bind("<Configure>", self._on_workspace_configure)
        self.workspace_canvas.bind("<Configure>", self._on_canvas_configure)
        self.workspace_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        top_pane = ttk.Panedwindow(self.workspace, orient="horizontal")
        top_pane.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        left = ttk.Frame(top_pane, padding=8)
        right = ttk.Frame(top_pane, padding=8)
        top_pane.add(left, weight=3)
        top_pane.add(right, weight=2)

        bottom = ttk.Frame(self.workspace, padding=(8, 8, 8, 8))
        bottom.pack(fill="both", expand=True)

        self.editor = EditorPanel(left)
        self.editor.pack(fill="both", expand=True)
        self.disassembly = DisassemblyView(left)
        self.disassembly.pack(fill="both", expand=True, pady=(8, 0))

        self.registers = RegisterPanel(right)
        self.registers.pack(fill="x")
        self.flags = FlagPanel(right)
        self.flags.pack(fill="x", pady=(8, 0))
        self.breakpoints = BreakpointPanel(right)
        self.breakpoints.pack(fill="x", pady=(8, 0))
        memory_book = ttk.Notebook(right)
        memory_book.pack(fill="both", expand=True, pady=(8, 0))
        self.memory = MemoryViewer(memory_book, title="RAM", default_base="2000", write_button_text="Write RAM")
        self.rom = MemoryViewer(memory_book, title="ROM", default_base="0000", write_button_text="Patch ROM")
        memory_book.add(self.memory, text="RAM")
        memory_book.add(self.rom, text="ROM")
        self.serial = SerialTerminal(bottom)
        self.serial.pack(fill="both", expand=True)

    def _wire_actions(self) -> None:
        self.run_button.configure(command=self.session.engine.start)
        self.step_button.configure(command=self._step)
        self.pause_button.configure(command=self.session.engine.pause)
        self.reset_button.configure(command=self._reset)
        self.theme_button.configure(command=self._toggle_theme)

        self.editor.open_button.configure(command=self._open_source)
        self.editor.load_example_button.configure(command=self._load_selected_example)
        self.editor.example_combo.bind("<<ComboboxSelected>>", self._load_selected_example)
        self.editor.load_rom_button.configure(command=self._load_rom_program)
        self.editor.load_button.configure(command=self._assemble_and_load)

        self.memory.refresh_button.configure(command=self._refresh_memory)
        self.memory.write_button.configure(command=self._write_memory)
        self.rom.refresh_button.configure(command=self._refresh_rom)
        self.rom.write_button.configure(command=self._write_rom)

        self.breakpoints.toggle_button.configure(command=self._toggle_breakpoint)
        self.breakpoints.clear_button.configure(command=self._clear_breakpoints)
        self.breakpoints.listbox.bind("<Double-Button-1>", self._remove_selected_breakpoint)

        self.serial.send_button.configure(command=self._send_serial_input)
        self.serial.clear_button.configure(command=self.serial.clear)
        self.serial.bind_input_handler(self._queue_serial_input)
        self.bind("<F6>", self._focus_terminal)

    def _load_default_example(self) -> None:
        example_path = self._examples_dir / "serial_echo.asm"
        if example_path.exists():
            self.editor.set_source(example_path.read_text())
            self.editor.example_var.set(example_path.name)

    def _populate_examples(self) -> None:
        if not self._examples_dir.exists():
            return
        example_paths = sorted(self._examples_dir.glob("*.asm"))
        self._example_paths = {path.name: path for path in example_paths}
        self.editor.example_combo.configure(values=list(self._example_paths))

    def _load_selected_example(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        selected = self.editor.example_var.get().strip()
        if not selected:
            return
        path = self._example_paths.get(selected)
        if path is None or not path.exists():
            messagebox.showerror("Example Error", f"Example not found: {selected}")
            return
        self.editor.set_source(path.read_text())

    def _open_source(self) -> None:
        path = filedialog.askopenfilename(
            title="Open 8085 Assembly Source",
            filetypes=[("Assembly files", "*.asm"), ("All files", "*.*")],
        )
        if path:
            self.editor.set_source(Path(path).read_text())

    def _load_rom_program(self) -> None:
        path = filedialog.askopenfilename(
            title="Open ROM Assembly Source",
            filetypes=[("Assembly files", "*.asm"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            source = Path(path).read_text()
            self.editor.set_source(source)
            if not self.editor.origin_var.get().strip():
                self.editor.origin_var.set("0000")
            origin = int(self.editor.origin_var.get(), 16)
            image = self.session.assemble(source, origin=origin)
            self._ensure_image_in_rom(image)
            self.session.flash_rom_image(image)
            start = image.segments[0].start if image.segments else 0x0000
            self.editor.origin_var.set(f"{start:04X}")
            self.rom.base_var.set(f"{start:04X}")
            self.session.reset(pc=start)
            self._refresh_all()
        except AssemblyError as exc:
            messagebox.showerror("Assembly Error", str(exc))
        except ValueError:
            messagebox.showerror("Input Error", "Origin must be a hexadecimal value")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("ROM Load Error", str(exc))

    def _assemble_and_load(self) -> None:
        try:
            origin = int(self.editor.origin_var.get(), 16)
            image = self.session.assemble_and_load(self.editor.get_source(), origin=origin, force=True)
            if image.segments:
                self.session.reset(pc=image.segments[0].start)
            self._refresh_all()
        except AssemblyError as exc:
            messagebox.showerror("Assembly Error", str(exc))
        except ValueError:
            messagebox.showerror("Input Error", "Origin must be a hexadecimal value")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Load Error", str(exc))

    def _step(self) -> None:
        try:
            self.session.engine.step()
            self._refresh_all()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Execution Error", str(exc))

    def _reset(self) -> None:
        self.session.reset()
        self._refresh_all()

    def _toggle_breakpoint(self) -> None:
        try:
            address = int(self.breakpoints.address_var.get(), 16)
            self.session.breakpoints.toggle(address)
            self._refresh_disassembly()
            self.breakpoints.render(self.session.breakpoints.all())
        except ValueError:
            messagebox.showerror("Input Error", "Breakpoint address must be hexadecimal")

    def _clear_breakpoints(self) -> None:
        self.session.breakpoints.clear()
        self.breakpoints.render(self.session.breakpoints.all())
        self._refresh_disassembly()

    def _remove_selected_breakpoint(self, _event: tk.Event[tk.Listbox]) -> None:
        selection = self.breakpoints.listbox.curselection()
        if not selection:
            return
        address = int(self.breakpoints.listbox.get(selection[0]), 16)
        self.session.breakpoints.remove(address)
        self.breakpoints.render(self.session.breakpoints.all())
        self._refresh_disassembly()

    def _refresh_memory(self) -> None:
        try:
            base = int(self.memory.base_var.get(), 16)
            self.memory.render(self.session.memory_lines(base))
        except ValueError:
            messagebox.showerror("Input Error", "Memory base must be hexadecimal")

    def _refresh_rom(self) -> None:
        try:
            base = int(self.rom.base_var.get(), 16)
            self.rom.render(self.session.memory_lines(base))
        except ValueError:
            messagebox.showerror("Input Error", "ROM base must be hexadecimal")

    def _write_memory(self) -> None:
        try:
            address = int(self.memory.edit_address_var.get(), 16)
            value = int(self.memory.edit_value_var.get(), 16)
            self.session.set_memory_byte(address, value)
            self._refresh_memory()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Memory Error", str(exc))

    def _write_rom(self) -> None:
        try:
            address = int(self.rom.edit_address_var.get(), 16)
            value = int(self.rom.edit_value_var.get(), 16)
            self.session.set_memory_byte(address, value, force=True)
            self._refresh_rom()
            self._refresh_disassembly()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("ROM Error", str(exc))

    def _send_serial_input(self) -> None:
        text = self.serial.input_var.get()
        if not text:
            return
        self._queue_serial_input(text)
        self.serial.input_var.set("")

    def _queue_serial_input(self, text: str) -> None:
        self.session.serial.push_input_text(text)

    def _focus_terminal(self, _event: tk.Event[tk.Misc] | None = None) -> str:
        self.serial.focus_screen()
        return "break"

    def _refresh_registers(self) -> None:
        snapshot = self.session.snapshot()
        self.registers.update_from_snapshot(snapshot, self.session.engine.is_running())
        self.flags.update_from_snapshot(snapshot)

    def _refresh_memory_view(self) -> None:
        try:
            base = int(self.memory.base_var.get(), 16)
        except ValueError:
            base = 0x2000
        self.memory.render(self.session.memory_lines(base))
        try:
            rom_base = int(self.rom.base_var.get(), 16)
        except ValueError:
            rom_base = 0x0000
        self.rom.render(self.session.memory_lines(rom_base))

    def _refresh_disassembly(self) -> None:
        snapshot = self.session.snapshot()
        start = snapshot.pc
        lines = self.session.disassemble(start, lines=24)
        self.disassembly.render(lines, snapshot.pc)

    def _refresh_serial(self) -> None:
        self.serial.update_device_state(self.session.serial)
        self.serial.append_output(self.session.serial.pop_output_text())

    def _refresh_all(self) -> None:
        self._refresh_registers()
        self._refresh_memory_view()
        self._refresh_disassembly()
        self.breakpoints.render(self.session.breakpoints.all())
        self._refresh_serial()

    def _schedule_refresh(self) -> None:
        self._refresh_all()
        self.after(125, self._schedule_refresh)

    def _toggle_theme(self) -> None:
        self._theme_mode = "dark" if self._theme_mode == "light" else "light"
        self._apply_theme()

    def _apply_theme(self) -> None:
        if self._theme_mode == "dark":
            palette = {
                "bg": "#15202b",
                "fg": "#e6edf3",
                "panel": "#1f2a36",
                "accent": "#ffe082",
            }
        else:
            palette = {
                "bg": "#f2efe7",
                "fg": "#1d232f",
                "panel": "#fffdf8",
                "accent": "#ffe082",
            }

        self.configure(bg=palette["bg"])
        self._style.configure(".", background=palette["bg"], foreground=palette["fg"])
        self._style.configure("TFrame", background=palette["bg"])
        self._style.configure("TLabelframe", background=palette["panel"], foreground=palette["fg"])
        self._style.configure("TLabelframe.Label", background=palette["panel"], foreground=palette["fg"])
        self._style.configure("TLabel", background=palette["panel"], foreground=palette["fg"])
        self._style.configure("TButton", background=palette["panel"], foreground=palette["fg"])
        self._style.configure("TEntry", fieldbackground=palette["panel"], foreground=palette["fg"])

        for widget in (self.memory.text, self.disassembly.text, self.editor.text):
            widget.configure(
                background=palette["panel"],
                foreground=palette["fg"],
                insertbackground=palette["fg"],
                selectbackground=palette["accent"],
            )
        self.rom.text.configure(
            background=palette["panel"],
            foreground=palette["fg"],
            insertbackground=palette["fg"],
            selectbackground=palette["accent"],
        )
        self.disassembly.text.tag_configure("current", background=palette["accent"], foreground="#111111")

    def _ensure_image_in_rom(self, image: ProgramImage) -> None:
        if not image.segments:
            raise ValueError("assembled image is empty")
        for segment in image.segments:
            start_segment = self.session.memory.resolve(segment.start)
            end_segment = self.session.memory.resolve(segment.start + len(segment.data) - 1)
            if start_segment.segment_type != SegmentType.ROM or end_segment.segment_type != SegmentType.ROM:
                raise ValueError(
                    f"ROM loader requires segments inside ROM; segment at {segment.start:04X} is outside ROM"
                )

    def _on_workspace_configure(self, _event: tk.Event[tk.Misc]) -> None:
        self.workspace_canvas.configure(scrollregion=self.workspace_canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event[tk.Misc]) -> None:
        self.workspace_canvas.itemconfigure(self.workspace_window, width=event.width)

    def _on_mousewheel(self, event: tk.Event[tk.Misc]) -> str | None:
        widget = self.focus_get()
        if isinstance(widget, tk.Text):
            return None
        self.workspace_canvas.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    def _on_close(self) -> None:
        self.session.engine.stop()
        self.destroy()
