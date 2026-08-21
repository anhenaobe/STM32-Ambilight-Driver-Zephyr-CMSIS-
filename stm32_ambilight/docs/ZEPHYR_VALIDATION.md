# Zephyr hardware validation

## Scope

- Target: ST Nucleo-L432KC / STM32L432KC.
- Firmware: the Zephyr `nucleo_l432kc` environment in this repository.
- Data path: USART2 Adalight RGBW input, parser, PWM translation, DMA1 Channel
  2, TIM2 update requests, TIM2_CH2/PB3, and the SK6812 RGBW strip.

This record summarizes the hardware evidence used to close the Zephyr
implementation. It does not claim certification or validation on other MCU or
board variants.

## Observed failure

The initial Zephyr implementation configured and started DMA without returning
an API error, but the transfer count did not advance. The focused diagnostic
recorded:

- `dma_config()` and `dma_start()` returned success;
- `DMA1_CSELR` selected `C2S=13` for DMA1 Channel 2;
- `CNDTR` remained at 3939 before and after the observation interval;
- TIM2 update DMA requests remained enabled;
- PB3 produced continuous PWM at approximately 800 kHz with an approximately
  1.25 microsecond period and 60% duty cycle.

That evidence isolated the fault to DMA request routing rather than TIM2,
TIM2_CH2, CCR2, or the PB3 pin configuration.

USART2 and the parser were validated independently on the same target:

- one complete 486-byte frame produced one valid frame with zero UART errors;
- the same frame split across 37 writes produced one valid frame with zero
  UART errors;
- two back-to-back frames (972 bytes) produced two valid frames with zero UART
  errors;
- no overrun, framing, parity, break, noise, or collision errors were observed
  in those cases.

## Root cause and correction

STM32L432 DMA1 uses `DMA1_CSELR`; it does not use a DMAMUX. Zephyr's STM32 V2
DMA driver forwards `dma_slot` as the peripheral request selection. The former
DMAMUX-style value `61` therefore selected `C2S=13`, not `TIM2_UP`.

The correction defines `PWM_DMA_SLOT_TIM2_UP` as request selection `4`, matching
the STM32L432 mapping and the functional CMSIS implementation. Production code
and the focused DMA diagnostic share that definition.

## Final result

The corrected Zephyr firmware was retested on the STM32L432KC hardware. The
end-to-end Zephyr path received Adalight frames and drove the SK6812 RGBW strip
correctly. This closes the original functional failure for the tested hardware
configuration.

## Evidence in the repository

- Production correction: `zephyr_platformio/include/bsp/dma.h` and
  `zephyr_platformio/src/bsp/dma.c`.
- DMA/TIM2 diagnostic: `zephyr_platformio/test/pb3_pwm_dma/main.c`.
- UART/parser diagnostic: `zephyr_platformio/test/uart_parser_diagnostics/main.c`.
- Deterministic host stimulus: `host/zephyr_link_test.py`.
- Combined peripheral diagnostic:
  `zephyr_platformio/test/peripheral_diagnostics/main.c`.

## Remaining limits

- The result applies to the documented STM32L432KC board, pin mapping, UART
  rate, and 120-LED RGBW configuration.
- Long-duration stress, malformed-frame fault injection, electrical compliance,
  and product certification were not part of this validation.
- Host COM port, monitor, capture backend, and output selection remain local
  configuration rather than board-independent defaults.
