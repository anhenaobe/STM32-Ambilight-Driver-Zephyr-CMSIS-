# Peripheral Diagnostics Firmware

This directory contains an alternative Zephyr `main.c` for step-by-step hardware
diagnostics. It is intentionally kept outside `src/` so the production firmware
entry point remains unchanged.

Build it with:

```powershell
C:\Users\justa\.platformio\penv\Scripts\platformio.exe run -e peripheral_diagnostics
```

Upload it with:

```powershell
C:\Users\justa\.platformio\penv\Scripts\platformio.exe run -e peripheral_diagnostics --target upload
```

Runtime checks:

1. USART2 TX prints diagnostic status messages at `921600` baud.
2. `diag_test_app_parser_and_translator()` feeds a synthetic Adalight frame into
   the app parser and verifies representative PWM samples.
3. `diag_test_pwm_timer()` changes `TIM2->CCR2` directly so PB3/TIM2_CH2 should
   show visible duty changes.
4. `diag_test_dma_to_pwm()` starts a short DMA transfer into `TIM2->CCR2`.
5. The final loop accepts real frames from `scripts/adalight_sim.py`, translates
   them, and sends them through the PWM DMA path.

Expected serial settings:

- Port: the board virtual COM port
- Baud: `921600`
- Data: `8N1`
