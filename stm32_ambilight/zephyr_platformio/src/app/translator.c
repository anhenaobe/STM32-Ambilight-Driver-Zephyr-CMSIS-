#include "app/translator.h"

#define PWM_LOGICAL_1 60
#define PWM_LOGICAL_0 32

static uint16_t led_buffer[PWM_BUFFER_SIZE];

void Translator_ToPWM(uint8_t *color_data, uint16_t length)
{
    uint16_t pwm_index = 0;

    for (uint16_t i = 0; i < length; i++) {
        uint8_t byte = color_data[i];

        for (int8_t bit = 7; bit >= 0; bit--) {
            if (byte & (1 << bit)) {
                led_buffer[pwm_index++] = PWM_LOGICAL_1;
            } else {
                led_buffer[pwm_index++] = PWM_LOGICAL_0;
            }
        }
    }

    while (pwm_index < PWM_BUFFER_SIZE) {
        led_buffer[pwm_index++] = 0;
    }
}

uint16_t *Translator_GetPWMBuffer(void)
{
    return led_buffer;
}
