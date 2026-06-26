"""Main Ambilight runtime loop."""

from __future__ import annotations

import time

import numpy as np
import serial

from .capture import create_capture_backend
from .config import (
    BORDER_SIZE_PX,
    CAPTURE_BACKEND,
    CAPTURE_MODE,
    MONITOR_INDEX,
    SERIAL_RETRY_SECONDS,
    TARGET_FPS,
    TOTAL_LEDS,
    validate_config,
)
from .diagnostics import Diagnostics, McuLogReader, report_debug
from .processing import build_edge_segments, process_edges
from .protocol import (
    AdalightFrameBuilder,
    build_adalight_header,
    open_serial,
    send_adalight_frame,
    send_black_frame,
)


def run_ambilight_loop(port: serial.Serial, frame_builder: AdalightFrameBuilder) -> None:
    """Ejecuta captura, procesamiento, transmision y temporizacion estable."""
    frame_interval = 1.0 / TARGET_FPS
    next_frame_time = time.perf_counter()
    filtered = np.zeros((TOTAL_LEDS, 3), dtype=np.float32)
    diag = Diagnostics(last_report=time.perf_counter())
    mcu_logs = McuLogReader()

    with create_capture_backend() as capture:
        segments = build_edge_segments(capture.regions)

        print(
            "Ambilight iniciado: "
            f"{TOTAL_LEDS} LEDs RGBW, {TARGET_FPS} FPS, "
            f"borde={BORDER_SIZE_PX}px, monitor={MONITOR_INDEX}, "
            f"backend={CAPTURE_BACKEND}, modo={CAPTURE_MODE}."
        )

        while True:
            capture_start = time.perf_counter()
            edges = capture.capture_edges()
            capture_end = time.perf_counter()

            process_start = time.perf_counter()
            output, filtered = process_edges(edges, segments, filtered)
            process_end = time.perf_counter()

            tx_start = time.perf_counter()
            bytes_sent = send_adalight_frame(port, frame_builder, output)
            tx_end = time.perf_counter()
            mcu_logs.poll(port)

            diag.frames += 1
            diag.bytes_sent += bytes_sent
            diag.capture_seconds += capture_end - capture_start
            diag.processing_seconds += process_end - process_start
            diag.transmit_seconds += tx_end - tx_start
            report_debug(diag, tx_end)

            next_frame_time += frame_interval
            sleep_seconds = next_frame_time - time.perf_counter()

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
            else:
                next_frame_time = time.perf_counter()


def main() -> None:
    """Punto de entrada con reconexion automatica y apagado limpio."""
    validate_config()
    header = build_adalight_header(TOTAL_LEDS)
    frame_builder = AdalightFrameBuilder(TOTAL_LEDS, header)

    while True:
        port: serial.Serial | None = None

        try:
            port = open_serial()
            run_ambilight_loop(port, frame_builder)

        except KeyboardInterrupt:
            print("\nDeteniendo Ambilight...")
            if port is not None and port.is_open:
                try:
                    send_black_frame(port, frame_builder)
                except serial.SerialException:
                    pass
            break

        except (serial.SerialException, OSError) as exc:
            print(f"Error serial: {exc}")
            print(f"Reintentando conexion en {SERIAL_RETRY_SECONDS:.1f} s...")
            time.sleep(SERIAL_RETRY_SECONDS)

        finally:
            if port is not None and port.is_open:
                try:
                    send_black_frame(port, frame_builder)
                except (serial.SerialException, OSError):
                    pass
                port.close()
