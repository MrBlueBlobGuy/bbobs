; Memory example: write a pattern into RAM using HL.
ORG 0000H
    LXI H, 2300H
    MVI M, 11H
    INX H
    MVI M, 22H
    INX H
    MVI M, 33H
    HLT
END

