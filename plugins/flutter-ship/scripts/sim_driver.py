#!/usr/bin/env python3
"""Generic Flutter iOS Simulator driver over the Dart VM Service.

Stdlib only. No app-specific subcommands — tap, eval, screenshot, tree,
boot, run, background, foreground, kill, shutdown.

Usage (from a Flutter app root):
  sim_driver.py boot [--name NAME] [--udid UDID]
  sim_driver.py run [--target lib/main.dart] [--device UDID] [--bundle-id ID]
  sim_driver.py status
  sim_driver.py tap X Y
  sim_driver.py eval EXPRESSION
  sim_driver.py screenshot [PATH]
  sim_driver.py tree
  sim_driver.py background | foreground | kill | shutdown
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import select
import socket
import ssl
import struct
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

STATE_NAME = ".sim_driver_state.json"
DEFAULT_SCREENSHOT = "screenshots/verify.png"
FLUTTER_BANNER_RE = re.compile(
    r"(?:Dart VM Service|A Dart VM Service).*(?:available at|listening on):\s*(https?://\S+)",
    re.IGNORECASE,
)
PBX_BUNDLE_RE = re.compile(
    r"PRODUCT_BUNDLE_IDENTIFIER\s*=\s*([^;]+);",
)


def repo_root(start: Path | None = None) -> Path:
    return (start or Path.cwd()).resolve()


def state_path(root: Path, override: str | None = None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    return root / STATE_NAME


def load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_state(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def ws_url_from_observatory(url: str) -> str:
    """Turn a Dart VM Service HTTP URI into a WebSocket URI."""
    parsed = urllib.parse.urlparse(url.strip())
    scheme = parsed.scheme
    if scheme == "https":
        scheme = "wss"
    elif scheme == "http":
        scheme = "ws"
    elif scheme not in {"ws", "wss"}:
        scheme = "ws"
    path = parsed.path or "/"
    stripped = path.rstrip("/")
    if stripped.endswith("/ws") or stripped == "ws":
        path = stripped
    else:
        path = f"{stripped}/ws" if stripped else "/ws"
    return urllib.parse.urlunparse((scheme, parsed.netloc, path, "", parsed.query, ""))


def parse_vm_service_url(text: str) -> str | None:
    """Extract an observatory HTTP URL from flutter-run console text."""
    match = FLUTTER_BANNER_RE.search(text)
    if match:
        return match.group(1).rstrip(".")
    return None


def parse_machine_ws_uri(line: str) -> str | None:
    """Parse a `flutter run --machine` event line for the VM Service URI."""
    raw = line.strip()
    if not raw.startswith("["):
        return None
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(msg, list) or not msg:
        return None
    event = msg[0]
    if not isinstance(event, dict):
        return None
    if event.get("event") != "app.debugPort":
        return None
    params = event.get("params") or {}
    if not isinstance(params, dict):
        return None
    uri = params.get("wsUri") or params.get("baseUri")
    return uri if isinstance(uri, str) and uri else None


def tap_expression(x: float, y: float) -> str:
    """Dart expression: pointer down/up at logical pixels in the Flutter view."""
    return (
        "() { "
        "final binding = GestureBinding.instance; "
        f"final position = Offset({x}, {y}); "
        "binding.handlePointerEvent(PointerDownEvent(position: position)); "
        "binding.handlePointerEvent(PointerUpEvent(position: position)); "
        "return 'ok'; "
        "}()"
    )


def guess_bundle_id(root: Path) -> str | None:
    pbx = root / "ios" / "Runner.xcodeproj" / "project.pbxproj"
    if not pbx.is_file():
        return None
    match = PBX_BUNDLE_RE.search(pbx.read_text(errors="replace"))
    if not match:
        return None
    value = match.group(1).strip().strip('"')
    if " " in value or value.startswith("$("):
        return None
    return value


# --- minimal WebSocket client (RFC 6455, text frames, stdlib) ---


def _ws_accept(key: str) -> str:
    magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    digest = hashlib.sha1((key + magic).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def encode_text_frame(payload: str, *, mask: bytes | None = None) -> bytes:
    data = payload.encode("utf-8")
    header = bytearray()
    header.append(0x81)
    n = len(data)
    mask_bit = 0x80
    if n < 126:
        header.append(mask_bit | n)
    elif n < 65536:
        header.append(mask_bit | 126)
        header.extend(struct.pack("!H", n))
    else:
        header.append(mask_bit | 127)
        header.extend(struct.pack("!Q", n))
    if mask is None:
        mask = os.urandom(4)
    if len(mask) != 4:
        raise ValueError("mask must be 4 bytes")
    header.extend(mask)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return bytes(header) + masked


def decode_frame(buf: bytes) -> tuple[int, bytes, int] | None:
    """Return (opcode, payload, bytes_consumed) or None if incomplete."""
    if len(buf) < 2:
        return None
    b0, b1 = buf[0], buf[1]
    opcode = b0 & 0x0F
    masked = bool(b1 & 0x80)
    n = b1 & 0x7F
    offset = 2
    if n == 126:
        if len(buf) < 4:
            return None
        n = struct.unpack("!H", buf[2:4])[0]
        offset = 4
    elif n == 127:
        if len(buf) < 10:
            return None
        n = struct.unpack("!Q", buf[2:10])[0]
        offset = 10
    mask = b""
    if masked:
        if len(buf) < offset + 4:
            return None
        mask = buf[offset : offset + 4]
        offset += 4
    if len(buf) < offset + n:
        return None
    payload = buf[offset : offset + n]
    if masked:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return opcode, payload, offset + n


class WebSocketClient:
    def __init__(self, sock: socket.socket):
        self._sock = sock
        self._buf = bytearray()

    def send_text(self, text: str) -> None:
        self._sock.sendall(encode_text_frame(text))

    def recv_text(self, timeout: float = 30.0) -> str:
        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError("websocket recv timed out")
            decoded = decode_frame(bytes(self._buf))
            if decoded is None:
                ready, _, _ = select.select([self._sock], [], [], remaining)
                if not ready:
                    raise TimeoutError("websocket recv timed out")
                chunk = self._sock.recv(65536)
                if not chunk:
                    raise ConnectionError("websocket closed")
                self._buf.extend(chunk)
                continue
            opcode, payload, consumed = decoded
            del self._buf[:consumed]
            if opcode == 0x8:
                raise ConnectionError("websocket close")
            if opcode == 0x9:
                self._sock.sendall(bytes([0x8A, 0x80]) + os.urandom(4))
                continue
            if opcode == 0x1:
                return payload.decode("utf-8")
            if opcode == 0x2:
                return payload.decode("utf-8", errors="replace")
            # skip ping/pong already handled; ignore other opcodes

    def close(self) -> None:
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._sock.close()


def connect_ws(url: str, timeout: float = 10.0) -> WebSocketClient:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"ws", "wss"}:
        raise ValueError(f"not a websocket url: {url}")
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "wss" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    raw = socket.create_connection((host, port), timeout=timeout)
    sock: socket.socket = raw
    if parsed.scheme == "wss":
        sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    sock.sendall(req.encode("ascii"))
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("websocket handshake closed")
        buf += chunk
    header, _, rest = buf.partition(b"\r\n\r\n")
    status = header.split(b"\r\n", 1)[0]
    if b"101" not in status:
        raise ConnectionError(f"websocket handshake failed: {status.decode(errors='replace')}")
    accept = None
    for line in header.split(b"\r\n")[1:]:
        if line.lower().startswith(b"sec-websocket-accept:"):
            accept = line.split(b":", 1)[1].strip().decode("ascii")
    if accept != _ws_accept(key):
        raise ConnectionError("websocket accept mismatch")
    client = WebSocketClient(sock)
    if rest:
        client._buf.extend(rest)
    sock.settimeout(None)
    return client


class VmService:
    def __init__(self, ws: WebSocketClient):
        self._ws = ws
        self._id = 0

    def call(self, method: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> Any:
        self._id += 1
        req_id = self._id
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
        self._ws.send_text(json.dumps(payload))
        deadline = time.time() + timeout
        while True:
            remaining = max(0.1, deadline - time.time())
            raw = self._ws.recv_text(timeout=remaining)
            msg = json.loads(raw)
            if msg.get("id") != req_id:
                continue
            if "error" in msg:
                raise RuntimeError(msg["error"])
            return msg.get("result")

    def close(self) -> None:
        self._ws.close()


def open_vm(state: dict[str, Any]) -> VmService:
    url = state.get("ws_url") or (
        ws_url_from_observatory(state["vm_service_url"]) if state.get("vm_service_url") else None
    )
    if not url:
        raise SystemExit("no VM Service URL — run `sim_driver.py run` first")
    return VmService(connect_ws(url))


def pick_isolate(vm: VmService) -> str:
    info = vm.call("getVM")
    isolates = info.get("isolates") or []
    if not isolates:
        raise RuntimeError("no isolates")
    for iso in isolates:
        name = str(iso.get("name") or "")
        if "main" in name.lower() or "flutter" in name.lower():
            return iso["id"]
    return isolates[0]["id"]


def flutter_binding_target(vm: VmService, isolate_id: str) -> str:
    isolate = vm.call("getIsolate", {"isolateId": isolate_id})
    for lib in isolate.get("libraries") or []:
        uri = str(lib.get("uri") or "")
        if uri.endswith("gestures/binding.dart") or uri.endswith("widgets/binding.dart"):
            return lib["id"]
    root = isolate.get("rootLib") or {}
    if root.get("id"):
        return root["id"]
    raise RuntimeError("no library to evaluate in")


def cmd_boot(args: argparse.Namespace, root: Path, state: dict[str, Any], path: Path) -> int:
    udid = args.udid
    created = False
    name = args.name or "sim-driver"
    if not udid:
        existing = _simctl(["list", "devices", "available"])
        # Prefer an already-booted device.
        booted = re.search(r"([0-9A-F-]{36})\s+\(Booted\)", existing, re.I)
        if booted:
            udid = booted.group(1)
        else:
            runtime = _pick_runtime()
            device_type = _pick_iphone_type()
            udid = _simctl(["create", name, device_type, runtime]).strip()
            created = True
    _simctl(["boot", udid], check=False)
    # boot is idempotent-ish; ignore already-booted.
    state.update({"udid": udid, "created_simulator": created, "device_name": name})
    save_state(path, state)
    print(udid)
    return 0


def _simctl(argv: list[str], check: bool = True) -> str:
    cmd = ["xcrun", "simctl", *argv]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        sys.stderr.write(proc.stderr or proc.stdout)
        raise SystemExit(proc.returncode)
    return proc.stdout


def _pick_runtime() -> str:
    text = _simctl(["list", "runtimes"])
    ids = re.findall(r"(com\.apple\.CoreSimulator\.SimRuntime\.iOS[^\s]+)", text)
    if not ids:
        raise SystemExit("no iOS Simulator runtimes installed")
    return ids[-1]


def _pick_iphone_type() -> str:
    text = _simctl(["list", "devicetypes"])
    ids = re.findall(r"(com\.apple\.CoreSimulator\.SimDeviceType\.iPhone-[^\s]+)", text)
    if not ids:
        raise SystemExit("no iPhone Simulator device types")
    return ids[-1]


def _uris_from_log(text: str) -> tuple[str | None, str | None]:
    """Return (ws_uri, http_uri) from flutter-run output, machine or banner."""
    ws_uri = None
    http_uri = None
    for line in text.splitlines():
        machine = parse_machine_ws_uri(line)
        if machine:
            if machine.startswith("ws"):
                ws_uri = machine
            else:
                http_uri = machine
                ws_uri = ws_url_from_observatory(machine)
        banner = parse_vm_service_url(line)
        if banner:
            http_uri = banner
            if not ws_uri:
                ws_uri = ws_url_from_observatory(banner)
    return ws_uri, http_uri


def cmd_run(args: argparse.Namespace, root: Path, state: dict[str, Any], path: Path) -> int:
    udid = args.device or state.get("udid")
    if not udid:
        raise SystemExit("no simulator — run `sim_driver.py boot` first")
    target = args.target
    bundle_id = args.bundle_id or state.get("bundle_id") or guess_bundle_id(root)
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "sim_driver_flutter.log"
    cmd = ["flutter", "run", "--machine", "-d", udid, target]
    handle = log_file.open("wb", buffering=0)
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=root,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except Exception:
        handle.close()
        raise
    ws_uri = None
    http_uri = None
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        handle.flush()
        ws_uri, http_uri = _uris_from_log(log_file.read_text(errors="replace"))
        if ws_uri:
            break
        time.sleep(0.2)
    if not ws_uri:
        proc.terminate()
        handle.close()
        raise SystemExit(f"timed out waiting for VM Service (log: {log_file})")
    handle.close()
    state.update(
        {
            "udid": udid,
            "flutter_pid": proc.pid,
            "ws_url": ws_uri,
            "vm_service_url": http_uri or ws_uri,
            "target": target,
            "bundle_id": bundle_id,
            "log_file": str(log_file),
        }
    )
    save_state(path, state)
    print(ws_uri)
    return 0


def cmd_status(_args: argparse.Namespace, _root: Path, state: dict[str, Any], _path: Path) -> int:
    if not state:
        print("no session")
        return 1
    print(json.dumps(state, indent=2))
    pid = state.get("flutter_pid")
    if pid:
        try:
            os.kill(int(pid), 0)
            print("flutter: running")
        except OSError:
            print("flutter: not running")
    return 0


def cmd_tap(args: argparse.Namespace, _root: Path, state: dict[str, Any], _path: Path) -> int:
    vm = open_vm(state)
    try:
        isolate = pick_isolate(vm)
        target = flutter_binding_target(vm, isolate)
        expr = tap_expression(args.x, args.y)
        result = vm.call(
            "evaluate",
            {"isolateId": isolate, "targetId": target, "expression": expr, "disableBreakpoints": True},
        )
        print(json.dumps(result, indent=2) if not isinstance(result, str) else result)
    finally:
        vm.close()
    return 0


def cmd_eval(args: argparse.Namespace, _root: Path, state: dict[str, Any], _path: Path) -> int:
    vm = open_vm(state)
    try:
        isolate = pick_isolate(vm)
        target = flutter_binding_target(vm, isolate)
        result = vm.call(
            "evaluate",
            {
                "isolateId": isolate,
                "targetId": target,
                "expression": args.expression,
                "disableBreakpoints": True,
            },
        )
        print(json.dumps(result, indent=2) if not isinstance(result, str) else result)
    finally:
        vm.close()
    return 0


def cmd_tree(_args: argparse.Namespace, _root: Path, state: dict[str, Any], _path: Path) -> int:
    vm = open_vm(state)
    try:
        isolate = pick_isolate(vm)
        result = vm.call(
            "ext.flutter.inspector.getRootWidgetSummaryTree",
            {"isolateId": isolate, "objectGroup": "verify-tree"},
        )
        print(json.dumps(result, indent=2))
    finally:
        vm.close()
    return 0


def cmd_screenshot(args: argparse.Namespace, root: Path, state: dict[str, Any], _path: Path) -> int:
    dest = Path(args.path or DEFAULT_SCREENSHOT)
    if not dest.is_absolute():
        dest = root / dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    udid = state.get("udid")
    if udid:
        proc = subprocess.run(
            ["xcrun", "simctl", "io", udid, "screenshot", str(dest)],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0 and dest.is_file():
            print(dest)
            return 0
        sys.stderr.write(proc.stderr or "simctl screenshot failed; trying VM Service\n")
    vm = open_vm(state)
    try:
        isolate = pick_isolate(vm)
        result = vm.call(
            "ext.flutter.inspector.screenshot",
            {"isolateId": isolate},
        )
        b64 = _extract_base64(result)
        dest.write_bytes(base64.b64decode(b64))
        print(dest)
    finally:
        vm.close()
    return 0


def _extract_base64(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("screenshot", "value", "png", "data"):
            val = result.get(key)
            if isinstance(val, str) and len(val) > 20:
                return val
        inner = result.get("result")
        if inner is not None:
            return _extract_base64(inner)
    raise RuntimeError(f"unexpected screenshot payload: {result!r}")


def cmd_background(_args: argparse.Namespace, _root: Path, _state: dict[str, Any], _path: Path) -> int:
    script = (
        'tell application "Simulator" to activate\n'
        'tell application "System Events" to keystroke "h" using {command down, shift down}\n'
    )
    proc = subprocess.run(["osascript"], input=script, text=True, capture_output=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return proc.returncode
    print("home")
    return 0


def cmd_foreground(_args: argparse.Namespace, _root: Path, state: dict[str, Any], _path: Path) -> int:
    udid = state.get("udid")
    bundle = state.get("bundle_id")
    if not udid or not bundle:
        raise SystemExit("need udid and bundle_id in state (pass --bundle-id on run)")
    print(_simctl(["launch", udid, bundle]))
    return 0


def cmd_kill(_args: argparse.Namespace, _root: Path, state: dict[str, Any], path: Path) -> int:
    pid = state.get("flutter_pid")
    if pid:
        try:
            os.kill(int(pid), 15)
        except OSError:
            pass
    state.pop("flutter_pid", None)
    save_state(path, state)
    print("killed")
    return 0


def cmd_shutdown(_args: argparse.Namespace, _root: Path, state: dict[str, Any], path: Path) -> int:
    cmd_kill(_args, _root, state, path)
    udid = state.get("udid")
    created = state.get("created_simulator")
    if udid:
        _simctl(["shutdown", udid], check=False)
        if created:
            _simctl(["delete", udid], check=False)
    if path.is_file():
        path.unlink()
    print("shutdown")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-C", dest="chdir", default=None, help="app repo root")
    parser.add_argument("--state", default=None, help="state file path")
    sub = parser.add_subparsers(dest="command", required=True)

    boot = sub.add_parser("boot", help="boot (or create) an iOS Simulator")
    boot.add_argument("--name", default="sim-driver")
    boot.add_argument("--udid", default=None)
    boot.set_defaults(func=cmd_boot)

    run = sub.add_parser("run", help="flutter run --machine and wait for VM Service")
    run.add_argument("--target", default="lib/main.dart")
    run.add_argument("--device", default=None)
    run.add_argument("--bundle-id", dest="bundle_id", default=None)
    run.add_argument("--timeout", type=float, default=180.0)
    run.set_defaults(func=cmd_run)

    status = sub.add_parser("status", help="print session state")
    status.set_defaults(func=cmd_status)

    tap = sub.add_parser("tap", help="pointer down/up at logical pixels")
    tap.add_argument("x", type=float)
    tap.add_argument("y", type=float)
    tap.set_defaults(func=cmd_tap)

    ev = sub.add_parser("eval", help="evaluate a Dart expression via VM Service")
    ev.add_argument("expression")
    ev.set_defaults(func=cmd_eval)

    shot = sub.add_parser("screenshot", help="simctl screenshot, VM Service fallback")
    shot.add_argument("path", nargs="?", default=None)
    shot.set_defaults(func=cmd_screenshot)

    tree = sub.add_parser("tree", help="Flutter inspector summary tree")
    tree.set_defaults(func=cmd_tree)

    bg = sub.add_parser("background", help="Simulator Home (Cmd-Shift-H)")
    bg.set_defaults(func=cmd_background)

    fg = sub.add_parser("foreground", help="simctl launch by bundle id")
    fg.set_defaults(func=cmd_foreground)

    kill = sub.add_parser("kill", help="stop flutter run")
    kill.set_defaults(func=cmd_kill)

    down = sub.add_parser("shutdown", help="kill + shutdown simulator we created")
    down.set_defaults(func=cmd_shutdown)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = repo_root(Path(args.chdir) if args.chdir else None)
    if args.chdir:
        os.chdir(root)
    path = state_path(root, args.state)
    state = load_state(path)
    return int(args.func(args, root, state, path) or 0)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
