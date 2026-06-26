"""
Animaciones Adalight para STM32.

Dependencias:
    pip install pyserial

Notas importantes:
    - PUERTO_COM, BAUD_RATE, NUM_LEDS y COLOR_ORDER deben coincidir con
      el firmware cargado en el STM32.
    - Adalight RGB clasico usa COLOR_ORDER = "RGB" o "GRB".
    - El firmware actual de este proyecto usa 4 bytes por LED, por eso el
      valor por defecto es "RGBW" con W=0 para mantener compatibilidad.
"""

from __future__ import annotations

import colorsys
import random
import time
from collections.abc import Iterator
from dataclasses import dataclass

import serial


PUERTO_COM = "COM8"
BAUD_RATE = 921600
NUM_LEDS = 120

COLOR_ORDER = "RGBW"

FPS_OBJETIVO = 60
AUTO_LIMITAR_FPS_POR_BAUDRATE = True
USO_MAX_UART = 0.85

BRILLO_GLOBAL = 0.70
COLOR_FONDO = (0, 0, 0)


SCANNER_COLOR = (0, 255, 255)
SCANNER_SPEED = 1.15
SCANNER_FADE = 0.84
SCANNER_HEAD_RADIUS = 2

METEOR_COLOR_A = (255, 70, 0)
METEOR_COLOR_B = (0, 120, 255)
METEOR_SPEED = 0.95
METEOR_FADE = 0.82
METEOR_HEAD_RADIUS = 2
METEOR_FLASH_FRAMES = 10

WORM_COUNT = 8
WORM_LENGTH = 5
WORM_MIN_SPEED = 0.35
WORM_MAX_SPEED = 1.20
WORM_FADE = 0.88


@dataclass
class Worm:
    pos: float
    direction: int
    speed: float
    color: tuple[int, int, int]
    length: int


def calcular_encabezado_adalight(num_leds: int) -> bytes:
    """Calcula el encabezado exacto: b'Ada' + high + low + checksum."""
    count = num_leds - 1
    high_byte = (count >> 8) & 0xFF
    low_byte = count & 0xFF
    checksum = high_byte ^ low_byte ^ 0x55
    return b"Ada" + bytes((high_byte, low_byte, checksum))


def bytes_por_led() -> int:
    """Devuelve cuantos bytes se enviaran por LED segun COLOR_ORDER."""
    orden = COLOR_ORDER.upper()
    if orden not in {"RGB", "GRB", "RGBW", "GRBW"}:
        raise ValueError("COLOR_ORDER debe ser RGB, GRB, RGBW o GRBW.")
    return len(orden)


def calcular_fps_real() -> float:
    """Evita saturar el UART si el baudrate no alcanza para 60 FPS."""
    bytes_frame = 6 + (NUM_LEDS * bytes_por_led())
    fps_max = ((BAUD_RATE / 10.0) * USO_MAX_UART) / bytes_frame

    if AUTO_LIMITAR_FPS_POR_BAUDRATE:
        return min(float(FPS_OBJETIVO), fps_max)

    return float(FPS_OBJETIVO)


def abrir_serial() -> serial.Serial:
    """Abre el puerto serial hacia el STM32."""
    print(f"Abriendo {PUERTO_COM} a {BAUD_RATE} baudios...")
    puerto = serial.Serial(PUERTO_COM, BAUD_RATE, timeout=1, write_timeout=1)
    time.sleep(2.0)
    print("Puerto serial listo.")
    return puerto


def limitar_color(valor: float) -> int:
    """Convierte un canal flotante a byte 0..255 con brillo global."""
    valor *= BRILLO_GLOBAL
    if valor <= 0:
        return 0
    if valor >= 255:
        return 255
    return int(valor)


def crear_payload(leds: list[list[float]]) -> bytes:
    """Convierte el buffer RGB interno al orden de bytes configurado."""
    payload = bytearray(NUM_LEDS * bytes_por_led())
    orden = COLOR_ORDER.upper()
    index = 0

    for red, green, blue in leds:
        canales = {
            "R": limitar_color(red),
            "G": limitar_color(green),
            "B": limitar_color(blue),
            "W": 0,
        }

        for canal in orden:
            payload[index] = canales[canal]
            index += 1

    return bytes(payload)


def enviar_frame(
    puerto: serial.Serial,
    encabezado: bytes,
    leds: list[list[float]],
) -> None:
    """Envia un frame completo Adalight."""
    puerto.write(encabezado + crear_payload(leds))


def crear_buffer_leds() -> list[list[float]]:
    """Crea el arreglo RGB de estado para todos los LEDs."""
    return [[float(COLOR_FONDO[0]), float(COLOR_FONDO[1]), float(COLOR_FONDO[2])]
            for _ in range(NUM_LEDS)]


def aplicar_fade(leds: list[list[float]], factor: float) -> None:
    """Atenua todos los LEDs para crear colas suaves."""
    for led in leds:
        led[0] *= factor
        led[1] *= factor
        led[2] *= factor


