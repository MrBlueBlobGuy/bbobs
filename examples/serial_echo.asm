; 8251 serial example: initialize the USART and echo received bytes.
ORG 0000H
    MVI A, 4EH
    OUT 11H
    MVI A, 37H
    OUT 11H
WAIT:
    IN 11H
    ANI 02H
    JZ WAIT
    IN 10H
TXWAIT:
    IN 11H
    ANI 01H
    JZ TXWAIT
    OUT 10H
    JMP WAIT
END
