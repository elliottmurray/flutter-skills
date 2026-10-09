#!/usr/bin/env python3
"""Stdlib tests for the l10n parity PostToolUse hook."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import l10n_parity_hook as hook

EN = {
    "@@locale": "en",
    "newGame": "NEW GAME",
    "mistakesCount": "{count, plural, =1{1 mistake} other{{count} mistakes}}",
    "@mistakesCount": {"placeholders": {"count": {"type": "int"}}},
}
FR = {
    "@@locale": "fr",
    "newGame": "NOUVELLE PARTIE",
    "mistakesCount": "{count, plural, =0{0 erreur} =1{1 erreur} other{{count} erreurs}}",
}

PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
\t<key>CFBundleLocalizations</key>
\t<array>
{strings}
\t</array>
\t<key>CFBundleDisplayName</key>
\t<string>Demo</string>
</dict>
</plist>
"""


def _package(root: Path, *, l10n_yaml: str | None = "arb-dir: lib/l10n\n", **locales) -> Path:
    if l10n_yaml is not None:
        (root / "l10n.yaml").write_text(l10n_yaml)
    arb_dir = root / "lib" / "l10n"
    arb_dir.mkdir(parents=True)
    for lang, messages in locales.items():
        (arb_dir / f"app_{lang}.arb").write_text(json.dumps(messages))
    return arb_dir


def _plist(root: Path, *codes: str) -> None:
    runner = root / "ios" / "Runner"
    runner.mkdir(parents=True)
    strings = "\n".join(f"\t\t<string>{c}</string>" for c in codes)
    (runner / "Info.plist").write_text(PLIST.format(strings=strings))


class ParityProblemsTest(unittest.TestCase):
    def test_silent_when_every_locale_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            arb_dir = _package(Path(tmp), en=EN, fr=FR)
            self.assertEqual(hook.parity_problems(arb_dir, "app_en.arb"), [])

    def test_reports_a_missing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            fr = {k: v for k, v in FR.items() if k != "newGame"}
            arb_dir = _package(Path(tmp), en=EN, fr=fr)
            self.assertEqual(
                hook.parity_problems(arb_dir, "app_en.arb"),
                ["app_fr.arb: missing newGame"],
            )

    def test_reports_a_key_the_template_does_not_have(self):
        with tempfile.TemporaryDirectory() as tmp:
            arb_dir = _package(Path(tmp), en=EN, fr={**FR, "stray": "x"})
            self.assertEqual(
                hook.parity_problems(arb_dir, "app_en.arb"),
                ["app_fr.arb: extra stray (not in the template)"],
            )

    def test_reports_placeholder_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            fr = {**FR, "mistakesCount": "{n, plural, other{{n} erreurs}}"}
            arb_dir = _package(Path(tmp), en=EN, fr=fr)
            self.assertEqual(
                hook.parity_problems(arb_dir, "app_en.arb"),
                ["app_fr.arb: mistakesCount placeholders {n} vs template {count}"],
            )

    def test_region_locales_share_the_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            arb_dir = _package(Path(tmp), en=EN, pt_BR={"@@locale": "pt_BR"})
            self.assertEqual(
                sorted(hook.locale_files(arb_dir, "app_en.arb")), ["en", "pt_BR"]
            )


class PlaceholderTest(unittest.TestCase):
    def test_plural_branch_text_is_not_a_placeholder(self):
        self.assertEqual(hook.placeholders(EN["mistakesCount"]), {"count"})

    def test_metadata_values_are_ignored(self):
        self.assertEqual(hook.placeholders({"placeholders": {}}), set())


class ConfigTest(unittest.TestCase):
    def test_reads_arb_dir_and_template_from_l10n_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "l10n.yaml").write_text(
                "arb-dir: lib/i18n  # strings\ntemplate-arb-file: 'intl_en.arb'\n"
            )
            arb_dir, template = hook.read_config(root)
            self.assertEqual(arb_dir, root / "lib" / "i18n")
            self.assertEqual(template, "intl_en.arb")

    def test_defaults_match_gen_l10n(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "l10n.yaml").write_text("output-class: AppLocalizations\n")
            self.assertEqual(hook.read_config(root), (root / "lib/l10n", "app_en.arb"))


