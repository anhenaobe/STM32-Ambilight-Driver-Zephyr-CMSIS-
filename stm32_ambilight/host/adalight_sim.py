import time

import serial


PUERTO_COM = "COM8"
BAUD_RATE = 921600
NUM_LEDS = 120
BYTES_PER_LED = 4
FPS = 24

COLOR_FIJO = True
RGBW_FIJO = (40, 0, 0, 0)

COLORES_PRUEBA = (
    (40, 0, 0, 0),
    (0, 40, 0, 0),
    (0, 0, 40, 0),
    (40, 40, 40, 0),
)


def calcular_encabezado_adalight(num_leds):
    """Calcula el encabezado exacto Adalight: b'Ada' + high + low + checksum."""
    count = num_leds - 1
    hi_byte = (count >> 8) & 0xFF
    lo_byte = count & 0xFF
    checksum = hi_byte ^ lo_byte ^ 0x55
    return b"Ada" + bytes((hi_byte, lo_byte, checksum))


def crear_payload_rgbw(color):
    """Crea un payload RGBW plano para todos los LEDs."""
    r, g, b, w = color
    led = bytes((r, g, b, w))
    return led * NUM_LEDS


def main():
    puerto = None

    try:
        print(f"Abriendo {PUERTO_COM} a {BAUD_RATE} baudios...")
        puerto = serial.Serial(PUERTO_COM, BAUD_RATE, timeout=1, write_timeout=1)
        time.sleep(2)

        encabezado = calcular_encabezado_adalight(NUM_LEDS)
        print(f"Encabezado generado: {[hex(b) for b in encabezado]}")
        print(f"Modo color fijo: {COLOR_FIJO}")

        frame_count = 0
        intervalo = 1.0 / FPS
        siguiente_frame = time.perf_counter()

        while True:
            if COLOR_FIJO:
                color = RGBW_FIJO
            else:
                color = COLORES_PRUEBA[(frame_count // (FPS * 3)) % len(COLORES_PRUEBA)]

            paquete = encabezado + crear_payload_rgbw(color)
            puerto.write(paquete)

            frame_count += 1
            if frame_count % FPS == 0:
                print(f"Frame {frame_count} enviado -> RGBW: {color}")

            siguiente_frame += intervalo
            espera = siguiente_frame - time.perf_counter()
            if espera > 0:
                time.sleep(espera)
            else:
                siguiente_frame = time.perf_counter()

    except serial.SerialException as exc:
        print(f"Error de puerto serial: {exc}")
        print("Revisa COM, baudrate y que ningun monitor serial este abierto.")
    except KeyboardInterrupt:
        print("\nSimulador detenido por el usuario.")
    finally:
        if puerto is not None and puerto.is_open:
            puerto.close()


if __name__ == "__main__":
    main()
