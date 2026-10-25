# WHORL

A physical musical controller: a two-magnet fidget spinner passes a Hall sensor, an Arduino GIGA R1 estimates rotational speed, and a Python bridge converts serial packets into MIDI control changes for Logic / Alchemy.

## Project layout

| Path | Purpose |
| --- | --- |
| `firmware/whorl/whorl.ino` | Arduino sketch; directory and sketch names match for the Arduino IDE |
| `spinner_midi_bridge.py` | Serial parsing, port selection, and MIDI forwarding |
| `docs/protocol.md` | Packet format and parameter definitions |
| `tests/test_bridge.py` | Offline Python tests and a simulated bridge loop |
| `tests/firmware_host_test.cpp` | Host checks using the actual sketch with simulated I/O |

## Hardware and firmware

The supplied sketch targets the existing GIGA R1 setup and expects two magnets per revolution. The Hall sensor signal is read on digital pin 2 with `INPUT_PULLUP`, and falling edges are counted. Connect a common ground and use the supply and output levels appropriate to the actual sensor module and the GIGA board. A sensor part number and complete wiring diagram were not supplied.

Open `firmware/whorl/whorl.ino` in the Arduino IDE, select the GIGA R1 board and its serial port, and upload. The original firmware is preserved unchanged in this package.

The sketch compares a magnet's arrival time with its previous arrival one full revolution earlier. It does not assume the two magnets are exactly half a revolution apart. Its first RPM estimate becomes available after the third accepted pulse.

| Parameter | Supplied value |
| --- | --- |
| Serial baud | 115200 |
| MIDI controller | CC 74 |
| Mapping | 50 RPM → 0; 550 RPM → 127, clamped outside that interval |
| Smoothing | Exponential moving average, alpha 0.30 |
| Debounce | Accept another falling edge only after more than 2000 microseconds |
| Stop detection | One measured revolution, clamped to 100–1500 milliseconds |

## macOS MIDI setup

1. In Audio MIDI Setup, open MIDI Studio, enable the IAC Driver, and add a port named `Spinner`.
2. Close Arduino Serial Monitor so the bridge can open the device.
3. Install the bridge in a Python 3.10+ virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[midi]'
```

4. List ports, then start the bridge:

```sh
whorl-bridge --list
whorl-bridge --serial /dev/cu.usbmodemXXXX --midi 'IAC Driver Spinner'
```

You can also run `python spinner_midi_bridge.py` with the same options. The bridge selects a unique likely Arduino and Spinner/IAC output automatically when possible. Ambiguity requires an explicit port argument.

5. In Logic / Alchemy, enable the IAC input and map MIDI CC 74 on channel 1 to the desired modulation target. The synthesizer mapping is configured in the DAW, not in this repository.

The bridge sends a resting CC 74 value of zero after startup and again when leaving its processing loop normally or through an exception. This avoids relying on a boot packet that may have been flushed from the serial buffer. Forced termination or a failed MIDI backend cannot guarantee that final send.

## Verify without hardware

```sh
python3 -m unittest discover -s tests -v
```

The 14 Python tests cover packet parsing, range and RPM validation, port selection, control-change construction, and a simulated serial/MIDI loop. Imports and tests do not require native MIDI or serial packages; those dependencies are loaded when hardware operations are invoked.

If a C++ compiler is available:

```sh
mkdir -p build
c++ -std=c++17 -Wall -Wextra -pedantic tests/firmware_host_test.cpp -o build/firmware_host_test
./build/firmware_host_test
```

The host test includes the actual sketch and checks mapping, debounce, a full-revolution RPM estimate, stop timeout clamping, and reset behavior. It is not an Arduino-target compilation, sensor test, or performance benchmark. Native host integer widths can differ from the board, so timer rollover remains a device-test question.

Review verification: all 14 Python tests and the C++ host checks passed. The physical prototype was reported working with Logic / Alchemy; it was not connected to the review environment.

## Device verification

- Verify the renamed sketch uploads to the existing GIGA setup.
- Check startup zero, spinning response, and return to zero after stopping.
- Compare the response at slow and fast speeds, and inspect serial values around the mapping boundaries.
- Check the chosen IAC output and the actual Alchemy mapping.
- Record a short demonstration showing the spinner and the modulation response together.

## Contributions

Project by Lyla Noe, developed with AI collaboration. ChatGPT contributed implementation and formalization support; Gemini contributed to resolving the Hall-sensor input behavior. This preparation adds bridge validation, offline tests, host firmware checks, and documentation while preserving the supplied firmware.

## References

- https://docs.arduino.cc/hardware/giga-r1-wifi/
- https://mido.readthedocs.io/en/stable/messages/
- https://pyserial.readthedocs.io/en/latest/pyserial_api.html
