; Loop example: sum numbers from 5 down to 1 into A.
ORG 0000H
    MVI A, 00H
    MVI B, 05H
LOOP:
    ADD B
    DCR B
    JNZ LOOP
    STA 2201H
    HLT
END

