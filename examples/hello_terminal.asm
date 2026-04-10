; Terminal hello-world example for the 8251 console.
ORG 0000H
    LXI SP, 0F000H
    MVI A, 4EH
    OUT 11H
    MVI A, 37H
    OUT 11H
    LXI H, MSG
    CALL PUTS
    HLT

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
    DB "HELLO FROM 8085", 0DH, 0AH, 00H
END