def mezclar_led(leds: list[list[float]], index: int, color: tuple[int, int, int], fuerza: float) -> None:
    """Suma color a un LED sin borrar lo que ya tenga."""
    if 0 <= index < NUM_LEDS:
        leds[index][0] = min(255.0, leds[index][0] + (color[0] * fuerza))
        leds[index][1] = min(255.0, leds[index][1] + (color[1] * fuerza))
        leds[index][2] = min(255.0, leds[index][2] + (color[2] * fuerza))


def dibujar_punto_suave(
    leds: list[list[float]],
    pos: float,
    color: tuple[int, int, int],
    radio: int,
) -> None:
    """Dibuja una cabeza luminosa con caida de intensidad alrededor."""
    centro = int(round(pos))
    for offset in range(-radio, radio + 1):
        distancia = abs(offset)
        fuerza = 1.0 - (distancia / (radio + 1))
        mezclar_led(leds, centro + offset, color, fuerza)


def dibujar_gusano(leds: list[list[float]], worm: Worm) -> None:
    """Dibuja un segmento corto con gradiente de cabeza a cola."""
    for tramo in range(worm.length):
        index = int(round(worm.pos - (worm.direction * tramo)))
        fuerza = 1.0 - (tramo / worm.length)
        mezclar_led(leds, index, worm.color, fuerza)


def color_aleatorio_vivo() -> tuple[int, int, int]:
    """Genera colores brillantes y saturados usando HSV."""
    hue = random.random()
    saturation = random.uniform(0.75, 1.0)
    value = random.uniform(0.70, 1.0)
    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
    return int(red * 255), int(green * 255), int(blue * 255)


def crear_worm() -> Worm:
    """Crea un gusano con direccion, color y velocidad aleatorios."""
    direction = random.choice((-1, 1))
    margen = WORM_LENGTH + 2
    pos = -margen if direction == 1 else NUM_LEDS + margen
    return Worm(
        pos=float(pos),
        direction=direction,
        speed=random.uniform(WORM_MIN_SPEED, WORM_MAX_SPEED),
        color=color_aleatorio_vivo(),
        length=random.randint(max(3, WORM_LENGTH - 2), WORM_LENGTH + 3),
    )


def efecto_scanner(leds: list[list[float]]) -> Iterator[None]:
    """Escaner bidireccional estilo Cylon / Knight Rider."""
    pos = 0.0
    direction = 1

    while True:
        aplicar_fade(leds, SCANNER_FADE)
        dibujar_punto_suave(leds, pos, SCANNER_COLOR, SCANNER_HEAD_RADIUS)

        pos += SCANNER_SPEED * direction
        if pos >= NUM_LEDS - 1:
            pos = float(NUM_LEDS - 1)
            direction = -1
        elif pos <= 0:
            pos = 0.0
            direction = 1

        yield


def efecto_meteoros(leds: list[list[float]]) -> Iterator[None]:
    """Dos meteoros que chocan en el centro, destellan y rebotan."""
    left_pos = 0.0
    right_pos = float(NUM_LEDS - 1)
    left_dir = 1
    right_dir = -1
    flash_frames = 0

    while True:
        aplicar_fade(leds, METEOR_FADE)

        dibujar_punto_suave(leds, left_pos, METEOR_COLOR_A, METEOR_HEAD_RADIUS)
        dibujar_punto_suave(leds, right_pos, METEOR_COLOR_B, METEOR_HEAD_RADIUS)

        if flash_frames > 0:
            centro = (NUM_LEDS - 1) / 2.0
            radio = 8 + (METEOR_FLASH_FRAMES - flash_frames)
            dibujar_punto_suave(leds, centro, (255, 255, 255), radio)
            flash_frames -= 1

        left_pos += METEOR_SPEED * left_dir
        right_pos += METEOR_SPEED * right_dir

        if left_dir == 1 and left_pos >= right_pos:
            left_pos = (NUM_LEDS / 2.0) - 1.0
            right_pos = NUM_LEDS / 2.0
            left_dir = -1
            right_dir = 1
            flash_frames = METEOR_FLASH_FRAMES

        if left_dir == -1 and left_pos <= 0:
            left_pos = 0.0
            right_pos = float(NUM_LEDS - 1)
            left_dir = 1
            right_dir = -1

        yield


def efecto_gusanos(leds: list[list[float]]) -> Iterator[None]:
    """Varios segmentos multicolores cruzandose en ambas direcciones."""
    worms = [crear_worm() for _ in range(WORM_COUNT)]

    while True:
        aplicar_fade(leds, WORM_FADE)

        for idx, worm in enumerate(worms):
            dibujar_gusano(leds, worm)
            worm.pos += worm.direction * worm.speed

            salio_por_derecha = worm.direction == 1 and worm.pos > NUM_LEDS + worm.length
            salio_por_izquierda = worm.direction == -1 and worm.pos < -worm.length
            if salio_por_derecha or salio_por_izquierda:
                worms[idx] = crear_worm()

        yield


