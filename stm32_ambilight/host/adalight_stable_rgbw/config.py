"""Runtime configuration for the Ambilight RGBW sender."""

from __future__ import annotations

# Serial settings must match the STM32 firmware.
SERIAL_PORT = "COM8"
BAUD_RATE = 921600
SERIAL_RETRY_SECONDS = 2.0
SERIAL_TIMEOUT_SECONDS = 1.0

# Active LED layout around the display.
LEDS_BOTTOM = 38
LEDS_RIGHT = 22
LEDS_TOP = 38
LEDS_LEFT = 22
TOTAL_LEDS = LEDS_BOTTOM + LEDS_RIGHT + LEDS_TOP + LEDS_LEFT

# Physical byte order expected by the LED strip.
# Many SK6812 RGBW strips expect GRBW: green, red, blue, white.
LED_COLOR_ORDER = "GRBW"
BYTES_PER_LED = 4
USE_WHITE_CHANNEL = False

MONITOR_INDEX = 2
BORDER_SIZE_PX = 40
DOWNSAMPLE_STEP = 6
TRIM_PERCENT = 8.0
CAPTURE_BACKEND = "dxcam"
CAPTURE_MODE = "edges"
# dxcam uses device/output indexes independent from mss monitor indexes.
# Current mapping: Device[0] = RTX 4050, Output[0] = 2560x1440 monitor.
DXCAM_DEVICE_IDX = 0
DXCAM_OUTPUT_IDX = 0
DXCAM_PROCESSOR_BACKEND = "numpy"
LIST_MONITORS_ON_START = True

GAMMA = 2.2
SATURATION_BOOST = 1.18
BRIGHTNESS = 0.75

SMOOTHING_ALPHA = 0.25
SMOOTHING_ALPHA_RISE = 0.22
SMOOTHING_ALPHA_FALL = 0.14
COLOR_DEADBAND = 4.0
MAX_COLOR_STEP = 18.0
TARGET_FPS = 60

DEBUG = True
DEBUG_INTERVAL_SECONDS = 1.0
READ_MCU_LOGS = True
MCU_LOG_PREFIX = "[MCU]"


def validate_config() -> None:
    """Valida que la configuracion sea coherente antes de iniciar."""
    if TOTAL_LEDS != (LEDS_BOTTOM + LEDS_RIGHT + LEDS_TOP + LEDS_LEFT):
        raise ValueError("TOTAL_LEDS no coincide con la suma de LEDs por lado.")
    if BYTES_PER_LED != 4:
        raise ValueError("Este script esta fijado para RGBW de 4 bytes por LED.")
    if sorted(LED_COLOR_ORDER) != ["B", "G", "R", "W"] or len(LED_COLOR_ORDER) != 4:
        raise ValueError("LED_COLOR_ORDER debe contener exactamente R, G, B y W.")
    if USE_WHITE_CHANNEL:
        raise ValueError("USE_WHITE_CHANNEL debe ser False durante calibracion.")
    for name, value in (
        ("SMOOTHING_ALPHA", SMOOTHING_ALPHA),
        ("SMOOTHING_ALPHA_RISE", SMOOTHING_ALPHA_RISE),
        ("SMOOTHING_ALPHA_FALL", SMOOTHING_ALPHA_FALL),
    ):
        if not 0.0 < value <= 1.0:
            raise ValueError(f"{name} debe estar en el rango (0, 1].")
    if COLOR_DEADBAND < 0.0:
        raise ValueError("COLOR_DEADBAND no puede ser negativo.")
    if MAX_COLOR_STEP <= 0.0:
        raise ValueError("MAX_COLOR_STEP debe ser mayor que cero.")
    if not 0.0 < BRIGHTNESS <= 1.0:
        raise ValueError("BRIGHTNESS debe estar en el rango (0, 1].")
    if TARGET_FPS <= 0:
        raise ValueError("TARGET_FPS debe ser mayor que cero.")
    if DOWNSAMPLE_STEP <= 0:
        raise ValueError("DOWNSAMPLE_STEP debe ser mayor que cero.")
    if CAPTURE_BACKEND not in {"mss", "dxcam"}:
        raise ValueError('CAPTURE_BACKEND debe ser "mss" o "dxcam".')
    if CAPTURE_MODE not in {"single", "edges"}:
        raise ValueError('CAPTURE_MODE debe ser "single" o "edges".')
    if DXCAM_DEVICE_IDX < 0:
        raise ValueError("DXCAM_DEVICE_IDX no puede ser negativo.")
    if DXCAM_OUTPUT_IDX < 0:
        raise ValueError("DXCAM_OUTPUT_IDX no puede ser negativo.")
    if DXCAM_PROCESSOR_BACKEND not in {"cv2", "numpy"}:
        raise ValueError('DXCAM_PROCESSOR_BACKEND debe ser "cv2" o "numpy".')
