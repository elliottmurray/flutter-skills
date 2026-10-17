#!/usr/bin/env python3
"""Local iOS signing helpers for /ios-ci-setup. No Xcode needed.

Secrets stay out of argv, stdout and the conversation. Passwords come from
the variable named by --env (default IOS_P12_PASSWORD), else a hidden prompt
in a real terminal, else a hidden macOS dialog.

  ios_signing.py identities
  ios_signing.py csr --email ME [--common-name NAME] [--out-dir DIR]
  ios_signing.py p12 --key KEY --cer CER --out P12
  ios_signing.py verify-p12 --p12 P12
  ios_signing.py profile-info PROFILE [--bundle-id ID] [--expect-type TYPE]
  ios_signing.py set-secret NAME --repo OWNER/REPO (--file F | --prompt | --env VAR)
"""

from __future__ import annotations

import argparse
import base64
import getpass
import os
import plistlib
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PASSWORD_ENV = "IOS_P12_PASSWORD"
IDENTITY_LINE = re.compile(
    r'^\s*\d+\)\s+([0-9A-F]{40})\s+"([^"]+)"(?:\s+\(([^)]+)\))?\s*$'
)
PEM_CERT = re.compile(
    r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", re.S
)
WRONG_PASSWORD = re.compile(
    r"invalid password|mac verify error|mac verification failed", re.I
)
# What macOS `security import` has always accepted. OpenSSL 3 defaults to
# AES-256 PBES2 and a SHA-256 MAC, which older macOS releases reject.
MACOS_P12_FLAGS = [
    "-keypbe", "PBE-SHA1-3DES", "-certpbe", "PBE-SHA1-3DES", "-macalg", "sha1",
]


def die(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


# --- secrets -----------------------------------------------------------------

def _dialog_secret(prompt: str) -> str:
    if sys.platform != "darwin":
        die(f"no terminal to prompt on; set ${PASSWORD_ENV} instead")
    safe = prompt.replace('"', "'").replace("\\", "")
    script = (
        f'text returned of (display dialog "{safe}" '
        'default answer "" with hidden answer)'
    )
    result = subprocess.run(["osascript", "-e", script],
                            capture_output=True, text=True)
    if result.returncode != 0:
        die("password dialog cancelled")
    return result.stdout.rstrip("\n")


def read_secret(prompt: str, env_name: str = PASSWORD_ENV,
                confirm: bool = False) -> str:
    """Env var first, then a hidden prompt. Never echoes."""
    value = os.environ.get(env_name)
    if value:
        return value
    if sys.stdin.isatty():
        first = getpass.getpass(f"{prompt}: ")
        if confirm and getpass.getpass("again: ") != first:
            die("passwords differ")
        return first
    first = _dialog_secret(prompt)
    if confirm and _dialog_secret(f"{prompt} (again)") != first:
        die("passwords differ")
    return first


# --- openssl -----------------------------------------------------------------

def openssl(args: list[str], password: str | None = None,
            stdin: bytes | None = None) -> subprocess.CompletedProcess:
    """Run openssl. Passwords travel in the environment, never in argv.

    Pass "env:IOS_P12_PASSWORD" in args wherever openssl wants a password.
    """
    env = dict(os.environ)
    if password is not None:
        env[PASSWORD_ENV] = password
    try:
        return subprocess.run(["openssl", *args], capture_output=True,
                              env=env, input=stdin)
    except FileNotFoundError:
        die("openssl not found on PATH")
        raise  # unreachable


def pkcs12_read(p12: str, password: str, extra: list[str]) -> bytes:
    """Read a p12 trying plain first, then -legacy for old Keychain exports.

    macOS Keychain writes RC2/3DES p12 files that OpenSSL 3 only opens with
    -legacy. A wrong password is reported as such and never retried.
    """
    base = ["pkcs12", "-in", p12, *extra, "-passin", f"env:{PASSWORD_ENV}"]
    first_error = ""
    for legacy in (False, True):
        result = openssl(base + (["-legacy"] if legacy else []), password)
        if result.returncode == 0:
            return result.stdout
        error = result.stderr.decode(errors="replace")
        first_error = first_error or error
        if WRONG_PASSWORD.search(error) and "unsupported" not in error.lower():
            die("wrong p12 password")
    die(f"openssl could not read {p12}: {first_error.strip()[-300:]}")
    raise AssertionError  # unreachable


def cert_facts(pem: bytes) -> dict[str, str]:
    result = openssl(["x509", "-noout", "-subject", "-enddate",
                      "-fingerprint", "-sha1"], stdin=pem)
    if result.returncode != 0:
        die("could not parse the certificate")
    text = result.stdout.decode()
    team = re.search(r"OU\s*=\s*([A-Z0-9]{10})", text)
    name = re.search(r"CN\s*=\s*([^,/\n]+)", text)
    expiry = re.search(r"notAfter=(.+)", text)
    sha1 = re.search(r"Fingerprint=([0-9A-F:]+)", text)
    return {
        "name": name.group(1).strip() if name else "?",
        "team": team.group(1) if team else "?",
        "expires": expiry.group(1).strip() if expiry else "?",
        "sha1": sha1.group(1).replace(":", "") if sha1 else "?",
    }


def is_expired(openssl_date: str) -> bool:
    try:
        when = datetime.strptime(openssl_date, "%b %d %H:%M:%S %Y %Z")
    except ValueError:
        return False
    return when.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc)


