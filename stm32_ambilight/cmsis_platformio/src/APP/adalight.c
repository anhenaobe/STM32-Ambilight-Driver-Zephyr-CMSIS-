#include "APP/adalight.h"

typedef enum {
    WAIT_A,
    WAIT_D,
    WAIT_A2,
    WAIT_HI,
    WAIT_LO,
    WAIT_CHK,
    RECEIVE_COLORS
} AdalightState;

static AdalightState state = WAIT_A;
static uint8_t hi_byte = 0;
static uint8_t lo_byte = 0;
static uint16_t color_index = 0;
static uint8_t color_buffer[COLOR_BUFFER_SIZE];

volatile uint8_t frame_ready = 0;

void Adalight_ProcessByte(uint8_t byte) {
    switch (state) {
        case WAIT_A:
            if (byte == 'A') {
                state = WAIT_D;
            }
            break;
        case WAIT_D:
            if (byte == 'd') {
                state = WAIT_A2;
            } else {
                state = WAIT_A;
            }
            break;
        case WAIT_A2:
            if (byte == 'a') {
                state = WAIT_HI;
            } else {
                state = WAIT_A;
            }
            break;
        case WAIT_HI:
            hi_byte = byte;
            state = WAIT_LO;
            break;
        case WAIT_LO:
            lo_byte = byte;
            state = WAIT_CHK;
            break;
        case WAIT_CHK: {
            uint8_t checksum = hi_byte ^ lo_byte ^ 0x55;
            uint16_t declared_leds_minus_one = ((uint16_t)hi_byte << 8) | lo_byte;
            if (checksum == byte && declared_leds_minus_one == (NUM_LEDS - 1)) {
                color_index = 0;
                state = RECEIVE_COLORS;
            } else {
                state = WAIT_A;
            }
            break;
        }
        case RECEIVE_COLORS:
            color_buffer[color_index++] = byte;
            if (color_index >= COLOR_BUFFER_SIZE) {
                frame_ready = 1;
                state = WAIT_A;
            }
            break;
    }
}

uint8_t* Adalight_GetColorBuffer(void) {
    return color_buffer;
}