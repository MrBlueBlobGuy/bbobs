; Arithmetic example: add two values and store the result in RAM.
ORG 0000H
    MVI A, 05H
    MVI B, 03H
    ADD B
    STA 2200H
    HLT
END

