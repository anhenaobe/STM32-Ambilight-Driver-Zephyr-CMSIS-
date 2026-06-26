"""
Ambilight estable para STM32L152KB + SK6812 RGBW usando Adalight.

Dependencias:
    pip install mss numpy pyserial

Este script captura solo una banda perimetral de la pantalla, calcula colores
robustos por LED y envia frames Adalight RGBW. La comunicacion replica el
formato usado por adalight_animaciones.py:

    b"Ada" + high + low + checksum + payload RGBW

El canal W permanece en 0 durante calibracion para evitar colores blanquecinos.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import mss
import numpy as np
import serial



SERIAL_PORT = "COM8"
BAUD_RATE = 921600
SERIAL_RETRY_SECONDS = 2.0
SERIAL_TIMEOUT_SECONDS = 1.0

LEDS_BOTTOM = 53
LEDS_RIGHT = 22
LEDS_TOP = 45
LEDS_LEFT = 0
TOTAL_LEDS = LEDS_BOTTOM + LEDS_RIGHT + LEDS_TOP + LEDS_LEFT

BYTES_PER_LED = 4
USE_WHITE_CHANNEL = False

MONITOR_INDEX = 1
BORDER_SIZE_PX = 40
DOWNSAMPLE_STEP = 6
TRIM_PERCENT = 8.0
CAPTURE_BACKEND = "dxcam"
CAPTURE_MODE = "edges"
LIST_MONITORS_ON_START = True

GAMMA = 2.2
SATURATION_BOOST = 1.18
BRIGHTNESS = 0.75

SMOOTHING_ALPHA = 0.25
SMOOTHING_ALPHA_RISE = 0.22
SMOOTHING_ALPHA_FALL = 0.14
COLOR_DEADBAND = 4.0
MAX_COLOR_STEP = 18.0
TARGET_FPS = 24

DEBUG = True
DEBUG_INTERVAL_SECONDS = 1.0


@dataclass(frozen=True)
class CaptureRegions:
    """Regiones perimetrales capturadas por mss."""

    top: dict[str, int]
    bottom: dict[str, int]
    left: dict[str, int]
    right: dict[str, int]


@dataclass(frozen=True)
class MonitorGeometry:
    """Geometria absoluta del monitor seleccionado."""

    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class EdgeSegments:
    """Segmentos 1D que asignan pixeles de cada borde a LEDs."""

    top: list[tuple[int, int]]
    bottom: list[tuple[int, int]]
    left: list[tuple[int, int]]
    right: list[tuple[int, int]]


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


class ScreenCapture:
    """Interfaz comun para backends de captura."""

    monitor: MonitorGeometry
    regions: CaptureRegions

    def __enter__(self) -> "ScreenCapture":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def capture_edges(self) -> dict[str, np.ndarray]:
        raise NotImplementedError



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
    """
    Convierte un arreglo (TOTAL_LEDS, 3) RGB uint8 al payload RGBW.

    El canal W se fuerza a 0. No se hace extraccion automatica de blanco.
    """
    payload = np.zeros((TOTAL_LEDS, BYTES_PER_LED), dtype=np.uint8)
    payload[:, 0:3] = colors_rgb

    if USE_WHITE_CHANNEL:
        raise ValueError("USE_WHITE_CHANNEL debe permanecer False durante calibracion.")

    return payload.ravel().tobytes()


def send_adalight_frame(
    port: serial.Serial,
    header: bytes,
    colors_rgb: np.ndarray,
) -> int:
    """Envia un frame Adalight completo y devuelve los bytes escritos."""
    packet = header + build_rgbw_payload(colors_rgb)
    return port.write(packet)


def send_black_frame(port: serial.Serial, header: bytes) -> None:
    """Apaga la tira con un frame negro RGBW."""
    black = np.zeros((TOTAL_LEDS, 3), dtype=np.uint8)
    send_adalight_frame(port, header, black)



def monitor_from_mss_dict(monitor: dict) -> MonitorGeometry:
    """Convierte la estructura de monitor de mss a geometria propia."""
    return MonitorGeometry(
        left=int(monitor["left"]),
        top=int(monitor["top"]),
        width=int(monitor["width"]),
        height=int(monitor["height"]),
    )


def list_mss_monitors(sct: Any) -> None:
    """Lista monitores detectados por mss para elegir MONITOR_INDEX."""
    if not LIST_MONITORS_ON_START:
        return

    print("Monitores detectados por mss:")
    for index, monitor in enumerate(sct.monitors):
        label = "virtual" if index == 0 else f"monitor {index}"
        print(
            f"  {index}: {label} "
            f"{monitor['width']}x{monitor['height']} "
            f"left={monitor['left']} top={monitor['top']}"
        )


def get_primary_monitor(sct: Any) -> MonitorGeometry:
    """Obtiene el monitor configurado para la captura."""
    if MONITOR_INDEX <= 0 or MONITOR_INDEX >= len(sct.monitors):
        raise ValueError(
            f"MONITOR_INDEX={MONITOR_INDEX} no existe. "
            f"Monitores disponibles: {len(sct.monitors) - 1}"
        )
    return monitor_from_mss_dict(sct.monitors[MONITOR_INDEX])


def build_capture_regions(monitor: MonitorGeometry) -> CaptureRegions:
    """
    Define cuatro regiones perimetrales.

    Los lados verticales excluyen las bandas superior e inferior para no duplicar
    esquinas. Top y bottom capturan todo el ancho.
    """
    left = monitor.left
    top = monitor.top
    width = monitor.width
    height = monitor.height
    border = max(1, min(BORDER_SIZE_PX, width // 3, height // 3))
    vertical_height = max(1, height - (2 * border))

    return CaptureRegions(
        top={
            "left": left,
            "top": top,
            "width": width,
            "height": border,
        },
        bottom={
            "left": left,
            "top": top + height - border,
            "width": width,
            "height": border,
        },
        left={
            "left": left,
            "top": top + border,
            "width": border,
            "height": vertical_height,
        },
        right={
            "left": left + width - border,
            "top": top + border,
            "width": border,
            "height": vertical_height,
        },
    )


def crop_edge_from_frame(
    frame_rgb: np.ndarray,
    monitor: MonitorGeometry,
    region: dict[str, int],
) -> np.ndarray:
    """Recorta una region absoluta desde un frame RGB del monitor completo."""
    y0 = region["top"] - monitor.top
    x0 = region["left"] - monitor.left
    y1 = y0 + region["height"]
    x1 = x0 + region["width"]
    return frame_rgb[y0:y1, x0:x1, :]


class MssCapture(ScreenCapture):
    """Captura con mss. Puede usar una sola captura o cuatro capturas de borde."""

    def __init__(self) -> None:
        self.sct: Any | None = None

    def __enter__(self) -> "MssCapture":
        self.sct = mss.mss()
        list_mss_monitors(self.sct)
        self.monitor = get_primary_monitor(self.sct)
        self.regions = build_capture_regions(self.monitor)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.sct is not None:
            self.sct.close()

    def capture_edges(self) -> dict[str, np.ndarray]:
        """
        Captura las bandas perimetrales y las convierte de BGRA a RGB.

        CAPTURE_MODE="single" hace una sola captura del monitor y recorta los
        bordes en NumPy. CAPTURE_MODE="edges" hace cuatro capturas pequenas.
        """
        if self.sct is None:
            raise RuntimeError("MssCapture no ha sido inicializado.")

        if CAPTURE_MODE == "single":
            frame = np.asarray(
                self.sct.grab(
                    {
                        "left": self.monitor.left,
                        "top": self.monitor.top,
                        "width": self.monitor.width,
                        "height": self.monitor.height,
                    }
                ),
                dtype=np.uint8,
            )[..., [2, 1, 0]]
            return {
                "bottom": crop_edge_from_frame(frame, self.monitor, self.regions.bottom),
                "right": crop_edge_from_frame(frame, self.monitor, self.regions.right),
                "top": crop_edge_from_frame(frame, self.monitor, self.regions.top),
                "left": crop_edge_from_frame(frame, self.monitor, self.regions.left),
            }

        if CAPTURE_MODE == "edges":
            return {
                "bottom": np.asarray(self.sct.grab(self.regions.bottom), dtype=np.uint8)[..., [2, 1, 0]],
                "right": np.asarray(self.sct.grab(self.regions.right), dtype=np.uint8)[..., [2, 1, 0]],
                "top": np.asarray(self.sct.grab(self.regions.top), dtype=np.uint8)[..., [2, 1, 0]],
                "left": np.asarray(self.sct.grab(self.regions.left), dtype=np.uint8)[..., [2, 1, 0]],
            }

        raise ValueError('CAPTURE_MODE debe ser "single" o "edges".')


class DxcamCapture(ScreenCapture):
    """Captura con dxcam/DXGI. Requiere instalar: pip install dxcam."""

    def __init__(self) -> None:
        self.camera: Any | None = None
        self.mss_context: Any | None = None

    def __enter__(self) -> "DxcamCapture":
        try:
            import dxcam
        except ImportError as exc:
            raise RuntimeError(
                "CAPTURE_BACKEND='dxcam' requiere instalar dxcam: pip install dxcam"
            ) from exc

        self.mss_context = mss.mss()
        list_mss_monitors(self.mss_context)
        self.monitor = get_primary_monitor(self.mss_context)
        self.regions = build_capture_regions(self.monitor)

        output_idx = MONITOR_INDEX - 1
        self.camera = dxcam.create(output_idx=output_idx, output_color="RGB")
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.camera = None
        if self.mss_context is not None:
            self.mss_context.close()

    def grab_region(self, region: dict[str, int]) -> np.ndarray:
        """Captura una region absoluta con dxcam."""
        if self.camera is None:
            raise RuntimeError("DxcamCapture no ha sido inicializado.")

        box = (
            region["left"],
            region["top"],
            region["left"] + region["width"],
            region["top"] + region["height"],
        )
        frame = self.camera.grab(region=box)
        if frame is None:
            raise RuntimeError("dxcam no entrego frame.")
        return np.asarray(frame, dtype=np.uint8)

    def capture_edges(self) -> dict[str, np.ndarray]:
        """Captura bordes con dxcam en RGB."""
        if CAPTURE_MODE == "single":
            frame = self.grab_region(
                {
                    "left": self.monitor.left,
                    "top": self.monitor.top,
                    "width": self.monitor.width,
                    "height": self.monitor.height,
                }
            )
            return {
                "bottom": crop_edge_from_frame(frame, self.monitor, self.regions.bottom),
                "right": crop_edge_from_frame(frame, self.monitor, self.regions.right),
                "top": crop_edge_from_frame(frame, self.monitor, self.regions.top),
                "left": crop_edge_from_frame(frame, self.monitor, self.regions.left),
            }

        if CAPTURE_MODE == "edges":
            return {
                "bottom": self.grab_region(self.regions.bottom),
                "right": self.grab_region(self.regions.right),
                "top": self.grab_region(self.regions.top),
                "left": self.grab_region(self.regions.left),
            }

        raise ValueError('CAPTURE_MODE debe ser "single" o "edges".')


def create_capture_backend() -> ScreenCapture:
    """Crea el backend de captura configurado."""
    if CAPTURE_BACKEND == "mss":
        return MssCapture()
    if CAPTURE_BACKEND == "dxcam":
        return DxcamCapture()
    raise ValueError('CAPTURE_BACKEND debe ser "mss" o "dxcam".')



def split_axis(length: int, led_count: int) -> list[tuple[int, int]]:
    """Divide un eje de pixeles en segmentos contiguos, uno por LED."""
    if led_count <= 0:
        return []

    limits = np.linspace(0, length, led_count + 1, dtype=np.int32)
    segments: list[tuple[int, int]] = []

    for index in range(led_count):
        start = int(limits[index])
        end = int(limits[index + 1])
        if end <= start:
            end = min(start + 1, length)
        segments.append((start, end))

    return segments


def build_edge_segments(regions: CaptureRegions) -> EdgeSegments:
    """Precalcula segmentos por borde para no repetir trabajo por frame."""
    return EdgeSegments(
        bottom=split_axis(regions.bottom["width"], LEDS_BOTTOM),
        right=split_axis(regions.right["height"], LEDS_RIGHT),
        top=split_axis(regions.top["width"], LEDS_TOP),
        left=split_axis(regions.left["height"], LEDS_LEFT),
    )


def physical_led_order(
    bottom_colors: np.ndarray,
    right_colors: np.ndarray,
    top_colors: np.ndarray,
    left_colors: np.ndarray,
) -> np.ndarray:
    """
    Aisla el recorrido fisico de la tira.

    LED 0: esquina inferior izquierda.
    Recorrido:
        1. inferior izquierda -> derecha
        2. derecha abajo -> arriba
        3. superior derecha -> izquierda
        4. izquierda arriba -> abajo
    """
    return np.vstack(
        (
            bottom_colors,
            right_colors[::-1],
            top_colors[::-1],
            left_colors,
        )
    )



def robust_segment_color(segment_rgb: np.ndarray) -> np.ndarray:
    """
    Calcula un color robusto para un segmento.

    Pasos:
        1. Downsampling por stride para reducir ruido y costo.
        2. Calculo de luminancia.
        3. Eliminacion del 10% mas oscuro y 10% mas brillante.
        4. Media truncada del resto.
    """
    pixels = segment_rgb.reshape(-1, 3).astype(np.float32)

    if pixels.size == 0:
        return np.zeros(3, dtype=np.float32)

    if pixels.shape[0] < 24:
        return np.mean(pixels, axis=0, dtype=np.float32)

    luminance = (
        (0.2126 * pixels[:, 0])
        + (0.7152 * pixels[:, 1])
        + (0.0722 * pixels[:, 2])
    )
    pixel_count = luminance.shape[0]
    trim_count = int(pixel_count * (TRIM_PERCENT / 100.0))

    if trim_count <= 0 or (trim_count * 2) >= pixel_count:
        return np.mean(pixels, axis=0, dtype=np.float32)

    high_index = pixel_count - trim_count - 1
    partitioned = np.partition(luminance, (trim_count, high_index))
    low = partitioned[trim_count]
    high = partitioned[high_index]
    mask = (luminance >= low) & (luminance <= high)

    if np.count_nonzero(mask) < 3:
        return np.mean(pixels, axis=0, dtype=np.float32)

    return np.mean(pixels[mask], axis=0, dtype=np.float32)


def sample_horizontal_edge(
    edge_rgb: np.ndarray,
    segments: list[tuple[int, int]],
) -> np.ndarray:
    """Muestrea un borde horizontal y devuelve colores RGB float por LED."""
    edge_rgb = edge_rgb[::DOWNSAMPLE_STEP, ::DOWNSAMPLE_STEP, :]
    colors = np.empty((len(segments), 3), dtype=np.float32)

    for led_index, (start, end) in enumerate(segments):
        scaled_start = start // DOWNSAMPLE_STEP
        scaled_end = max(scaled_start + 1, (end + DOWNSAMPLE_STEP - 1) // DOWNSAMPLE_STEP)
        colors[led_index] = robust_segment_color(edge_rgb[:, scaled_start:scaled_end, :])

    return colors


def sample_vertical_edge(
    edge_rgb: np.ndarray,
    segments: list[tuple[int, int]],
) -> np.ndarray:
    """Muestrea un borde vertical y devuelve colores RGB float por LED."""
    edge_rgb = edge_rgb[::DOWNSAMPLE_STEP, ::DOWNSAMPLE_STEP, :]
    colors = np.empty((len(segments), 3), dtype=np.float32)

    for led_index, (start, end) in enumerate(segments):
        scaled_start = start // DOWNSAMPLE_STEP
        scaled_end = max(scaled_start + 1, (end + DOWNSAMPLE_STEP - 1) // DOWNSAMPLE_STEP)
        colors[led_index] = robust_segment_color(edge_rgb[scaled_start:scaled_end, :, :])

    return colors


def boost_saturation(colors: np.ndarray) -> np.ndarray:
    """
    Aumenta saturacion sin convertir a blanco.

    Se desplaza cada color desde su luminancia hacia sus canales originales.
    El canal dominante se conserva mejor que con extraccion de blanco.
    """
    luminance = (
        (0.2126 * colors[:, 0:1])
        + (0.7152 * colors[:, 1:2])
        + (0.0722 * colors[:, 2:3])
    )
    saturated = luminance + ((colors - luminance) * SATURATION_BOOST)
    return np.clip(saturated, 0.0, 255.0)


def apply_gamma_and_brightness(colors: np.ndarray) -> np.ndarray:
    """Aplica brillo global y correccion gamma por canal RGB."""
    normalized = np.clip(colors / 255.0, 0.0, 1.0)
    corrected = np.power(normalized, GAMMA) * 255.0
    corrected *= BRIGHTNESS
    return np.clip(corrected, 0.0, 255.0)


def process_edges(
    edges: dict[str, np.ndarray],
    segments: EdgeSegments,
    previous_filtered: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Convierte las capturas perimetrales en colores finales por LED.

    Devuelve:
        - colores uint8 listos para enviar.
        - estado filtrado float para el siguiente frame.
    """
    bottom = sample_horizontal_edge(edges["bottom"], segments.bottom)
    right = sample_vertical_edge(edges["right"], segments.right)
    top = sample_horizontal_edge(edges["top"], segments.top)
    left = sample_vertical_edge(edges["left"], segments.left)

    current = physical_led_order(bottom, right, top, left)
    current = boost_saturation(current)
    current = apply_gamma_and_brightness(current)

    delta = current - previous_filtered
    stable_current = np.where(np.abs(delta) < COLOR_DEADBAND, previous_filtered, current)
    stable_delta = stable_current - previous_filtered
    limited_delta = np.clip(stable_delta, -MAX_COLOR_STEP, MAX_COLOR_STEP)
    alpha = np.where(limited_delta >= 0.0, SMOOTHING_ALPHA_RISE, SMOOTHING_ALPHA_FALL)
    filtered = previous_filtered + (alpha * limited_delta)
    output = np.clip(filtered, 0.0, 255.0).astype(np.uint8)
    return output, filtered



