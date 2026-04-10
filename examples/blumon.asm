; Commands:
;   R hhhh          Read 16 bytes from address
;   W hhhh bb ...   Write one or more bytes
;   G hhhh          Jump to address
;   C hhhh          Call address and return on RET
;   H               Show help
;
; Memory map:
;   2400H-2401H     line buffer write pointer
;   2402H           line length
;   2403H           line ready flag
;   2410H+          line buffer

ORG 2000

STACKTOP   EQU 0F000H
BUF_PTR    EQU 02400H
BUF_COUNT  EQU 02402H
LINE_READY EQU 02403H
BUFFER     EQU 02410H

        ORG 0000H
        JMP START

        ORG 0034H
        JMP SERIAL_RX_ISR

        ORG 0040H
START:
        DI
        LXI SP, STACKTOP
        CALL RESET_INPUT
        CALL INIT8251
        CALL INIT_INTERRUPTS
        LXI H, BANNER
        CALL PUTS

MAIN:
        CALL RESET_INPUT
        LXI H, PROMPT
        CALL PUTS
WAIT_LINE:
        EI
        HLT
        DI
        LDA LINE_READY
        ORA A
        JZ WAIT_LINE
        CALL DISPATCH
        JMP MAIN

SERIAL_RX_ISR_BODY:
SERIAL_RX_ISR:
        PUSH PSW
        PUSH B
        PUSH D
        PUSH H

        IN 11H
        ANI 02H
        JZ ISR_DONE
        IN 10H
        CALL TOUPPER
        CPI 00AH
        JZ ISR_DONE
        CPI 00DH
        JZ ISR_ENDLINE

        MOV B, A
        LDA BUF_COUNT
        CPI 03FH
        JNC ISR_DONE
        LHLD BUF_PTR
        MOV A, B
        MOV M, A
        INX H
        SHLD BUF_PTR
        LDA BUF_COUNT
        INR A
        STA BUF_COUNT
        MOV A, B
        CALL PUTCHAR
        JMP ISR_DONE

ISR_ENDLINE:
        LHLD BUF_PTR
        MVI M, 00H
        MVI A, 01H
        STA LINE_READY
        CALL CRLF

ISR_DONE:
        POP H
        POP D
        POP B
        POP PSW
        RET

DISPATCH:
        LXI H, BUFFER
        CALL SKIPSP
        MOV A, M
        CPI 00H
        RZ
        CPI 052H
        JZ CMD_READ
        CPI 057H
        JZ CMD_WRITE
        CPI 047H
        JZ CMD_GO
        CPI 043H
        JZ CMD_CALL
        CPI 048H
        JZ CMD_HELP
        CPI 03FH
        JZ CMD_HELP
        JMP BAD_INPUT

CMD_READ:
        INX H
        CALL SKIPSP
        CALL PARSE_HEX_WORD
        JC BAD_INPUT
        CALL PRINT_DUMP_LINE
        RET

CMD_WRITE:
        INX H
        CALL SKIPSP
        CALL PARSE_HEX_WORD
        JC BAD_INPUT
WRITE_LOOP:
        CALL SKIPSP
        MOV A, M
        CPI 00H
        JZ WRITE_DONE
        CALL PARSE_HEX_BYTE
        JC BAD_INPUT
        STAX D
        INX D
        JMP WRITE_LOOP
WRITE_DONE:
        LXI H, OKMSG
        CALL PUTS
        RET

CMD_GO:
        INX H
        CALL SKIPSP
        CALL PARSE_HEX_WORD
        JC BAD_INPUT
        XCHG
        PCHL

CMD_CALL:
        INX H
        CALL SKIPSP
        CALL PARSE_HEX_WORD
        JC BAD_INPUT
        XCHG
        LXI D, CALL_RETURN
        PUSH D
        PCHL

CALL_RETURN:
        RET

CMD_HELP:
        LXI H, HELPMSG
        CALL PUTS
        RET

BAD_INPUT:
        LXI H, ERRMSG
        CALL PUTS
        RET

INIT8251:
        MVI A, 04EH
        OUT 11H
        MVI A, 037H
        OUT 11H
        RET

