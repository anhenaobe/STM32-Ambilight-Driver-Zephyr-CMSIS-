"""Screen capture backends and monitor geometry helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import mss
import numpy as np

from .config import (
    BORDER_SIZE_PX,
    CAPTURE_BACKEND,
    CAPTURE_MODE,
    DXCAM_DEVICE_IDX,
    DXCAM_OUTPUT_IDX,
    DXCAM_PROCESSOR_BACKEND,
    LIST_MONITORS_ON_START,
    MONITOR_INDEX,
)


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
    """Define cuatro regiones perimetrales sin duplicar esquinas verticales."""
    left = monitor.left
    top = monitor.top
    width = monitor.width
    height = monitor.height
    border = max(1, min(BORDER_SIZE_PX, width // 3, height // 3))
    vertical_height = max(1, height - (2 * border))

    return CaptureRegions(
        top={"left": left, "top": top, "width": width, "height": border},
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

    def _grab_rgb(self, region: dict[str, int]) -> np.ndarray:
        if self.sct is None:
            raise RuntimeError("MssCapture no ha sido inicializado.")
        return np.asarray(self.sct.grab(region), dtype=np.uint8)[..., [2, 1, 0]]

    def capture_edges(self) -> dict[str, np.ndarray]:
        """Captura las bandas perimetrales y las convierte de BGRA a RGB."""
        if self.sct is None:
            raise RuntimeError("MssCapture no ha sido inicializado.")

        if CAPTURE_MODE == "single":
            frame = self._grab_rgb(
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
                "bottom": self._grab_rgb(self.regions.bottom),
                "right": self._grab_rgb(self.regions.right),
                "top": self._grab_rgb(self.regions.top),
                "left": self._grab_rgb(self.regions.left),
            }

        raise ValueError('CAPTURE_MODE debe ser "single" o "edges".')


class DxcamCapture(ScreenCapture):
    """Captura con dxcam/DXGI. Requiere instalar: pip install dxcam."""

    def __init__(self) -> None:
        self.camera: Any | None = None
        self.mss_context: Any | None = None
        self.last_full_frame: np.ndarray | None = None

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

        print(
            "dxcam seleccionado: "
            f"device_idx={DXCAM_DEVICE_IDX}, output_idx={DXCAM_OUTPUT_IDX}, "
            f"processor_backend={DXCAM_PROCESSOR_BACKEND}"
        )
        self.camera = dxcam.create(
            device_idx=DXCAM_DEVICE_IDX,
            output_idx=DXCAM_OUTPUT_IDX,
            output_color="RGB",
            processor_backend=DXCAM_PROCESSOR_BACKEND,
        )
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.camera = None
        if self.mss_context is not None:
            self.mss_context.close()

    def grab_region(self, region: dict[str, int]) -> np.ndarray:
        """Captura una region absoluta con dxcam."""
        if self.camera is None:
            raise RuntimeError("DxcamCapture no ha sido inicializado.")

        # dxcam expects coordinates local to the selected output.
        # mss reports virtual-desktop coordinates, so normalize them here.
        left = region["left"] - self.monitor.left
        top = region["top"] - self.monitor.top
        box = (
            left,
            top,
            left + region["width"],
            top + region["height"],
        )
        frame = self.camera.grab(region=box, new_frame_only=False)
        if frame is None:
            raise RuntimeError("dxcam no entrego frame.")
        return np.asarray(frame, dtype=np.uint8)

    def grab_full_frame(self) -> np.ndarray:
        """Captura el monitor completo una vez y permite reutilizar el ultimo frame."""
        frame = self.grab_region(
            {
                "left": self.monitor.left,
                "top": self.monitor.top,
                "width": self.monitor.width,
                "height": self.monitor.height,
            }
        )
        self.last_full_frame = frame
        return frame

    def capture_edges(self) -> dict[str, np.ndarray]:
        """Captura un frame completo con dxcam y recorta los cuatro bordes."""
        if CAPTURE_MODE not in {"single", "edges"}:
            raise ValueError('CAPTURE_MODE debe ser "single" o "edges".')

        # Four consecutive dxcam grab() calls can return None while waiting for new frames.
        # Capture one full frame and crop from it instead.
        # This also keeps all edges synchronized to the same screen frame.
        frame = self.grab_full_frame()
        return {
            "bottom": crop_edge_from_frame(frame, self.monitor, self.regions.bottom),
            "right": crop_edge_from_frame(frame, self.monitor, self.regions.right),
            "top": crop_edge_from_frame(frame, self.monitor, self.regions.top),
            "left": crop_edge_from_frame(frame, self.monitor, self.regions.left),
        }


def create_capture_backend() -> ScreenCapture:
    """Crea el backend de captura configurado."""
    if CAPTURE_BACKEND == "mss":
        return MssCapture()
    if CAPTURE_BACKEND == "dxcam":
        return DxcamCapture()
    raise ValueError('CAPTURE_BACKEND debe ser "mss" o "dxcam".')

