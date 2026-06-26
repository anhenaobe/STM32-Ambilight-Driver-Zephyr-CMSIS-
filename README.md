# STM32 Ambilight

This repository contains the STM32 firmware and supporting documentation for an Ambilight system that drives a 120-LED SK6812 RGBW LED strip from Adalight RGBW frames sent by a Host PC.

The project is organized around two firmware implementations with the same functional contract:

- `cmsis_platformio/`: CMSIS implementation using register-level programming for low-level control.
- `zephyr_platformio/`: Zephyr implementation using DeviceTree, Zephyr drivers, and a compatible BSP.

The Host PC sends RGBW frames over UART. The STM32 receives each frame, validates the Adalight protocol, expands RGBW bytes into PWM duty cycle samples, and uses DMA with `TIM2` to generate the SK6812 waveform on `PB3 / TIM2_CH2`.

## Documentation

- [Technical Documentation](docs/TECHNICAL_DOCUMENTATION.md): full system architecture, firmware flow, protocol, diagnostics, and CMSIS versus Zephyr comparison.
- [Wiring Guide](hardware/WIRING.md): physical wiring, power supply, common ground, power injection, and signal notes.
- [Zephyr PlatformIO README](zephyr_platformio/README.md): concise firmware overview and PlatformIO commands for the Zephyr implementation.

## Core Data Path

```text
Host PC -> UART -> Adalight parser -> RGBW color buffer -> PWM buffer -> DMA/TIM2 -> PB3 -> SK6812 LED strip
```

## Hardware Summary

- LED controller: STM32L432KC.
- LED strip: SK6812 RGBW, 120 LEDs.
- Data output: `PB3 / TIM2_CH2`.
- LED power: external 5V power supply rated for 10A or higher.
- Required ground reference: common ground between the power supply, LED strip, and STM32.

## Build Entry Points

The Zephyr implementation is the current PlatformIO firmware path:

```powershell
cd zephyr_platformio
pio run -e nucleo_l432kc
```

Diagnostic environments are also defined under `zephyr_platformio/platformio.ini`.
