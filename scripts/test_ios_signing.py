import contextlib
import io
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ios_signing

IDENTITIES = """\
  1) 1111111111111111111111111111111111111111 "Apple Distribution: A B (ABCDE12345)" (CSSMERR_TP_CERT_REVOKED)
  2) 2222222222222222222222222222222222222222 "Apple Development: A B (FGHIJ67890)"
  3) 3333333333333333333333333333333333333333 "Apple Distribution: A B (ABCDE12345)"
     3 valid identities found
"""
PASSWORD = "s3cret-pass-w0rd"


class IdentityTests(unittest.TestCase):
    def test_parse_marks_revoked_and_valid(self):
        found = ios_signing.parse_identities(IDENTITIES)
        self.assertEqual([i["status"] for i in found],
                         ["CSSMERR_TP_CERT_REVOKED", "valid", "valid"])
        self.assertEqual(found[2]["sha1"],
                         "3333333333333333333333333333333333333333")
        self.assertEqual(found[2]["team"], "ABCDE12345")

    def test_summary_line_is_ignored(self):
        self.assertEqual(len(ios_signing.parse_identities(IDENTITIES)), 3)


class ProfileTests(unittest.TestCase):
    def test_app_store_has_no_device_list(self):
        self.assertEqual(ios_signing.classify_profile({}), "app-store")

    def test_development_allows_debugging(self):
        profile = {"ProvisionedDevices": ["x"],
                   "Entitlements": {"get-task-allow": True}}
        self.assertEqual(ios_signing.classify_profile(profile), "development")

    def test_ad_hoc_has_devices_without_debugging(self):
        profile = {"ProvisionedDevices": ["x"],
                   "Entitlements": {"get-task-allow": False}}
        self.assertEqual(ios_signing.classify_profile(profile), "ad-hoc")

    def test_enterprise_provisions_all_devices(self):
        self.assertEqual(
            ios_signing.classify_profile({"ProvisionsAllDevices": True}),
            "enterprise")


class SecretTests(unittest.TestCase):
    def test_env_wins_over_prompting(self):
        with mock.patch.dict(os.environ, {"MY_SECRET": "abc"}):
            self.assertEqual(
                ios_signing.read_secret("x", env_name="MY_SECRET"), "abc")

    def test_expired_date_is_detected(self):
        self.assertTrue(ios_signing.is_expired("Jan  1 00:00:00 2001 GMT"))
        self.assertFalse(ios_signing.is_expired("Jan  1 00:00:00 2999 GMT"))


@unittest.skipUnless(shutil.which("openssl"), "openssl not installed")
class RoundTripTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        key, pem, cer = (self.tmp / n for n in ("k.key", "c.pem", "c.cer"))
        run = lambda *a: subprocess.run(["openssl", *a], check=True,
                                        capture_output=True)
        run("genrsa", "-out", str(key), "2048")
        run("req", "-x509", "-new", "-key", str(key), "-days", "2",
            "-subj", "/CN=Apple Distribution: Test (ABCDE12345)"
                     "/OU=ABCDE12345/O=Test/C=US", "-out", str(pem))
        run("x509", "-in", str(pem), "-outform", "DER", "-out", str(cer))
        self.key, self.cer, self.p12 = key, cer, self.tmp / "out.p12"

    def build(self):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {ios_signing.PASSWORD_ENV: PASSWORD}):
            with contextlib.redirect_stdout(out):
                code = ios_signing.main(
                    ["p12", "--key", str(self.key), "--cer", str(self.cer),
                     "--out", str(self.p12)])
        return code, out.getvalue()

    def test_p12_round_trip_reports_team_and_key(self):
        code, text = self.build()
        self.assertEqual(code, 0)
        self.assertIn("ABCDE12345", text)
        self.assertIn("private key : present", text)
        self.assertNotIn(PASSWORD, text)

    def test_p12_is_private_to_the_owner(self):
        self.build()
        self.assertEqual(self.p12.stat().st_mode & 0o077, 0)

    def test_password_never_appears_in_a_command_line(self):
        seen = []
        real = subprocess.run

        def spy(args, *a, **kw):
            seen.append(list(args))
            return real(args, *a, **kw)

        with mock.patch.object(ios_signing.subprocess, "run", spy):
            self.build()
        self.assertTrue(seen)
        for argv in seen:
            self.assertNotIn(PASSWORD, " ".join(argv))

    def test_wrong_password_is_reported_as_such(self):
        self.build()
        err = io.StringIO()
        with mock.patch.dict(os.environ, {ios_signing.PASSWORD_ENV: "nope"}):
            with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
                ios_signing.main(["verify-p12", "--p12", str(self.p12)])
        self.assertIn("wrong p12 password", err.getvalue())

    def test_certificate_for_another_key_is_rejected(self):
        other = self.tmp / "other.key"
        subprocess.run(["openssl", "genrsa", "-out", str(other), "2048"],
                       check=True, capture_output=True)
        err = io.StringIO()
        with mock.patch.dict(os.environ, {ios_signing.PASSWORD_ENV: PASSWORD}):
            with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
                ios_signing.main(["p12", "--key", str(other), "--cer",
                                  str(self.cer), "--out", str(self.p12)])
        self.assertIn("not issued for this private key", err.getvalue())

    def test_csr_refuses_to_replace_an_existing_key(self):
        args = ["csr", "--email", "a@b.c", "--out-dir", str(self.tmp / "out")]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ios_signing.main(args), 0)
        with contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit):
            ios_signing.main(args)


class SetSecretTests(unittest.TestCase):
    def run_set(self, *extra, env=None):
        calls = []

        def fake(args, **kw):
            calls.append((list(args), kw.get("input")))
            return subprocess.CompletedProcess(args, 0, b"", b"")

        out = io.StringIO()
        with mock.patch.object(ios_signing.subprocess, "run", fake), \
                mock.patch.dict(os.environ, env or {}), \
                contextlib.redirect_stdout(out):
            ios_signing.main(["set-secret", "NAME", "--repo", "o/r", *extra])
        return calls, out.getvalue()

    def test_value_goes_on_stdin_never_argv(self):
        calls, _ = self.run_set("--env", "V", env={"V": "top-secret-value"})
        argv, stdin = calls[0]
        self.assertEqual(stdin, b"top-secret-value")
        self.assertNotIn("top-secret-value", " ".join(argv))
        self.assertEqual(argv[:3], ["gh", "secret", "set"])
        self.assertIn("--repo", argv)

    def test_file_is_sent_as_base64_and_only_its_length_is_printed(self):
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            handle.write(b"\x00\x01binary")
        self.addCleanup(os.unlink, handle.name)
        calls, printed = self.run_set("--file", handle.name)
        self.assertEqual(calls[0][1], b"AAFiaW5hcnk=")
        self.assertNotIn("AAFiaW5hcnk", printed)
        self.assertIn("12 chars", printed)


if __name__ == "__main__":
    unittest.main()
