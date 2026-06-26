#ifndef ADALIGHT_H
#define ADALIGHT_H

#include <stdint.h>

#define NUM_LEDS 120
#define BYTES_PER_LED 4
#define COLOR_BUFFER_SIZE (NUM_LEDS * BYTES_PER_LED)

extern volatile uint8_t frame_ready;

void Adalight_ProcessByte(uint8_t byte);
uint8_t* Adalight_GetColorBuffer(void);

#endif