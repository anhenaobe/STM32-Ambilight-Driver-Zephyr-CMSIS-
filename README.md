# STM32 Ambilight Driver

An Ambilight-style system that captures display-edge colors on a host PC and
streams Adalight RGBW frames over UART to an STM32L432KC. The microcontroller
translates each frame into the 800 kHz waveform required by a 120-LED SK6812
RGBW strip using TIM2, PWM, and DMA.

| Implementation | Location | Status |
| --- | --- | --- |
| CMSIS | [`stm32_ambilight/cmsis_platformio`](stm32_ambilight/cmsis_platformio) | Functional, hardware-demonstrated reference implementation. |
| Zephyr | [`stm32_ambilight/zephyr_platformio`](stm32_ambilight/zephyr_platformio) | Functional on STM32L432KC hardware after correcting the TIM2 update DMA request selection. |

The Zephyr failure was isolated systematically: UART and TIM2/PB3 operated
correctly, but DMA transfer count did not advance even though configuration
calls succeeded. On STM32L432, `TIM2_UP` must select request 4 through
`DMA1_CSELR`; the previous DMAMUX-style value selected the wrong request. See
the concise [Zephyr hardware validation record](stm32_ambilight/docs/ZEPHYR_VALIDATION.md).

## System overview

```text
Host screen capture -> edge-color processing -> Adalight RGBW over UART
                    -> STM32 frame parser -> RGBW-to-PWM translation
                    -> DMA + TIM2_CH2 -> PB3 -> SK6812 RGBW strip
```

The host sends an `Ada` frame containing four color bytes per LED. Firmware
validates the header, length, and checksum, converts the RGBW payload into PWM
duty-cycle samples, and transfers those samples to `TIM2->CCR2` through DMA.

## Hardware

- STM32L432KC development board (`nucleo_l432kc` PlatformIO target).
- 120-LED SK6812 RGBW strip.
- External 5 V supply rated for the LED load; the wiring guide specifies 10 A
  or higher for this installation.
- Data output on `PB3 / TIM2_CH2` through a 300 ohm series resistor.
- Common ground between the STM32, LED strip, and external supply.

Read the [wiring guide](stm32_ambilight/hardware/WIRING.md) before powering the
strip.

## Repository layout

```text
stm32_ambilight/
├── cmsis_platformio/     CMSIS reference firmware and demonstration video
├── zephyr_platformio/    Hardware-validated Zephyr firmware and diagnostics
├── host/                 Python screen capture and Adalight senders
├── hardware/             Wiring and power documentation
└── docs/                 Architecture and validation records
```

## Build and run

Both firmware implementations target PlatformIO's `nucleo_l432kc` board.

```powershell
cd stm32_ambilight\cmsis_platformio
pio run -e nucleo_l432kc

cd ..\zephyr_platformio
pio run -e nucleo_l432kc
```

Install the host dependencies and review the machine-specific defaults before
running the modular sender:

```powershell
python -m pip install -r stm32_ambilight\host\requirements.txt
python stm32_ambilight\host\adalight_stable_rgbw.py
```

Serial port, LED layout, capture backend, monitor/output selection, and visual
calibration are intentionally configured in
[`host/adalight_stable_rgbw/config.py`](stm32_ambilight/host/adalight_stable_rgbw/config.py).

## Demonstration and documentation

- [Ambilight hardware demonstration video](stm32_ambilight/cmsis_platformio/assets/videos/ambilight_program.mp4)
- [Technical documentation](stm32_ambilight/docs/TECHNICAL_DOCUMENTATION.md)
- [Zephyr hardware validation](stm32_ambilight/docs/ZEPHYR_VALIDATION.md)
- [Wiring guide](stm32_ambilight/hardware/WIRING.md)
- [Zephyr build and diagnostic notes](stm32_ambilight/zephyr_platformio/README.md)

## Validation boundary

CMSIS and the corrected Zephyr implementation have both operated the project
hardware. The Zephyr validation establishes the tested STM32L432KC UART,
parser, TIM2/PWM, DMA, PB3, and LED-output path; it is not a claim of product
certification, exhaustive fault-injection coverage, or operation on other MCU
variants. Host capture settings remain machine-specific and must be reviewed
on another PC.

## License

This project is distributed under the [GNU General Public License v3.0](LICENSE).
