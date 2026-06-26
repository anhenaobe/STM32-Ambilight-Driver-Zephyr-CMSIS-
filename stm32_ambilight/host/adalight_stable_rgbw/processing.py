"""Color sampling, filtering, and physical LED ordering."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .capture import CaptureRegions
from .config import (
    BRIGHTNESS,
    COLOR_DEADBAND,
    DOWNSAMPLE_STEP,
    GAMMA,
    LEDS_BOTTOM,
    LEDS_LEFT,
    LEDS_RIGHT,
    LEDS_TOP,
    MAX_COLOR_STEP,
    SATURATION_BOOST,
    SMOOTHING_ALPHA_FALL,
    SMOOTHING_ALPHA_RISE,
    TRIM_PERCENT,
)


@dataclass(frozen=True)
class EdgeSegments:
    """Segmentos 1D que asignan pixeles de cada borde a LEDs."""

    top: list[tuple[int, int]]
    bottom: list[tuple[int, int]]
    left: list[tuple[int, int]]
    right: list[tuple[int, int]]


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
    """Aisla el recorrido fisico de la tira."""
    return np.vstack(
        (
            bottom_colors,
            right_colors[::-1],
            top_colors[::-1],
            left_colors,
        )
    )


def robust_segment_color(segment_rgb: np.ndarray) -> np.ndarray:
    """Calcula un color robusto para un segmento."""
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
    """Aumenta saturacion sin convertir a blanco."""
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
    """Convierte las capturas perimetrales en colores finales por LED."""
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

