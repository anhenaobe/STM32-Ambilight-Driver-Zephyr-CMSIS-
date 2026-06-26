#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>

#define PB3_PIN 3U
#define DIAG_PRINT_BUFFER_SIZE 160U

static const struct device *const diag_uart = DEVICE_DT_GET(DT_NODELABEL(usart2));
static const struct device *const gpio_b = DEVICE_DT_GET(DT_NODELABEL(gpiob));

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

int main(void)
{
    diag_puts("\r\n=== PB3 GPIO diagnostic ===\r\n");

    if (!device_is_ready(gpio_b)) {
        diag_puts("[GPIO] FAIL: GPIOB device is not ready\r\n");
        return 0;
    }

    int ret = gpio_pin_configure(gpio_b, PB3_PIN, GPIO_OUTPUT_INACTIVE);
    if (ret != 0) {
        diag_printf("[GPIO] FAIL: gpio_pin_configure(PB3) returned %d\r\n", ret);
        return 0;
    }

    diag_puts("[GPIO] Toggling PB3 every 1000 ms. Expect a slow square wave.\r\n");

    while (1) {
        gpio_pin_set(gpio_b, PB3_PIN, 1);
        diag_puts("[GPIO] PB3=1\r\n");
        k_msleep(1000);

        gpio_pin_set(gpio_b, PB3_PIN, 0);
        diag_puts("[GPIO] PB3=0\r\n");
        k_msleep(1000);
    }
}
