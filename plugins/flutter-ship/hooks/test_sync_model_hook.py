#!/usr/bin/env python3
"""Stdlib tests for the cross-language sync PostToolUse hook."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sync_model_hook import (
    compare,
    dart_models,
    dart_test_cases,
    find_test,
    main,
    py_models,
    py_test_cases,
    slug,
    snake,
)

DART_MODEL = """
class User {
  final String name;
  final String emailAddress;
  final int? age;

  User({required this.name, this.emailAddress});
}
"""

PY_MODEL = """
from pydantic import BaseModel


class User(BaseModel):
    name: str
    age: int | None = None
    legacy_id: str = ""
"""

PY_MODEL_IN_SYNC = """
from pydantic import BaseModel


class User(BaseModel):
    name: str
    email_address: str
    age: int | None = None
"""

DART_ENUM = """
enum AppChannel { dev, testflight, appStore }
"""

PY_ENUM = """
from enum import Enum


class AppChannel(str, Enum):
    DEV = "dev"
    TESTFLIGHT = "testflight"
    APP_STORE = "appStore"
"""


class SnakeTest(unittest.TestCase):
    def test_camel_to_snake(self):
        self.assertEqual(snake("emailAddress"), "email_address")

    def test_snake_stays(self):
        self.assertEqual(snake("legacy_id"), "legacy_id")


class ExtractTest(unittest.TestCase):
    def test_dart_class_fields(self):
        self.assertEqual(
            dart_models(DART_MODEL), {"User": ["name", "emailAddress", "age"]}
        )

    def test_dart_enum_values(self):
        self.assertEqual(
            dart_models(DART_ENUM), {"AppChannel": ["dev", "testflight", "appStore"]}
        )

    def test_python_class_fields(self):
        self.assertEqual(
            py_models(PY_MODEL), {"User": ["name", "age", "legacy_id"]}
        )

    def test_python_enum_members(self):
        self.assertEqual(
            py_models(PY_ENUM), {"AppChannel": ["DEV", "TESTFLIGHT", "APP_STORE"]}
        )

    def test_plain_functions_are_not_models(self):
        self.assertEqual(dart_models("void main() {\n  print('hi');\n}\n"), {})
        self.assertEqual(py_models("def main():\n    print('hi')\n"), {})

    def test_python_class_without_base_is_a_model(self):
        self.assertEqual(
            py_models("class Account:\n    name: str\n    email: str\n"),
            {"Account": ["name", "email"]},
        )


class SlugTest(unittest.TestCase):
    def test_description_slug(self):
        self.assertEqual(slug("round-trips through serialization"), "round_trips_through_serialization")

    def test_python_name_slug(self):
        self.assertEqual(slug("test_round_trips_through_serialization"), "round_trips_through_serialization")

    def test_both_forms_match(self):
        self.assertEqual(
            slug("constructs with valid fields"),
            slug("test_constructs_with_valid_fields"),
        )


class ExtractCasesTest(unittest.TestCase):
    def test_dart_descriptions(self):
        text = """
void main() {
  test('constructs with valid fields', () {});
  testWidgets('round-trips through serialization', (tester) async {});
}
"""
        self.assertEqual(
            dart_test_cases(text),
            ["constructs_with_valid_fields", "round_trips_through_serialization"],
        )

    def test_python_function_names(self):
        text = """
def test_constructs_with_valid_fields():
    pass


def test_round_trips_through_serialization():
    pass
