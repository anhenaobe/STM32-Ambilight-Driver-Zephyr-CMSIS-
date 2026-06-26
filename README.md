# Ambilight STM32 Zephyr

Este proyecto implementa el firmware actual de un sistema Ambilight para una tira LED RGBW direccionable. La placa STM32 recibe frames seriales compatibles con Adalight, valida el encabezado y la longitud, convierte los bytes RGBW a muestras PWM y usa DMA para alimentar `TIM2->CCR2`. La salida fisica hacia la tira sale por `PB3 / TIM2_CH2`.

La documentacion tecnica completa esta en:

`docs/TECHNICAL_DOCUMENTATION.md`

## Que hace

El flujo funcional es:

```text
PC / herramienta Ambilight
  -> UART 921600 baudios
  -> frame Adalight RGBW
  -> parser Adalight en STM32
  -> buffer de color
  -> conversion RGBW a PWM
  -> DMA + TIM2_CH2
  -> PB3
  -> tira LED SK6812/RGBW
```

El firmware no calcula el contenido visual. Solo recibe bytes de color ya ordenados desde el host, acepta frames validos y genera la senal temporizada que entiende la tira LED.

## Estado actual

- Implementacion principal: Zephyr sobre PlatformIO.
- Entorno por defecto: `nucleo_l432kc`.
- MCU objetivo documentado para esta version: STM32L432KC.
- Protocolo de entrada: Adalight con encabezado `Ada`.
- LEDs activos: `120`.
- Formato de color: `RGBW`, 4 bytes por LED.
- Payload por frame: `480` bytes.
- Buffer PWM: `3940` muestras, incluyendo zona de reset/latch.
- UART: `USART2` a `921600` baudios.
- Salida LED: `PB3 / TIM2_CH2`.

## Estructura principal

- `src/main.c`: inicializa BSP, registra el callback UART, procesa frames completos y dispara DMA.
- `src/app/adalight.c`: FSM que valida el protocolo Adalight y llena el buffer RGBW.
- `src/app/translator.c`: expande cada bit RGBW a muestras PWM.
- `src/bsp/uart.c`: adaptador UART sobre Zephyr.
- `src/bsp/pwm.c`: configuracion de PWM/TIM2.
- `src/bsp/dma.c`: transferencia DMA hacia el registro de comparacion PWM.
- `zephyr/prj.conf`: opciones Zephyr necesarias para UART, DMA y PWM.
- `zephyr/app.overlay`: habilita USART2, DMA1 y TIM2/PB3 en DeviceTree.
- `test/`: firmwares de diagnostico para UART, PB3, PWM y DMA.

El documento tecnico tambien describe herramientas Python de host para generar frames Ambilight desde la pantalla, simular colores y ejecutar diagnosticos. En la copia actual leida del proyecto, el directorio `scripts/` no aparece en el arbol de archivos, por lo que este README documenta principalmente el firmware presente en este repositorio.

## Comandos utiles

Compilar el firmware principal:

```powershell
pio run -e nucleo_l432kc
```

Compilar pruebas de diagnostico:

```powershell
pio run -e uart_echo
pio run -e pb3_gpio
pio run -e pb3_pwm_zephyr
pio run -e pb3_pwm_dma
pio run -e peripheral_diagnostics
```

Monitorear la salida serial:

```powershell
pio device monitor -e nucleo_l432kc
```

## Notas de diagnostico

El firmware principal imprime contadores de diagnostico por UART: bytes recibidos, frames parseados, frames procesados y estado de DMA. Si la tira no responde, el camino recomendado es aislar la falla por etapas:

1. UART recibe bytes.
2. La FSM acepta frames Adalight.
3. El translator genera el buffer PWM.
4. DMA actualiza `TIM2->CCR2`.
5. `PB3 / TIM2_CH2` emite la forma de onda hacia la tira.

La version CMSIS original y la explicacion larga de arquitectura, protocolo, temporizacion y herramientas host permanecen en `docs/TECHNICAL_DOCUMENTATION.md`.

