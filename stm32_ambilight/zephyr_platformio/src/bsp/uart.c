#include <stddef.h>
#include <stdint.h>

#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>

#include "bsp/uart.h"

#define UART_RX_FIFO_SIZE 32U

static const struct device *const uart_dev = DEVICE_DT_GET(DT_NODELABEL(usart2));
static uart_rx_callback_t app_rx_callback;

static void uart_feed_received_byte(uint8_t data)
{
    uart_rx_callback_t callback = app_rx_callback;

    if (callback == NULL) {
        return;
    }

    callback(data);
}

static void uart_irq_callback(const struct device *dev, void *user_data)
{
    uint8_t fifo[UART_RX_FIFO_SIZE];

    ARG_UNUSED(user_data);

    if (!uart_irq_update(dev)) {
        return;
    }

    while (uart_irq_rx_ready(dev)) {
        const int bytes_read = uart_fifo_read(dev, fifo, sizeof(fifo));

        for (int i = 0; i < bytes_read; i++) {
            uart_feed_received_byte(fifo[i]);
        }
    }
}

void uart_init(void)
{
    if (!device_is_ready(uart_dev)) {
        return;
    }

    const struct uart_config config = {
        .baudrate = BAUDS,
        .parity = UART_CFG_PARITY_NONE,
        .stop_bits = UART_CFG_STOP_BITS_1,
        .data_bits = UART_CFG_DATA_BITS_8,
        .flow_ctrl = UART_CFG_FLOW_CTRL_NONE,
    };

    (void)uart_configure(uart_dev, &config);
    (void)uart_irq_callback_user_data_set(uart_dev, uart_irq_callback, NULL);
    uart_irq_rx_enable(uart_dev);
}

void uart_set_rx_callback(uart_rx_callback_t callback)
{
    app_rx_callback = callback;
}
