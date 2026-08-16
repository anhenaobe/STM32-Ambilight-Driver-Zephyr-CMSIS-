# STM32 Ambilight: Zephyr implementation

This directory contains the Zephyr-based implementation of the STM32 Ambilight firmware. It is a development path, not the stable reference implementation.

## Status

The CMSIS implementation in [`../cmsis_platformio/`](../cmsis_platformio/) is the currently functional and stable version. The Zephyr implementation is retained for debugging and further development; it requires additional build and hardware validation before it can be considered equivalent.

No attempt is made here to conceal that difference or to present the Zephyr source as production-ready.

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
- `uart_echo`, `pb3_gpio`, `pb3_pwm_registers`, `pb3_pwm_zephyr`, and `pb3_pwm_dma`: focused diagnostics.

The configuration targets PlatformIO's `nucleo_l432kc` board environment. When PlatformIO and the required framework packages are already installed, build an environment from this directory, for example:

```powershell
pio run -e peripheral_diagnostics
```

These commands are source-defined entry points only; they do not imply that the Zephyr implementation currently builds successfully or drives the LEDs correctly.

## Related documentation

- [Repository overview](../../README.md)
- [Technical documentation](../docs/TECHNICAL_DOCUMENTATION.md)
- [Peripheral diagnostics notes](test/peripheral_diagnostics/README.md)

