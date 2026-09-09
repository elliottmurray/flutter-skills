#!/usr/bin/env python3
"""A few classifier cases — docs skip, app code runs the full Flutter set."""

import unittest

from ci_change_classifier import classify


class ClassifyTest(unittest.TestCase):
    def test_docs_run_nothing(self):
        flags = classify(["docs/readme.md", "CATALOG.md"])
        self.assertFalse(any(flags.values()))

    def test_lib_runs_full_flutter(self):
        flags = classify(["lib/main.dart"])
        self.assertTrue(flags["flutter_lint"])
        self.assertTrue(flags["flutter_unit"])
        self.assertTrue(flags["flutter_complexity"])
        self.assertTrue(flags["flutter_integration"])

    def test_unit_test_skips_integration(self):
        flags = classify(["test/widget_test.dart"])
        self.assertTrue(flags["flutter_unit"])
        self.assertFalse(flags["flutter_integration"])

    def test_backend_python(self):
        flags = classify(["backend/main.py"])
        self.assertTrue(flags["python_lint"])
        self.assertTrue(flags["python_unit"])
        self.assertFalse(flags["flutter_integration"])


if __name__ == "__main__":
    unittest.main()
