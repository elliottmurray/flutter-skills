#!/usr/bin/env python3
"""Tiny stdlib tests for render.py helpers."""

import tempfile
import unittest
from pathlib import Path

from render import copy_tree, package_name, render_text, main as render_main


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

    def test_nested_package_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            dest = Path(tmp) / "dest"
            nested = src / "test" / "config"
            nested.mkdir(parents=True)
            (nested / "app_channel_test.dart").write_text(
                "import 'package:{{PACKAGE_NAME}}/config/app_channel.dart';\n"
            )
            copy_tree(src, dest, {"PACKAGE_NAME": "demo_app"}, force=True)
            self.assertEqual(
                (dest / "test" / "config" / "app_channel_test.dart").read_text(),
                "import 'package:demo_app/config/app_channel.dart';\n",
            )

    def test_render_copies_sim_driver(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "app"
            dest.mkdir()
            rc = render_main(
                [
                    "--dest",
                    str(dest),
                    "--app-name",
                    "Demo",
                    "--bundle-id",
                    "com.example.demo",
                ]
            )
            self.assertEqual(rc, 0)
            driver = dest / "scripts" / "sim_driver.py"
            self.assertTrue(driver.is_file(), "sim_driver.py should be copied into the app")
            self.assertIn("tap", driver.read_text())

    def test_fastapi_overlay_includes_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "app"
            dest.mkdir()
            rc = render_main(
                [
                    "--dest",
                    str(dest),
                    "--app-name",
                    "Demo",
                    "--bundle-id",
                    "com.example.demo",
                    "--fastapi",
                ]
            )
            self.assertEqual(rc, 0)
            self.assertTrue((dest / "backend" / "Dockerfile").is_file())
            self.assertIn("uvicorn", (dest / "backend" / "Dockerfile").read_text())

    def test_firebase_overlay_includes_app_check_doc(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "app"
            dest.mkdir()
            rc = render_main(
                [
                    "--dest",
                    str(dest),
                    "--app-name",
                    "Demo",
                    "--bundle-id",
                    "com.example.demo",
                    "--firebase",
                ]
            )
            self.assertEqual(rc, 0)
            doc = dest / "docs" / "app-check.md"
            self.assertTrue(doc.is_file())
            registry = (dest / "lib" / "config" / "flag_registry.dart").read_text()
            self.assertIn("DISABLE_FIREBASE_APP_CHECK", registry)

if __name__ == "__main__":
    unittest.main()
