# STM32 Ambilight: Zephyr implementation

This directory contains the hardware-validated Zephyr-based implementation of the STM32 Ambilight firmware for the STM32L432KC.

## Status

The main Zephyr firmware completes the end-to-end host UART to SK6812 RGBW output path on physical STM32L432KC hardware. During bring-up, TIM2 generated the expected PB3 waveform and the UART/parser path worked, but DMA did not advance because the `TIM2_UP` request was assigned the wrong STM32L4 DMA request value. Selecting request 4 corrected the transfer and produced working LED output.

The CMSIS implementation in [`../cmsis_platformio/`](../cmsis_platformio/) remains the register-level reference implementation. See the concise [Zephyr validation record](../docs/ZEPHYR_VALIDATION.md) for measured evidence and limits.

## Intended data path

```text
Host PC -> UART -> Adalight parser -> RGBW buffer -> PWM samples
        -> DMA -> TIM2_CH2 / PB3 -> SK6812 RGBW strip
```

`src/app/` contains the parser and RGBW-to-PWM translation. `src/bsp/` contains the Zephyr-facing UART, PWM, and DMA components. Zephyr configuration lives in `zephyr/`, while diagnostic entry points are under `test/`.

## PlatformIO environments

`platformio.ini` declares the following environments:

- `nucleo_l432kc`: main Zephyr firmware.
- `peripheral_diagnostics`: combined parser, timer, and DMA diagnostics.
- `uart_echo`, `uart_parser_diagnostics`, `pb3_gpio`, `pb3_pwm_registers`, `pb3_pwm_zephyr`, and `pb3_pwm_dma`: focused diagnostics.

The configuration targets PlatformIO's `nucleo_l432kc` board environment. When PlatformIO and the required framework packages are already installed, build an environment from this directory, for example:

```powershell
pio run -e nucleo_l432kc
```

The diagnostic environments are retained as focused engineering evidence; they are not alternative product firmware.

## Related documentation

- [Repository overview](../../README.md)
- [Technical documentation](../docs/TECHNICAL_DOCUMENTATION.md)
- [Zephyr hardware validation](../docs/ZEPHYR_VALIDATION.md)
- [Peripheral diagnostics notes](test/peripheral_diagnostics/README.md)
