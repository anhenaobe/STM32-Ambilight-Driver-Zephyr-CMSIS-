#include "APP/translator.h"

static uint16_t led_buffer[PWM_BUFFER_SIZE];

void Translator_ToPWM(uint8_t* input_colors, uint16_t size) {
    uint32_t pwm_index = 0;

    for (int i = 0; i < size; i++) {
        uint8_t current_color = input_colors[i];

        for (int bit = 7; bit >= 0; bit--) {
            if (current_color & (1 << bit)) {
                led_buffer[pwm_index++] = PWM_LOGICAL_1;
            } else {
                led_buffer[pwm_index++] = PWM_LOGICAL_0;
            }
        }
    }

    // Reset slots keep the SK6812 latch low after the frame.
    while (pwm_index < PWM_BUFFER_SIZE) {
        led_buffer[pwm_index++] = 0;
    }
}

uint16_t* Translator_GetPWMBuffer(void) {
    return led_buffer;
}