INIT_INTERRUPTS:
        MVI A, 00DH      ; mask RST 5.5 / 7.5, unmask RST 6.5, update masks
        SIM
        RET

RESET_INPUT:
        LXI H, BUFFER
        SHLD BUF_PTR
        XRA A
        STA BUF_COUNT
        STA LINE_READY
        RET

PUTCHAR:
        PUSH B
        MOV B, A
TXWAIT:
        IN 11H
        ANI 01H
        JZ TXWAIT
        MOV A, B
        OUT 10H
        POP B
        RET

PUTS:
        MOV A, M
        CPI 00H
        RZ
        CALL PUTCHAR
        INX H
        JMP PUTS

CRLF:
        MVI A, 00DH
        CALL PUTCHAR
        MVI A, 00AH
        CALL PUTCHAR
        RET

SKIPSP:
        MOV A, M
        CPI 020H
        JZ SKIPSP_ADV
        CPI 009H
        JNZ SKIPSP_DONE
SKIPSP_ADV:
        INX H
        JMP SKIPSP
SKIPSP_DONE:
        RET

TOUPPER:
        CPI 061H
        JC TOUPPER_DONE
        CPI 07BH
        JNC TOUPPER_DONE
        SUI 020H
TOUPPER_DONE:
        RET

PARSE_HEX_WORD:
        CALL PARSE_HEX_BYTE
        RC
        MOV D, A
        CALL PARSE_HEX_BYTE
        RC
        MOV E, A
        ORA A
        RET

PARSE_HEX_BYTE:
        CALL PARSE_HEX_DIGIT
        RC
        MOV B, A
        MOV A, B
        RLC
        RLC
        RLC
        RLC
        MOV B, A
        CALL PARSE_HEX_DIGIT
        RC
        ORA B
        RET

PARSE_HEX_DIGIT:
        MOV A, M
        CPI 030H
        JC PARSE_DIGIT_ERR
        CPI 03AH
        JC PARSE_DIGIT_DEC
        CPI 041H
        JC PARSE_DIGIT_ERR
        CPI 047H
        JNC PARSE_DIGIT_ERR
        SUI 037H
        INX H
        ORA A
        RET
PARSE_DIGIT_DEC:
        SUI 030H
        INX H
        ORA A
        RET
PARSE_DIGIT_ERR:
        STC
        RET

PRINT_DUMP_LINE:
        PUSH B
        PUSH D
        MOV A, D
        CALL PRINT_HEX_BYTE
        MOV A, E
        CALL PRINT_HEX_BYTE
        MVI A, 03AH
        CALL PUTCHAR
        MVI A, 020H
        CALL PUTCHAR
        POP D
        MVI B, 010H
DUMP_LOOP:
        LDAX D
        CALL PRINT_HEX_BYTE
        MVI A, 020H
        CALL PUTCHAR
        INX D
        DCR B
        JNZ DUMP_LOOP
        POP B
        CALL CRLF
        RET

PRINT_HEX_BYTE:
        PUSH B
        MOV B, A
        ANI 0F0H
        RRC
        RRC
        RRC
        RRC
        CALL PRINT_HEX_DIGIT
        MOV A, B
        ANI 00FH
        CALL PRINT_HEX_DIGIT
        POP B
        RET

PRINT_HEX_DIGIT:
        ANI 00FH
        CPI 00AH
        JC PRINT_DIGIT_NUM
        ADI 037H
        JMP PRINT_DIGIT_OUT
PRINT_DIGIT_NUM:
        ADI 030H
PRINT_DIGIT_OUT:
        CALL PUTCHAR
        RET

BANNER:
        DB "\r\n8085 BLUMON (IRQ INPUT)\r\n", 00H
PROMPT:
        DB "\\ ", 00H
OKMSG:
        DB "OK\r\n", 00H
ERRMSG:
        DB "?\r\n", 00H
HELPMSG:
        DB "R HHHH      READ 16 BYTES\r\n"
        DB "W HHHH BB   WRITE BYTES\r\n"
        DB "G HHHH      GO\r\n"
        DB "C HHHH      CALL / RET\r\n"
        DB "H           HELP\r\n", 00H
END
