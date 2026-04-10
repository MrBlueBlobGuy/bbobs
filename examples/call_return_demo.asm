; Demonstrates CALL/RET with a terminal-printing subroutine.
ORG 0000H
    LXI SP, 0F000H
    MVI A, 4EH
    OUT 11H
    MVI A, 37H
    OUT 11H
    CALL SUBROUTINE
    MVI A, 55H
    STA 2200H
    HLT

SUBROUTINE:
    LXI H, MSG
    CALL PUTS
    RET

PUTCHAR:
    MOV B, A
TXWAIT:
    IN 11H
    ANI 01H
    JZ TXWAIT
    MOV A, B
    OUT 10H
    RET

PUTS:
    MOV A, M
    CPI 00H
    RZ
    CALL PUTCHAR
    INX H
    JMP PUTS

MSG:
    DB "CALL/RET OK", 0DH, 0AH, 00H
END
