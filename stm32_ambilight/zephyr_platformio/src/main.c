#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>

#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>

#include <stm32l4xx.h>

#include "app/adalight.h"
#include "app/translator.h"
#include "bsp/dma.h"
#include "bsp/pwm.h"
#include "bsp/uart.h"

#define DIAG_PRINT_BUFFER_SIZE 192U
#define DIAG_REPORT_PERIOD_MS 1000U

static const struct device *const diag_uart = DEVICE_DT_GET(DT_NODELABEL(usart2));

static volatile uint32_t diag_rx_bytes;
static volatile uint32_t diag_parser_frames;
static uint32_t diag_processed_frames;
static uint32_t diag_dma_ok;
static uint32_t diag_dma_fail;
static int diag_last_dma_ret;

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

static void diag_adalight_rx_callback(uint8_t data)
{
    const uint8_t was_ready = frame_ready;

    diag_rx_bytes++;
    Adalight_ProcessByte(data);

    if ((was_ready == 0U) && (frame_ready != 0U)) {
        diag_parser_frames++;
    }
}

static void diag_report(uint32_t *last_report_ms, uint32_t *last_rx_bytes)
{
    const uint32_t now_ms = (uint32_t)k_uptime_get();

    if ((now_ms - *last_report_ms) < DIAG_REPORT_PERIOD_MS) {
        return;
    }

    const uint32_t rx_total = diag_rx_bytes;
    const uint32_t rx_delta = rx_total - *last_rx_bytes;

    *last_rx_bytes = rx_total;
    *last_report_ms = now_ms;

    diag_printf("[DIAG] rx_total=%lu rx/s=%lu parsed=%lu processed=%lu "
                "dma_ok=%lu dma_fail=%lu last_dma=%d frame_ready=%u "
                "ccr2=%lu dier=0x%lx cr1=0x%lx\r\n",
                (unsigned long)rx_total,
                (unsigned long)rx_delta,
                (unsigned long)diag_parser_frames,
                (unsigned long)diag_processed_frames,
                (unsigned long)diag_dma_ok,
                (unsigned long)diag_dma_fail,
                diag_last_dma_ret,
                (unsigned int)frame_ready,
                (unsigned long)TIM2->CCR2,
                (unsigned long)TIM2->DIER,
                (unsigned long)TIM2->CR1);
}

int main(void)
{
    uint32_t last_report_ms = 0U;
    uint32_t last_rx_bytes = 0U;

    rcc_init();
    uart_init();
    pwm_init();
    dma_init();
    uart_set_rx_callback(diag_adalight_rx_callback);

    diag_puts("\r\n=== Ambilight runtime diagnostics ===\r\n");
    diag_printf("[INIT] USART2 ready at %u baud, TIM2_CH2/PB3 PWM path active\r\n", BAUDS);

    while (1) {
        if (frame_ready) {
            frame_ready = 0;

            uint8_t *raw_colors = Adalight_GetColorBuffer();
            Translator_ToPWM(raw_colors, COLOR_BUFFER_SIZE);

            diag_last_dma_ret = dma_start_pwm_transfer(Translator_GetPWMBuffer(), PWM_BUFFER_SIZE);
            diag_processed_frames++;

            if (diag_last_dma_ret == 0) {
                diag_dma_ok++;
            } else {
                diag_dma_fail++;
            }
        }

        diag_report(&last_report_ms, &last_rx_bytes);
        k_yield();
    }
}
