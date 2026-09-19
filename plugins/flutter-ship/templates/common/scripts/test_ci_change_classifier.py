#!/usr/bin/env python3
"""Classifier cases: docs skip, app code runs the full Flutter set, and the
whole table follows `project_layout.py` when the project is laid out
differently."""

import os
import unittest
from contextlib import contextmanager

import project_layout as layout
from ci_change_classifier import _exact_rules, _prefix_rules, classify


@contextmanager
def layout_of(*, dart: str, python: str):
    """Run a block with the layout pinned, caches cleared either way.

    Every test pins a layout explicitly, so the suite passes whether or not
    this project has a `.flutter-ship.json` of its own.
    """
    previous = {
        "FLUTTER_SHIP_DART_PACKAGES": os.environ.get("FLUTTER_SHIP_DART_PACKAGES"),
        "FLUTTER_SHIP_PYTHON_PACKAGES": os.environ.get("FLUTTER_SHIP_PYTHON_PACKAGES"),
    }
    os.environ["FLUTTER_SHIP_DART_PACKAGES"] = dart
    os.environ["FLUTTER_SHIP_PYTHON_PACKAGES"] = python
    _prefix_rules.cache_clear()
    _exact_rules.cache_clear()
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _prefix_rules.cache_clear()
        _exact_rules.cache_clear()


class DefaultLayoutTest(unittest.TestCase):
    """App at the repo root, service in `backend/` — what /setup-project renders."""

    def setUp(self):
        self._layout = layout_of(dart=".", python="backend")
        self._layout.__enter__()
        self.addCleanup(self._layout.__exit__, None, None, None)

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

    def test_backend_tests_skip_complexity(self):
        flags = classify(["backend/tests/test_health.py"])
        self.assertTrue(flags["python_unit"])
        self.assertFalse(flags["python_complexity"])

    def test_pubspec_runs_full_flutter(self):
        flags = classify(["pubspec.yaml"])
        self.assertTrue(flags["flutter_integration"])

    def test_analysis_options_is_lint_only(self):
        flags = classify(["analysis_options.yaml"])
        self.assertTrue(flags["flutter_lint"])
        self.assertFalse(flags["flutter_unit"])


class RelocatedLayoutTest(unittest.TestCase):
    """Move the app to `app/` and the service to `api/`: rules follow."""

    def setUp(self):
        self._layout = layout_of(dart="app", python="api")
        self._layout.__enter__()
        self.addCleanup(self._layout.__exit__, None, None, None)

    def test_relocated_dart_package(self):
        flags = classify(["app/lib/main.dart"])
        self.assertTrue(flags["flutter_integration"])
        self.assertFalse(flags["python_lint"])

    def test_relocated_manifest(self):
        self.assertTrue(classify(["app/pubspec.yaml"])["flutter_unit"])
        self.assertTrue(classify(["app/analysis_options.yaml"])["flutter_lint"])

    def test_relocated_python_package(self):
        flags = classify(["api/main.py"])
        self.assertTrue(flags["python_complexity"])
        self.assertFalse(flags["flutter_lint"])

    def test_relocated_python_tests_skip_complexity(self):
        flags = classify(["api/tests/test_health.py"])
        self.assertTrue(flags["python_unit"])
        self.assertFalse(flags["python_complexity"])

    def test_old_root_paths_go_quiet_after_a_move(self):
        """Nothing claims `lib/` once the app lives in `app/`."""
        self.assertFalse(any(classify(["lib/main.dart"]).values()))

    def test_scripts_stay_at_the_repo_root(self):
        self.assertTrue(all(classify(["scripts/ci_change_classifier.py"]).values()))


class LayoutTest(unittest.TestCase):
    def test_shipped_defaults(self):
        """The module's own defaults, ignoring any project config."""
        self.assertEqual(list(layout.DEFAULT_DART_PACKAGES), ["."])
        self.assertEqual(list(layout.DEFAULT_PYTHON_PACKAGES), ["backend"])

    def test_join_treats_root_package_as_empty(self):
        self.assertEqual(layout.join(".", "lib"), "lib")
        self.assertEqual(layout.join("app", "lib"), "app/lib")

    def test_lang_for_path(self):
        with layout_of(dart=".", python="backend"):
            self.assertEqual(layout.lang_for_path("backend/main.py"), "python")
            self.assertEqual(layout.lang_for_path("lib/main.dart"), "dart")


if __name__ == "__main__":
    unittest.main()
