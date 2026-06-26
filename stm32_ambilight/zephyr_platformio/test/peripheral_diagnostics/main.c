#include <stdarg.h>
#include <stddef.h>
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

#define DIAG_DMA_BUFFER_SIZE 96U
#define DIAG_PRINT_BUFFER_SIZE 160U

static const struct device *const diag_uart = DEVICE_DT_GET(DT_NODELABEL(usart2));
static uint16_t diag_dma_buffer[DIAG_DMA_BUFFER_SIZE];
static volatile uint32_t diag_uart_rx_bytes;
static volatile uint32_t diag_uart_frames;

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

static void diag_uart_rx_callback(uint8_t data)
{
    diag_uart_rx_bytes++;
    Adalight_ProcessByte(data);

    if (frame_ready) {
        diag_uart_frames++;
    }
}

static void diag_fill_dma_pattern(void)
{
    for (uint16_t i = 0; i < DIAG_DMA_BUFFER_SIZE; i++) {
        if ((i % 24U) < 12U) {
            diag_dma_buffer[i] = 60U;
        } else {
            diag_dma_buffer[i] = 32U;
        }
    }
}

static int diag_test_app_parser_and_translator(void)
{
    const uint16_t led_count_minus_one = NUM_LEDS - 1U;
    const uint8_t hi = (uint8_t)((led_count_minus_one >> 8) & 0xFFU);
    const uint8_t lo = (uint8_t)(led_count_minus_one & 0xFFU);
    const uint8_t checksum = hi ^ lo ^ 0x55U;
    const uint8_t header[] = { 'A', 'd', 'a', hi, lo, checksum };

    frame_ready = 0U;

    for (size_t i = 0; i < sizeof(header); i++) {
        Adalight_ProcessByte(header[i]);
    }

    for (uint16_t i = 0; i < COLOR_BUFFER_SIZE; i++) {
        if ((i % BYTES_PER_LED) == 0U) {
            Adalight_ProcessByte(0x80U);
        } else {
            Adalight_ProcessByte(0x00U);
        }
    }

    if (!frame_ready) {
        diag_puts("[APP] FAIL: Adalight parser did not raise frame_ready\r\n");
        return -1;
    }

    Translator_ToPWM(Adalight_GetColorBuffer(), COLOR_BUFFER_SIZE);
    uint16_t *pwm_buffer = Translator_GetPWMBuffer();

    if ((pwm_buffer[0] != 60U) || (pwm_buffer[1] != 32U) ||
        (pwm_buffer[PWM_BUFFER_SIZE - 1U] != 0U)) {
        diag_printf("[APP] FAIL: translator unexpected samples: %u %u %u\r\n",
                    pwm_buffer[0], pwm_buffer[1],
                    pwm_buffer[PWM_BUFFER_SIZE - 1U]);
        return -1;
    }

    frame_ready = 0U;
    diag_puts("[APP] PASS: parser accepted synthetic frame and translator produced PWM data\r\n");
    return 0;
}

static void diag_test_pwm_timer(void)
{
    diag_puts("[PWM] Testing TIM2_CH2 on PB3 with direct duty changes\r\n");

    for (uint8_t cycle = 0U; cycle < 4U; cycle++) {
        TIM2->CCR2 = 32U;
        k_msleep(250);
        TIM2->CCR2 = 60U;
        k_msleep(250);
    }

    TIM2->CCR2 = 0U;
    diag_puts("[PWM] Done. PB3 should have shown duty changes during this step\r\n");
}

static void diag_test_dma_to_pwm(void)
{
    diag_fill_dma_pattern();

    diag_puts("[DMA] Starting short DMA transfer into TIM2->CCR2\r\n");
    int ret = dma_start_pwm_transfer(diag_dma_buffer, DIAG_DMA_BUFFER_SIZE);

    if (ret == 0) {
        diag_puts("[DMA] PASS: dma_start_pwm_transfer returned 0\r\n");
    } else {
        diag_printf("[DMA] FAIL: dma_start_pwm_transfer returned %d\r\n", ret);
    }

    k_msleep(20);
}

static void diag_process_external_frame_if_ready(void)
{
    if (!frame_ready) {
        return;
    }

    frame_ready = 0U;

    Translator_ToPWM(Adalight_GetColorBuffer(), COLOR_BUFFER_SIZE);
    int ret = dma_start_pwm_transfer(Translator_GetPWMBuffer(), PWM_BUFFER_SIZE);

    if (ret == 0) {
        diag_puts("[APP] External Adalight frame accepted and sent to PWM DMA\r\n");
    } else {
        diag_printf("[APP] External frame parsed, but PWM DMA failed: %d\r\n", ret);
    }
}

int main(void)
{
    diag_puts("\r\n=== Ambilight peripheral diagnostics ===\r\n");
    diag_printf("[UART] USART2 diagnostic TX ready at %u baud\r\n", BAUDS);

    rcc_init();
    uart_init();
    uart_set_rx_callback(diag_uart_rx_callback);
    pwm_init();
    dma_init();

    diag_puts("[INIT] BSP init sequence completed\r\n");

    (void)diag_test_app_parser_and_translator();
    diag_test_pwm_timer();
    diag_test_dma_to_pwm();

    diag_puts("[LOOP] Send adalight_sim.py frames now; RX and accepted-frame counters will update\r\n");

    while (1) {
        diag_process_external_frame_if_ready();
        diag_printf("[UART] rx_bytes=%lu parsed_frames=%lu frame_ready=%u\r\n",
                    (unsigned long)diag_uart_rx_bytes,
                    (unsigned long)diag_uart_frames,
                    (unsigned int)frame_ready);
        k_sleep(K_SECONDS(1));
    }
}
