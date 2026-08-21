#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/device.h>
#include <zephyr/drivers/dma.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>

#include <stm32l4xx.h>

#include "bsp/dma.h"
#include "bsp/pwm.h"

#define DMA_PATTERN_SAMPLES 3940U
#define DMA_DATA_SAMPLES 3840U
#define DIAG_DMA_CHANNEL 2U
#define DIAG_WAIT_US 10000U
#define DIAG_PRINT_BUFFER_SIZE 224U
#define DMA_CHANNEL2_FLAGS                                                    \
    (DMA_ISR_GIF2 | DMA_ISR_TCIF2 | DMA_ISR_HTIF2 | DMA_ISR_TEIF2)

static const struct device *const diag_uart = DEVICE_DT_GET(DT_NODELABEL(usart2));
static const struct device *const diag_dma = DEVICE_DT_GET(DT_NODELABEL(dma1));
static uint16_t dma_pattern[DMA_PATTERN_SAMPLES];
static struct dma_block_config diag_dma_block;
static struct dma_config diag_dma_config;

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
        if (i >= DMA_DATA_SAMPLES) {
            dma_pattern[i] = 0U;
        } else if ((i % 32U) < 16U) {
            dma_pattern[i] = 60U;
        } else {
            dma_pattern[i] = 32U;
        }
    }
}

static int configure_production_dma_request(void)
{
    (void)memset(&diag_dma_block, 0, sizeof(diag_dma_block));
    (void)memset(&diag_dma_config, 0, sizeof(diag_dma_config));

    diag_dma_block.source_address = (uint32_t)&dma_pattern[1];
    diag_dma_block.dest_address = (uint32_t)&TIM2->CCR2;
    diag_dma_block.block_size =
        (DMA_PATTERN_SAMPLES - 1U) * sizeof(dma_pattern[0]);
    diag_dma_block.source_addr_adj = DMA_ADDR_ADJ_INCREMENT;
    diag_dma_block.dest_addr_adj = DMA_ADDR_ADJ_NO_CHANGE;

    /* Share the exact request selector used by the production BSP. */
    diag_dma_config.dma_slot = PWM_DMA_SLOT_TIM2_UP;
    diag_dma_config.channel_direction = MEMORY_TO_PERIPHERAL;
    diag_dma_config.source_data_size = sizeof(dma_pattern[0]);
    diag_dma_config.dest_data_size = sizeof(dma_pattern[0]);
    diag_dma_config.source_burst_length = 1U;
    diag_dma_config.dest_burst_length = 1U;
    diag_dma_config.head_block = &diag_dma_block;

    return dma_config(diag_dma, DIAG_DMA_CHANNEL, &diag_dma_config);
}

