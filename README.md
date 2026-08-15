# STM32 Ambilight Driver

Firmware and host-side tools for an Ambilight-style system that drives a 120-LED SK6812 RGBW strip from Adalight RGBW frames received over UART.

| Implementation | Location | Status |
| --- | --- | --- |
| CMSIS | [`stm32_ambilight/cmsis_platformio`](stm32_ambilight/cmsis_platformio) | Functional and currently the stable reference implementation. |
| Zephyr | [`stm32_ambilight/zephyr_platformio`](stm32_ambilight/zephyr_platformio) | In development; it requires further debugging before it can be considered equivalent to the CMSIS implementation. |

This distinction is intentional. The Zephyr implementation is included as development work, not presented as a completed replacement for the stable CMSIS firmware.

## System overview

```text
Host PC -> UART / Adalight RGBW frame -> STM32 parser -> RGBW-to-PWM translation
        -> DMA + TIM2_CH2 -> PB3 -> SK6812 RGBW LED strip
```

The host sends an `Ada` frame containing four color bytes per LED. Firmware validates the header, length, and checksum, then converts the RGBW payload into PWM duty-cycle samples. DMA feeds `TIM2->CCR2`, which produces the SK6812 waveform on `PB3 / TIM2_CH2`.

## Hardware

- STM32L432KC development board.
- 120-LED SK6812 RGBW strip.
- External 5 V supply rated for the LED load (the wiring guide specifies 10 A or higher).
- Data output: `PB3 / TIM2_CH2` through a 300 ohm series resistor.
- Common ground between the STM32, LED strip, and external supply.

See the [wiring guide](stm32_ambilight/hardware/WIRING.md) before powering the strip.

## Repository layout

```text
stm32_ambilight/
├── cmsis_platformio/     Stable CMSIS firmware and PlatformIO configuration
├── zephyr_platformio/    Zephyr firmware under development and diagnostic targets
├── host/                 Python senders and screen-capture utilities
├── hardware/             Wiring documentation
└── docs/                 Architecture and protocol documentation
```

## Build information

Both firmware directories contain a `platformio.ini` file targeting PlatformIO's `nucleo_l432kc` board environment.

Build the stable CMSIS firmware from its directory:

```powershell
cd stm32_ambilight\cmsis_platformio
pio run -e nucleo_l432kc
```

The Zephyr directory defines a corresponding main environment and several diagnostic environments. Its source and configuration are retained for debugging, but a successful build or hardware result is not claimed here. See its [implementation notes](stm32_ambilight/zephyr_platformio/README.md).

The host tools are Python source files. Their current imports require `numpy`, `mss`, and `pyserial`; `dxcam` is used by the configurable DXGI capture backend. No locked Python dependency set is currently provided, so host execution remains environment-dependent.

## Documentation

- [Technical documentation](stm32_ambilight/docs/TECHNICAL_DOCUMENTATION.md): architecture, protocol, implementation boundaries, and status.
- [Wiring guide](stm32_ambilight/hardware/WIRING.md): power, ground, and signal connections.
- [Zephyr notes](stm32_ambilight/zephyr_platformio/README.md): available PlatformIO environments and diagnostic targets.

## Current limitations and next steps

- The CMSIS implementation is the stable reference; its behavior should be preserved when comparing future work.
- The Zephyr implementation needs debugging and validation on the target hardware.
- Host configuration currently includes machine-specific serial and capture settings; review `stm32_ambilight/host/adalight_stable_rgbw/config.py` before running it on another PC.
- Future work should add repeatable firmware validation and a pinned host dependency environment without changing the established protocol or hardware timing accidentally.

## License

This project is distributed under the [Apache License 2.0](LICENSE).
