#!/usr/bin/env python3
"""Bridge Arduino spinner serial messages to a macOS MIDI output.

Expected Arduino lines:
    CC,74,93,RPM,416.1

Setup on macOS:
  1. In Audio MIDI Setup, open MIDI Studio, open IAC Driver, enable it,
     and add a port named "Spinner".
  2. Close Arduino Serial Monitor (only one program can own the port).
  3. Install dependencies in a virtual environment:
       python3 -m venv .venv
       source .venv/bin/activate
       python -m pip install pyserial mido python-rtmidi
  4. Run:
       python spinner_midi_bridge.py

Useful options:
    python spinner_midi_bridge.py --list
    python spinner_midi_bridge.py --serial /dev/cu.usbmodemXXXX
    python spinner_midi_bridge.py --midi "IAC Driver Spinner"
"""

from __future__ import annotations

import argparse
import math
import sys
import time



BAUD_RATE = 115200


def available_serial_ports() -> list:
    from serial.tools import list_ports
    return list(list_ports.comports())


def available_midi_outputs() -> list[str]:
    import mido
    return mido.get_output_names()


def choose_serial_port(explicit_port: str | None) -> str:
    if explicit_port:
        return explicit_port

    ports = available_serial_ports()
    likely = [
        port
        for port in ports
        if "usbmodem" in port.device.lower()
        or "arduino" in (port.description or "").lower()
        or "giga" in (port.description or "").lower()
    ]

    if len(likely) == 1:
        return likely[0].device

    if not likely:
        raise RuntimeError(
            "No likely Arduino serial port found. Run with --list, then pass "
            "the port explicitly with --serial."
        )

    choices = "\n".join(
        f"  {port.device}  ({port.description})" for port in likely
    )
    raise RuntimeError(
        "Multiple likely Arduino ports found:\n"
        f"{choices}\n"
        "Choose one with --serial /dev/cu.usbmodemXXXX."
    )


def choose_midi_port(explicit_name: str | None) -> str:
    names = available_midi_outputs()

    if explicit_name:
        exact = [name for name in names if name == explicit_name]
        if exact:
            return exact[0]

        partial = [
            name for name in names if explicit_name.lower() in name.lower()
        ]
        if len(partial) == 1:
            return partial[0]

        raise RuntimeError(
            f'No unique MIDI output matched "{explicit_name}". '\
            f"Available outputs: {names}"
        )

    spinner_ports = [name for name in names if "spinner" in name.lower()]
    if len(spinner_ports) == 1:
        return spinner_ports[0]

    iac_ports = [name for name in names if "iac" in name.lower()]
    if len(iac_ports) == 1:
        return iac_ports[0]

    raise RuntimeError(
        "Could not choose a unique IAC MIDI output. Create an IAC port named "
        f'"Spinner", or pass --midi with one of: {names}'
    )


def print_available_ports() -> None:
    print("Serial ports:")
    for port in available_serial_ports():
        print(f"  {port.device}  ({port.description})")

    print("\nMIDI output ports:")
    for name in available_midi_outputs():
        print(f"  {name}")


def parse_cc_line(line: str) -> tuple[int, int] | None:
    parts = [part.strip() for part in line.split(",")]
    if len(parts) not in (3, 5) or parts[0] != "CC":
        return None

    try:
        control = int(parts[1])
        value = int(parts[2])
    except ValueError:
        return None

    if not 0 <= control <= 127 or not 0 <= value <= 127:
        return None

    if len(parts) == 5:
        if parts[3] != "RPM":
            return None
        try:
            rpm = float(parts[4])
        except ValueError:
            return None
        if not math.isfinite(rpm) or rpm < 0:
            return None
    return control, value


def forward_cc_line(line, midi_output, *, message_factory=None):
    """Parse and forward one control value; injectable factory supports offline tests."""
    parsed = parse_cc_line(line)
    if parsed is None:
        return None
    if message_factory is None:
        from mido import Message
        message_factory = Message
    control, value = parsed
    midi_output.send(message_factory("control_change", channel=0, control=control, value=value))
    return parsed


def run_bridge(serial_port: str, midi_port: str) -> None:
    import mido
    import serial
    print(f"Serial input: {serial_port} at {BAUD_RATE} baud")
    print(f"MIDI output: {midi_port}")
    print("Press Control-C to stop.\n")

    with mido.open_output(midi_port) as midi_output:
        with serial.Serial(serial_port, BAUD_RATE, timeout=1) as serial_input:
            # Opening the serial port can reset an Arduino; allow it to boot.
            time.sleep(2)
            serial_input.reset_input_buffer()

            # The boot packet can be discarded by reset_input_buffer. Establish
            # an explicit resting value, and return to rest on a normal shutdown.
            resting = mido.Message("control_change", channel=0, control=74, value=0)
            midi_output.send(resting)
            try:
                while True:
                    raw_line = serial_input.readline()
                    if not raw_line:
                        continue
                    # A timed-out partial line is not a complete firmware packet.
                    if not raw_line.endswith(b"\n"):
                        continue
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    parsed = forward_cc_line(line, midi_output, message_factory=mido.Message)
                    if parsed is None:
                        if line:
                            print(f"Arduino: {line}")
                        continue
                    control, value = parsed
                    print(f"MIDI CC {control}: {value}")
            finally:
                midi_output.send(resting)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bridge Arduino spinner serial data to macOS MIDI."
    )
    parser.add_argument("--serial", help="Arduino serial device path")
    parser.add_argument("--midi", help="MIDI output name or unique substring")
    parser.add_argument(
        "--list",
        action="store_true",
        help="list serial and MIDI outputs, then exit",
    )
    args = parser.parse_args()

    try:
        if args.list:
            print_available_ports()
            return 0
        serial_port = choose_serial_port(args.serial)
        midi_port = choose_midi_port(args.midi)
        run_bridge(serial_port, midi_port)
    except KeyboardInterrupt:
        print("\nSpinner bridge stopped.")
        return 0
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
