# Ambilight STM32 Zephyr

This project implements the current firmware for an Ambilight system that controls an addressable RGBW LED strip. The STM32 receives serial frames compatible with Adalight, validates the header and length, converts RGBW bytes into PWM samples, and uses DMA to feed `TIM2->CCR2`. The physical output to the LED strip is `PB3 / TIM2_CH2`.

The complete technical documentation is available at:

[Technical Documentation](../docs/TECHNICAL_DOCUMENTATION.md)

## What It Does

The functional flow is:

```text
Host PC / Ambilight tool
  -> UART 921600 baud
  -> Adalight RGBW frame
  -> Adalight parser on STM32
  -> color buffer
  -> RGBW-to-PWM conversion
  -> DMA + TIM2_CH2
  -> PB3
  -> SK6812/RGBW LED strip
```

The firmware does not calculate the visual content. It only receives already ordered color bytes from the host, accepts valid frames, and generates the timed signal understood by the LED strip.

## Current State

- Main implementation: Zephyr on PlatformIO.
- Default environment: `nucleo_l432kc`.
- Target MCU documented for this version: STM32L432KC.
- Input protocol: Adalight with `Ada` header.
- Active LEDs: `120`.
- Color format: `RGBW`, 4 bytes per LED.
- Payload per frame: `480` bytes.
- PWM buffer: `3940` samples, including the reset/latch zone.
- UART: `USART2` at `921600` baud.
- LED output: `PB3 / TIM2_CH2`.

## Main Structure

- `src/main.c`: initializes the BSP, registers the UART callback, processes complete frames, and triggers DMA.
- `src/app/adalight.c`: FSM that validates the Adalight protocol and fills the RGBW buffer.
- `src/app/translator.c`: expands each RGBW bit into PWM samples.
- `src/bsp/uart.c`: UART adapter over Zephyr.
- `src/bsp/pwm.c`: PWM/TIM2 configuration.
- `src/bsp/dma.c`: DMA transfer toward the PWM compare register.
- `zephyr/prj.conf`: Zephyr options required for UART, DMA, and PWM.
- `zephyr/app.overlay`: enables USART2, DMA1, and TIM2/PB3 in DeviceTree.
- `test/`: diagnostic firmware for UART, PB3, PWM, and DMA.

The technical documentation also describes Python host tools for generating Ambilight frames from the screen, simulating colors, and running diagnostics. In the current copy of this project, the `scripts/` directory is not present in the file tree, so this README primarily documents the firmware present in this repository.

## Useful Commands

Build the main firmware:

```powershell
pio run -e nucleo_l432kc
```

Build diagnostic tests:

```powershell
pio run -e uart_echo
pio run -e pb3_gpio
pio run -e pb3_pwm_zephyr
pio run -e pb3_pwm_dma
pio run -e peripheral_diagnostics
```

Monitor serial output:

```powershell
pio device monitor -e nucleo_l432kc
```

## Diagnostic Notes

The main firmware prints diagnostic counters over UART: received bytes, parsed frames, processed frames, and DMA status. If the LED strip does not respond, the recommended path is to isolate the failure by stage:

1. UART receives bytes.
2. The FSM accepts Adalight frames.
3. The translator generates the PWM buffer.
4. DMA updates `TIM2->CCR2`.
5. `PB3 / TIM2_CH2` emits the waveform toward the LED strip.

The original CMSIS version and the full explanation of architecture, protocol, timing, and host tools remain in [Technical Documentation](../docs/TECHNICAL_DOCUMENTATION.md).

