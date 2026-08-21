#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>

#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>

#include "app/adalight.h"

#define UART_NODE DT_NODELABEL(usart2)
#define DIAG_BAUDRATE 921600U
#define DIAG_RX_FIFO_SIZE 32U
#define DIAG_PRINT_BUFFER_SIZE 192U

static const struct device *const diag_uart = DEVICE_DT_GET(UART_NODE);
static volatile uint32_t rx_bytes;
static volatile uint32_t valid_frames;
static volatile uint32_t uart_error_events;
static volatile uint32_t uart_overrun_errors;
static volatile uint32_t uart_framing_errors;
static volatile uint32_t uart_parity_errors;
static volatile uint32_t uart_break_errors;
static volatile uint32_t uart_noise_errors;
static volatile uint32_t uart_collision_errors;
static volatile uint32_t uart_error_check_failures;

static void diag_puts(const char *text)
{
    while (*text != '\0') {
        uart_poll_out(diag_uart, *text++);
    }
}

static void diag_printf(const char *format, ...)
{
    char buffer[DIAG_PRINT_BUFFER_SIZE];
    va_list args;

    va_start(args, format);
    const int written = vsnprintk(buffer, sizeof(buffer), format, args);
    va_end(args);

    if (written <= 0) {
        return;
    }

    buffer[sizeof(buffer) - 1U] = '\0';
    diag_puts(buffer);
}

static void record_uart_errors(int errors)
{
    if (errors < 0) {
        uart_error_check_failures++;
        return;
    }

    if (errors == 0) {
        return;
    }

    uart_error_events++;

    if ((errors & UART_ERROR_OVERRUN) != 0) {
        uart_overrun_errors++;
    }
    if ((errors & UART_ERROR_FRAMING) != 0) {
        uart_framing_errors++;
    }
    if ((errors & UART_ERROR_PARITY) != 0) {
        uart_parity_errors++;
    }
    if ((errors & UART_BREAK) != 0) {
        uart_break_errors++;
    }
    if ((errors & UART_ERROR_NOISE) != 0) {
        uart_noise_errors++;
    }
    if ((errors & UART_ERROR_COLLISION) != 0) {
        uart_collision_errors++;
    }
}

static void process_received_byte(uint8_t data)
{
    rx_bytes++;
    Adalight_ProcessByte(data);

    if (frame_ready) {
        valid_frames++;
        /* This diagnostic consumes each publication immediately so two
         * concatenated frames remain countable. Production parser code is
         * unchanged and no LED output is started from this target.
         */
        frame_ready = 0U;
    }
}

static void uart_irq_callback(const struct device *dev, void *user_data)
{
    uint8_t fifo[DIAG_RX_FIFO_SIZE];

    ARG_UNUSED(user_data);

    const int update_result = uart_irq_update(dev);
    if (update_result <= 0) {
        if (update_result < 0) {
            uart_error_check_failures++;
        }
        return;
    }

    record_uart_errors(uart_err_check(dev));

    while (uart_irq_rx_ready(dev) > 0) {
        const int bytes_read = uart_fifo_read(dev, fifo, sizeof(fifo));
        if (bytes_read <= 0) {
            if (bytes_read < 0) {
                uart_error_check_failures++;
            }
            break;
        }

        for (int i = 0; i < bytes_read; i++) {
            process_received_byte(fifo[i]);
        }
    }
}

static void report_counters(void)
{
    diag_printf("RX_BYTES=%lu\r\n", (unsigned long)rx_bytes);
    diag_printf("VALID_FRAMES=%lu\r\n", (unsigned long)valid_frames);
    diag_printf("UART_ERRORS=%lu\r\n", (unsigned long)uart_error_events);
    diag_printf("UART_OVERRUN=%lu\r\n", (unsigned long)uart_overrun_errors);
    diag_printf("UART_FRAMING=%lu\r\n", (unsigned long)uart_framing_errors);
    diag_printf("UART_PARITY=%lu\r\n", (unsigned long)uart_parity_errors);
    diag_printf("UART_BREAK=%lu\r\n", (unsigned long)uart_break_errors);
    diag_printf("UART_NOISE=%lu\r\n", (unsigned long)uart_noise_errors);
    diag_printf("UART_COLLISION=%lu\r\n",
                (unsigned long)uart_collision_errors);
    diag_printf("UART_ERROR_CHECK_FAILURES=%lu\r\n",
                (unsigned long)uart_error_check_failures);
    diag_puts("---\r\n");
}

int main(void)
{
    if (!device_is_ready(diag_uart)) {
        return 0;
    }

    const struct uart_config config = {
        .baudrate = DIAG_BAUDRATE,
        .parity = UART_CFG_PARITY_NONE,
        .stop_bits = UART_CFG_STOP_BITS_1,
        .data_bits = UART_CFG_DATA_BITS_8,
        .flow_ctrl = UART_CFG_FLOW_CTRL_NONE,
    };

    const int config_result = uart_configure(diag_uart, &config);
    const int callback_result = uart_irq_callback_user_data_set(
        diag_uart, uart_irq_callback, NULL);

    diag_puts("\r\n=== USART2 Adalight parser diagnostic ===\r\n");
    diag_printf("UART_CONFIG_RESULT=%d\r\n", config_result);
    diag_printf("UART_CALLBACK_RESULT=%d\r\n", callback_result);
    diag_puts("RX_PIN_CONFIGURED=PA15\r\n");
    diag_puts("PROBE_COMPARE=PA15,PA3\r\n");

    if ((config_result != 0) || (callback_result != 0)) {
        diag_puts("UART_DIAGNOSTIC_READY=NO\r\n");
        return 0;
    }

    frame_ready = 0U;
    uart_irq_err_enable(diag_uart);
    uart_irq_rx_enable(diag_uart);
    diag_puts("UART_DIAGNOSTIC_READY=YES\r\n");

    while (1) {
        report_counters();
        k_sleep(K_MSEC(500));
    }
}