static void run_dma_diagnostic(uint32_t transfer_count)
{
    (void)dma_stop(diag_dma, DIAG_DMA_CHANNEL);
    DMA1->IFCR = DMA_CHANNEL2_FLAGS;

    TIM2->CR1 &= ~TIM_CR1_CEN;
    TIM2->CNT = 0U;
    TIM2->CCR2 = dma_pattern[0];
    TIM2->EGR |= TIM_EGR_UG;

    const int config_ret = configure_production_dma_request();
    const uint32_t cselr = DMA1_CSELR->CSELR;
    const uint32_t c2s = (cselr & DMA_CSELR_C2S_Msk) >> DMA_CSELR_C2S_Pos;
    const uint32_t cndtr_start = DMA1_Channel2->CNDTR;

    int start_ret = -1;
    if (config_ret == 0) {
        start_ret = dma_start(diag_dma, DIAG_DMA_CHANNEL);
    }

    if (start_ret == 0) {
        TIM2->CR1 |= TIM_CR1_CEN;
    }

    const uint32_t cndtr_immediate = DMA1_Channel2->CNDTR;
    k_busy_wait(DIAG_WAIT_US);
    const uint32_t cndtr_after = DMA1_Channel2->CNDTR;
    const uint32_t dma_isr = DMA1->ISR;
    const uint32_t dma_flags = dma_isr & DMA_CHANNEL2_FLAGS;
    const uint32_t channel_enabled =
        (DMA1_Channel2->CCR & DMA_CCR_EN) != 0U ? 1U : 0U;
    const bool completion = (start_ret == 0) &&
        (((dma_flags & DMA_ISR_TCIF2) != 0U) ||
         ((cndtr_start > 0U) && (cndtr_after == 0U)));
    const bool progress = (start_ret == 0) &&
        ((cndtr_immediate < cndtr_start) ||
         (cndtr_after < cndtr_start) || completion);
    const bool expected_config = c2s == PWM_DMA_SLOT_TIM2_UP;
    const bool pass = (config_ret == 0) && (start_ret == 0) &&
                      expected_config && progress &&
                      ((dma_flags & DMA_ISR_TEIF2) == 0U);

    diag_printf("\r\nDMA_TEST=%lu\r\n", (unsigned long)transfer_count);
    diag_printf("DMA_CONFIG_RESULT=%d\r\n", config_ret);
    diag_printf("DMA_CONFIG_OK=%s\r\n", config_ret == 0 ? "YES" : "NO");
    diag_printf("DMA_START_RESULT=%d\r\n", start_ret);
    diag_printf("DMA_START_OK=%s\r\n", start_ret == 0 ? "YES" : "NO");
    diag_printf("DMA1_CSELR=0x%08lx\r\n", (unsigned long)cselr);
    diag_printf("C2S=%lu\r\n", (unsigned long)c2s);
    diag_printf("EXPECTED_C2S=%u\r\n", PWM_DMA_SLOT_TIM2_UP);
    diag_printf("DMA_CONFIG_EXPECTED=%s\r\n",
                expected_config ? "YES" : "NO");
    diag_printf("CNDTR_START=%lu\r\n", (unsigned long)cndtr_start);
    diag_printf("CNDTR_IMMEDIATE=%lu\r\n",
                (unsigned long)cndtr_immediate);
    diag_printf("CNDTR_AFTER=%lu\r\n", (unsigned long)cndtr_after);
    diag_printf("DMA_ISR=0x%08lx\r\n", (unsigned long)dma_isr);
    diag_printf("DMA_FLAGS_CH2=0x%02lx\r\n", (unsigned long)dma_flags);
    diag_printf("DMA_COMPLETION=%s\r\n", completion ? "YES" : "NO");
    diag_printf("DMA_CHANNEL_ENABLED=%s\r\n",
                channel_enabled != 0U ? "YES" : "NO");
    diag_printf("TIM2_DIER=0x%08lx\r\n", (unsigned long)TIM2->DIER);
    diag_printf("TIM2_CCR2=%lu\r\n", (unsigned long)TIM2->CCR2);
    diag_printf("DMA_PROGRESS=%s\r\n", progress ? "YES" : "NO");
    diag_printf("DMA_DIAGNOSTIC_PASS=%s\r\n", pass ? "YES" : "NO");
}

int main(void)
{
    uint32_t transfer_count = 0U;

    diag_puts("\r\n=== PB3 TIM2_CH2 DMA diagnostic ===\r\n");

    fill_dma_pattern();
    rcc_init();
    pwm_init();

    if (!device_is_ready(diag_dma)) {
        diag_puts("DMA_DEVICE_READY=NO\r\n");
        return 0;
    }

    diag_puts("DMA_DEVICE_READY=YES\r\n");
    diag_puts("NOTE=slot 4 is shared with the production DMA BSP\r\n");
    diag_puts("NOTE=logic analyzer probe is PB3 TIM2_CH2\r\n");

    while (1) {
        transfer_count++;
        run_dma_diagnostic(transfer_count);
        k_msleep(1000);
    }
}
