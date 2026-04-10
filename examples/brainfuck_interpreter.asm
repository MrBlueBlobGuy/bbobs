; Brainfuck-style interpreter adapted for the b8085 assembler.
; This example is laid out for the segmented machine profile:
;   0000H = ROM reset entry
;   0003H+ = interpreter code in ROM
;   3000H = data tape in RAM
;   4000H = input buffer in RAM
;   5000H = output byte location in RAM
;   6000H = stack top in RAM
;   SOURCE = embedded Brainfuck source in ROM
;
; Character literals in CPI instructions are encoded as ASCII hex values
; because the assembler expects numeric immediates there.

        ORG 0000H
        JMP START

START:  LXI H, SOURCE    ; HL = Brainfuck program pointer in ROM
        LXI D, 3000H     ; DE = data pointer
        LXI B, 4000H     ; BC = input pointer
        LXI SP, 6000H    ; stack

NEXT:   MOV A, M         ; A = current instruction
        CPI 00H
        JZ  END

        CPI 3EH          ; '>'
        JZ  INC_DP

        CPI 3CH          ; '<'
        JZ  DEC_DP

        CPI 2BH          ; '+'
        JZ  INC_VAL

        CPI 2DH          ; '-'
        JZ  DEC_VAL

        CPI 2EH          ; '.'
        JZ  OUTPUT

        CPI 2CH          ; ','
        JZ  INPUT

        CPI 5BH          ; '['
        JZ  LOOP_START

        CPI 5DH          ; ']'
        JZ  LOOP_END

ADV:    INX H
        JMP NEXT

; --- Pointer movement ---

INC_DP: INX D
        JMP ADV

DEC_DP: DCX D
        JMP ADV

; --- Data operations ---

INC_VAL:
        LDAX D
        INR A
        STAX D
        JMP ADV

DEC_VAL:
        LDAX D
        DCR A
        STAX D
        JMP ADV

; --- Output (store to memory buffer) ---

OUTPUT:
        LDAX D
        STA 5000H
        JMP ADV

; --- Input (read from memory buffer) ---

INPUT:
        LDAX B
        STAX D
        INX B
        JMP ADV

; --- Loop handling ---

LOOP_START:
        LDAX D
        CPI 00H
        JNZ ADV

        MVI C, 01H       ; loop depth

LS1:    INX H
        MOV A, M
        CPI 5BH          ; '['
        JNZ LS2
        INR C
        JMP LS1

LS2:    CPI 5DH          ; ']'
        JNZ LS1
        DCR C
        JNZ LS1

        JMP ADV

LOOP_END:
        LDAX D
        CPI 00H
        JZ ADV

        MVI C, 01H

LE1:    DCX H
        MOV A, M
        CPI 5DH          ; ']'
        JNZ LE2
        INR C
        JMP LE1

LE2:    CPI 5BH          ; '['
        JNZ LE1
        DCR C
        JNZ LE1

        JMP ADV

END:    HLT

SOURCE:
        DB "+++++[>+++++++++++++<-]>.", 00H
