#!/usr/bin/env python3
"""Tiny stdlib tests for render.py helpers."""

import tempfile
import unittest
from pathlib import Path

from render import copy_tree, package_name, render_text


class PackageNameTest(unittest.TestCase):
    def test_spaces_and_case(self):
        self.assertEqual(package_name("My App"), "my_app")

    def test_leading_digit(self):
        self.assertEqual(package_name("99 bottles"), "app_99_bottles")


class RenderTest(unittest.TestCase):
    def test_placeholder(self):
        self.assertEqual(render_text("hi {{APP_NAME}}", {"APP_NAME": "Demo"}), "hi Demo")

    def test_copy_tree_substitutes(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            dest = Path(tmp) / "dest"
            src.mkdir()
            (src / "hello.txt").write_text("{{APP_NAME}}\n")
            written = copy_tree(src, dest, {"APP_NAME": "Demo"}, force=True)
            self.assertEqual(written, ["hello.txt"])
            self.assertEqual((dest / "hello.txt").read_text(), "Demo\n")


if __name__ == "__main__":
    unittest.main()
