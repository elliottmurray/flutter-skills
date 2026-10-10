#!/usr/bin/env python3
"""Stdlib tests for plugin_preflight.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import plugin_preflight as pf

LONG_README = "# x\n\n" + "word " * 45


def entry(path: str, mode: str = "100644") -> str:
    return f"{mode} 0000000000000000000000000000000000000000 0\t{path}"


class ReadmeWordsTest(unittest.TestCase):
    def test_code_blocks_do_not_count(self):
        text = "one two three\n```\nfour five six seven\n```\n"
        self.assertEqual(pf.readme_words(text), 3)


class ManifestTest(unittest.TestCase):
    def write_plugin(self, root: Path, manifest: dict, readme: str | None) -> None:
        (root / ".claude-plugin").mkdir()
        (root / ".claude-plugin/plugin.json").write_text(json.dumps(manifest))
        if readme is not None:
            (root / "README.md").write_text(readme)

    def test_complete_manifest_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_plugin(root, {"name": "p", "description": "d", "version": "1.0.0",
                                     "author": {"name": "a"}, "license": "MIT"}, LONG_README)
            self.assertEqual(pf.check_manifest(root, {"README.md"}), [])

    def test_missing_author_licence_and_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_plugin(root, {"name": "p", "description": "d", "version": "1.0"}, None)
            problems = " ".join(pf.check_manifest(root, set()))
            for needle in ("author", "semver", "LICENSE", "README.md missing"):
                self.assertIn(needle, problems)

    def test_short_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_plugin(root, {"name": "p", "description": "d", "version": "1.0.0",
                                     "author": "a", "license": "MIT"}, "too short")
            self.assertIn("under 40 words", pf.check_manifest(root, {"README.md"})[0])


class FilesTest(unittest.TestCase):
    def test_symlink_submodule_and_junk(self):
        problems = " ".join(pf.check_files([
            entry("p/link", "120000"),
            entry("p/sub", "160000"),
            entry("p/a/.DS_Store", "120000"),
        ]))
        self.assertIn("symlink", problems)
        self.assertIn("submodule", problems)
        self.assertIn("OS junk", problems)

    def test_windows_names_and_case_clash(self):
        problems = " ".join(pf.check_files([
            entry("p/con.md", "120000"),
            entry("p/a:b", "120000"),
            entry("p/Readme", "120000"),
            entry("p/readme", "120000"),
        ]))
        self.assertIn("p/con.md: name is not valid", problems)
        self.assertIn("p/a:b: name is not valid", problems)
        self.assertIn("only by case", problems)

    def test_large_and_binary_files(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(pf, "REPO_ROOT", Path(tmp)):
            (Path(tmp) / "big.md").write_text("x" * (pf.MAX_TEXT_BYTES + 1))
            (Path(tmp) / "blob.bin").write_bytes(b"\0\1\2")
            (Path(tmp) / "pic.png").write_bytes(b"\0" * (pf.MAX_TEXT_BYTES + 1))
            problems = " ".join(pf.check_files([
                entry("big.md"), entry("blob.bin"), entry("pic.png")]))
        self.assertIn("big.md", problems)
        self.assertIn("blob.bin: binary", problems)
        self.assertNotIn("pic.png", problems)


if __name__ == "__main__":
    unittest.main()
