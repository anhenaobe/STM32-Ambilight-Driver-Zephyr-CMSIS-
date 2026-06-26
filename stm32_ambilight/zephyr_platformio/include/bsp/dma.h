#ifndef BSP_DMA_H
#define BSP_DMA_H

#include <stdint.h>

void dma_init(void);
int dma_start_pwm_transfer(uint16_t *buffer, uint16_t length);

#endif
