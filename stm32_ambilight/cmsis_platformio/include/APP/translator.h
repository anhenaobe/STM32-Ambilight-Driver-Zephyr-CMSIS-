#ifndef TRANSLATOR_H
#define TRANSLATOR_H

#include <stdint.h>

#define PWM_LOGICAL_1 60
#define PWM_LOGICAL_0 32

#define NUM_LEDS 120
#define BYTES_PER_LED 4
#define COLOR_BUFFER_SIZE (NUM_LEDS * BYTES_PER_LED)
#define PWM_BUFFER_SIZE ((COLOR_BUFFER_SIZE * 8) + 100)

void Translator_ToPWM(uint8_t* input_colors, uint16_t size);
uint16_t* Translator_GetPWMBuffer(void);

#endif