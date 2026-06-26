#include <zephyr/device.h>

#include <stm32l4xx.h>

#include "bsp/pwm.h"

static const struct device *const pwm_dev = DEVICE_DT_GET(DT_NODELABEL(pwm2));

void rcc_init(void)
{
    /*
     * Zephyr owns system clock setup. This compatibility entry point remains so
     * the legacy initialization sequence can stay unchanged.
     */
}

void pwm_init(void)
{
    if (!device_is_ready(pwm_dev)) {
        return;
    }

    TIM2->CR1 &= ~TIM_CR1_CEN;
    TIM2->PSC = 0U;
    TIM2->ARR = 99U;
    TIM2->CNT = 0U;
    TIM2->CCR2 = 0U;

    TIM2->CCMR1 &= ~TIM_CCMR1_OC2M_Msk;
    TIM2->CCMR1 |= (6U << TIM_CCMR1_OC2M_Pos);
    TIM2->CCMR1 |= TIM_CCMR1_OC2PE;

    TIM2->CCER |= TIM_CCER_CC2E;
    TIM2->DIER &= ~TIM_DIER_CC2DE;
    TIM2->DIER |= TIM_DIER_UDE;
    TIM2->EGR |= TIM_EGR_UG;
    TIM2->CR1 |= TIM_CR1_ARPE;
    TIM2->CR1 |= TIM_CR1_CEN;
}
