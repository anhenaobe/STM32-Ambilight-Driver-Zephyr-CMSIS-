#include "app/adalight.h"

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
static uint8_t color_buffer[COLOR_BUFFER_SIZE];
static uint16_t led_count = 0;
static uint16_t bytes_expected = 0;
static uint16_t byte_index = 0;
static uint8_t hi_byte = 0;
static uint8_t lo_byte = 0;
volatile uint8_t frame_ready = 0;

void Adalight_ProcessByte(uint8_t byte)
{
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

    case WAIT_CHK:
        if (byte == (hi_byte ^ lo_byte ^ 0x55)) {
            led_count = ((uint16_t)hi_byte << 8) | lo_byte;
            led_count += 1;

            if (led_count == NUM_LEDS) {
                bytes_expected = led_count * BYTES_PER_LED;
                byte_index = 0;
                state = RECEIVE_COLORS;
            } else {
                state = WAIT_A;
            }
        } else {
            state = WAIT_A;
        }
        break;

    case RECEIVE_COLORS:
        if (byte_index < COLOR_BUFFER_SIZE) {
            color_buffer[byte_index++] = byte;
        }

        if (byte_index >= bytes_expected) {
            frame_ready = 1;
            state = WAIT_A;
        }
        break;

    default:
        state = WAIT_A;
        break;
    }
}

uint8_t *Adalight_GetColorBuffer(void)
{
    return color_buffer;
}
