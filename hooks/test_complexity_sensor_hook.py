#!/usr/bin/env python3
"""Stdlib tests for the complexity PostToolUse hook."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from complexity_sensor_hook import analyze, main, reminder


class AnalyzeTest(unittest.TestCase):
    def test_ignores_non_source(self):
        self.assertEqual(analyze("README.md"), [])

    def test_quiet_when_sensor_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("complexity_sensor_hook.PROJECT_DIR", Path(tmp)), patch(
                "complexity_sensor_hook.SENSOR", Path(tmp) / "scripts" / "complexity_sensor.py"
            ):
                self.assertEqual(analyze("lib/main.dart"), [])


class ReminderTest(unittest.TestCase):
    def test_lists_each_function(self):
        text = reminder(
            "lib/foo.dart",
            [{"qualname": "Foo.bar", "lineno": 12, "complexity": 14, "ceiling": 10}],
        )
        self.assertIn("lib/foo.dart", text)
        self.assertIn("Foo.bar", text)
        self.assertIn("14", text)
        self.assertIn("10", text)


class MainTest(unittest.TestCase):
    def test_invalid_stdin_is_quiet(self):
        with patch("sys.stdin", io.StringIO("not-json")), patch(
            "sys.stdout", io.StringIO()
        ) as out:
            self.assertEqual(main(), 0)
            self.assertEqual(out.getvalue(), "")

    def test_markdown_edit_is_quiet(self):
        event = json.dumps({"tool_input": {"file_path": "docs/readme.md"}})
        with patch("sys.stdin", io.StringIO(event)), patch(
            "sys.stdout", io.StringIO()
        ) as out:
            self.assertEqual(main(), 0)
            self.assertEqual(out.getvalue(), "")

    def test_over_ceiling_emits_additional_context(self):
        event = json.dumps({"tool_input": {"file_path": "lib/foo.dart"}})
        over = [{"qualname": "Foo.bar", "lineno": 3, "complexity": 12, "ceiling": 10}]
        with patch("sys.stdin", io.StringIO(event)), patch(
            "sys.stdout", io.StringIO()
        ) as out, patch("complexity_sensor_hook.analyze", return_value=over):
            self.assertEqual(main(), 0)
            payload = json.loads(out.getvalue())
            ctx = payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("Foo.bar", ctx)
            self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "PostToolUse")


if __name__ == "__main__":
    unittest.main()
