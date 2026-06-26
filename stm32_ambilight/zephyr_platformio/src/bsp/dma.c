#include <errno.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/device.h>
#include <zephyr/drivers/dma.h>

#include <stm32l4xx.h>

#include "bsp/dma.h"

#define PWM_DMA_CHANNEL 2U
#define PWM_DMA_SLOT_TIM2_UP 61U

static const struct device *const dma_dev = DEVICE_DT_GET(DT_NODELABEL(dma1));
static struct dma_block_config pwm_dma_block;
static struct dma_config pwm_dma_config;
static uint8_t dma_ready;

void dma_init(void)
{
    if (!device_is_ready(dma_dev)) {
        dma_ready = 0U;
        return;
    }

    (void)memset(&pwm_dma_block, 0, sizeof(pwm_dma_block));
    (void)memset(&pwm_dma_config, 0, sizeof(pwm_dma_config));

    pwm_dma_block.dest_address = (uint32_t)&TIM2->CCR2;
    pwm_dma_block.source_addr_adj = DMA_ADDR_ADJ_INCREMENT;
    pwm_dma_block.dest_addr_adj = DMA_ADDR_ADJ_NO_CHANGE;

    pwm_dma_config.dma_slot = PWM_DMA_SLOT_TIM2_UP;
    pwm_dma_config.channel_direction = MEMORY_TO_PERIPHERAL;
    pwm_dma_config.source_data_size = 2U;
    pwm_dma_config.dest_data_size = 2U;
    pwm_dma_config.source_burst_length = 1U;
    pwm_dma_config.dest_burst_length = 1U;
    pwm_dma_config.head_block = &pwm_dma_block;

    dma_ready = 1U;
}

int dma_start_pwm_transfer(uint16_t *buffer, uint16_t length)
{
    if (!dma_ready) {
        return -ENODEV;
    }

    if ((buffer == NULL) || (length == 0U)) {
        return -EINVAL;
    }

    (void)dma_stop(dma_dev, PWM_DMA_CHANNEL);

    TIM2->CR1 &= ~TIM_CR1_CEN;
    TIM2->CNT = 0U;
    TIM2->CCR2 = buffer[0];
    TIM2->EGR |= TIM_EGR_UG;

    if (length == 1U) {
        TIM2->CR1 |= TIM_CR1_CEN;
        return 0;
    }

    pwm_dma_block.source_address = (uint32_t)&buffer[1];
    pwm_dma_block.dest_address = (uint32_t)&TIM2->CCR2;
    pwm_dma_block.block_size = (uint32_t)(length - 1U) * sizeof(buffer[0]);

    int ret = dma_config(dma_dev, PWM_DMA_CHANNEL, &pwm_dma_config);
    if (ret != 0) {
        return ret;
    }

    ret = dma_start(dma_dev, PWM_DMA_CHANNEL);
    if (ret != 0) {
        return ret;
    }

    TIM2->CR1 |= TIM_CR1_CEN;
    return 0;
}
