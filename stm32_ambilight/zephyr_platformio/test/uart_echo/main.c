#include <stdint.h>

#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>

#define UART_NODE DT_NODELABEL(usart2)

static const struct device *const echo_uart = DEVICE_DT_GET(UART_NODE);

static void uart_puts(const char *text)
{
    while (*text != '\0') {
        uart_poll_out(echo_uart, *text++);
    }
}

static void uart_put_hex_nibble(uint8_t value)
{
    value &= 0x0f;
    uart_poll_out(echo_uart, value < 10 ? ('0' + value) : ('A' + value - 10));
}

static void uart_put_hex_byte(uint8_t value)
{
    uart_put_hex_nibble(value >> 4);
    uart_put_hex_nibble(value);
}

int main(void)
{
    uint8_t byte;

    if (!device_is_ready(echo_uart)) {
        return 0;
    }

    uart_puts("\r\n=== USART2 polling echo diagnostic ===\r\n");
    uart_puts("Type in this terminal. Each received byte will be echoed.\r\n");
    uart_puts("Expected path: PC -> ST-Link VCP -> STM32 USART2 RX -> USART2 TX -> PC.\r\n\r\n");

    while (1) {
        if (uart_poll_in(echo_uart, &byte) == 0) {
            uart_puts("[RX 0x");
            uart_put_hex_byte(byte);
            uart_puts("] ");

            if (byte == '\r') {
                uart_puts("\\r\r\n");
            } else if (byte == '\n') {
                uart_puts("\\n\r\n");
            } else {
                uart_poll_out(echo_uart, byte);
                uart_puts("\r\n");
            }
        }

        k_sleep(K_MSEC(1));
    }
}
