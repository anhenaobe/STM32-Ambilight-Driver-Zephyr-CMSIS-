#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>

#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>

#include <stm32l4xx.h>

#include "bsp/dma.h"
#include "bsp/pwm.h"

#define DMA_PATTERN_SAMPLES 512U
#define DIAG_PRINT_BUFFER_SIZE 192U

static const struct device *const diag_uart = DEVICE_DT_GET(DT_NODELABEL(usart2));
static uint16_t dma_pattern[DMA_PATTERN_SAMPLES];

static void diag_puts(const char *text)
{
    if (!device_is_ready(diag_uart)) {
        return;
    }

    while (*text != '\0') {
        uart_poll_out(diag_uart, *text++);
    }
}

static void diag_printf(const char *format, ...)
{
    char buffer[DIAG_PRINT_BUFFER_SIZE];
    va_list args;

    va_start(args, format);
    int written = vsnprintk(buffer, sizeof(buffer), format, args);
    va_end(args);

    if (written <= 0) {
        return;
    }

    buffer[sizeof(buffer) - 1U] = '\0';
    diag_puts(buffer);
}

static void fill_dma_pattern(void)
{
    for (uint16_t i = 0; i < DMA_PATTERN_SAMPLES; i++) {
        if ((i % 32U) < 16U) {
            dma_pattern[i] = 60U;
        } else {
            dma_pattern[i] = 32U;
        }
    }
}

int main(void)
{
    uint32_t transfer_count = 0U;

    diag_puts("\r\n=== PB3 TIM2_CH2 DMA diagnostic ===\r\n");

    fill_dma_pattern();
    rcc_init();
    pwm_init();
    dma_init();

    diag_puts("[PWM_DMA] BSP pwm_init() and dma_init() completed.\r\n");
    diag_puts("[PWM_DMA] Repeating short DMA bursts into TIM2->CCR2 every 1000 ms.\r\n");

    while (1) {
        int ret = dma_start_pwm_transfer(dma_pattern, DMA_PATTERN_SAMPLES);
        transfer_count++;

        diag_printf("[PWM_DMA] transfer=%lu ret=%d ccr2=%lu dier=0x%lx cr1=0x%lx\r\n",
                    (unsigned long)transfer_count,
                    ret,
                    (unsigned long)TIM2->CCR2,
                    (unsigned long)TIM2->DIER,
                    (unsigned long)TIM2->CR1);

        k_msleep(1000);
    }
}
