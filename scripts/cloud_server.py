from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent
CLOUD_DIR = ROOT / "cloud-data"
USERS_PATH = CLOUD_DIR / "users.json"
HOST = os.environ.get("PET_CLOUD_HOST", "0.0.0.0")
PORT = int(os.environ.get("PET_CLOUD_PORT", "8765"))


def read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default
    return data if isinstance(data, dict) else default


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def password_hash(password: str, salt: str | None = None) -> str:
    raw_salt = base64.b64decode(salt) if salt else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), raw_salt, 200_000)
    return f"{base64.b64encode(raw_salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(password_hash(password, salt).split("$", 1)[1], expected)


def safe_user_id(username: str) -> str:
    digest = hashlib.sha256(username.lower().encode("utf-8")).hexdigest()[:20]
    return digest


def safe_rel_path(value: str) -> str | None:
    rel = value.replace("\\", "/").strip("/")
    if not (rel.startswith("data/") or rel.startswith("reports/")):
        return None
    if ".." in rel.split("/"):
        return None
    parts = rel.split("/")
    if len(parts) != 2:
        return None
    if parts[0] == "data" and not parts[1].endswith(".json"):
        return None
    if parts[0] == "reports" and not parts[1].endswith(".md"):
        return None
    return rel


class CloudHandler(BaseHTTPRequestHandler):
    server_version = "DesktopPetCloud/1.0"

    def respond(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        data = self.rfile.read(length).decode("utf-8")
        payload = json.loads(data)
        return payload if isinstance(payload, dict) else {}

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/login":
                self.handle_login()
            elif path == "/api/sync":
                self.handle_sync()
            else:
                self.respond(404, {"error": "not found"})
        except Exception as exc:
            self.respond(500, {"error": str(exc)})

    def handle_login(self) -> None:
        payload = self.read_body()
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", ""))
        device_id = str(payload.get("device_id", "")).strip()
        device_name = str(payload.get("device_name", "")).strip()
        if not username or not password:
            self.respond(400, {"error": "username and password are required"})
            return

        users = read_json(USERS_PATH, {"users": {}, "tokens": {}})
        user = users["users"].get(username)
        if user:
            if not verify_password(password, user.get("password_hash", "")):
                self.respond(401, {"error": "invalid username or password"})
                return
        else:
            user = {
                "id": safe_user_id(username),
                "password_hash": password_hash(password),
                "created_at": time.time(),
                "devices": {},
            }
            users["users"][username] = user

        token = secrets.token_urlsafe(32)
        users.setdefault("tokens", {})[token] = username
        user.setdefault("devices", {})[device_id or secrets.token_hex(8)] = {
            "name": device_name or "unknown",
            "last_login": time.time(),
        }
        write_json(USERS_PATH, users)
        self.respond(200, {"token": token, "username": username})

    def current_user(self) -> tuple[str, dict] | None:
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        token = auth.removeprefix("Bearer ").strip()
        users = read_json(USERS_PATH, {"users": {}, "tokens": {}})
        username = users.get("tokens", {}).get(token)
        if not username:
            return None
        user = users.get("users", {}).get(username)
        if not user:
            return None
        return username, user

    def handle_sync(self) -> None:
        current = self.current_user()
        if not current:
            self.respond(401, {"error": "unauthorized"})
            return
        _username, user = current
        payload = self.read_body()
        user_dir = CLOUD_DIR / "users" / user["id"]
        manifest_path = user_dir / "manifest.json"
        manifest = read_json(manifest_path, {"files": {}})

        for item in payload.get("files", []):
            if not isinstance(item, dict):
                continue
            rel = safe_rel_path(str(item.get("path", "")))
            if not rel:
                continue
            incoming_mtime = float(item.get("mtime") or time.time())
            known = manifest["files"].get(rel, {})
            if known and float(known.get("mtime", 0)) > incoming_mtime + 0.5:
                continue
            target = user_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(item.get("content", "")), encoding="utf-8")
            os.utime(target, (incoming_mtime, incoming_mtime))
            manifest["files"][rel] = {"mtime": incoming_mtime, "updated_at": time.time()}

        files = []
        for rel, meta in sorted(manifest.get("files", {}).items()):
            safe_rel = safe_rel_path(rel)
            if not safe_rel:
                continue
            path = user_dir / safe_rel
            if not path.exists():
                continue
            files.append(
                {
                    "path": safe_rel,
                    "mtime": float(meta.get("mtime") or path.stat().st_mtime),
                    "content": path.read_text(encoding="utf-8"),
                }
            )

        write_json(manifest_path, manifest)
        self.respond(200, {"files": files})

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    CLOUD_DIR.mkdir(exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), CloudHandler)
    print(f"Desktop Pet cloud server listening on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
