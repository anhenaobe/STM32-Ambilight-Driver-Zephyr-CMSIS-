#include <stdint.h>
#include "stm32l4xx.h"
#include "bsp/pwm.h"
#include "bsp/dma.h"
#include "bsp/uart.h"
#include "app/adalight.h"
#include "app/translator.h"

int main(void) {
    rcc_init();
    uart_init();
    pwm_init();
    dma_init();

    uart_set_rx_callback(Adalight_ProcessByte);

    while (1) {
        if (frame_ready) {
            frame_ready = 0;

            uint8_t* raw_colors = Adalight_GetColorBuffer();
            Translator_ToPWM(raw_colors, COLOR_BUFFER_SIZE);

            uint16_t* pwm_data_ptr = Translator_GetPWMBuffer();

            DMA1_Channel2->CCR  &= ~DMA_CCR_EN;
            DMA1_Channel2->CNDTR = PWM_BUFFER_SIZE;
            DMA1_Channel2->CMAR  = (uint32_t)pwm_data_ptr;
            DMA1_Channel2->CCR  |= DMA_CCR_EN;
        }
    }
}