# --- identities --------------------------------------------------------------

def parse_identities(text: str) -> list[dict[str, str]]:
    found = []
    for line in text.splitlines():
        match = IDENTITY_LINE.match(line)
        if match:
            sha1, name, status = match.groups()
            team = re.search(r"\(([A-Z0-9]{10})\)$", name)
            found.append({
                "sha1": sha1,
                "name": name,
                "team": team.group(1) if team else "?",
                "status": status or "valid",
            })
    return found


def cmd_identities(_: argparse.Namespace) -> int:
    try:
        out = subprocess.run(["security", "find-identity", "-p", "codesigning"],
                             capture_output=True, text=True).stdout
    except FileNotFoundError:
        die("`security` is macOS only; use the csr/p12 route instead")
    identities = parse_identities(out)
    if not identities:
        print("no signing identities in the keychain search list")
        return 0
    for item in identities:
        print(f"{item['sha1']}  {item['status']:<28} {item['name']}")
    print("\nUse the SHA-1 of a `valid` Apple Distribution row. A revoked row"
          " with the same name is a different certificate.")
    return 0


# --- csr ---------------------------------------------------------------------

def cmd_csr(args: argparse.Namespace) -> int:
    for value in (args.email, args.common_name):
        if "/" in value:
            die("no '/' allowed in --email or --common-name")
    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    key, csr = out_dir / "dist.key", out_dir / "dist.csr"
    if key.exists() and not args.force:
        die(f"{key} exists. Losing this key means losing the certificate;"
            " pass --force to replace it")
    old_umask = os.umask(0o077)
    try:
        made = openssl(["genrsa", "-out", str(key), "2048"])
        if made.returncode != 0:
            die(made.stderr.decode(errors="replace"))
        subject = f"/emailAddress={args.email}/CN={args.common_name}/C=US"
        req = openssl(["req", "-new", "-key", str(key), "-out", str(csr),
                       "-subj", subject])
        if req.returncode != 0:
            die(req.stderr.decode(errors="replace"))
    finally:
        os.umask(old_umask)
    print(f"private key (keep, never upload): {key}")
    print(f"CSR (upload to developer.apple.com): {csr}")
    return 0


# --- p12 ---------------------------------------------------------------------

def cmd_p12(args: argparse.Namespace) -> int:
    cer = Path(args.cer).expanduser().read_bytes()
    pem = b""
    for form in ("DER", "PEM"):
        result = openssl(["x509", "-inform", form], stdin=cer)
        if result.returncode == 0:
            pem = result.stdout
            break
    if not pem:
        die(f"{args.cer} is not a certificate")
    cert_pub = openssl(["x509", "-noout", "-pubkey"], stdin=pem).stdout
    key_pub = openssl(["pkey", "-in", str(Path(args.key).expanduser()),
                       "-pubout"]).stdout
    if not cert_pub.strip() or cert_pub.strip() != key_pub.strip():
        die("this certificate was not issued for this private key")
    password = read_secret("Choose a password for the .p12",
                           args.env, confirm=True)
    out = Path(args.out).expanduser()
    with tempfile.TemporaryDirectory() as tmp:
        pem_path = Path(tmp) / "cert.pem"
        pem_path.write_bytes(pem)
        base = ["pkcs12", "-export", "-inkey", str(Path(args.key).expanduser()),
                "-in", str(pem_path), "-name", "iOS Distribution",
                "-out", str(out), "-passout", f"env:{PASSWORD_ENV}"]
        built = openssl(base + MACOS_P12_FLAGS, password)
        if built.returncode != 0:  # LibreSSL or a build without these flags
            built = openssl(base, password)
        if built.returncode != 0:
            die(built.stderr.decode(errors="replace"))
    out.chmod(0o600)
    return verify(str(out), password)