class PlistTest(unittest.TestCase):
    def test_quiet_without_an_ios_plist(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(hook.plist_problems(Path(tmp), ["en", "fr"]), [])

    def test_reports_a_locale_missing_from_the_plist(self):
        with tempfile.TemporaryDirectory() as tmp:
            _plist(Path(tmp), "en")
            self.assertEqual(
                hook.plist_problems(Path(tmp), ["en", "fr"]),
                ["ios/Runner/Info.plist: CFBundleLocalizations is missing fr"],
            )

    def test_reports_a_plist_locale_with_no_arb(self):
        with tempfile.TemporaryDirectory() as tmp:
            _plist(Path(tmp), "en", "fr", "de")
            self.assertEqual(
                hook.plist_problems(Path(tmp), ["en", "fr"]),
                ["ios/Runner/Info.plist: CFBundleLocalizations lists de but there is no ARB for it"],
            )

    def test_region_separators_compare_equal(self):
        with tempfile.TemporaryDirectory() as tmp:
            _plist(Path(tmp), "en", "pt-BR")
            self.assertEqual(hook.plist_problems(Path(tmp), ["en", "pt_BR"]), [])


class MainTest(unittest.TestCase):
    def _run(self, project: Path, file_path: str) -> str:
        out = io.StringIO()
        event = json.dumps({"tool_input": {"file_path": file_path}})
        with patch.object(hook, "PROJECT_DIR", project), patch(
            "sys.stdin", io.StringIO(event)
        ), patch("sys.stdout", out):
            self.assertEqual(hook.main(), 0)
        return out.getvalue()

    def _context(self, out: str) -> str:
        return json.loads(out)["hookSpecificOutput"]["additionalContext"]

    def test_prompts_a_cross_language_review_after_an_arb_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            arb_dir = _package(root, en=EN, fr={"@@locale": "fr"})
            context = self._context(self._run(root, str(arb_dir / "app_en.arb")))
            self.assertIn("app_fr.arb: missing newGame", context)
            self.assertIn("en, fr", context)
            self.assertIn("flutter gen-l10n", context)
            self.assertIn("lib/l10n/app_en.arb", context)

    def test_still_reminds_when_everything_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            arb_dir = _package(root, en=EN, fr=FR)
            _plist(root, "en", "fr")
            context = self._context(self._run(root, str(arb_dir / "app_fr.arb")))
            self.assertIn("match across every locale", context)
            self.assertIn("Translate new or changed values", context)

    def test_includes_plist_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            arb_dir = _package(root, en=EN, fr=FR)
            _plist(root, "en")
            context = self._context(self._run(root, str(arb_dir / "app_fr.arb")))
            self.assertIn("CFBundleLocalizations is missing fr", context)

    def test_finds_a_nested_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            app = root / "app"
            app.mkdir()
            _package(app, en=EN, fr={"@@locale": "fr"})
            context = self._context(self._run(root, "app/lib/l10n/app_fr.arb"))
            self.assertIn("app_fr.arb: missing newGame", context)
            self.assertIn("app/lib/l10n/app_fr.arb", context)

    def test_ignores_generated_dart_and_unrelated_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            arb_dir = _package(root, en=EN, fr=FR)
            self.assertEqual(self._run(root, str(arb_dir / "app_localizations.dart")), "")
            self.assertEqual(self._run(root, str(root / "lib" / "main.dart")), "")

    def test_quiet_without_l10n_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            arb_dir = _package(root, l10n_yaml=None, en=EN, fr={"@@locale": "fr"})
            self.assertEqual(self._run(root, str(arb_dir / "app_en.arb")), "")

    def test_quiet_for_an_arb_outside_the_arb_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            _package(root, en=EN, fr=FR)
            fixtures = root / "test" / "fixtures"
            fixtures.mkdir(parents=True)
            self.assertEqual(self._run(root, str(fixtures / "sample.arb")), "")

    def test_bad_stdin_is_quiet(self):
        out = io.StringIO()
        with patch("sys.stdin", io.StringIO("not json")), patch("sys.stdout", out):
            self.assertEqual(hook.main(), 0)
        self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
