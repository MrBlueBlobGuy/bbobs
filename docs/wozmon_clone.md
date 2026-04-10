# WozMon Clone

`examples/wozmon_clone.asm` is a small WozMon-inspired serial monitor for the
8085 emulator. It runs over the built-in 8251 terminal console and gives you a
minimal interactive monitor for memory inspection, patching, and program
execution.

## What It Does

On startup the monitor:

1. sets the stack pointer to `F000H`
2. initializes the 8251 USART
3. prints a banner
4. enters a command loop on the serial console

The input buffer lives at `2400H`.

## Loading It

1. Start the emulator:

```bash
python3 main.py
```

2. Open [wozmon_clone.asm](/mnt/d/dev/b8085/examples/wozmon_clone.asm).
3. Click `Assemble + Load`.
4. Click `Run`.
5. Click inside the `8251 Terminal Console` or press `F6`.
6. Type commands and press `Enter`.

## Prompt

The monitor prompt is:

```text
\ 
```

Input is normalized to uppercase, so `r 2000` and `R 2000` behave the same.

## Commands

### `H`

Show help.

Example:

```text
\ H
```

### `R hhhh`

Read 16 bytes starting at address `hhhh`.

Format:

```text
R 2000
```

Example output:

```text
2000: 3E 41 D3 10 76 00 00 00 00 00 00 00 00 00 00 00
```

### `W hhhh bb ...`

Write one or more bytes starting at address `hhhh`.

Format:

```text
W 2200 3E 41 D3 10 76
```

That writes:

- `3E` to `2200H`
- `41` to `2201H`
- `D3` to `2202H`
- `10` to `2203H`
- `76` to `2204H`

The monitor replies with:

```text
OK
```

### `G hhhh`

Jump to address `hhhh`.

Format:

```text
G 2200
```

This transfers control directly to the target address using `PCHL`.

### `C hhhh`

Call address `hhhh` and return to the monitor when the target executes `RET`.

Format:

```text
C 2200
```

The monitor pushes an internal return address onto the stack, transfers
control to the target, and resumes the monitor command loop when the guest
program executes `RET`.

## Example Session

The following creates a tiny program in RAM that prints `A` to the serial
terminal, then halts:

```text
\ W 2200 3E 41 D3 10 76
OK
\ R 2200
2200: 3E 41 D3 10 76 00 00 00 00 00 00 00 00 00 00 00
\ G 2200
A
```

The following creates a tiny subroutine in RAM that prints `B` and returns to
the monitor with `RET`:

```text
\ W 2210 3E 42 D3 10 C9
OK
\ C 2210
B\ 
```

## Input Rules

- Addresses must be 4 hexadecimal digits.
- Data bytes must be 2 hexadecimal digits.
- Spaces between fields are allowed and skipped by the monitor.
- Invalid input prints `?`.

## Limitations

This is a WozMon-style monitor, not a full symbolic debugger.

- `R` always dumps exactly 16 bytes.
- `W` accepts raw hex bytes only.
- There is no disassembler command inside the monitor.
- There is no built-in file loading command inside the monitor.
- `G` does not return to the monitor.
- `C` returns to the monitor only if the target program executes `RET`.

## Implementation Notes

The monitor source is in [wozmon_clone.asm](/mnt/d/dev/b8085/examples/wozmon_clone.asm).
The command dispatcher starts at label `DISPATCH`, the USART setup is in
`INIT8251`, and command parsing is based on `PARSE_HEX_WORD` and
`PARSE_HEX_BYTE`.
