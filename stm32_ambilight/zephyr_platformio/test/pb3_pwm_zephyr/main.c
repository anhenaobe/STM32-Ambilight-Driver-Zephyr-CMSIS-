#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>

#include <zephyr/device.h>
#include <zephyr/drivers/pwm.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>

#define TIM2_CH2_CHANNEL 2U
#define PWM_PERIOD_NS 1250U
#define PWM_DUTY_32_NS 400U
#define PWM_DUTY_60_NS 750U
#define DIAG_PRINT_BUFFER_SIZE 160U

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

static void set_pwm(uint32_t pulse_ns)
{
    int ret = pwm_set(pwm_dev, TIM2_CH2_CHANNEL, PWM_PERIOD_NS, pulse_ns, 0);

    diag_printf("[PWM_ZEPHYR] pwm_set(period=%lu ns, pulse=%lu ns) ret=%d\r\n",
                (unsigned long)PWM_PERIOD_NS,
                (unsigned long)pulse_ns,
                ret);
}

int main(void)
{
    diag_puts("\r\n=== PB3 Zephyr PWM API diagnostic ===\r\n");

    if (!device_is_ready(pwm_dev)) {
        diag_puts("[PWM_ZEPHYR] FAIL: pwm2 device is not ready\r\n");
        return 0;
    }

    diag_puts("[PWM_ZEPHYR] Testing pwm2 channel 2 on PB3.\r\n");

    while (1) {
        set_pwm(PWM_DUTY_32_NS);
        k_msleep(2000);

        set_pwm(PWM_DUTY_60_NS);
        k_msleep(2000);

        set_pwm(0U);
        k_msleep(1000);
    }
}