"""
        self.assertEqual(
            py_test_cases(text),
            ["constructs_with_valid_fields", "round_trips_through_serialization"],
        )

    def test_non_test_functions_ignored(self):
        self.assertEqual(py_test_cases("def helper():\n    pass\n"), [])


class CompareTest(unittest.TestCase):
    def test_camel_snake_fields_match(self):
        missing, extra = compare(["name", "emailAddress"], ["name", "email_address"])
        self.assertEqual((missing, extra), ([], []))

    def test_drift_is_reported(self):
        missing, extra = compare(["name", "email"], ["name", "legacy_id"])
        self.assertEqual(missing, ["email"])
        self.assertEqual(extra, ["legacy_id"])


class FindTestTest(unittest.TestCase):
    def test_finds_dart_test_by_stem(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            test = root / "models" / "user_test.dart"
            test.parent.mkdir(parents=True)
            test.write_text("")
            self.assertEqual(find_test([root], "user", "_test.dart"), test)

    def test_finds_python_test_with_test_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            test = root / "tests" / "test_user.py"
            test.parent.mkdir(parents=True)
            test.write_text("")
            self.assertEqual(find_test([root], "user", ".py"), test)

    def test_missing_test_is_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(find_test([Path(tmp)], "user", "_test.dart"))


class MainTest(unittest.TestCase):
    def _run(self, event: dict, project: Path) -> str:
        with patch("sync_model_hook.PROJECT_DIR", project), patch(
            "sys.stdin", io.StringIO(json.dumps(event))
        ), patch("sys.stdout", io.StringIO()) as out:
            self.assertEqual(main(), 0)
            return out.getvalue()

    def _project(self, tmp: str) -> Path:
        root = Path(tmp)
        (root / "lib" / "models").mkdir(parents=True)
        (root / "backend" / "models").mkdir(parents=True)
        (root / "test" / "models").mkdir(parents=True)
        (root / "backend" / "tests").mkdir(parents=True)
        return root

    def test_invalid_stdin_is_quiet(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "sync_model_hook.PROJECT_DIR", Path(tmp)
        ), patch("sys.stdin", io.StringIO("not-json")), patch(
            "sys.stdout", io.StringIO()
        ) as out:
            self.assertEqual(main(), 0)
            self.assertEqual(out.getvalue(), "")

    def test_non_source_file_is_quiet(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self._run({"tool_input": {"file_path": "docs/readme.md"}}, Path(tmp))
            self.assertEqual(out, "")

    def test_dart_file_outside_lib_is_quiet(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self._run(
                {"tool_input": {"file_path": "web/models/user.dart"}}, Path(tmp)
            )
            self.assertEqual(out, "")

    def test_model_without_counterpart_is_quiet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp)
            (root / "lib" / "models" / "user.dart").write_text(DART_MODEL)
            out = self._run(
                {"tool_input": {"file_path": str(root / "lib" / "models" / "user.dart")}},
                root,
            )
            self.assertEqual(out, "")

    def test_drifted_counterpart_reports_missing_and_extra(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp)
            (root / "lib" / "models" / "user.dart").write_text(DART_MODEL)
            (root / "backend" / "models" / "user.py").write_text(PY_MODEL)
            out = self._run(
                {"tool_input": {"file_path": str(root / "lib" / "models" / "user.dart")}},
                root,
            )
            payload = json.loads(out)
            ctx = payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("backend/models/user.py", ctx)
            self.assertIn("email_address", ctx)
            self.assertIn("legacy_id", ctx)

    def test_enum_drift_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp)
            (root / "lib" / "config" / "app_channel.dart").parent.mkdir(
                parents=True, exist_ok=True
            )
            (root / "lib" / "config" / "app_channel.dart").write_text(DART_ENUM)
            (root / "backend" / "config" / "app_channel.py").parent.mkdir(
                parents=True, exist_ok=True
            )
            (root / "backend" / "config" / "app_channel.py").write_text(PY_ENUM)
            out = self._run(
                {
                    "tool_input": {
                        "file_path": str(root / "lib" / "config" / "app_channel.dart")
                    }
                },
                root,
            )
            payload = json.loads(out)
            ctx = payload["hookSpecificOutput"]["additionalContext"]
            # dev/testflight/appStore all match after normalization — only the
            # missing tests should be reported.
            self.assertNotIn("missing fields", ctx)
            self.assertIn("test/app_channel_test.dart", ctx)
            self.assertIn("backend/tests/test_app_channel.py", ctx)

    def test_missing_tests_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp)
            (root / "lib" / "models" / "user.dart").write_text(DART_MODEL)
            (root / "backend" / "models" / "user.py").write_text(PY_MODEL_IN_SYNC)
            out = self._run(
                {"tool_input": {"file_path": str(root / "lib" / "models" / "user.dart")}},
                root,
            )
            payload = json.loads(out)
            ctx = payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("test/user_test.dart", ctx)
            self.assertIn("backend/tests/test_user.py", ctx)

    def test_python_edit_reports_dart_side(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp)
            (root / "lib" / "models" / "user.dart").write_text(DART_MODEL)
            (root / "backend" / "models" / "user.py").write_text(PY_MODEL)
            out = self._run(
                {
                    "tool_input": {
                        "file_path": str(root / "backend" / "models" / "user.py")
                    }
                },
                root,
            )
            payload = json.loads(out)
            ctx = payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("lib/models/user.dart", ctx)
            self.assertIn("email_address", ctx)

    def test_manifest_pair_with_different_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp)
            (root / ".sync-model.json").write_text(
                json.dumps(
                    {
                        "pairs": [
                            {
                                "dart": "lib/models/user.dart",
                                "python": "backend/models/account.py",
                            }
                        ]
                    }
                )
            )
            (root / "lib" / "models" / "user.dart").write_text(DART_MODEL)
            (root / "backend" / "models" / "account.py").write_text(
                "class Account(BaseModel):\n    name: str\n"
            )
            out = self._run(
                {"tool_input": {"file_path": str(root / "lib" / "models" / "user.dart")}},
                root,
            )
            payload = json.loads(out)
            ctx = payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("backend/models/account.py", ctx)
            self.assertIn("email_address", ctx)

    def test_manifest_ignore_suppresses_name_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp)
            (root / ".sync-model.json").write_text(json.dumps({"ignore": ["User"]}))
            (root / "lib" / "models" / "user.dart").write_text(DART_MODEL)
            (root / "backend" / "models" / "user.py").write_text(PY_MODEL)
            out = self._run(
                {"tool_input": {"file_path": str(root / "lib" / "models" / "user.dart")}},
                root,
            )
            self.assertEqual(out, "")

    def test_manifest_pair_phrased_from_python_side(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp)
            (root / ".sync-model.json").write_text(
                json.dumps(
                    {
                        "pairs": [
                            {
                                "dart": "lib/models/user.dart",
                                "python": "backend/models/user.py",
                            }
                        ]
                    }
                )
            )
            (root / "lib" / "models" / "user.dart").write_text(DART_MODEL)
            (root / "backend" / "models" / "user.py").write_text(PY_MODEL)
            out = self._run(
                {
                    "tool_input": {
                        "file_path": str(root / "backend" / "models" / "user.py")
                    }
                },
                root,
            )
            payload = json.loads(out)
            ctx = payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("lib/models/user.dart", ctx)
            self.assertIn("email_address", ctx)

    def test_invalid_manifest_falls_back_to_name_matching(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp)
            (root / ".sync-model.json").write_text("{not json")
            (root / "lib" / "models" / "user.dart").write_text(DART_MODEL)
            (root / "backend" / "models" / "user.py").write_text(PY_MODEL)
            out = self._run(
                {"tool_input": {"file_path": str(root / "lib" / "models" / "user.dart")}},
                root,
            )
            payload = json.loads(out)
            ctx = payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("backend/models/user.py", ctx)

    def test_dart_test_drift_reports_case_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp)
            (root / "test" / "models" / "user_test.dart").write_text(
                "void main() {\n"
                "  test('constructs with valid fields', () {});\n"
                "  test('rejects an empty name', () {});\n"
                "}\n"
            )
            (root / "backend" / "tests" / "test_user.py").write_text(
                "def test_constructs_with_valid_fields():\n    pass\n"
            )
            out = self._run(
                {
                    "tool_input": {
                        "file_path": str(root / "test" / "models" / "user_test.dart")
                    }
                },
                root,
            )
            payload = json.loads(out)
            ctx = payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("backend/tests/test_user.py", ctx)
            self.assertIn("rejects_an_empty_name", ctx)

    def test_python_test_drift_reports_case_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp)
            (root / "test" / "models" / "user_test.dart").write_text(
                "void main() {\n"
                "  test('constructs with valid fields', () {});\n"
                "}\n"
            )
            (root / "backend" / "tests" / "test_user.py").write_text(
                "def test_constructs_with_valid_fields():\n    pass\n\n\n"
                "def test_rejects_an_empty_name():\n    pass\n"
            )
            out = self._run(
                {
                    "tool_input": {
                        "file_path": str(root / "backend" / "tests" / "test_user.py")
                    }
                },
                root,
            )
            payload = json.loads(out)
            ctx = payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("test/models/user_test.dart", ctx)
            self.assertIn("rejects_an_empty_name", ctx)

    def test_equal_test_cases_are_quiet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp)
            (root / "test" / "models" / "user_test.dart").write_text(
                "void main() {\n"
                "  test('constructs with valid fields', () {});\n"
                "  test('round-trips through serialization', () {});\n"
                "}\n"
            )
            (root / "backend" / "tests" / "test_user.py").write_text(
                "def test_constructs_with_valid_fields():\n    pass\n\n\n"
                "def test_round_trips_through_serialization():\n    pass\n"
            )
            out = self._run(
                {
                    "tool_input": {
                        "file_path": str(root / "test" / "models" / "user_test.dart")
                    }
                },
                root,
            )
            self.assertEqual(out, "")

    def test_test_file_without_counterpart_is_quiet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp)
            (root / "test" / "models" / "user_test.dart").write_text(
                "void main() {\n  test('constructs with valid fields', () {});\n}\n"
            )
            out = self._run(
                {
                    "tool_input": {
                        "file_path": str(root / "test" / "models" / "user_test.dart")
                    }
                },
                root,
            )
            self.assertEqual(out, "")

    def test_in_sync_models_with_tests_are_quiet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp)
            (root / "lib" / "models" / "user.dart").write_text(DART_MODEL)
            (root / "backend" / "models" / "user.py").write_text(
                "from pydantic import BaseModel\n\n\n"
                "class User(BaseModel):\n"
                "    name: str\n"
                "    email_address: str\n"
                "    age: int | None = None\n"
            )
            (root / "test" / "models" / "user_test.dart").write_text("")
            (root / "backend" / "tests" / "test_user.py").write_text("")
            out = self._run(
                {"tool_input": {"file_path": str(root / "lib" / "models" / "user.dart")}},
                root,
            )
            self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