def verify(p12: str, password: str) -> int:
    certs = pkcs12_read(p12, password, ["-nokeys"])
    blocks = PEM_CERT.findall(certs.decode(errors="replace"))
    if not blocks:
        die("no certificate in the p12")
    facts = [cert_facts(block.encode()) for block in blocks]
    chosen = next((f for f in facts if "Distribution" in f["name"]), facts[0])
    keys = pkcs12_read(p12, password, ["-nocerts", "-nodes"])
    has_key = b"PRIVATE KEY" in keys
    print(f"certificate : {chosen['name']}")
    print(f"team id     : {chosen['team']}")
    print(f"expires     : {chosen['expires']}")
    print(f"sha1        : {chosen['sha1']}")
    print(f"private key : {'present' if has_key else 'MISSING'}")
    problems = []
    if not has_key:
        problems.append("export from My Certificates so the key comes along")
    if "Distribution" not in chosen["name"]:
        problems.append("not an Apple Distribution certificate")
    if is_expired(chosen["expires"]):
        problems.append("certificate expired")
    for problem in problems:
        print(f"problem     : {problem}", file=sys.stderr)
    return 1 if problems else 0


def cmd_verify_p12(args: argparse.Namespace) -> int:
    return verify(str(Path(args.p12).expanduser()),
                  read_secret("p12 password", args.env))


# --- provisioning profile ----------------------------------------------------

def classify_profile(profile: dict) -> str:
    if profile.get("ProvisionsAllDevices"):
        return "enterprise"
    if profile.get("ProvisionedDevices"):
        allow = profile.get("Entitlements", {}).get("get-task-allow")
        return "development" if allow else "ad-hoc"
    return "app-store"


def cmd_profile_info(args: argparse.Namespace) -> int:
    path = str(Path(args.profile).expanduser())
    decoded = subprocess.run(["security", "cms", "-D", "-i", path],
                             capture_output=True)
    if decoded.returncode != 0:
        die(f"could not decode {path}")
    profile = plistlib.loads(decoded.stdout)
    app_id = profile.get("Entitlements", {}).get("application-identifier", "?")
    expires = profile.get("ExpirationDate")
    kind = classify_profile(profile)
    print(f"name    : {profile.get('Name', '?')}")
    print(f"uuid    : {profile.get('UUID', '?')}")
    print(f"team    : {', '.join(profile.get('TeamIdentifier', []))}")
    print(f"app id  : {app_id}")
    print(f"type    : {kind}")
    print(f"expires : {expires}")
    problems = []
    if args.bundle_id and not app_id.endswith("." + args.bundle_id):
        problems.append(f"app id does not end in .{args.bundle_id}")
    if args.expect_type and kind != args.expect_type:
        problems.append(f"expected {args.expect_type}, got {kind}")
    if expires and expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        problems.append("profile expired")
    for problem in problems:
        print(f"problem : {problem}", file=sys.stderr)
    return 1 if problems else 0


# --- GitHub secret -----------------------------------------------------------

def cmd_set_secret(args: argparse.Namespace) -> int:
    if args.file:
        value = base64.b64encode(Path(args.file).expanduser().read_bytes()).decode()
    elif args.env:
        value = os.environ.get(args.env, "")
    else:
        value = read_secret(args.name, env_name="__NO_ENV__")
    if not value:
        die("empty value")
    try:
        result = subprocess.run(
            ["gh", "secret", "set", args.name, "--repo", args.repo],
            input=value.encode(), capture_output=True)
    except FileNotFoundError:
        die("gh not found on PATH")
        raise  # unreachable
    if result.returncode != 0:
        die(result.stderr.decode(errors="replace").strip())
    print(f"set {args.name} on {args.repo} ({len(value)} chars)")
    return 0


# --- cli ---------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("identities").set_defaults(func=cmd_identities)

    csr = sub.add_parser("csr")
    csr.add_argument("--email", required=True)
    csr.add_argument("--common-name", default="iOS Distribution")
    csr.add_argument("--out-dir", default="~/ios-signing")
    csr.add_argument("--force", action="store_true")
    csr.set_defaults(func=cmd_csr)

    p12 = sub.add_parser("p12")
    p12.add_argument("--key", required=True)
    p12.add_argument("--cer", required=True)
    p12.add_argument("--out", required=True)
    p12.add_argument("--env", default=PASSWORD_ENV)
    p12.set_defaults(func=cmd_p12)

    check = sub.add_parser("verify-p12")
    check.add_argument("--p12", required=True)
    check.add_argument("--env", default=PASSWORD_ENV)
    check.set_defaults(func=cmd_verify_p12)

    profile = sub.add_parser("profile-info")
    profile.add_argument("profile")
    profile.add_argument("--bundle-id")
    profile.add_argument("--expect-type", default="app-store")
    profile.set_defaults(func=cmd_profile_info)

    secret = sub.add_parser("set-secret")
    secret.add_argument("name")
    secret.add_argument("--repo", required=True)
    source = secret.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", help="base64 of this file")
    source.add_argument("--prompt", action="store_true")
    source.add_argument("--env", help="read the value from this variable")
    secret.set_defaults(func=cmd_set_secret)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
