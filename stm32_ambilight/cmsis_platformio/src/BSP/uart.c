#include "BSP/uart.h"

static uart_rx_callback_t app_rx_callback = 0;

void uart_init(void) {
    RCC->AHB2ENR |= RCC_AHB2ENR_GPIOAEN;
    RCC->APB1ENR1 |= RCC_APB1ENR1_USART2EN;

    GPIOA->MODER &= ~GPIO_MODER_MODE2_Msk;
    GPIOA->MODER |= (2U << GPIO_MODER_MODE2_Pos);
    GPIOA->OSPEEDR |= (3U << GPIO_OSPEEDR_OSPEED2_Pos);
    GPIOA->AFR[0] &= ~GPIO_AFRL_AFSEL2_Msk;
    GPIOA->AFR[0] |= (7U << GPIO_AFRL_AFSEL2_Pos);

    GPIOA->MODER &= ~GPIO_MODER_MODE3_Msk;
    GPIOA->MODER |= (2U << GPIO_MODER_MODE3_Pos);
    GPIOA->AFR[0] &= ~GPIO_AFRL_AFSEL3_Msk;
    GPIOA->AFR[0] |= (7U << GPIO_AFRL_AFSEL3_Pos);

    // PA15 is kept in AF3 as an alternate USART2 RX route for the Nucleo wiring.
    GPIOA->MODER &= ~GPIO_MODER_MODE15_Msk;
    GPIOA->MODER |= (2U << GPIO_MODER_MODE15_Pos);
    GPIOA->AFR[1] &= ~GPIO_AFRH_AFSEL15_Msk;
    GPIOA->AFR[1] |= (3U << GPIO_AFRH_AFSEL15_Pos);

    USART2->CR1 &= ~USART_CR1_UE;
    USART2->BRR = CLOCK_SPEED / BAUDS;
    USART2->CR1 &= ~(USART_CR1_M1 | USART_CR1_M0);
    USART2->CR1 &= ~USART_CR1_PCE;
    USART2->CR2 &= ~USART_CR2_STOP;
    USART2->CR1 |= USART_CR1_RXNEIE;
    USART2->CR1 |= USART_CR1_TE | USART_CR1_RE;
    USART2->CR1 |= USART_CR1_UE;

    NVIC_SetPriority(USART2_IRQn, 1);
    NVIC_EnableIRQ(USART2_IRQn);
}

void uart_set_rx_callback(uart_rx_callback_t callback) {
    app_rx_callback = callback;
}

void USART2_IRQHandler(void) {
    if (USART2->ISR & USART_ISR_RXNE) {
        uint8_t received_data = (uint8_t)(USART2->RDR & 0xFF);

        if (app_rx_callback) {
            app_rx_callback(received_data);
        }
    }
}