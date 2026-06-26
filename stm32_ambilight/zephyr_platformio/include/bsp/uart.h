#ifndef BSP_UART_H
#define BSP_UART_H

#include <stdint.h>

#define CLOCK_SPEED 80000000U
#define BAUDS 921600U

typedef void (*uart_rx_callback_t)(uint8_t data);

void uart_init(void);
void uart_set_rx_callback(uart_rx_callback_t callback);

#endif
