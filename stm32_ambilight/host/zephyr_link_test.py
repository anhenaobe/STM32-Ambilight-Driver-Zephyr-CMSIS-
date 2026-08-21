"""Send deterministic Adalight frames to the Zephyr UART diagnostic target."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence

import serial

BAUDRATE = 921_600
LED_COUNT = 120
BYTES_PER_LED = 4
PAYLOAD_SIZE = LED_COUNT * BYTES_PER_LED
FRAME_SIZE = 6 + PAYLOAD_SIZE


def build_frame(payload: bytes) -> bytes:
    """Build one standard Adalight frame for the fixed 120-LED contract."""
    if len(payload) != PAYLOAD_SIZE:
        raise ValueError(f"payload must be exactly {PAYLOAD_SIZE} bytes")

    count_minus_one = LED_COUNT - 1
    high = (count_minus_one >> 8) & 0xFF
    low = count_minus_one & 0xFF
    checksum = high ^ low ^ 0x55
    return b"Ada" + bytes((high, low, checksum)) + payload


def incremental_payload() -> bytes:
    """Return a deterministic payload containing all byte values repeatedly."""
    return bytes(index & 0xFF for index in range(PAYLOAD_SIZE))


def repeated_grbw(green: int, red: int, blue: int, white: int) -> bytes:
    """Return 120 identical, easily recognizable GRBW pixels."""
    pixel = bytes((green, red, blue, white))
    return pixel * LED_COUNT


def fragmented_writes(frame: bytes) -> list[bytes]:
    """Split a frame across deterministic, irregular write boundaries."""
    chunk_sizes = (1, 2, 3, 5, 7, 11, 17, 23, 31, 47)
    chunks: list[bytes] = []
    offset = 0
    chunk_index = 0

    while offset < len(frame):
        size = chunk_sizes[chunk_index % len(chunk_sizes)]
        chunks.append(frame[offset : offset + size])
        offset += size
        chunk_index += 1

    return chunks


def writes_for_case(case: str) -> tuple[list[bytes], str]:
    """Return serial writes and a human-readable payload description."""
    base_frame = build_frame(incremental_payload())

    if case == "complete":
        return [base_frame], "one 486-byte frame in one write"
    if case == "fragmented":
        return fragmented_writes(base_frame), "one frame in irregular writes"
    if case == "back-to-back":
        frame_a = build_frame(repeated_grbw(0x11, 0x22, 0x33, 0x00))
        frame_b = build_frame(repeated_grbw(0xAA, 0xBB, 0xCC, 0x00))
        return [frame_a + frame_b], "two distinct frames in one 972-byte write"
    if case == "known":
        known = build_frame(repeated_grbw(0x11, 0x22, 0x33, 0x44))
        return [known], "120 pixels with repeated GRBW=11,22,33,44"

    raise ValueError(f"unsupported case: {case}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send deterministic frames to uart_parser_diagnostics."
    )
    parser.add_argument("--port", required=True, help="Serial port, for example COM8")
    parser.add_argument(
        "--case",
        choices=("complete", "fragmented", "back-to-back", "known"),
        default="complete",
        help="Transmission shape to exercise (default: complete)",
    )
    parser.add_argument(
        "--settle-seconds",
        type=float,
        default=2.0,
        help="Delay after opening the port before sending (default: 2.0)",
    )
    parser.add_argument(
        "--read-seconds",
        type=float,
        default=2.0,
        help="Time to print MCU diagnostic output after sending (default: 2.0)",
    )
    parser.add_argument(
        "--inter-write-ms",
        type=float,
        default=2.0,
        help="Pause between fragmented writes (default: 2.0 ms)",
    )
    return parser.parse_args(argv)


def read_mcu_output(port: serial.Serial, duration_seconds: float) -> None:
    """Print complete and partial text returned by the diagnostic firmware."""
    deadline = time.monotonic() + max(0.0, duration_seconds)
    pending = bytearray()

    while time.monotonic() < deadline:
        waiting = port.in_waiting
        data = port.read(waiting if waiting > 0 else 1)
        if not data:
            continue
        pending.extend(data)

        while b"\n" in pending:
            line, _, remainder = pending.partition(b"\n")
            pending = bytearray(remainder)
            print(f"MCU> {line.decode('ascii', errors='replace').rstrip()}")

    if pending:
        print(f"MCU> {pending.decode('ascii', errors='replace').rstrip()}")


def run(args: argparse.Namespace) -> int:
    writes, description = writes_for_case(args.case)
    total_attempted = sum(len(chunk) for chunk in writes)

    print(f"CASE={args.case}")
    print(f"DESCRIPTION={description}")
    print(f"FRAME_SIZE={FRAME_SIZE}")
    print(f"WRITE_COUNT={len(writes)}")
    print(f"TOTAL_ATTEMPTED={total_attempted}")

    with serial.Serial(
        port=args.port,
        baudrate=BAUDRATE,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.1,
        write_timeout=1.0,
    ) as port:
        time.sleep(max(0.0, args.settle_seconds))
        port.reset_input_buffer()

        total_returned = 0
        for index, chunk in enumerate(writes, start=1):
            returned = port.write(chunk)
            total_returned += returned
            print(
                f"WRITE[{index}] ATTEMPTED={len(chunk)} RETURNED={returned}"
            )
            if returned != len(chunk):
                print(
                    f"ERROR=short write at index {index}: "
                    f"expected {len(chunk)}, returned {returned}",
                    file=sys.stderr,
                )
                return 2
            if index < len(writes):
                time.sleep(max(0.0, args.inter_write_ms) / 1000.0)

        port.flush()
        print(f"TOTAL_RETURNED={total_returned}")
        print("WRITE_STATUS=OK")
        read_mcu_output(port, args.read_seconds)

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run(args)
    except (OSError, serial.SerialException, ValueError) as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
