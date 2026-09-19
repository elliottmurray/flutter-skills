#!/usr/bin/env python3
"""Stdlib tests for sim_driver helpers (no Simulator required)."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sim_driver import (
    decode_frame,
    encode_text_frame,
    parse_machine_ws_uri,
    parse_vm_service_url,
    tap_expression,
    ws_url_from_observatory,
    guess_bundle_id,
    load_state,
    save_state,
    build_parser,
)


class ObservatoryUrlTest(unittest.TestCase):
    def test_http_to_ws_appends_ws(self):
        self.assertEqual(
            ws_url_from_observatory("http://127.0.0.1:12345/AUTH/"),
            "ws://127.0.0.1:12345/AUTH/ws",
        )

    def test_strips_and_https(self):
        self.assertEqual(
            ws_url_from_observatory(" https://127.0.0.1:9/tok "),
            "wss://127.0.0.1:9/tok/ws",
        )

    def test_does_not_double_ws(self):
        self.assertEqual(
            ws_url_from_observatory("http://127.0.0.1:1/x/ws"),
            "ws://127.0.0.1:1/x/ws",
        )


class BannerParseTest(unittest.TestCase):
    def test_standard_banner(self):
        text = (
            "A Dart VM Service on iPhone 16 is available at: "
            "http://127.0.0.1:54321/AbC123/\n"
        )
        self.assertEqual(
            parse_vm_service_url(text),
            "http://127.0.0.1:54321/AbC123/",
        )

    def test_listening_on(self):
        text = "The Dart VM Service is listening on: http://127.0.0.1:9/z/"
        self.assertEqual(parse_vm_service_url(text), "http://127.0.0.1:9/z/")

    def test_no_match(self):
        self.assertIsNone(parse_vm_service_url("Flutter run key commands."))


class MachineParseTest(unittest.TestCase):
    def test_debug_port_ws(self):
        line = json.dumps(
            [
                {
                    "event": "app.debugPort",
                    "params": {"wsUri": "ws://127.0.0.1:9/tok=/ws"},
                }
            ]
        )
        self.assertEqual(parse_machine_ws_uri(line), "ws://127.0.0.1:9/tok=/ws")

    def test_ignores_other_events(self):
        line = json.dumps([{"event": "app.started", "params": {}}])
        self.assertIsNone(parse_machine_ws_uri(line))

    def test_garbage(self):
        self.assertIsNone(parse_machine_ws_uri("not json"))
        self.assertIsNone(parse_machine_ws_uri("{}\n"))

    def test_uris_from_mixed_log(self):
        from sim_driver import _uris_from_log

        machine = json.dumps(
            [{"event": "app.debugPort", "params": {"wsUri": "ws://127.0.0.1:9/t/ws"}}]
        )
        ws, http = _uris_from_log(f"hello\n{machine}\n")
        self.assertEqual(ws, "ws://127.0.0.1:9/t/ws")
        self.assertIsNone(http)


class TapExpressionTest(unittest.TestCase):
    def test_embeds_coordinates(self):
        expr = tap_expression(12.5, 80)
        self.assertIn("12.5", expr)
        self.assertIn("80", expr)
        self.assertIn("PointerDownEvent", expr)
        self.assertIn("PointerUpEvent", expr)


class FrameRoundTripTest(unittest.TestCase):
    def test_masked_text_roundtrip(self):
        mask = b"\x00\x01\x02\x03"
        frame = encode_text_frame('{"jsonrpc":"2.0"}', mask=mask)
        decoded = decode_frame(frame)
        self.assertIsNotNone(decoded)
        opcode, payload, consumed = decoded
        self.assertEqual(opcode, 0x1)
        self.assertEqual(payload, b'{"jsonrpc":"2.0"}')
        self.assertEqual(consumed, len(frame))

    def test_incomplete_returns_none(self):
        self.assertIsNone(decode_frame(b"\x81"))


class StateTest(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            save_state(path, {"udid": "ABC", "ws_url": "ws://x"})
            self.assertEqual(load_state(path)["udid"], "ABC")

    def test_missing_is_empty(self):
        self.assertEqual(load_state(Path("/no/such/state.json")), {})


class BundleIdTest(unittest.TestCase):
    def test_reads_pbx(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pbx = root / "ios" / "Runner.xcodeproj"
            pbx.mkdir(parents=True)
            (pbx / "project.pbxproj").write_text(
                "PRODUCT_BUNDLE_IDENTIFIER = com.example.demo;\n"
            )
            self.assertEqual(guess_bundle_id(root), "com.example.demo")

    def test_skips_build_setting_refs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pbx = root / "ios" / "Runner.xcodeproj"
            pbx.mkdir(parents=True)
            (pbx / "project.pbxproj").write_text(
                "PRODUCT_BUNDLE_IDENTIFIER = $(PRODUCT_BUNDLE_IDENTIFIER);\n"
            )
            self.assertIsNone(guess_bundle_id(root))


class ParserTest(unittest.TestCase):
    def test_known_commands(self):
        parser = build_parser()
        for name in (
            "boot",
            "run",
            "status",
            "tap",
            "eval",
            "screenshot",
            "tree",
            "background",
            "foreground",
            "kill",
            "shutdown",
        ):
            args = parser.parse_args([name] if name not in {"tap", "eval"} else (
                ["tap", "1", "2"] if name == "tap" else ["eval", "1+1"]
            ))
            self.assertEqual(args.command, name)

    def test_no_app_specific_commands(self):
        parser = build_parser()
        with self.assertRaises(SystemExit), patch("sys.stderr", io.StringIO()):
            parser.parse_args(["solve"])


if __name__ == "__main__":
    unittest.main()
