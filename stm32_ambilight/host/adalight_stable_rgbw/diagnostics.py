"""Runtime diagnostics for the Ambilight loop."""

from __future__ import annotations

from dataclasses import dataclass

import serial

from .config import DEBUG, DEBUG_INTERVAL_SECONDS, MCU_LOG_PREFIX, READ_MCU_LOGS


@dataclass
class Diagnostics:
    """Acumula tiempos y bytes para imprimir diagnostico periodico."""

    frames: int = 0
    bytes_sent: int = 0
    capture_seconds: float = 0.0
    processing_seconds: float = 0.0
    transmit_seconds: float = 0.0
    last_report: float = 0.0

    def reset(self, now: float) -> None:
        self.frames = 0
        self.bytes_sent = 0
        self.capture_seconds = 0.0
        self.processing_seconds = 0.0
        self.transmit_seconds = 0.0
        self.last_report = now


class McuLogReader:
    """Lee diagnosticos de la STM32 sin bloquear el loop de captura."""

    def __init__(self) -> None:
        self._pending = bytearray()

    def poll(self, port: serial.Serial) -> None:
        """Imprime lineas completas recibidas desde el firmware."""
        if not READ_MCU_LOGS:
            return

        waiting = port.in_waiting
        if waiting <= 0:
            return

        self._pending.extend(port.read(waiting))

        while True:
            newline_index = self._pending.find(b"\n")
            if newline_index < 0:
                break

            raw_line = bytes(self._pending[:newline_index])
            del self._pending[: newline_index + 1]

            line = raw_line.rstrip(b"\r").decode("utf-8", errors="replace")
            if line:
                print(f"{MCU_LOG_PREFIX} {line}")


def report_debug(diag: Diagnostics, now: float) -> None:
    """Imprime metricas de rendimiento cada DEBUG_INTERVAL_SECONDS."""
    if not DEBUG:
        return

    elapsed = now - diag.last_report
    if elapsed < DEBUG_INTERVAL_SECONDS or diag.frames == 0:
        return

    fps = diag.frames / elapsed
    capture_ms = (diag.capture_seconds / diag.frames) * 1000.0
    process_ms = (diag.processing_seconds / diag.frames) * 1000.0
    transmit_ms = (diag.transmit_seconds / diag.frames) * 1000.0
    bytes_per_frame = diag.bytes_sent / diag.frames

    print(
        "DEBUG "
        f"fps={fps:.1f} "
        f"captura={capture_ms:.2f}ms "
        f"proceso={process_ms:.2f}ms "
        f"tx={transmit_ms:.2f}ms "
        f"bytes/frame={bytes_per_frame:.0f}"
    )
    diag.reset(now)
