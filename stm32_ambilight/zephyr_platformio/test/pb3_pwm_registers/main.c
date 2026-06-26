#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>

#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>

#include <stm32l4xx.h>

#define DIAG_PRINT_BUFFER_SIZE 192U

static const struct device *const diag_uart = DEVICE_DT_GET(DT_NODELABEL(usart2));
static const struct device *const pwm_dev = DEVICE_DT_GET(DT_NODELABEL(pwm2));

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

static void tim2_ch2_pwm_init_registers(void)
{
    TIM2->CR1 &= ~TIM_CR1_CEN;
    TIM2->PSC = 0U;
    TIM2->ARR = 99U;
    TIM2->CNT = 0U;
    TIM2->CCR2 = 0U;

    TIM2->CCMR1 &= ~TIM_CCMR1_OC2M_Msk;
    TIM2->CCMR1 |= (6U << TIM_CCMR1_OC2M_Pos);
    TIM2->CCMR1 |= TIM_CCMR1_OC2PE;

    TIM2->CCER |= TIM_CCER_CC2E;
    TIM2->EGR |= TIM_EGR_UG;
    TIM2->CR1 |= TIM_CR1_ARPE;
    TIM2->CR1 |= TIM_CR1_CEN;
}

int main(void)
{
    diag_puts("\r\n=== PB3 TIM2_CH2 register PWM diagnostic ===\r\n");

    if (!device_is_ready(pwm_dev)) {
        diag_puts("[PWM_REG] FAIL: pwm2 device is not ready\r\n");
        return 0;
    }

    tim2_ch2_pwm_init_registers();
    diag_puts("[PWM_REG] TIM2_CH2 configured by registers: ARR=99, PSC=0.\r\n");

    while (1) {
        TIM2->CCR2 = 32U;
        diag_printf("[PWM_REG] CCR2=32 cr1=0x%lx ccer=0x%lx ccmr1=0x%lx\r\n",
                    (unsigned long)TIM2->CR1,
                    (unsigned long)TIM2->CCER,
                    (unsigned long)TIM2->CCMR1);
        k_msleep(2000);

        TIM2->CCR2 = 60U;
        diag_printf("[PWM_REG] CCR2=60 cr1=0x%lx ccer=0x%lx ccmr1=0x%lx\r\n",
                    (unsigned long)TIM2->CR1,
                    (unsigned long)TIM2->CCER,
                    (unsigned long)TIM2->CCMR1);
        k_msleep(2000);

        TIM2->CCR2 = 0U;
        diag_puts("[PWM_REG] CCR2=0\r\n");
        k_msleep(1000);
    }
}
