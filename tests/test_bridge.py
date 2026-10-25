from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import spinner_midi_bridge as bridge


class ParsingTests(unittest.TestCase):
    def test_firmware_packet(self):
        self.assertEqual(bridge.parse_cc_line("CC,74,93,RPM,416.1"), (74, 93))

    def test_legacy_short_packet(self):
        self.assertEqual(bridge.parse_cc_line("CC,74,0"), (74, 0))

    def test_whitespace_and_limits(self):
        self.assertEqual(bridge.parse_cc_line(" CC , 127 , 127 , RPM , 550.0 \r\n"), (127, 127))
        self.assertEqual(bridge.parse_cc_line("CC,0,0,RPM,0.0"), (0, 0))

    def test_debug_and_malformed_lines_are_rejected(self):
        for line in ["", "Spinner MIDI-value test ready", "CC,74", "CC,74,x", "CC,74,1,RPM", "CC,74,1,wrong,300", "CC,74,1,RPM,300,extra"]:
            with self.subTest(line=line):
                self.assertIsNone(bridge.parse_cc_line(line))

    def test_midi_values_out_of_range_are_rejected(self):
        for line in ["CC,-1,0", "CC,128,0", "CC,74,-1", "CC,74,128"]:
            self.assertIsNone(bridge.parse_cc_line(line))

    def test_nonfinite_negative_or_invalid_rpm_is_rejected(self):
        for rpm in ["nan", "inf", "-inf", "-0.1", "bad"]:
            self.assertIsNone(bridge.parse_cc_line(f"CC,74,93,RPM,{rpm}"))

    def test_valid_line_becomes_channel_one_control_message(self):
        sent = []
        def factory(kind, **fields):
            return {"type": kind, **fields}
        bridge.forward_cc_line("CC,74,93,RPM,416.1", SimpleNamespace(send=sent.append), message_factory=factory)
        self.assertEqual(sent, [{"type": "control_change", "channel": 0, "control": 74, "value": 93}])

    def test_invalid_line_never_sends_midi(self):
        sent = []
        self.assertIsNone(bridge.forward_cc_line("debug line", SimpleNamespace(send=sent.append)))
        self.assertEqual(sent, [])


class PortTests(unittest.TestCase):
    def test_explicit_serial_port_needs_no_detection(self):
        self.assertEqual(bridge.choose_serial_port("/dev/example"), "/dev/example")

    def test_unique_arduino_is_selected(self):
        ports = [SimpleNamespace(device="/dev/cu.usbmodem123", description="GIGA")]
        with patch.object(bridge, "available_serial_ports", return_value=ports):
            self.assertEqual(bridge.choose_serial_port(None), ports[0].device)

    def test_serial_ambiguity_is_reported(self):
        ports = [SimpleNamespace(device=f"/dev/cu.usbmodem{i}", description="Arduino") for i in [1, 2]]
        with patch.object(bridge, "available_serial_ports", return_value=ports), self.assertRaises(RuntimeError):
            bridge.choose_serial_port(None)

    def test_midi_exact_and_unique_partial_matches(self):
        with patch.object(bridge, "available_midi_outputs", return_value=["IAC Driver Spinner", "Other"]):
            self.assertEqual(bridge.choose_midi_port("IAC Driver Spinner"), "IAC Driver Spinner")
            self.assertEqual(bridge.choose_midi_port("spinner"), "IAC Driver Spinner")

    def test_midi_ambiguity_is_reported(self):
        with patch.object(bridge, "available_midi_outputs", return_value=["Spinner A", "Spinner B"]), self.assertRaises(RuntimeError):
            bridge.choose_midi_port("Spinner")


class BridgeLoopTests(unittest.TestCase):
    def test_simulated_serial_stream_forwards_values_and_resets_on_exit(self):
        sent = []
        class MidiOutput:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def send(self, message): sent.append(message)
        class SerialInput:
            lines = iter([b"CC,74,9", b"debug\n", b"CC,74,93,RPM,416.1\n"])
            reset = False
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def reset_input_buffer(self): self.reset = True
            def readline(self):
                try: return next(self.lines)
                except StopIteration: raise KeyboardInterrupt
        serial_input = SerialInput()
        def serial_factory(port, baud, timeout):
            self.assertEqual((port, baud, timeout), ("test-serial", 115200, 1))
            return serial_input
        fake_mido = SimpleNamespace(open_output=lambda name: MidiOutput(), Message=lambda kind, **fields: {"type": kind, **fields})
        fake_serial = SimpleNamespace(Serial=serial_factory)
        with patch.dict("sys.modules", {"mido": fake_mido, "serial": fake_serial}), patch.object(bridge.time, "sleep"), redirect_stdout(StringIO()), self.assertRaises(KeyboardInterrupt):
            bridge.run_bridge("test-serial", "test-midi")
        self.assertTrue(serial_input.reset)
        self.assertEqual([message["value"] for message in sent], [0, 93, 0])


if __name__ == "__main__":
    unittest.main()