def apagar_tira(puerto: serial.Serial, encabezado: bytes) -> None:
    """Apaga todos los LEDs al salir de un efecto."""
    leds = crear_buffer_leds()
    enviar_frame(puerto, encabezado, leds)


def ejecutar_generador(
    puerto: serial.Serial,
    encabezado: bytes,
    nombre: str,
    leds: list[list[float]],
    generador: Iterator[None],
    segundos: float | None,
    fps_real: float,
) -> None:
    """Ejecuta un efecto respetando el intervalo de frame."""
    print(f"\nEjecutando: {nombre}")
    print("Presiona Ctrl+C para volver al menu.")

    inicio = time.perf_counter()
    intervalo = 1.0 / fps_real
    siguiente_frame = time.perf_counter()

    while segundos is None or (time.perf_counter() - inicio) < segundos:
        next(generador)
        enviar_frame(puerto, encabezado, leds)

        siguiente_frame += intervalo
        espera = siguiente_frame - time.perf_counter()
        if espera > 0:
            time.sleep(espera)
        else:
            siguiente_frame = time.perf_counter()


def pedir_duracion() -> float | None:
    """Pide duracion para un efecto. 0 significa infinito."""
    texto = input("Duracion en segundos [Enter=30, 0=infinito]: ").strip()
    if not texto:
        return 30.0

    try:
        valor = float(texto)
    except ValueError:
        print("Valor no valido. Uso 30 segundos.")
        return 30.0

    if valor <= 0:
        return None
    return valor


def mostrar_info_uart(fps_real: float) -> None:
    """Muestra advertencia si el baudrate no permite el FPS objetivo."""
    bytes_frame = 6 + (NUM_LEDS * bytes_por_led())
    baud_necesario = int((bytes_frame * 10 * FPS_OBJETIVO) / USO_MAX_UART)

    print(f"LEDs: {NUM_LEDS}, orden: {COLOR_ORDER}, bytes/frame: {bytes_frame}")
    print(f"FPS objetivo: {FPS_OBJETIVO}, FPS usado: {fps_real:.1f}")

    if fps_real < FPS_OBJETIVO:
        print(
            f"Aviso: para {FPS_OBJETIVO} FPS sin saturar, usa al menos "
            f"{baud_necesario} baudios en Python y en el STM32."
        )


def menu() -> str:
    """Menu simple de seleccion de efectos."""
    print("\n=== Animaciones Adalight ===")
    print("1. Escaner bidireccional con estela")
    print("2. Choque de meteoros")
    print("3. Gusanos aleatorios multicolores")
    print("4. Demo secuencial")
    print("q. Salir")
    return input("Seleccion: ").strip().lower()


def main() -> None:
    encabezado = calcular_encabezado_adalight(NUM_LEDS)
    fps_real = calcular_fps_real()
    mostrar_info_uart(fps_real)

    puerto = None
    try:
        puerto = abrir_serial()

        while True:
            opcion = menu()
            leds = crear_buffer_leds()

            try:
                if opcion == "1":
                    segundos = pedir_duracion()
                    ejecutar_generador(
                        puerto,
                        encabezado,
                        "Escaner bidireccional",
                        leds,
                        efecto_scanner(leds),
                        segundos,
                        fps_real,
                    )
                elif opcion == "2":
                    segundos = pedir_duracion()
                    ejecutar_generador(
                        puerto,
                        encabezado,
                        "Choque de meteoros",
                        leds,
                        efecto_meteoros(leds),
                        segundos,
                        fps_real,
                    )
                elif opcion == "3":
                    segundos = pedir_duracion()
                    ejecutar_generador(
                        puerto,
                        encabezado,
                        "Gusanos aleatorios",
                        leds,
                        efecto_gusanos(leds),
                        segundos,
                        fps_real,
                    )
                elif opcion == "4":
                    for nombre, fabrica in (
                        ("Escaner bidireccional", efecto_scanner),
                        ("Choque de meteoros", efecto_meteoros),
                        ("Gusanos aleatorios", efecto_gusanos),
                    ):
                        leds = crear_buffer_leds()
                        ejecutar_generador(
                            puerto,
                            encabezado,
                            nombre,
                            leds,
                            fabrica(leds),
                            20.0,
                            fps_real,
                        )
                elif opcion == "q":
                    break
                else:
                    print("Opcion no valida.")
                    continue

                apagar_tira(puerto, encabezado)

            except KeyboardInterrupt:
                print("\nVolviendo al menu...")
                apagar_tira(puerto, encabezado)

    except serial.SerialException as exc:
        print(f"Error de puerto serial: {exc}")
        print("Revisa COM, baudrate y que ningun monitor serial este abierto.")
    except KeyboardInterrupt:
        print("\nPrograma detenido por el usuario.")
    finally:
        if puerto is not None and puerto.is_open:
            try:
                apagar_tira(puerto, encabezado)
            except serial.SerialException:
                pass
            puerto.close()


if __name__ == "__main__":
    main()
