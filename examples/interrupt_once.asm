; Interrupt-driven serial input example using RST 6.5.
ORG 0000H
    JMP START

ORG 0034H
    JMP SERIAL_ISR

ORG 0040H
START:
    LXI SP, 0F000H
    MVI A, 4EH
    OUT 11H
    MVI A, 37H
    OUT 11H
    XRA A
    STA 2201H
WAIT:
    EI
    HLT
    DI
    LDA 2201H
    ORA A
    JZ WAIT
    HLT

SERIAL_ISR:
    PUSH PSW
    IN 11H
    ANI 02H
    JZ ISR_DONE
    IN 10H
    STA 2200H
    MVI A, 01H
    STA 2201H
ISR_DONE:
    POP PSW
    RET
END
