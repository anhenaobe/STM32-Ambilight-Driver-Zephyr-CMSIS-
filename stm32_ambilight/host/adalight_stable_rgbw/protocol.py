"""Adalight RGBW serial protocol helpers."""

from __future__ import annotations

import time

import numpy as np
import serial

from .config import (
    BAUD_RATE,
    BYTES_PER_LED,
    LED_COLOR_ORDER,
    SERIAL_PORT,
    SERIAL_TIMEOUT_SECONDS,
    TOTAL_LEDS,
    USE_WHITE_CHANNEL,
)


class AdalightFrameBuilder:
    """Builds RGBW Adalight packets while reusing frame buffers."""

    def __init__(self, num_leds: int, header: bytes) -> None:
        self.num_leds = num_leds
        self.header = header
        self.payload = np.zeros((num_leds, BYTES_PER_LED), dtype=np.uint8)
        self.packet = bytearray(len(header) + (num_leds * BYTES_PER_LED))
        self.packet_view = memoryview(self.packet)
        self.packet[: len(header)] = header
        self.channel_indices = tuple("RGBW".index(channel) for channel in LED_COLOR_ORDER)

    def _fill_payload(self, colors_rgb: np.ndarray) -> None:
        """Ordena RGB de pantalla al orden fisico RGBW/GRBW de la tira."""
        if colors_rgb.shape != (self.num_leds, 3):
            raise ValueError(f"colors_rgb debe tener forma ({self.num_leds}, 3).")

        self.payload[:, 0:3] = colors_rgb
        self.payload[:, 3] = 0
        self.payload[:] = self.payload[:, self.channel_indices]

    def build_payload(self, colors_rgb: np.ndarray) -> bytes:
        """Convierte un arreglo RGB uint8 al payload RGBW reutilizando buffer."""
        if USE_WHITE_CHANNEL:
            raise ValueError("USE_WHITE_CHANNEL debe permanecer False durante calibracion.")

        self._fill_payload(colors_rgb)
        return self.payload.ravel().tobytes()

    def build_packet(self, colors_rgb: np.ndarray) -> memoryview:
        """Devuelve un frame Adalight completo como vista escribible."""
        self._fill_payload(colors_rgb)
        payload_view = memoryview(self.payload).cast("B")
        self.packet_view[len(self.header) :] = payload_view
        return self.packet_view


def build_adalight_header(num_leds: int) -> bytes:
    """Construye el encabezado exacto: b'Ada' + high + low + checksum."""
    if num_leds <= 0:
        raise ValueError("TOTAL_LEDS debe ser mayor que cero.")

    count = num_leds - 1
    high = (count >> 8) & 0xFF
    low = count & 0xFF
    checksum = high ^ low ^ 0x55
    return b"Ada" + bytes((high, low, checksum))


def open_serial() -> serial.Serial:
    """Abre el puerto serie hacia la STM32."""
    print(f"Abriendo {SERIAL_PORT} a {BAUD_RATE} baudios...")
    port = serial.Serial(
        SERIAL_PORT,
        BAUD_RATE,
        timeout=SERIAL_TIMEOUT_SECONDS,
        write_timeout=SERIAL_TIMEOUT_SECONDS,
    )
    time.sleep(2.0)
    print("Puerto serial listo.")
    return port


def build_rgbw_payload(colors_rgb: np.ndarray) -> bytes:
    """Compatibilidad: construye un payload RGBW/GRBW nuevo desde colores RGB."""
    builder = AdalightFrameBuilder(TOTAL_LEDS, build_adalight_header(TOTAL_LEDS))
    return builder.build_payload(colors_rgb)


def send_adalight_frame(
    port: serial.Serial,
    frame_builder: AdalightFrameBuilder,
    colors_rgb: np.ndarray,
) -> int:
    """Envia un frame Adalight completo y devuelve los bytes escritos."""
    return port.write(frame_builder.build_packet(colors_rgb))


def send_black_frame(port: serial.Serial, frame_builder: AdalightFrameBuilder) -> None:
    """Apaga la tira con un frame negro RGBW."""
    black = np.zeros((frame_builder.num_leds, 3), dtype=np.uint8)
    send_adalight_frame(port, frame_builder, black)
