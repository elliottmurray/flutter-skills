#!/usr/bin/env python3
"""Adding a language touches the ARB, the iOS plist and pubspec together."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import l10n_locales as l10n

FLUTTER_CREATE_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
\t<key>CFBundleDevelopmentRegion</key>
\t<string>$(DEVELOPMENT_LANGUAGE)</string>
\t<key>CFBundleDisplayName</key>
\t<string>Demo</string>
</dict>
</plist>
"""

PUBSPEC = """name: demo
environment:
  sdk: ^3.8.0

dependencies:
  flutter:
    sdk: flutter

flutter:
  uses-material-design: true
"""

EN = {
    "@@locale": "en",
    "appTitle": "Demo",
    "greeting": "Hello {name}",
    "@greeting": {"placeholders": {"name": {"type": "String"}}},
}


def _package(root: Path, **locales: dict) -> Path:
    arb_dir = root / "lib" / "l10n"
    arb_dir.mkdir(parents=True)
    for code, data in {"en": EN, **locales}.items():
        (arb_dir / f"app_{code}.arb").write_text(json.dumps(data))
    runner = root / "ios" / "Runner"
    runner.mkdir(parents=True)
    (runner / "Info.plist").write_text(FLUTTER_CREATE_PLIST)
    (root / "pubspec.yaml").write_text(PUBSPEC)
    return root


def _quiet(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args)


class CanonicalTest(unittest.TestCase):
    def test_normalizes_separators_and_case(self):
        self.assertEqual(l10n.canonical("pt-br"), "pt_BR")
        self.assertEqual(l10n.canonical("zh-hant-tw"), "zh_Hant_TW")
        self.assertEqual(l10n.canonical("FR"), "fr")

    def test_rejects_nonsense(self):
        with self.assertRaises(ValueError):
            l10n.canonical("french")


class AddTest(unittest.TestCase):
    def test_new_arb_copies_template_messages_without_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = _package(Path(tmp))
            self.assertEqual(_quiet(l10n.cmd_add, pkg, ["fr"]), 0)
            fr = json.loads((pkg / "lib/l10n/app_fr.arb").read_text())
            self.assertEqual(
                fr, {"@@locale": "fr", "appTitle": "Demo", "greeting": "Hello {name}"}
            )

    def test_lists_english_first_in_the_plist(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = _package(Path(tmp))
            _quiet(l10n.cmd_add, pkg, ["es", "de"])
            text = (pkg / "ios/Runner/Info.plist").read_text()
            self.assertEqual(l10n.plist_locales(text), ["en", "de", "es"])
            self.assertIn("\t<key>CFBundleLocalizations</key>\n\t<array>\n\t\t<string>en", text)

    def test_never_overwrites_an_existing_translation(self):
        with tempfile.TemporaryDirectory() as tmp:
            fr = {"@@locale": "fr", "appTitle": "Demo", "greeting": "Bonjour {name}"}
            pkg = _package(Path(tmp), fr=fr)
            _quiet(l10n.cmd_add, pkg, ["fr"])
            self.assertEqual(json.loads((pkg / "lib/l10n/app_fr.arb").read_text()), fr)

    def test_region_needs_its_base_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = _package(Path(tmp))
            self.assertEqual(_quiet(l10n.cmd_add, pkg, ["pt_BR"]), 1)
            self.assertFalse((pkg / "lib/l10n/app_pt_BR.arb").exists())
            self.assertEqual(_quiet(l10n.cmd_add, pkg, ["pt", "pt-BR"]), 0)
            self.assertTrue((pkg / "lib/l10n/app_pt_BR.arb").exists())


class PlistTest(unittest.TestCase):
    def test_replaces_an_existing_array(self):
        text = l10n.set_plist_locales(FLUTTER_CREATE_PLIST, ["en", "fr"])
        text = l10n.set_plist_locales(text, ["en", "de"])
        self.assertEqual(l10n.plist_locales(text), ["en", "de"])
        self.assertEqual(text.count("CFBundleLocalizations"), 1)
        self.assertIn("<key>CFBundleDisplayName</key>", text)

    def test_sync_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = _package(Path(tmp), fr={"@@locale": "fr"})
            self.assertTrue(l10n.sync_plist(pkg).startswith("set"))
            self.assertTrue(l10n.sync_plist(pkg).startswith("ok"))

    def test_sync_skips_a_project_without_ios(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = _package(Path(tmp))
            (pkg / "ios/Runner/Info.plist").unlink()
            self.assertTrue(l10n.sync_plist(pkg).startswith("skip"))


class PubspecTest(unittest.TestCase):
    def test_adds_generate_to_the_flutter_section(self):
        out = l10n.enable_generate(PUBSPEC)
        self.assertIn("flutter:\n  generate: true\n  uses-material-design: true", out)
        self.assertIn("  flutter:\n    sdk: flutter", out)

    def test_flips_generate_false(self):
        out = l10n.enable_generate(PUBSPEC.replace("flutter:\n  uses", "flutter:\n  generate: false\n  uses"))
        self.assertEqual(out.count("generate:"), 1)
        self.assertIn("generate: true", out)

    def test_is_idempotent(self):
        once = l10n.enable_generate(PUBSPEC)
        self.assertEqual(l10n.enable_generate(once), once)

    def test_reports_missing_dependencies(self):
        self.assertEqual(
            l10n.missing_dependencies(PUBSPEC),
            [
                "flutter pub add flutter_localizations --sdk=flutter",
                "flutter pub add intl:any",
            ],
        )

    def test_setup_fails_until_dependencies_are_added(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = _package(Path(tmp))
            self.assertEqual(_quiet(l10n.cmd_setup, pkg), 1)
            pubspec = pkg / "pubspec.yaml"
            pubspec.write_text(
                pubspec.read_text().replace(
                    "    sdk: flutter\n",
                    "    sdk: flutter\n  flutter_localizations:\n    sdk: flutter\n  intl: any\n",
                    1,
                )
            )
            self.assertEqual(_quiet(l10n.cmd_setup, pkg), 0)


class CheckTest(unittest.TestCase):
    def test_clean_after_add_and_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = _package(Path(tmp))
            _quiet(l10n.cmd_add, pkg, ["fr"])
            self.assertEqual(l10n.parity_problems(pkg), [])

    def test_reports_key_placeholder_and_plist_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = _package(Path(tmp), fr={"@@locale": "fr", "greeting": "Salut {nom}", "x": "y"})
            self.assertEqual(
                l10n.parity_problems(pkg),
                [
                    "app_fr.arb: missing appTitle",
                    "app_fr.arb: extra x",
                    "app_fr.arb: greeting placeholders differ from app_en.arb",
                    "ios/Runner/Info.plist: CFBundleLocalizations [] != ARB locales",
                ],
            )


if __name__ == "__main__":
    unittest.main()
