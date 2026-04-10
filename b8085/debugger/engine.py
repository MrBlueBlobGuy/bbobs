"""Execution engine with run, pause, and step support."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from b8085.cpu import CPU8085, ExecutionResult

from .breakpoints import BreakpointManager

Observer = Callable[[ExecutionResult], None]


@dataclass(slots=True)
class ExecutionEngine:
    """Background execution loop for the emulator."""

    cpu: CPU8085
    breakpoints: BreakpointManager
    observers: list[Observer] = field(default_factory=list)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _run_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)

    def start(self) -> None:
        """Run continuously until paused, a terminal halt, or a breakpoint is hit."""

        with self._lock:
            if self._thread and self._thread.is_alive():
                self._run_event.set()
                return
            self._run_event.set()
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def pause(self) -> None:
        """Pause execution."""

        self._run_event.clear()

    def stop(self) -> None:
        """Stop the worker thread."""

        self._run_event.clear()
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)

    def step(self) -> ExecutionResult:
        """Execute one instruction regardless of breakpoints."""

        with self._lock:
            result = self.cpu.step()
        self._notify(result)
        return result

    def reset(self, pc: int = 0x0000, sp: int = 0xFFFF) -> None:
        """Reset the CPU and pause execution."""

        with self._lock:
            self.pause()
            self.cpu.reset(pc=pc, sp=sp)

    def is_running(self) -> bool:
        """Return whether the engine is currently running."""

        return self._run_event.is_set()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            if not self._run_event.wait(timeout=0.05):
                continue
            with self._lock:
                if self.breakpoints.contains(self.cpu.registers.pc) and not self.cpu.halted:
                    self._run_event.clear()
                    continue
                result = self.cpu.step()
            if result.halted:
                if self.cpu.interrupts.enabled:
                    # A halted 8085 can still resume on an interrupt, so keep the
                    # run loop armed while we wait for an external event.
                    time.sleep(0.01)
                    continue
                self._notify(result)
                self._run_event.clear()
                continue
            self._notify(result)
            time.sleep(0.0005)

    def _notify(self, result: ExecutionResult) -> None:
        for observer in list(self.observers):
            observer(result)
