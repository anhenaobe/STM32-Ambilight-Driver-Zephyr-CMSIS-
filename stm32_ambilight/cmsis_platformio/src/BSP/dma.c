#include "BSP/dma.h"

void dma_init(void) {
    RCC->AHB1ENR |= RCC_AHB1ENR_DMA1EN;

    // DMA1 Channel 2 is mapped to TIM2_UP and writes PWM samples to TIM2->CCR2.
    DMA1_CSELR->CSELR &= ~DMA_CSELR_C2S;
    DMA1_CSELR->CSELR |= (4U << DMA_CSELR_C2S_Pos);
    DMA1_Channel2->CPAR = (uint32_t)&TIM2->CCR2;
    DMA1_Channel2->CCR = DMA_CCR_DIR     |
                         DMA_CCR_MINC    |
                         DMA_CCR_MSIZE_0 |
                         DMA_CCR_PSIZE_1;
}