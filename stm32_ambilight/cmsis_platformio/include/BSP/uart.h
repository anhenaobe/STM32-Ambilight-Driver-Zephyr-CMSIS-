#ifndef UART_H
#define UART_H

#include "stm32l4xx.h"

typedef void (*uart_rx_callback_t)(uint8_t byte);

void uart_init(void);
void uart_set_rx_callback(uart_rx_callback_t callback);

#define CLOCK_SPEED 80000000
#define BAUDS 921600

#endif