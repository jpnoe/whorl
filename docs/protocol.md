# WHORL serial protocol

The firmware emits newline-terminated UTF-8/ASCII-compatible text at 115200 baud:

```text
CC,74,93,RPM,416.1
```

| Field | Meaning |
| --- | --- |
| `CC` | Control-change record marker |
| `74` | Integer MIDI controller number, 0–127 |
| `93` | Integer MIDI controller value, 0–127 |
| `RPM` | RPM diagnostic field marker |
| `416.1` | Nonnegative finite RPM estimate |

The bridge also accepts the legacy three-field form `CC,74,93`. Other field counts, invalid numbers, out-of-range MIDI values, and invalid RPM diagnostics are rejected. Whitespace around fields is ignored. Debug and startup messages are printed as diagnostics rather than converted to MIDI.

The supplied firmware always emits controller 74. The parser accepts any valid controller number so it remains usable with an explicitly modified sketch. The bridge's startup and shutdown resting message is configured for the supplied CC 74 sketch.

The bridge forwards only the controller number and value to a `control_change` message on zero-based channel 0, which is displayed as MIDI channel 1 in the DAW. RPM is diagnostic data; it is not a second MIDI message.

The sketch emits a record only when its quantized controller value changes. Consequently, packets are not a fixed-rate RPM sampling stream. A zero-valued record is emitted after stopping only if the last sent controller value was nonzero.

The magnet-slot method assumes consistent pulse detection. Missed or extra pulses can alter slot association and distort the RPM estimate; check this on the physical sensor setup.

The bridge uses timed line reads. A fragment that times out before a newline is dropped rather than forwarded as a short control packet; the next complete packet is needed to resume valid updates. A future framing layer could accumulate such fragments if required by device testing.

## Preparation changes

- Hardware dependencies load lazily so parsing and command help can run offline.
- The complete five-field format validates its RPM marker and numeric diagnostic.
- Port matching retains explicit errors for missing or ambiguous outputs.
- The processing loop establishes and restores the supplied controller's resting value.
- Firmware logic and tuning constants remain unchanged.
