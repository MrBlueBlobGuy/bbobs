# b8085

A modular Intel 8085 emulator written in Python with:

- full 64KB address-space modeling
- cycle-counting CPU execution
- built-in two-pass assembler
- breakpoint-aware execution engine
- Tkinter debugger UI
- port-mapped and serial I/O support

## Project Layout

```text
b8085/
  assembler/
  cpu/
  debugger/
  io/
  memory/
  ui/
examples/
tests/
main.py
```

## Run

```bash
python3 main.py
```

## Included Examples

- `examples/arithmetic.asm`
- `examples/brainfuck_interpreter.asm`
- `examples/call_return_demo.asm`
- `examples/hello_terminal.asm`
- `examples/interrupt_once.asm`
- `examples/loop.asm`
- `examples/memory.asm`
- `examples/serial_echo.asm`
- `examples/wozmon_clone.asm`

## WozMon Clone

The project includes a WozMon-inspired serial monitor in
`examples/wozmon_clone.asm`.

It supports:

- `H` for help
- `R hhhh` to read 16 bytes from memory
- `W hhhh bb ...` to write bytes into memory
- `G hhhh` to jump to an address
- `C hhhh` to call an address and return on `RET`

Full usage notes and example sessions are in
[docs/wozmon_clone.md](/mnt/d/dev/b8085/docs/wozmon_clone.md).

## Test

```bash
python3 -m unittest discover -s tests
```

## Serial I/O

The default serial device is an Intel 8251-style USART mapped to:

- `10H`: data register
- `11H`: status register when read, mode/command register when written

Typical guest initialization:

```asm
MVI A, 4EH    ; async, 8-bit, no parity, 1 stop, x16
OUT 11H
MVI A, 37H    ; enable Tx/Rx, assert RTS/DTR, clear errors
OUT 11H
```

`SIM` and `RIM` remain available for SID/SOD-style line control through the
same terminal abstraction.

## Interrupts

The emulator now models the standard 8085 interrupt set:

- `TRAP`
- `RST 7.5`
- `RST 6.5`
- `RST 5.5`
- `INTR`

Behavior includes fixed priority, mask handling through `SIM`/`RIM`, delayed
enable semantics for `EI`, the `RST 7.5` latch, and bus-vectored `INTR`
acknowledge using a supplied `RST` or `CALL` instruction.

From Python, interrupt lines can be driven through the session helpers:

- `request_trap(...)`
- `pulse_rst_7_5()`
- `set_rst_6_5(...)`
- `set_rst_5_5(...)`
- `request_intr(...)`
- `clear_intr()`