def validate_config() -> None:
    """Valida que la configuracion sea coherente antes de iniciar."""
    if TOTAL_LEDS != (LEDS_BOTTOM + LEDS_RIGHT + LEDS_TOP + LEDS_LEFT):
        raise ValueError("TOTAL_LEDS no coincide con la suma de LEDs por lado.")
    if BYTES_PER_LED != 4:
        raise ValueError("Este script esta fijado para RGBW de 4 bytes por LED.")
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


def run_ambilight_loop(port: serial.Serial, header: bytes) -> None:
    """Ejecuta captura, procesamiento, transmision y temporizacion estable."""
    frame_interval = 1.0 / TARGET_FPS
    next_frame_time = time.perf_counter()
    filtered = np.zeros((TOTAL_LEDS, 3), dtype=np.float32)
    diag = Diagnostics(last_report=time.perf_counter())

    with create_capture_backend() as capture:
        segments = build_edge_segments(capture.regions)

        print(
            "Ambilight iniciado: "
            f"{TOTAL_LEDS} LEDs RGBW, {TARGET_FPS} FPS, "
            f"borde={BORDER_SIZE_PX}px, monitor={MONITOR_INDEX}, "
            f"backend={CAPTURE_BACKEND}, modo={CAPTURE_MODE}."
        )

        while True:
            frame_start = time.perf_counter()

            capture_start = time.perf_counter()
            edges = capture.capture_edges()
            capture_end = time.perf_counter()

            process_start = time.perf_counter()
            output, filtered = process_edges(edges, segments, filtered)
            process_end = time.perf_counter()

            tx_start = time.perf_counter()
            bytes_sent = send_adalight_frame(port, header, output)
            tx_end = time.perf_counter()

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

    while True:
        port: serial.Serial | None = None

        try:
            port = open_serial()
            run_ambilight_loop(port, header)

        except KeyboardInterrupt:
            print("\nDeteniendo Ambilight...")
            if port is not None and port.is_open:
                try:
                    send_black_frame(port, header)
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
                    send_black_frame(port, header)
                except (serial.SerialException, OSError):
                    pass
                port.close()


if __name__ == "__main__":
    main()
