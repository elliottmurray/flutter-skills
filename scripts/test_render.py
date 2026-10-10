#!/usr/bin/env python3
"""Tiny stdlib tests for render.py helpers."""

import json
import tempfile
import unittest
from pathlib import Path

from render import copy_tree, is_skipped, package_name, render_text, main as render_main


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

    def test_copy_tree_copies_undecodable_file_verbatim(self):
        """A binary with an unlisted suffix must not be read as text."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            dest = Path(tmp) / "dest"
            src.mkdir()
            blob = b"\xf3\r\n{{APP_NAME}}"
            (src / "keystore.jks").write_bytes(blob)
            written = copy_tree(src, dest, {"APP_NAME": "Demo"}, force=True)
            self.assertEqual(written, ["keystore.jks"])
            self.assertEqual((dest / "keystore.jks").read_bytes(), blob)

    def test_copy_tree_copies_known_binary_suffix_verbatim(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            dest = Path(tmp) / "dest"
            src.mkdir()
            png = b"\x89PNG\r\n{{APP_NAME}}"
            (src / "icon.png").write_bytes(png)
            copy_tree(src, dest, {"APP_NAME": "Demo"}, force=True)
            self.assertEqual((dest / "icon.png").read_bytes(), png)

    def test_copy_tree_skips_build_detritus(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            dest = Path(tmp) / "dest"
            cache = src / "scripts" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "helper.cpython-311.pyc").write_bytes(b"\xf3\r\n\x00")
            (src / ".DS_Store").write_bytes(b"\x00\x01Bud1")
            (src / "scripts" / "helper.py").write_text("# {{APP_NAME}}\n")
            written = copy_tree(src, dest, {"APP_NAME": "Demo"}, force=True)
            self.assertEqual(written, ["scripts/helper.py"])
            self.assertFalse((dest / "scripts" / "__pycache__").exists())
            self.assertFalse((dest / ".DS_Store").exists())

    def test_is_skipped(self):
        self.assertTrue(is_skipped(Path("scripts/__pycache__/x.pyc")))
        self.assertTrue(is_skipped(Path("docs/.DS_Store")))
        self.assertFalse(is_skipped(Path("scripts/helper.py")))

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

    def test_l10n_overlay_seeds_english_and_the_tooling(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "app"
            dest.mkdir()
            rc = render_main(
                [
                    "--dest",
                    str(dest),
                    "--app-name",
                    "My Demo",
                    "--bundle-id",
                    "com.example.demo",
                    "--l10n",
                ]
            )
            self.assertEqual(rc, 0)
            self.assertIn("arb-dir: lib/l10n", (dest / "l10n.yaml").read_text())
            arb = (dest / "lib" / "l10n" / "app_en.arb").read_text()
            self.assertIn('"appTitle": "My Demo"', arb)
            self.assertIn(
                "package:my_demo/l10n/app_localizations.dart",
                (dest / "lib" / "l10n" / "l10n.dart").read_text(),
            )
            for rel in (
                "test/l10n/arb_parity_test.dart",
                "test/l10n/l10n_test.dart",
                "scripts/l10n_locales.py",
                "docs/localization.md",
            ):
                self.assertTrue((dest / rel).is_file(), rel)

    def test_no_l10n_files_without_the_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "app"
            dest.mkdir()
            render_main(
                ["--dest", str(dest), "--app-name", "Demo", "--bundle-id", "com.example.demo"]
            )
            self.assertFalse((dest / "l10n.yaml").exists())
            self.assertFalse((dest / "lib" / "l10n").exists())

    def _render_sync(self, dest: Path, flavour: str) -> int:
        return render_main(
            [
                "--dest", str(dest),
                "--app-name", "Demo",
                "--bundle-id", "com.example.demo",
                "--fastapi",
                "--sync-model", flavour,
            ]
        )

    def test_sync_model_intent_renders_twinned_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            self.assertEqual(self._render_sync(dest, "intent"), 0)
            self.assertTrue((dest / "lib/models/user_profile.dart").is_file())
            self.assertTrue((dest / "backend/models/user_profile.py").is_file())
            dart_test = (dest / "test/models/user_profile_test.dart").read_text()
            self.assertIn("package:demo/models/user_profile.dart", dart_test)
            self.assertFalse((dest / "test_vectors").exists())
            config = json.loads((dest / ".sync-model.json").read_text())
            self.assertEqual(config, {"tests": "intent"})

    def test_sync_model_shared_renders_vectors(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            self.assertEqual(self._render_sync(dest, "shared"), 0)
            vectors = json.loads((dest / "test_vectors/user_profile.json").read_text())
            self.assertEqual(vectors["model"], "UserProfile")
            self.assertTrue((dest / "test_vectors/vectors.schema.json").is_file())
            self.assertTrue((dest / "test/support/test_vectors.dart").is_file())
            self.assertTrue((dest / "backend/tests/vectors.py").is_file())
            config = json.loads((dest / ".sync-model.json").read_text())
            self.assertEqual(config, {"tests": "shared"})

    def test_sync_model_needs_fastapi(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(SystemExit):
            render_main(
                [
                    "--dest", tmp,
                    "--app-name", "Demo",
                    "--bundle-id", "com.example.demo",
                    "--sync-model", "intent",
                ]
            )


if __name__ == "__main__":
    unittest.main()
