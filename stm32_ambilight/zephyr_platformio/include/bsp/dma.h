#ifndef BSP_DMA_H
#define BSP_DMA_H

#include <stdint.h>

/* STM32L432 DMA1 has no DMAMUX. Zephyr's STM32 V2 driver forwards dma_slot
 * to LL_DMA_Init.PeriphRequest, which the L432 LL writes into DMA_CSELR.
 * Request selection 4 maps TIM2_UP to DMA1 Channel 2 on this SoC.
 */
#define PWM_DMA_SLOT_TIM2_UP 4U

void dma_init(void);
int dma_start_pwm_transfer(uint16_t *buffer, uint16_t length);

#endif
