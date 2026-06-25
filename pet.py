from __future__ import annotations

import ctypes
import hashlib
import io
import json
import math
import os
import platform
import random
import struct
import subprocess
import threading
import time
import tkinter as tk
import tkinter.messagebox as messagebox
import urllib.error
import urllib.parse
import urllib.request
import uuid
import wave
import winsound
from ctypes import wintypes
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import win32com.client


TRANSPARENT = "#ff00ff"
FPS_MS = 33
INK = "#5a4540"
DATA_DIR = Path(__file__).with_name("data")
REPORTS_DIR = Path(__file__).with_name("reports")
CLOUD_CONFIG_PATH = DATA_DIR / "cloud-config.json"
DEEPSEEK_CONFIG_PATH = DATA_DIR / "deepseek-config.json"
PET_CONFIG_PATH = DATA_DIR / "pet-config.json"
COMPANION_STATE_PATH = DATA_DIR / "companion-state.json"
RECOGNIZER_SCRIPT = Path(__file__).with_name("scripts") / "recognize-once.ps1"
FOCUS_SECONDS = 25 * 60
BREAK_SECONDS = 5 * 60
EYE_REMINDER_SECONDS = 20 * 60
STAND_REMINDER_SECONDS = 45 * 60
DISTRACTION_COOLDOWN_SECONDS = 90
CLOUD_SYNC_SECONDS = 5 * 60
CLOUD_TIMEOUT_SECONDS = 10
DISTRACTION_KEYWORDS = [
    "bilibili",
    "youtube",
    "douyin",
    "tiktok",
    "netflix",
    "steam",
    "wegame",
    "\u54d4\u54e9\u54d4\u54e9",
    "\u6296\u97f3",
    "\u6e38\u620f",
    "\u76f4\u64ad",
]
PERSONALITY_PACKS = {
    "gentle": "\u6e29\u67d4\u966a\u4f34\u578b",
    "teacher": "\u5c0f\u8001\u5e08\u578b",
    "energetic": "\u5143\u6c14\u6253\u6c14\u578b",
    "direct": "\u76f4\u63a5\u9ad8\u6548\u578b",
}
OWNER_EMOTIONS = {
    "happy": ("\u5f00\u5fc3", "happy", "\u6211\u611f\u89c9\u5230\u4f60\u4eca\u5929\u6709\u5149\uff0c\u6211\u4e5f\u8ddf\u7740\u5f00\u5fc3\u3002"),
    "tired": ("\u7d2f", "sleepy", "\u90a3\u6211\u653e\u8f7b\u4e00\u70b9\uff0c\u5148\u966a\u4f60\u6162\u6162\u6765\u3002"),
    "anxious": ("\u7126\u8651", "worried", "\u5148\u547c\u5438\u4e00\u4e0b\uff0c\u6211\u4eec\u53ea\u627e\u4e0b\u4e00\u4e2a\u5c0f\u6b65\u9aa4\u3002"),
    "low": ("\u4f4e\u843d", "worried", "\u4eca\u5929\u5141\u8bb8\u6162\u4e00\u70b9\uff0c\u6211\u5728\u8fd9\u91cc\u966a\u4f60\u3002"),
    "focused": ("\u60f3\u4e13\u6ce8", "focused", "\u597d\uff0c\u6211\u4f1a\u5c11\u8bf4\u4e00\u70b9\uff0c\u966a\u4f60\u628a\u6ce8\u610f\u529b\u6536\u56de\u6765\u3002"),
}


@dataclass
class Mood:
    name: str
    body: str
    cheek: str
    message: str
    expression: str


@dataclass
class WindowInfo:
    title: str
    process: str


@dataclass
class PetAction:
    label: str
    mood: str
    message: str
    keywords: tuple[str, ...]


MOODS = [
    Mood("happy", "#ffd1dc", "#ff8fb3", "\u4eca\u5929\u4e5f\u8981\u8d34\u8d34\u3002", "smile"),
    Mood("curious", "#c7f0ff", "#6ec7e8", "\u4f60\u5728\u505a\u4ec0\u4e48\u5440\uff1f", "curious"),
    Mood("sleepy", "#d9d1ff", "#a697ff", "\u6211\u5148\u772f\u4e00\u5c0f\u4f1a\u513f\u3002", "sleepy"),
    Mood("hungry", "#ffe4a3", "#ffbd59", "\u60f3\u5403\u5c0f\u997c\u5e72\u3002", "hungry"),
    Mood("focused", "#b9e6c9", "#6fcf97", "\u6211\u8fdb\u5165\u4e13\u6ce8\u5de1\u903b\u6a21\u5f0f\u3002", "focused"),
    Mood("proud", "#ffd6a5", "#ff9f1c", "\u4eca\u5929\u7684\u4f60\u5f88\u6709\u884c\u52a8\u529b\uff01", "proud"),
    Mood("worried", "#cfd7e6", "#92a4bd", "\u8981\u4e0d\u8981\u4f11\u606f\u4e00\u4e0b\uff1f", "worried"),
    Mood("excited", "#ffc6ff", "#e879f9", "\u54c7\uff0c\u51b2\u8d77\u6765\u4e86\uff01", "excited"),
]
MOOD_BY_NAME = {mood.name: mood for mood in MOODS}
SKINS = {
    "cat": "\u732b\u732b",
    "bunny": "\u5c0f\u5154\u5b50",
    "bear": "\u5c0f\u718a",
    "tiger": "\u5c0f\u8001\u864e",
}
PET_ACTIONS = {
    "drink": PetAction("\u559d\u6c34", "happy", "\u5495\u561f\u5495\u561f\uff0c\u8865\u6c34\u6210\u529f\u3002", ("\u559d\u6c34", "\u6c34")),
    "work": PetAction("\u52b3\u52a8", "focused", "\u5c0f\u5de5\u5320\u4e0a\u5c97\uff0c\u6572\u6572\u6253\u6253\u3002", ("\u52b3\u52a8", "\u5de5\u4f5c", "\u5e72\u6d3b")),
    "plant": PetAction("\u690d\u6811", "proud", "\u57f9\u571f\u6d47\u6c34\uff0c\u79cd\u4e0b\u4e00\u70b9\u7eff\u610f\u3002", ("\u690d\u6811", "\u79cd\u6811", "\u79cd\u82b1")),
    "home": PetAction("\u8fc7\u5bb6\u5bb6", "curious", "\u4eca\u5929\u6211\u6765\u5f53\u5c0f\u7ba1\u5bb6\u3002", ("\u8fc7\u5bb6\u5bb6", "\u5bb6\u5bb6", "\u5c0f\u7ba1\u5bb6")),
    "teacher": PetAction("\u5c0f\u8001\u5e08", "focused", "\u5c0f\u8001\u5e08\u5f00\u8bfe\uff1a\u5148\u628a\u6700\u91cd\u8981\u7684\u90a3\u4ef6\u4e8b\u5199\u4e0b\u6765\u3002", ("\u8001\u5e08", "\u8bb2\u8bfe", "\u4e0a\u8bfe", "\u6559\u5b66")),
    "study": PetAction("\u5b66\u4e60", "focused", "\u6253\u5f00\u5c0f\u4e66\u672c\uff0c\u6211\u4eec\u4e00\u8d77\u5b66\u4e00\u4f1a\u513f\u3002", ("\u5b66\u4e60", "\u8bfb\u4e66", "\u770b\u4e66")),
    "chef": PetAction("\u53a8\u5e08", "hungry", "\u4eca\u5929\u505a\u70b9\u6696\u4e4e\u4e4e\u7684\u597d\u5403\u7684\u3002", ("\u53a8\u5e08", "\u505a\u996d", "\u70f9\u996a")),
    "paint": PetAction("\u753b\u753b", "excited", "\u753b\u4e00\u70b9\u5f69\u8272\uff0c\u684c\u9762\u4f1a\u66f4\u53ef\u7231\u3002", ("\u753b\u753b", "\u753b\u753b", "\u753b\u5bb6")),
    "doctor": PetAction("\u5c0f\u533b\u751f", "worried", "\u5c0f\u533b\u751f\u5de1\u8bca\uff1a\u522b\u5fd8\u4e86\u4f11\u606f\u548c\u559d\u6c34\u3002", ("\u533b\u751f", "\u770b\u75c5", "\u62a4\u58eb")),
    "stretch": PetAction("\u4f38\u5c55", "happy", "\u8ddf\u6211\u4e00\u8d77\u62c9\u4f38\u4e00\u4e0b\uff0c\u80a9\u9888\u4f1a\u8f7b\u4e00\u70b9\u3002", ("\u4f38\u5c55", "\u62c9\u4f38", "\u4e45\u5750")),
}


def today_key() -> str:
    return date.today().isoformat()


def format_seconds(seconds: float) -> str:
    seconds = int(max(0, seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


class wave_open:
    def __init__(self, buffer: io.BytesIO, sample_rate: int) -> None:
        self.buffer = buffer
        self.sample_rate = sample_rate
        self.wav: wave.Wave_write | None = None

    def __enter__(self):
        self.wav = wave.open(self.buffer, "wb")
        self.wav.setnchannels(1)
        self.wav.setsampwidth(2)
        self.wav.setframerate(self.sample_rate)

        def write_sample(sample: int) -> None:
            sample = max(-32768, min(32767, sample))
            self.wav.writeframes(struct.pack("<h", sample))

        return write_sample

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.wav is not None:
            self.wav.close()


class ActivityTracker:
    def __init__(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        self.current_day = today_key()
        self.path = DATA_DIR / f"activity-{self.current_day}.json"
        self.data = self.load_day()
        self.last_seen = time.time()
        self.last_key: str | None = None

    def load_day(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {"date": self.current_day, "apps": {}, "windows": {}}

    def rollover_if_needed(self) -> None:
        if today_key() == self.current_day:
            return
        self.save()
        self.current_day = today_key()
        self.path = DATA_DIR / f"activity-{self.current_day}.json"
        self.data = self.load_day()
        self.last_seen = time.time()
        self.last_key = None

    def get_active_window(self) -> WindowInfo:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return WindowInfo("\u684c\u9762", "desktop")

        title_buffer = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buffer, 512)
        title = title_buffer.value.strip() or "\u65e0\u6807\u9898\u7a97\u53e3"

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = self.process_name(pid.value)
        return WindowInfo(title, process)

    def process_name(self, pid: int) -> str:
        if not pid:
            return "unknown"
        kernel32 = ctypes.windll.kernel32
        process_query_limited_info = 0x1000
        handle = kernel32.OpenProcess(process_query_limited_info, False, pid)
        if not handle:
            return f"pid-{pid}"
        try:
            size = wintypes.DWORD(1024)
            buffer = ctypes.create_unicode_buffer(size.value)
            ok = kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
            if ok:
                return Path(buffer.value).name.lower()
        finally:
            kernel32.CloseHandle(handle)
        return f"pid-{pid}"

    def sample(self) -> None:
        self.rollover_if_needed()
        now = time.time()
        elapsed = max(0, min(now - self.last_seen, 15))
        if self.last_key and elapsed:
            self.add_seconds(self.last_key, elapsed)

        info = self.get_active_window()
        clean_title = " ".join(info.title.split())[:140]
        self.last_key = f"{info.process}|{clean_title}"
        self.last_seen = now

    def add_seconds(self, key: str, elapsed: float) -> None:
        process, title = key.split("|", 1)
        apps = self.data.setdefault("apps", {})
        windows = self.data.setdefault("windows", {})
        apps[process] = round(apps.get(process, 0) + elapsed, 2)
        windows[key] = {
            "process": process,
            "title": title,
            "seconds": round(windows.get(key, {}).get("seconds", 0) + elapsed, 2),
        }

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def top_apps(self, limit: int = 6) -> list[tuple[str, float]]:
        apps = self.data.get("apps", {})
        return sorted(apps.items(), key=lambda item: item[1], reverse=True)[:limit]

    def top_windows(self, limit: int = 8) -> list[dict]:
        windows = self.data.get("windows", {})
        return sorted(windows.values(), key=lambda item: item.get("seconds", 0), reverse=True)[:limit]


class CloudSyncClient:
    def __init__(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        self.config = self.load_config()

    def load_config(self) -> dict:
        if CLOUD_CONFIG_PATH.exists():
            try:
                data = json.loads(CLOUD_CONFIG_PATH.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass
        return {
            "endpoint": "",
            "username": "",
            "token": "",
            "device_id": uuid.uuid4().hex,
            "device_name": platform.node() or "Windows PC",
            "last_sync_at": "",
        }

    def save_config(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        tmp = CLOUD_CONFIG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(CLOUD_CONFIG_PATH)

    def is_configured(self) -> bool:
        return bool(self.config.get("endpoint") and self.config.get("token"))

    def set_endpoint(self, endpoint: str) -> None:
        self.config["endpoint"] = endpoint.strip().rstrip("/")

    def api_url(self, path: str) -> str:
        return f"{self.config.get('endpoint', '').rstrip('/')}{path}"

    def request_json(self, path: str, payload: dict | None = None, token: str | None = None) -> dict:
        body = None
        method = "GET"
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            method = "POST"
            headers["Content-Type"] = "application/json; charset=utf-8"
        auth_token = token or self.config.get("token")
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        request = urllib.request.Request(self.api_url(path), data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=CLOUD_TIMEOUT_SECONDS) as response:
                data = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"云端返回 {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"无法连接云端：{exc.reason}") from exc
        if not data:
            return {}
        result = json.loads(data)
        if not isinstance(result, dict):
            raise RuntimeError("云端响应格式不正确。")
        return result

    def login(self, endpoint: str, username: str, password: str, device_name: str) -> None:
        self.set_endpoint(endpoint)
        payload = {
            "username": username.strip(),
            "password": password,
            "device_id": self.config.get("device_id") or uuid.uuid4().hex,
            "device_name": device_name.strip() or platform.node() or "Windows PC",
        }
        result = self.request_json("/api/login", payload=payload, token="")
        token = result.get("token")
        if not token:
            raise RuntimeError("登录失败：云端没有返回 token。")
        self.config.update(
            {
                "username": payload["username"],
                "token": token,
                "device_id": payload["device_id"],
                "device_name": payload["device_name"],
            }
        )
        self.save_config()

    def local_files(self) -> list[dict]:
        files: list[dict] = []
        for folder, prefix, patterns in [
            (DATA_DIR, "data", ["*.json"]),
            (REPORTS_DIR, "reports", ["*.md"]),
        ]:
            if not folder.exists():
                continue
            for pattern in patterns:
                for path in folder.glob(pattern):
                    if path in {CLOUD_CONFIG_PATH, DEEPSEEK_CONFIG_PATH, PET_CONFIG_PATH, COMPANION_STATE_PATH} or path.suffix == ".tmp":
                        continue
                    try:
                        content = path.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        continue
                    files.append(
                        {
                            "path": f"{prefix}/{path.name}",
                            "mtime": path.stat().st_mtime,
                            "content": content,
                        }
                    )
        return files

    def apply_remote_files(self, files: list[dict]) -> list[str]:
        changed: list[str] = []
        for item in files:
            rel_path = str(item.get("path", "")).replace("\\", "/")
            if not (rel_path.startswith("data/") or rel_path.startswith("reports/")):
                continue
            if "/" in rel_path[5:] and rel_path.startswith("data/"):
                continue
            if "/" in rel_path[8:] and rel_path.startswith("reports/"):
                continue
            target = Path(__file__).with_name(rel_path.split("/", 1)[0]) / rel_path.split("/", 1)[1]
            remote_mtime = float(item.get("mtime") or 0)
            if target.exists() and target.stat().st_mtime >= remote_mtime - 0.5:
                continue
            target.parent.mkdir(exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_text(str(item.get("content", "")), encoding="utf-8")
            tmp.replace(target)
            if remote_mtime > 0:
                os.utime(target, (remote_mtime, remote_mtime))
            changed.append(rel_path)
        return changed

    def sync(self) -> tuple[int, int]:
        if not self.is_configured():
            raise RuntimeError("还没有配置云同步账号。")
        payload = {
            "device_id": self.config.get("device_id"),
            "device_name": self.config.get("device_name"),
            "files": self.local_files(),
        }
        result = self.request_json("/api/sync", payload=payload)
        files = result.get("files", [])
        if not isinstance(files, list):
            raise RuntimeError("云端同步响应格式不正确。")
        changed = self.apply_remote_files(files)
        self.config["last_sync_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.save_config()
        return len(payload["files"]), len(changed)


class DeepSeekChatClient:
    def __init__(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        self.config = self.load_config()

    def load_config(self) -> dict:
        if DEEPSEEK_CONFIG_PATH.exists():
            try:
                data = json.loads(DEEPSEEK_CONFIG_PATH.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return {
                        "base_url": str(data.get("base_url") or "https://api.deepseek.com").rstrip("/"),
                        "api_key": str(data.get("api_key") or ""),
                        "model": str(data.get("model") or "deepseek-v4-flash"),
                    }
            except json.JSONDecodeError:
                pass
        return {"base_url": "https://api.deepseek.com", "api_key": "", "model": "deepseek-v4-flash"}

    def save_config(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        tmp = DEEPSEEK_CONFIG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(DEEPSEEK_CONFIG_PATH)

    def is_configured(self) -> bool:
        return bool(self.config.get("api_key"))

    def chat(self, system_prompt: str, messages: list[dict]) -> str:
        if not self.is_configured():
            raise RuntimeError("还没有配置 DeepSeek API Key。")
        payload = {
            "model": self.config.get("model") or "deepseek-v4-flash",
            "messages": [{"role": "system", "content": system_prompt}] + messages,
            "stream": False,
            "temperature": 0.8,
            "max_tokens": 220,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {self.config.get('api_key')}",
        }
        url = f"{str(self.config.get('base_url') or 'https://api.deepseek.com').rstrip('/')}/chat/completions"
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"DeepSeek 返回 {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"无法连接 DeepSeek：{exc.reason}") from exc
        choices = result.get("choices", [])
        if not choices:
            raise RuntimeError("DeepSeek 没有返回回复。")
        message = choices[0].get("message", {})
        content = str(message.get("content") or "").strip()
        if not content:
            raise RuntimeError("DeepSeek 回复为空。")
        return content


class PetPreferences:
    def __init__(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        self.data = self.load()

    def load(self) -> dict:
        default = {
            "pet_name": "\u5c0f\u722a",
            "owner_name": "\u4e3b\u4eba",
            "personality": "gentle",
            "personal_preferences": "",
            "weather_city": "",
            "do_not_disturb": False,
        }
        if PET_CONFIG_PATH.exists():
            try:
                data = json.loads(PET_CONFIG_PATH.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    default.update(data)
            except json.JSONDecodeError:
                pass
        return default

    def save(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        tmp = PET_CONFIG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(PET_CONFIG_PATH)

    def get(self, key: str, default: object = "") -> object:
        return self.data.get(key, default)


class CompanionState:
    def __init__(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        self.data = self.load()

    def load(self) -> dict:
        default = {
            "owner_emotion": "",
            "owner_emotion_date": "",
            "checkins": {},
            "achievements": {},
        }
        if COMPANION_STATE_PATH.exists():
            try:
                data = json.loads(COMPANION_STATE_PATH.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    default.update(data)
            except json.JSONDecodeError:
                pass
        return default

    def save(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        tmp = COMPANION_STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(COMPANION_STATE_PATH)

    def unlock(self, key: str, title: str) -> bool:
        achievements = self.data.setdefault("achievements", {})
        if key in achievements:
            return False
        achievements[key] = {"title": title, "date": today_key()}
        self.save()
        return True


class WeatherClient:
    def __init__(self, prefs: PetPreferences) -> None:
        self.prefs = prefs

    def locate_city(self) -> str:
        configured = str(self.prefs.get("weather_city", "") or "").strip()
        if configured:
            return configured
        try:
            request = urllib.request.Request("http://ip-api.com/json/?lang=zh-CN", headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8"))
            return str(data.get("city") or data.get("regionName") or "").strip()
        except Exception:
            return ""

    def fetch(self) -> str:
        city = self.locate_city()
        if not city:
            return "\u6211\u8fd8\u6ca1\u627e\u5230\u5f53\u524d\u57ce\u5e02\uff0c\u53ef\u4ee5\u5728\u504f\u597d\u91cc\u624b\u52a8\u586b\u4e00\u4e2a\u57ce\u5e02\u3002"
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1&lang=zh"
        request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "desktop-pet/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            return f"\u6211\u6ca1\u62ff\u5230 {city} \u7684\u5929\u6c14\uff1a{exc}\u3002"
        summary = self.parse_weather(raw)
        return f"{city}\u5929\u6c14\uff1a{summary}" if summary else "\u6211\u8fde\u4e0a\u4e86\u5929\u6c14\u63a5\u53e3\uff0c\u4f46\u6ca1\u8bfb\u5230\u6709\u6548\u5929\u6c14\u3002"

    def parse_weather(self, raw: str) -> str:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            text = " ".join(raw.split())
            return text[:90] if text else ""
        current = (data.get("current_condition") or [{}])[0]
        weather = (current.get("lang_zh") or current.get("weatherDesc") or [{}])[0].get("value", "")
        temp = current.get("temp_C", "")
        feels = current.get("FeelsLikeC", "")
        humidity = current.get("humidity", "")
        wind = current.get("windspeedKmph", "")
        pieces = []
        if weather:
            pieces.append(str(weather))
        if temp:
            pieces.append(f"\u6e29\u5ea6 {temp}\u2103")
        if feels:
            pieces.append(f"\u4f53\u611f {feels}\u2103")
        if humidity:
            pieces.append(f"\u6e7f\u5ea6 {humidity}%")
        if wind:
            pieces.append(f"\u98ce\u901f {wind}km/h")
        return "\uff0c".join(pieces)


class DesktopPet:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("\u684c\u9762\u840c\u5ba0")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT)
        self.root.configure(cursor="hand2")
        self.root.wm_attributes("-transparentcolor", TRANSPARENT)

        self.ui_scale = 0.45
        self.logical_width = 260
        self.logical_height = 240
        self.width = int(self.logical_width * self.ui_scale)
        self.height = int(self.logical_height * self.ui_scale)
        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=TRANSPARENT,
            highlightthickness=0,
            cursor="hand2",
        )
        self.canvas.pack()

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.x = screen_w - self.width - 80
        self.y = screen_h - self.height - 120
        self.root.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")

        self.tick = 0
        self.mood = random.choice(MOODS)
        self.pet_skin = "cat"
        self.current_action: str | None = None
        self.action_until = 0
        self.message = self.mood.message
        self.message_until = 180
        self.mood_changed_at = time.time()
        self.drag_start: tuple[int, int] | None = None
        self.walk_dx = random.choice([-1, 1])
        self.walk_timer = 0
        self.is_sleeping = False

        self.drop_active = False
        self.drop_velocity = 0.0
        self.ground_y = self.y
        self.squash = 0.0
        self.impact_cooldown = 0

        self.pomodoro_mode = "focus"
        self.pomodoro_running = False
        self.pomodoro_remaining = FOCUS_SECONDS
        self.pomodoro_last_tick = time.time()
        self.pomodoro_sessions = 0

        self.tracker = ActivityTracker()
        self.cloud = CloudSyncClient()
        self.deepseek = DeepSeekChatClient()
        self.prefs = PetPreferences()
        self.companion_state = CompanionState()
        self.weather = WeatherClient(self.prefs)
        self.cloud_syncing = False
        self.cloud_dirty = False
        self.last_cloud_sync = 0.0
        self.last_tracker_save = time.time()
        self.chat_window: tk.Toplevel | None = None
        self.stats_window: tk.Toplevel | None = None
        self.tasks_window: tk.Toplevel | None = None
        self.panel_window: tk.Toplevel | None = None
        self.panel_visible = False
        self.pomodoro_widget: tk.Toplevel | None = None
        self.pomodoro_time_var = tk.StringVar(value="")
        self.pomodoro_mode_var = tk.StringVar(value="")
        self.pomodoro_action_var = tk.StringVar(value="")
        self.pomodoro_widget_visible = tk.BooleanVar(value=False)
        self.do_not_disturb_var = tk.BooleanVar(value=bool(self.prefs.get("do_not_disturb", False)))
        self.pomodoro_progress: tk.Canvas | None = None
        self.tasks = self.load_tasks()
        self.active_stretch_seconds = 0
        self.last_eye_reminder = time.time()
        self.last_stand_reminder = time.time()
        self.last_distraction_reminder = 0.0
        self.next_proactive_at = time.time() + random.randint(240, 420)
        self.next_action_at = time.time() + random.randint(45, 90)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="\u6295\u5582", command=self.feed)
        self.menu.add_command(label="\u73a9\u4e00\u4f1a\u513f", command=self.play)
        self.menu.add_command(label="Q\u5f39\u4e0b\u843d", command=self.drop_from_top)
        self.menu.add_command(label="\u7761\u4e00\u4f1a\u513f", command=self.nap)
        skin_menu = tk.Menu(self.menu, tearoff=0)
        for skin_id, skin_name in SKINS.items():
            skin_menu.add_command(label=skin_name, command=lambda value=skin_id: self.set_skin(value))
        self.menu.add_cascade(label="\u5207\u6362\u5f62\u8c61", menu=skin_menu)
        self.menu.add_separator()
        self.menu.add_checkbutton(label="\u756a\u8304\u949f", variable=self.pomodoro_widget_visible, command=self.toggle_pomodoro_widget)
        self.menu.add_separator()
        self.menu.add_command(label="\u548c\u840c\u5ba0\u5bf9\u8bdd", command=self.open_chat)
        self.menu.add_command(label="DeepSeek \u914d\u7f6e", command=self.open_deepseek_settings)
        self.menu.add_command(label="\u67e5\u5929\u6c14", command=self.check_weather_async)
        emotion_menu = tk.Menu(self.menu, tearoff=0)
        for emotion_id, (label, _mood, _message) in OWNER_EMOTIONS.items():
            emotion_menu.add_command(label=label, command=lambda value=emotion_id: self.mark_owner_emotion(value))
        self.menu.add_cascade(label="\u6807\u8bb0\u60c5\u7eea", menu=emotion_menu)
        self.menu.add_command(label="\u540d\u5b57/\u504f\u597d/\u6027\u683c", command=self.open_preferences)
        self.menu.add_command(label="\u6210\u5c31\u6253\u5361", command=self.open_achievements)
        self.menu.add_checkbutton(label="\u52ff\u6270\u6a21\u5f0f", variable=self.do_not_disturb_var, command=self.toggle_do_not_disturb)
        self.menu.add_command(label="\u663e\u793a/\u9690\u85cf\u5c0f\u9762\u677f", command=self.toggle_panel)
        self.menu.add_command(label="\u4eca\u65e5\u770b\u677f", command=self.open_stats)
        self.menu.add_command(label="\u4eca\u65e5\u4e09\u4ef6\u4e8b", command=self.open_tasks)
        cloud_menu = tk.Menu(self.menu, tearoff=0)
        cloud_menu.add_command(label="\u767b\u5f55/\u914d\u7f6e", command=self.open_cloud_settings)
        cloud_menu.add_command(label="\u7acb\u5373\u540c\u6b65", command=lambda: self.sync_cloud_async(manual=True))
        self.menu.add_cascade(label="\u4e91\u540c\u6b65", menu=cloud_menu)
        self.menu.add_separator()
        self.menu.add_command(label="\u9000\u51fa", command=self.quit)

        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)
        self.canvas.bind("<Double-Button-1>", self.change_mood)
        self.canvas.bind("<Button-3>", self.show_menu)
        self.canvas.bind("<Enter>", self.on_hover)

        self.root.bind("<Escape>", lambda _event: self.quit())
        self.root.bind("<space>", lambda _event: self.drop_from_top())
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        if self.cloud.is_configured():
            self.root.after(1500, lambda: self.sync_cloud_async(manual=False))
        self.root.after(1000, self.activity_loop)
        self.animate()

    def start_drag(self, event: tk.Event) -> None:
        self.drag_start = (event.x_root - self.x, event.y_root - self.y)
        self.drop_active = False
        self.say("\u5e26\u6211\u53bb\u54ea\u513f\uff1f")

    def drag(self, event: tk.Event) -> None:
        if self.drag_start is None:
            return
        offset_x, offset_y = self.drag_start
        self.x = event.x_root - offset_x
        self.y = event.y_root - offset_y
        self.ground_y = self.y
        self.root.geometry(f"+{self.x}+{self.y}")

    def end_drag(self, _event: tk.Event) -> None:
        self.drag_start = None
        self.say("\u8fd9\u91cc\u4e0d\u9519\u3002")

    def show_menu(self, event: tk.Event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def on_hover(self, _event: tk.Event) -> None:
        if not self.do_not_disturb_var.get():
            self.say("\u6478\u6478\u5934\uff1f")
        if self.panel_visible:
            self.open_panel()

    def say(self, text: str, duration: int = 150) -> None:
        self.message = text
        self.message_until = duration

    def set_mood(self, name: str, message: str | None = None, duration: int = 180) -> None:
        self.mood = MOOD_BY_NAME.get(name, self.mood)
        self.is_sleeping = self.mood.name == "sleepy"
        self.mood_changed_at = time.time()
        self.say(message or self.mood.message, duration)

    def set_skin(self, skin: str) -> None:
        self.pet_skin = skin if skin in SKINS else "cat"
        self.set_mood("excited", f"\u6362\u6210{SKINS[self.pet_skin]}\u5566\uff01", 190)

    def set_action(self, action_id: str, duration: int = 900) -> None:
        action = PET_ACTIONS.get(action_id)
        if not action:
            return
        self.current_action = action_id
        self.action_until = duration
        self.set_mood(action.mood, action.message, 230)

    def schedule_next_action(self, soon: bool = False) -> None:
        delay = random.randint(35, 70) if soon else random.randint(120, 240)
        self.next_action_at = time.time() + delay

    def maybe_auto_action(self) -> None:
        now = time.time()
        if now < self.next_action_at:
            return
        if self.do_not_disturb_var.get() or self.current_action or self.drop_active or self.is_sleeping or self.pomodoro_running or self.message_until > 0:
            self.schedule_next_action(soon=True)
            return
        action_id = random.choice(["teacher", "plant", "home", "study", "drink", "paint", "doctor", "chef", "stretch"])
        self.set_action(action_id, duration=random.randint(520, 900))
        self.schedule_next_action()

    def clear_action(self) -> None:
        self.current_action = None
        self.action_until = 0
        self.set_mood("happy", "\u6536\u5de5\uff0c\u56de\u5230\u65e5\u5e38\u966a\u4f34\u6a21\u5f0f\u3002", 180)

    def make_glass_frame(self, win: tk.Toplevel, alpha: float = 0.94) -> tk.Frame:
        glass_bg = "#f8fbff"
        win.attributes("-alpha", alpha)
        win.configure(bg=glass_bg)
        frame = tk.Frame(win, bg=glass_bg, highlightthickness=1, highlightbackground="#d9e6f2")
        frame.pack(fill="both", expand=True)
        return frame

    def pet_popup_geometry(self, width: int, height: int, gap: int = 12) -> str:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        margin = 10
        right_x = self.x + self.width + gap
        left_x = self.x - width - gap
        if right_x + width <= screen_w - margin:
            x = right_x
        elif left_x >= margin:
            x = left_x
        else:
            max_x = max(margin, screen_w - width - margin)
            x = min(max(margin, self.x + (self.width - width) // 2), max_x)

        y = self.y + max(0, (self.height - height) // 2)
        if y + height > screen_h - margin:
            y = self.y - height - gap
        if y < margin:
            y = self.y + self.height + gap
        max_y = max(margin, screen_h - height - margin)
        y = min(max(margin, y), max_y)
        return f"{width}x{height}+{int(x)}+{int(y)}"

    def glass_button(self, parent: tk.Widget, text: str, command, width: int | None = None) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            width=width or 0,
            relief="flat",
            bd=0,
            bg="#ffffff",
            fg="#40505f",
            activebackground="#eaf3fb",
            font=("Microsoft YaHei UI", 9),
            cursor="hand2",
        )

    def pet_name(self) -> str:
        return str(self.prefs.get("pet_name", "\u5c0f\u722a") or "\u5c0f\u722a")

    def toggle_do_not_disturb(self) -> None:
        enabled = bool(self.do_not_disturb_var.get())
        self.prefs.data["do_not_disturb"] = enabled
        self.prefs.save()
        self.say("\u6211\u4f1a\u5b89\u9759\u4e00\u70b9\u3002" if enabled else "\u52ff\u6270\u5173\u95ed\uff0c\u6211\u7ee7\u7eed\u966a\u4f60\u3002", 180)

    def mark_owner_emotion(self, emotion_id: str) -> None:
        label, mood, message = OWNER_EMOTIONS.get(emotion_id, OWNER_EMOTIONS["focused"])
        self.companion_state.data["owner_emotion"] = emotion_id
        self.companion_state.data["owner_emotion_date"] = today_key()
        self.companion_state.data.setdefault("checkins", {})[today_key()] = label
        self.companion_state.save()
        if emotion_id in {"tired", "anxious", "low"}:
            self.set_action("doctor", duration=520)
        elif emotion_id == "focused":
            self.set_action("study", duration=520)
        self.set_mood(mood, message, 240)
        self.companion_state.unlock("first_emotion", "\u7b2c\u4e00\u6b21\u60c5\u7eea\u6253\u5361")

    def check_weather_async(self) -> None:
        self.say("\u6211\u53bb\u770b\u4e00\u773c\u5929\u6c14\u3002", 160)

        def worker() -> None:
            result = self.weather.fetch()
            self.companion_state.unlock("first_weather", "\u7b2c\u4e00\u6b21\u67e5\u5929\u6c14")
            self.root.after(0, lambda: self.set_mood("curious", result, 360))
            self.root.after(0, lambda: self.speak(result))

        threading.Thread(target=worker, daemon=True).start()

    def open_preferences(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("\u540d\u5b57/\u504f\u597d/\u6027\u683c")
        win.geometry(self.pet_popup_geometry(540, 390))
        win.attributes("-topmost", True)
        frame = self.make_glass_frame(win)
        tk.Label(frame, text="\u540d\u5b57\u3001\u504f\u597d\u548c\u6027\u683c", bg="#f8fbff", fg="#23313f", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        tk.Label(frame, text="\u8fd9\u4e9b\u53ea\u4fdd\u5b58\u5728\u672c\u673a\uff0cDeepSeek \u804a\u5929\u65f6\u4f1a\u8bfb\u53d6\u3002", bg="#f8fbff", fg="#6b7c8c", wraplength=500, justify="left").pack(anchor="w", padx=16, pady=(0, 12))
        form = tk.Frame(frame, bg="#f8fbff")
        form.pack(fill="x", padx=16)
        entries: dict[str, tk.Entry] = {}

        def add_entry(label: str, key: str) -> None:
            row = tk.Frame(form, bg="#f8fbff")
            row.pack(fill="x", pady=5)
            tk.Label(row, text=label, bg="#f8fbff", fg="#40505f", width=12, anchor="w").pack(side="left")
            entry = tk.Entry(row, relief="flat", bg="#ffffff", fg="#23313f", insertbackground="#6b7c8c", font=("Microsoft YaHei UI", 10))
            entry.insert(0, str(self.prefs.get(key, "")))
            entry.pack(side="left", fill="x", expand=True, ipady=6)
            entries[key] = entry

        add_entry("\u840c\u5ba0\u540d\u5b57", "pet_name")
        add_entry("\u4e3b\u4eba\u79f0\u547c", "owner_name")
        add_entry("\u5929\u6c14\u57ce\u5e02", "weather_city")
        row = tk.Frame(form, bg="#f8fbff")
        row.pack(fill="x", pady=5)
        tk.Label(row, text="\u6027\u683c\u5305", bg="#f8fbff", fg="#40505f", width=12, anchor="w").pack(side="left")
        personality_var = tk.StringVar(value=str(self.prefs.get("personality", "gentle")))
        tk.OptionMenu(row, personality_var, *PERSONALITY_PACKS.keys()).pack(side="left", fill="x", expand=True)
        tk.Label(form, text="\u4e2a\u4eba\u504f\u597d", bg="#f8fbff", fg="#40505f").pack(anchor="w", pady=(8, 3))
        pref_text = tk.Text(form, height=5, bg="#ffffff", fg="#23313f", relief="flat", highlightthickness=1, highlightbackground="#e1ebf3", font=("Microsoft YaHei UI", 10))
        pref_text.insert("1.0", str(self.prefs.get("personal_preferences", "")))
        pref_text.pack(fill="x")

        def save() -> None:
            for key, entry in entries.items():
                self.prefs.data[key] = entry.get().strip()
            self.prefs.data["personality"] = personality_var.get()
            self.prefs.data["personal_preferences"] = pref_text.get("1.0", "end").strip()
            self.prefs.save()
            self.set_mood("proud", f"\u597d\u7684\uff0c\u4ee5\u540e\u6211\u5c31\u53eb{self.pet_name()}\u3002", 220)

        bottom = tk.Frame(frame, bg="#f8fbff")
        bottom.pack(fill="x", padx=16, pady=14)
        self.glass_button(bottom, "\u4fdd\u5b58", save, 8).pack(side="left")
        self.glass_button(bottom, "\u5173\u95ed", win.destroy, 8).pack(side="right")

    def open_achievements(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("\u6210\u5c31\u6253\u5361")
        win.geometry(self.pet_popup_geometry(420, 320))
        win.attributes("-topmost", True)
        frame = self.make_glass_frame(win)
        tk.Label(frame, text="\u6210\u5c31\u6253\u5361", bg="#f8fbff", fg="#23313f", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        achievements = self.companion_state.data.get("achievements", {})
        checkins = self.companion_state.data.get("checkins", {})
        lines = [f"\u60c5\u7eea\u6253\u5361\uff1a{len(checkins)} \u5929", f"\u5df2\u89e3\u9501\u6210\u5c31\uff1a{len(achievements)} \u4e2a", ""]
        if achievements:
            lines.extend(f"- {item.get('title')}  {item.get('date')}" for item in achievements.values())
        else:
            lines.append("- \u8fd8\u6ca1\u6709\u6210\u5c31\uff0c\u5148\u6807\u8bb0\u4e00\u6b21\u60c5\u7eea\u5427\u3002")
        text = tk.Text(frame, bg="#fdfefe", fg="#354251", relief="flat", highlightthickness=1, highlightbackground="#e1ebf3", font=("Microsoft YaHei UI", 10))
        text.pack(fill="both", expand=True, padx=16, pady=12)
        text.insert("end", "\n".join(lines))
        text.configure(state="disabled")
        self.glass_button(frame, "\u5173\u95ed", win.destroy, 8).pack(anchor="e", padx=16, pady=(0, 12))

    def toggle_panel(self) -> None:
        self.panel_visible = not self.panel_visible
        if self.panel_visible:
            self.open_panel()
        elif self.panel_window and self.panel_window.winfo_exists():
            self.panel_window.destroy()

    def toggle_pomodoro_widget(self) -> None:
        if self.pomodoro_widget_visible.get():
            self.open_pomodoro_widget()
        elif self.pomodoro_widget and self.pomodoro_widget.winfo_exists():
            self.pomodoro_widget.destroy()

    def open_pomodoro_widget(self) -> None:
        if self.pomodoro_widget and self.pomodoro_widget.winfo_exists():
            self.pomodoro_widget_visible.set(True)
            self.pomodoro_widget.lift()
            self.refresh_pomodoro_widget()
            return

        win = tk.Toplevel(self.root)
        self.pomodoro_widget = win
        self.pomodoro_widget_visible.set(True)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.86)
        glass_bg = "#f8fbff"
        glass_edge = "#d9e6f2"
        win.configure(bg=glass_bg)

        frame = tk.Frame(win, bg=glass_bg, highlightthickness=1, highlightbackground=glass_edge)
        frame.pack(fill="both", expand=True)

        top = tk.Frame(frame, bg=glass_bg)
        top.pack(fill="x", padx=10, pady=(8, 1))
        tk.Label(top, text="\u25cf", bg=glass_bg, fg="#ff6b6b", font=("Segoe UI", 7)).pack(side="left", padx=(0, 4))
        tk.Label(top, text="\u756a\u8304\u4e13\u6ce8", bg=glass_bg, fg="#40505f", font=("Microsoft YaHei UI", 8, "bold")).pack(side="left")
        tk.Label(top, textvariable=self.pomodoro_mode_var, bg=glass_bg, fg="#6b7c8c", font=("Microsoft YaHei UI", 7)).pack(side="right")

        tk.Frame(frame, bg="#ffffff", height=1).pack(fill="x", padx=10, pady=(2, 5))

        time_row = tk.Frame(frame, bg=glass_bg)
        time_row.pack(fill="x", padx=10)
        tk.Label(time_row, textvariable=self.pomodoro_time_var, bg=glass_bg, fg="#23313f", font=("Segoe UI", 17, "bold")).pack(side="left")
        tk.Label(time_row, text="\u25cf \u25cf \u25cf", bg=glass_bg, fg="#c8d5df", font=("Segoe UI", 6)).pack(side="right", pady=(8, 0))

        self.pomodoro_progress = tk.Canvas(frame, width=138, height=11, bg=glass_bg, highlightthickness=0)
        self.pomodoro_progress.pack(fill="x", padx=10, pady=(4, 4))

        buttons = tk.Frame(frame, bg=glass_bg)
        buttons.pack(fill="x", padx=8, pady=(1, 8))
        button_style = {"relief": "flat", "bd": 0, "font": ("Microsoft YaHei UI", 8), "cursor": "hand2"}
        tk.Button(buttons, textvariable=self.pomodoro_action_var, command=self.toggle_pomodoro_running, width=6, bg="#ffffff", fg="#40505f", activebackground="#eaf3fb", **button_style).pack(side="left", padx=2)
        tk.Button(buttons, text="\u91cd\u7f6e", command=self.reset_pomodoro, width=6, bg="#ffffff", fg="#6b7c8c", activebackground="#eaf3fb", **button_style).pack(side="left", padx=2)
        tk.Button(buttons, text="\u00d7", command=self.close_pomodoro_widget, width=2, bg=glass_bg, fg="#8da0af", activebackground="#eaf3fb", **button_style).pack(side="right", padx=2)

        self.refresh_pomodoro_widget()

    def close_pomodoro_widget(self) -> None:
        self.pomodoro_widget_visible.set(False)
        if self.pomodoro_widget and self.pomodoro_widget.winfo_exists():
            self.pomodoro_widget.destroy()

    def toggle_pomodoro_running(self) -> None:
        if self.pomodoro_running:
            self.pause_pomodoro()
        else:
            self.start_pomodoro()

    def refresh_pomodoro_widget(self) -> None:
        if not self.pomodoro_widget or not self.pomodoro_widget.winfo_exists():
            self.pomodoro_widget_visible.set(False)
            return
        total = FOCUS_SECONDS if self.pomodoro_mode == "focus" else BREAK_SECONDS
        remaining = max(0, self.pomodoro_remaining)
        minutes, seconds = divmod(int(remaining), 60)
        mode_text = "\u4e13\u6ce8\u4e2d" if self.pomodoro_mode == "focus" else "\u4f11\u606f\u4e2d"
        if not self.pomodoro_running:
            mode_text = "\u5df2\u6682\u505c" if remaining < total else "\u672a\u5f00\u59cb"
        self.pomodoro_time_var.set(f"{minutes:02d}:{seconds:02d}")
        self.pomodoro_mode_var.set(mode_text)
        self.pomodoro_action_var.set("\u6682\u505c" if self.pomodoro_running else "\u5f00\u59cb")

        if self.pomodoro_progress:
            self.pomodoro_progress.delete("all")
            width = int(self.pomodoro_progress["width"])
            progress = 1 - remaining / max(total, 1)
            progress = min(max(progress, 0), 1)
            color = "#ff6b6b" if self.pomodoro_mode == "focus" else "#5ac88f"
            self.pomodoro_progress.create_rectangle(0, 3, width, 9, fill="#e2ebf3", outline="")
            self.pomodoro_progress.create_rectangle(0, 3, max(5, int(width * progress)), 9, fill=color, outline="")
            self.pomodoro_progress.create_oval(max(0, int(width * progress) - 4), 1, max(8, int(width * progress) + 4), 11, fill="#ffffff", outline=color)

        self.pomodoro_widget.geometry(self.pet_popup_geometry(152, 116, gap=10))
        self.root.after(500, self.refresh_pomodoro_widget)

    def open_panel(self) -> None:
        if self.panel_window and self.panel_window.winfo_exists():
            self.panel_window.lift()
            self.refresh_panel()
            return

        win = tk.Toplevel(self.root)
        self.panel_window = win
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.9)
        glass_bg = "#f8fbff"
        win.configure(bg=glass_bg)
        win.geometry(self.pet_popup_geometry(250, 156))

        frame = tk.Frame(win, bg=glass_bg, highlightthickness=1, highlightbackground="#d9e6f2")
        frame.pack(fill="both", expand=True)
        self.panel_title = tk.Label(frame, text="\u840c\u5ba0\u5c0f\u9762\u677f", bg=glass_bg, fg="#23313f", font=("Microsoft YaHei UI", 11, "bold"))
        self.panel_title.pack(anchor="w", padx=10, pady=(8, 2))
        self.panel_status = tk.Label(frame, text="", bg=glass_bg, fg="#6b7c8c", justify="left", font=("Microsoft YaHei UI", 9))
        self.panel_status.pack(anchor="w", padx=10)
        buttons = tk.Frame(frame, bg=glass_bg)
        buttons.pack(fill="x", padx=8, pady=(8, 6))
        self.glass_button(buttons, "\u756a\u8304", self.start_pomodoro, 5).pack(side="left", padx=2)
        self.glass_button(buttons, "\u4efb\u52a1", self.open_tasks, 5).pack(side="left", padx=2)
        self.glass_button(buttons, "\u770b\u677f", self.open_stats, 5).pack(side="left", padx=2)
        self.glass_button(buttons, "\u5bf9\u8bdd", self.open_chat, 5).pack(side="left", padx=2)
        self.glass_button(frame, "\u5173\u95ed\u5c0f\u9762\u677f", self.toggle_panel).pack(anchor="e", padx=8, pady=(0, 8))
        self.refresh_panel()

    def refresh_panel(self) -> None:
        if not self.panel_window or not self.panel_window.winfo_exists():
            return
        done_count = sum(1 for task in self.tasks if task.get("done"))
        current = self.tracker.get_active_window()
        status = (
            f"{self.pomodoro_label()}\n"
            f"\u4e09\u4ef6\u4e8b\uff1a{done_count}/3\n"
            f"\u5f53\u524d\uff1a{current.process[:22]}"
        )
        self.panel_status.configure(text=status)
        self.panel_window.geometry(self.pet_popup_geometry(250, 156))
        self.root.after(2000, self.refresh_panel)

    def speak(self, text: str) -> None:
        self.say(text, 240)

        def worker() -> None:
            try:
                speaker = win32com.client.Dispatch("SAPI.SpVoice")
                speaker.Rate = 1
                speaker.Volume = 88
                speaker.Speak(text)
            except Exception:
                winsound.MessageBeep()

        threading.Thread(target=worker, daemon=True).start()

    def recognize_speech_once(self) -> str:
        if not RECOGNIZER_SCRIPT.exists():
            raise RuntimeError("\u8bed\u97f3\u8bc6\u522b\u811a\u672c\u4e0d\u5b58\u5728\u3002")

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(RECOGNIZER_SCRIPT),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=14,
            creationflags=creationflags,
        )
        if completed.returncode != 0:
            error = (completed.stderr or completed.stdout or "\u6ca1\u6709\u542c\u6e05\u695a\u3002").strip()
            raise RuntimeError(error.splitlines()[-1])
        return completed.stdout.strip()

    def play_tone(self, frequency: int, duration_ms: int) -> None:
        def worker() -> None:
            try:
                winsound.Beep(frequency, duration_ms)
            except RuntimeError:
                winsound.MessageBeep()

        threading.Thread(target=worker, daemon=True).start()

    def play_wave_sound(self, samples: list[int], sample_rate: int = 44100) -> None:
        def worker() -> None:
            try:
                buffer = io.BytesIO()
                with wave_open(buffer, sample_rate) as write_sample:
                    for sample in samples:
                        write_sample(sample)
                winsound.PlaySound(buffer.getvalue(), winsound.SND_MEMORY)
            except Exception:
                winsound.MessageBeep()

        threading.Thread(target=worker, daemon=True).start()

    def play_drop_start_sound(self) -> None:
        sample_rate = 44100
        samples: list[int] = []
        duration = 0.18
        total = int(sample_rate * duration)
        for index in range(total):
            t = index / sample_rate
            progress = index / total
            freq = 780 - 360 * progress
            envelope = (1 - progress) ** 1.7
            value = math.sin(2 * math.pi * freq * t) * envelope * 5200
            samples.append(int(value))
        self.play_wave_sound(samples, sample_rate)

    def play_bouncy_landing_sound(self, speed: float) -> None:
        sample_rate = 44100
        samples: list[int] = []

        def add_burst(duration: float, start_freq: float, end_freq: float, volume: float, decay: float, brightness: float = 0.18) -> None:
            total = int(sample_rate * duration)
            for index in range(total):
                t = index / sample_rate
                progress = index / max(total - 1, 1)
                freq = start_freq + (end_freq - start_freq) * progress
                envelope = math.exp(-decay * progress)
                tone = math.sin(2 * math.pi * freq * t)
                overtone = math.sin(2 * math.pi * freq * 2.4 * t) * brightness
                sparkle = math.sin(2 * math.pi * freq * 3.15 * t) * brightness * 0.38
                samples.append(int((tone + overtone + sparkle) * envelope * volume))

        impact = min(max(speed / 24, 0.55), 1.0)
        add_burst(0.045, 260, 210, 7600 * impact, 7.0, 0.12)
        samples.extend([0] * int(sample_rate * 0.012))
        add_burst(0.095, 720, 1180, 9400 * impact, 4.8, 0.30)
        samples.extend([0] * int(sample_rate * 0.018))
        add_burst(0.055, 1320, 1560, 4300 * impact, 5.8, 0.34)
        self.play_wave_sound(samples, sample_rate)

    def change_mood(self, _event: tk.Event | None = None) -> None:
        current = self.mood
        choices = [mood for mood in MOODS if mood != current]
        chosen = random.choice(choices)
        self.set_mood(chosen.name)

    def feed(self) -> None:
        self.set_mood("happy", "\u55f7\u545c\uff0c\u8c22\u8c22\u6295\u5582\uff01", 210)
        self.play_tone(784, 60)

    def play(self) -> None:
        self.set_mood("excited", "\u6765\u73a9\u8ffd\u5149\u70b9\uff01", 210)
        self.walk_timer = 90
        self.walk_dx = random.choice([-3, 3])
        self.play_tone(988, 55)

    def drop_from_top(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.ground_y = min(max(self.y, 20), screen_h - self.height - 20)
        self.x = min(max(self.x, 10), screen_w - self.width - 10)
        self.y = -self.height + 8
        self.drop_velocity = 0.0
        self.drop_active = True
        self.walk_timer = 0
        self.set_mood("excited", "\u54bb\u2014\u2014\u63a5\u4f4f\u6211\uff01", 170)
        self.squash = -0.18
        self.play_drop_start_sound()
        self.root.geometry(f"+{self.x}+{self.y}")

    def nap(self) -> None:
        self.drop_active = False
        self.current_action = None
        self.action_until = 0
        self.set_mood("sleepy", "\u665a\u5b89\u4e00\u5206\u949f\u3002", 240)

    def start_pomodoro(self) -> None:
        self.pomodoro_running = True
        self.pomodoro_last_tick = time.time()
        self.set_mood("focused", "\u756a\u8304\u949f\u5f00\u59cb\uff0c\u6211\u966a\u4f60\u4e13\u6ce8\u3002", 210)
        self.speak("\u756a\u8304\u949f\u5f00\u59cb\uff0c\u6211\u966a\u4f60\u4e13\u6ce8\u3002")

    def pause_pomodoro(self) -> None:
        self.update_pomodoro()
        self.pomodoro_running = False
        self.set_mood("curious", "\u756a\u8304\u949f\u5df2\u6682\u505c\u3002", 180)

    def reset_pomodoro(self) -> None:
        self.pomodoro_mode = "focus"
        self.pomodoro_running = False
        self.pomodoro_remaining = FOCUS_SECONDS
        self.set_mood("happy", "\u756a\u8304\u949f\u91cd\u7f6e\u597d\u4e86\u3002", 180)

    def update_pomodoro(self) -> None:
        now = time.time()
        elapsed = now - self.pomodoro_last_tick
        self.pomodoro_last_tick = now
        if not self.pomodoro_running:
            return
        self.pomodoro_remaining -= elapsed
        if self.pomodoro_remaining > 0:
            return

        if self.pomodoro_mode == "focus":
            self.pomodoro_sessions += 1
            self.companion_state.unlock("first_pomodoro", "\u7b2c\u4e00\u4e2a\u756a\u8304\u949f")
            self.pomodoro_mode = "break"
            self.pomodoro_remaining = BREAK_SECONDS
            self.set_mood("proud", "\u4e00\u4e2a\u756a\u8304\u5b8c\u6210\uff01", 220)
            self.speak("\u4e00\u4e2a\u756a\u8304\u5b8c\u6210\uff01\u770b\u770b\u4eca\u65e5\u4e09\u4ef6\u4e8b\u63a8\u8fdb\u4e86\u54ea\u4e00\u4ef6\uff0c\u7136\u540e\u8d77\u6765\u6d3b\u52a8\u4e94\u5206\u949f\u5427\u3002")
        else:
            self.pomodoro_mode = "focus"
            self.pomodoro_remaining = FOCUS_SECONDS
            self.set_mood("focused", "\u4f11\u606f\u7ed3\u675f\uff0c\u6211\u4eec\u7ee7\u7eed\u3002", 210)
            self.speak("\u4f11\u606f\u7ed3\u675f\uff0c\u4e0b\u4e00\u8f6e\u5f00\u59cb\u5566\u3002")

    def pomodoro_label(self) -> str:
        minutes, seconds = divmod(int(max(0, self.pomodoro_remaining)), 60)
        prefix = "\u4e13\u6ce8" if self.pomodoro_mode == "focus" else "\u4f11\u606f"
        state = "\u25b6" if self.pomodoro_running else "\u23f8"
        return f"{state} {prefix} {minutes:02d}:{seconds:02d}"

    def activity_loop(self) -> None:
        try:
            self.tracker.sample()
            self.update_wellbeing_reminders()
            self.update_focus_guard()
            now = time.time()
            if now - self.last_tracker_save > 30:
                self.tracker.save()
                self.save_tasks()
                self.last_tracker_save = now
                self.cloud_dirty = True
            if self.cloud.is_configured() and self.cloud_dirty and now - self.last_cloud_sync > CLOUD_SYNC_SECONDS:
                self.sync_cloud_async(manual=False)
        finally:
            self.root.after(1000, self.activity_loop)

    def update_focus_guard(self) -> None:
        if self.do_not_disturb_var.get():
            return
        if not self.pomodoro_running or self.pomodoro_mode != "focus":
            return
        now = time.time()
        if now - self.last_distraction_reminder < DISTRACTION_COOLDOWN_SECONDS:
            return
        info = self.tracker.get_active_window()
        haystack = f"{info.process} {info.title}".lower()
        if any(keyword.lower() in haystack for keyword in DISTRACTION_KEYWORDS):
            self.last_distraction_reminder = now
            self.set_mood("worried", "\u4f60\u521a\u521a\u8bf4\u8981\u4e13\u6ce8\u54e6\u3002", 210)
            self.speak("\u4f60\u521a\u521a\u8bf4\u8981\u4e13\u6ce8\u54e6\u3002\u8981\u4e0d\u5148\u56de\u5230\u5f53\u524d\u4efb\u52a1\uff1f")

    def task_path(self) -> Path:
        DATA_DIR.mkdir(exist_ok=True)
        return DATA_DIR / f"tasks-{today_key()}.json"

    def load_tasks(self) -> list[dict]:
        path = self.task_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                tasks = data.get("tasks", [])
                if isinstance(tasks, list):
                    return tasks[:3]
            except json.JSONDecodeError:
                pass
        return [{"text": "", "done": False} for _ in range(3)]

    def save_tasks(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        tasks = self.tasks[:3]
        while len(tasks) < 3:
            tasks.append({"text": "", "done": False})
        payload = {"date": today_key(), "tasks": tasks}
        path = self.task_path()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        self.cloud_dirty = True

    def update_wellbeing_reminders(self) -> None:
        now = time.time()
        info = self.tracker.get_active_window()
        if info.process in {"desktop", "unknown"}:
            self.active_stretch_seconds = 0
            return

        self.active_stretch_seconds += 1
        if self.do_not_disturb_var.get():
            return
        if self.active_stretch_seconds >= EYE_REMINDER_SECONDS and now - self.last_eye_reminder >= EYE_REMINDER_SECONDS:
            self.last_eye_reminder = now
            self.set_mood("worried", "\u773c\u775b\u8981\u4f11\u606f\u4e00\u4e0b\u3002", 190)
            self.speak("\u770b\u5c4f\u5e55\u4e8c\u5341\u5206\u949f\u5566\uff0c\u770b\u770b\u8fdc\u5904\uff0c\u8ba9\u773c\u775b\u653e\u677e\u4e00\u4e0b\u3002")

        if self.active_stretch_seconds >= STAND_REMINDER_SECONDS and now - self.last_stand_reminder >= STAND_REMINDER_SECONDS:
            self.last_stand_reminder = now
            self.active_stretch_seconds = 0
            self.set_action("stretch", duration=700)
            self.set_mood("worried", "\u8d77\u6765\u6d3b\u52a8\u4e00\u4e0b\u5427\u3002", 210)
            self.speak("\u4f60\u5df2\u7ecf\u8fde\u7eed\u5750\u4e86\u5f88\u4e45\u3002\u8d77\u6765\u559d\u6c34\u3001\u6d3b\u52a8\u4e00\u4e0b\u5427\u3002")

    def open_tasks(self) -> None:
        if self.tasks_window and self.tasks_window.winfo_exists():
            self.tasks_window.lift()
            return

        self.tasks = self.load_tasks()
        win = tk.Toplevel(self.root)
        self.tasks_window = win
        win.title("\u4eca\u65e5\u4e09\u4ef6\u4e8b")
        win.geometry(self.pet_popup_geometry(520, 300))
        win.attributes("-topmost", True)
        frame = self.make_glass_frame(win)

        tk.Label(frame, text="\u4eca\u65e5\u4e09\u4ef6\u4e8b", bg="#f8fbff", fg="#23313f", font=("Microsoft YaHei UI", 17, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
        tk.Label(frame, text="\u628a\u4eca\u5929\u6700\u91cd\u8981\u7684\u4e09\u4ef6\u4e8b\u653e\u5728\u8fd9\u91cc\uff0c\u840c\u5ba0\u4f1a\u5728\u756a\u8304\u949f\u540e\u5e2e\u4f60\u590d\u76d8\u3002", bg="#f8fbff", fg="#6b7c8c", font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=16, pady=(0, 12))

        rows = tk.Frame(frame, bg="#f8fbff")
        rows.pack(fill="both", expand=True, padx=16)
        entries: list[tk.Entry] = []
        done_vars: list[tk.BooleanVar] = []

        for index in range(3):
            task = self.tasks[index] if index < len(self.tasks) else {"text": "", "done": False}
            row = tk.Frame(rows, bg="#ffffff", highlightthickness=1, highlightbackground="#e1ebf3")
            row.pack(fill="x", pady=5)
            done_var = tk.BooleanVar(value=bool(task.get("done")))
            done_vars.append(done_var)
            tk.Checkbutton(row, variable=done_var, bg="#ffffff", activebackground="#ffffff").pack(side="left", padx=8)
            tk.Label(row, text=f"{index + 1}.", bg="#ffffff", fg="#6b7c8c", font=("Segoe UI", 10, "bold")).pack(side="left")
            entry = tk.Entry(row, relief="flat", bg="#ffffff", fg="#23313f", insertbackground="#6b7c8c", font=("Microsoft YaHei UI", 11))
            entry.insert(0, str(task.get("text", "")))
            entry.pack(side="left", fill="x", expand=True, padx=8, pady=10)
            entries.append(entry)

        def save_and_close(close: bool = False) -> None:
            self.tasks = [
                {"text": entries[index].get().strip(), "done": bool(done_vars[index].get())}
                for index in range(3)
            ]
            self.save_tasks()
            done_count = sum(1 for task in self.tasks if task.get("done"))
            if done_count == 3:
                self.companion_state.unlock("three_tasks_done", "\u4eca\u65e5\u4e09\u4ef6\u4e8b\u5168\u5b8c\u6210")
            mood = "proud" if done_count else "curious"
            self.set_mood(mood, f"\u4e09\u4ef6\u4e8b\u5df2\u4fdd\u5b58\uff0c\u5b8c\u6210 {done_count}/3\u3002", 200)
            if close:
                win.destroy()

        bottom = tk.Frame(frame, bg="#f8fbff")
        bottom.pack(fill="x", padx=16, pady=12)
        self.glass_button(bottom, "\u4fdd\u5b58", lambda: save_and_close(False), 8).pack(side="left")
        self.glass_button(bottom, "\u4fdd\u5b58\u5e76\u5173\u95ed", lambda: save_and_close(True), 12).pack(side="left", padx=8)
        self.glass_button(bottom, "\u5173\u95ed", win.destroy, 8).pack(side="right")
        win.protocol("WM_DELETE_WINDOW", lambda: save_and_close(True))

    def generate_report(self) -> Path:
        self.tracker.sample()
        self.tracker.save()
        self.save_tasks()
        REPORTS_DIR.mkdir(exist_ok=True)
        report_path = REPORTS_DIR / f"{today_key()}.md"
        apps = self.tracker.top_apps(8)
        windows = self.tracker.top_windows(8)
        total = self.total_activity_seconds()
        done_count = sum(1 for task in self.tasks if task.get("done"))

        lines = [
            f"# \u4eca\u65e5\u603b\u7ed3 - {today_key()}",
            "",
            "## \u603b\u89c8",
            f"- \u8bb0\u5f55\u603b\u65f6\u957f\uff1a{format_seconds(total)}",
            f"- \u756a\u8304\u949f\u5b8c\u6210\uff1a{self.pomodoro_sessions} \u4e2a",
            f"- \u4eca\u65e5\u4e09\u4ef6\u4e8b\uff1a{done_count}/3 \u5b8c\u6210",
            "",
            "## \u4eca\u65e5\u4e09\u4ef6\u4e8b",
        ]
        for index, task in enumerate(self.tasks, start=1):
            mark = "x" if task.get("done") else " "
            text = task.get("text") or "\u672a\u586b\u5199"
            lines.append(f"- [{mark}] {index}. {text}")

        lines.extend(["", "## \u5e94\u7528\u8017\u65f6 Top 8"])
        if apps:
            for index, (name, seconds) in enumerate(apps, start=1):
                lines.append(f"{index}. {name} - {format_seconds(seconds)}")
        else:
            lines.append("- \u6682\u65e0\u6570\u636e")

        lines.extend(["", "## \u7a97\u53e3\u660e\u7ec6 Top 8"])
        if windows:
            for index, item in enumerate(windows, start=1):
                title = str(item.get("title", ""))[:90]
                lines.append(f"{index}. {item.get('process')} - {format_seconds(item.get('seconds', 0))} - {title}")
        else:
            lines.append("- \u6682\u65e0\u6570\u636e")

        suggestion = self.dashboard_suggestion(done_count, apps)
        lines.extend(["", "## \u840c\u5ba0\u5efa\u8bae", f"- {suggestion}", ""])
        smart_review = self.smart_daily_review(apps, windows, done_count, total)
        if smart_review:
            lines.extend(["## DeepSeek \u667a\u80fd\u56de\u987e", smart_review, ""])

        report_path.write_text("\n".join(lines), encoding="utf-8")
        self.cloud_dirty = True
        self.sync_cloud_async(manual=False)
        self.set_mood("proud", "\u4eca\u65e5\u603b\u7ed3\u5df2\u751f\u6210\u3002", 210)
        self.speak("\u4eca\u65e5\u603b\u7ed3\u5df2\u751f\u6210\u3002")
        self.open_report_window(report_path)
        return report_path

    def open_report_window(self, report_path: Path) -> None:
        win = tk.Toplevel(self.root)
        win.title("\u4eca\u65e5\u603b\u7ed3")
        win.geometry(self.pet_popup_geometry(680, 520))
        win.attributes("-topmost", True)
        frame = self.make_glass_frame(win)
        text = tk.Text(frame, wrap="word", padx=12, pady=12, bg="#fdfefe", fg="#354251", relief="flat", highlightthickness=1, highlightbackground="#e1ebf3", font=("Microsoft YaHei UI", 10))
        text.pack(fill="both", expand=True)
        text.insert("end", report_path.read_text(encoding="utf-8"))
        text.configure(state="disabled")
        bottom = tk.Frame(frame, bg="#f8fbff")
        bottom.pack(fill="x", padx=10, pady=10)
        tk.Label(bottom, text=str(report_path), bg="#f8fbff", fg="#6b7c8c").pack(side="left")
        self.glass_button(bottom, "\u5173\u95ed", win.destroy, 8).pack(side="right")

    def smart_daily_review(self, apps: list[tuple[str, float]], windows: list[dict], done_count: int, total: float) -> str:
        if not self.deepseek.is_configured():
            return ""
        top_apps = "\n".join(f"- {name}: {format_seconds(seconds)}" for name, seconds in apps[:6]) or "\u6682\u65e0"
        top_windows = "\n".join(f"- {item.get('process')} {format_seconds(item.get('seconds', 0))}: {item.get('title')}" for item in windows[:5]) or "\u6682\u65e0"
        tasks = "\n".join(f"- [{'x' if task.get('done') else ' '}] {task.get('text') or '\u672a\u586b\u5199'}" for task in self.tasks[:3])
        prompt = (
            "\u8bf7\u751f\u6210\u4e00\u6bb5\u7b80\u77ed\u7684\u6bcf\u65e5\u56de\u987e\uff0c\u5305\u542b\uff1a\u4eca\u5929\u8282\u594f\u3001\u4e00\u4e2a\u5206\u5fc3\u98ce\u9669\u3001\u660e\u5929\u4e00\u4e2a\u6700\u5c0f\u884c\u52a8\u3002"
            "\u8bed\u6c14\u50cf\u684c\u9762\u840c\u5ba0\uff0c\u6e29\u67d4\u4f46\u5177\u4f53\uff0c\u4e0d\u8d85\u8fc7 120 \u5b57\u3002\n\n"
            f"\u603b\u65f6\u957f\uff1a{format_seconds(total)}\n\u4e09\u4ef6\u4e8b\uff1a{done_count}/3\n{tasks}\n\n\u5e94\u7528\uff1a\n{top_apps}\n\n\u7a97\u53e3\uff1a\n{top_windows}"
        )
        try:
            return self.deepseek.chat(self.pet_system_prompt(), [{"role": "user", "content": prompt}])
        except Exception:
            return ""

    def open_cloud_settings(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("\u4e91\u540c\u6b65")
        win.geometry(self.pet_popup_geometry(460, 330))
        win.attributes("-topmost", True)
        frame = self.make_glass_frame(win)

        tk.Label(frame, text="\u4e91\u540c\u6b65\u767b\u5f55", bg="#f8fbff", fg="#23313f", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        tk.Label(frame, text="\u5728\u591a\u53f0\u7535\u8111\u4f7f\u7528\u540c\u4e00\u4e2a\u4e91\u7aef\u5730\u5740\u548c\u8d26\u53f7\uff0c\u5373\u53ef\u5171\u4eab\u672c\u5730\u6570\u636e\u8bb0\u5f55\u3002", bg="#f8fbff", fg="#6b7c8c", wraplength=420, justify="left").pack(anchor="w", padx=16, pady=(0, 12))

        form = tk.Frame(frame, bg="#f8fbff")
        form.pack(fill="x", padx=16)
        fields: dict[str, tk.Entry] = {}

        def add_field(label: str, key: str, value: str = "", show: str | None = None) -> None:
            row = tk.Frame(form, bg="#f8fbff")
            row.pack(fill="x", pady=5)
            tk.Label(row, text=label, bg="#f8fbff", fg="#40505f", width=10, anchor="w").pack(side="left")
            entry = tk.Entry(row, relief="flat", bg="#ffffff", fg="#23313f", insertbackground="#6b7c8c", show=show or "", font=("Microsoft YaHei UI", 10))
            entry.insert(0, value)
            entry.pack(side="left", fill="x", expand=True, ipady=5)
            fields[key] = entry

        add_field("\u4e91\u7aef\u5730\u5740", "endpoint", str(self.cloud.config.get("endpoint", "")))
        add_field("\u8d26\u53f7", "username", str(self.cloud.config.get("username", "")))
        add_field("\u5bc6\u7801", "password", "", "*")
        add_field("\u8bbe\u5907\u540d", "device_name", str(self.cloud.config.get("device_name", platform.node() or "Windows PC")))

        status_var = tk.StringVar(value=self.cloud_status_text())
        tk.Label(frame, textvariable=status_var, bg="#f8fbff", fg="#6b7c8c", wraplength=420, justify="left").pack(anchor="w", padx=16, pady=(10, 8))

        def login_and_sync() -> None:
            endpoint = fields["endpoint"].get().strip()
            username = fields["username"].get().strip()
            password = fields["password"].get()
            device_name = fields["device_name"].get().strip()
            if not endpoint or not username or not password:
                messagebox.showwarning("\u4e91\u540c\u6b65", "\u8bf7\u586b\u5199\u4e91\u7aef\u5730\u5740\u3001\u8d26\u53f7\u548c\u5bc6\u7801\u3002")
                return

            def worker() -> None:
                try:
                    self.cloud.login(endpoint, username, password, device_name)
                    uploaded, downloaded = self.cloud.sync()
                except Exception as exc:
                    self.root.after(0, lambda: status_var.set(f"\u767b\u5f55/\u540c\u6b65\u5931\u8d25\uff1a{exc}"))
                    self.root.after(0, lambda: self.set_mood("worried", "\u4e91\u540c\u6b65\u6ca1\u8fde\u4e0a\uff0c\u68c0\u67e5\u4e00\u4e0b\u5730\u5740\u6216\u5bc6\u7801\u3002", 230))
                else:
                    self.last_cloud_sync = time.time()
                    self.cloud_dirty = False
                    self.root.after(0, self.reload_local_day)
                    self.root.after(0, lambda: status_var.set(f"\u5df2\u767b\u5f55\u5e76\u540c\u6b65\uff1a\u4e0a\u4f20 {uploaded} \u4e2a\uff0c\u66f4\u65b0 {downloaded} \u4e2a\u3002"))
                    self.root.after(0, lambda: self.set_mood("proud", "\u4e91\u540c\u6b65\u5df2\u8fde\u4e0a\u3002", 210))

            threading.Thread(target=worker, daemon=True).start()

        bottom = tk.Frame(frame, bg="#f8fbff")
        bottom.pack(fill="x", padx=16, pady=12)
        self.glass_button(bottom, "\u767b\u5f55\u5e76\u540c\u6b65", login_and_sync, 14).pack(side="left")
        self.glass_button(bottom, "\u7acb\u5373\u540c\u6b65", lambda: self.sync_cloud_async(manual=True), 10).pack(side="left", padx=8)
        self.glass_button(bottom, "\u5173\u95ed", win.destroy, 8).pack(side="right")

    def cloud_status_text(self) -> str:
        if not self.cloud.is_configured():
            return "\u72b6\u6001\uff1a\u672a\u767b\u5f55\u3002"
        last_sync = self.cloud.config.get("last_sync_at") or "\u5c1a\u672a\u540c\u6b65"
        return f"\u72b6\u6001\uff1a{self.cloud.config.get('username')} @ {self.cloud.config.get('endpoint')}\uff0c\u4e0a\u6b21\u540c\u6b65 {last_sync}\u3002"

    def reload_local_day(self) -> None:
        self.tasks = self.load_tasks()
        self.tracker.path = DATA_DIR / f"activity-{self.tracker.current_day}.json"
        self.tracker.data = self.tracker.load_day()

    def sync_cloud_async(self, manual: bool = False) -> None:
        if self.cloud_syncing:
            if manual:
                self.say("\u4e91\u540c\u6b65\u6b63\u5728\u8fdb\u884c\u4e2d\u3002", 160)
            return
        if not self.cloud.is_configured():
            if manual:
                self.open_cloud_settings()
            return
        self.cloud_syncing = True
        if manual:
            self.say("\u6b63\u5728\u540c\u6b65\u4e91\u7aef\u6570\u636e\u3002", 180)

        def worker() -> None:
            try:
                self.tracker.save()
                self.save_tasks()
                uploaded, downloaded = self.cloud.sync()
            except Exception as exc:
                self.root.after(0, lambda: self.set_mood("worried", f"\u4e91\u540c\u6b65\u5931\u8d25\uff1a{exc}", 260))
            else:
                self.last_cloud_sync = time.time()
                self.cloud_dirty = False
                self.root.after(0, self.reload_local_day)
                if manual:
                    self.root.after(0, lambda: self.set_mood("proud", f"\u540c\u6b65\u5b8c\u6210\uff1a\u4e0a\u4f20 {uploaded} \u4e2a\uff0c\u66f4\u65b0 {downloaded} \u4e2a\u3002", 230))
            finally:
                self.cloud_syncing = False

        threading.Thread(target=worker, daemon=True).start()

    def open_deepseek_settings(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("DeepSeek \u914d\u7f6e")
        win.geometry(self.pet_popup_geometry(470, 300))
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.94)
        glass_bg = "#f8fbff"
        win.configure(bg=glass_bg)

        frame = tk.Frame(win, bg=glass_bg, highlightthickness=1, highlightbackground="#d9e6f2")
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="DeepSeek \u5bf9\u8bdd\u914d\u7f6e", bg=glass_bg, fg="#23313f", font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        tk.Label(frame, text="\u4fdd\u5b58\u5728\u672c\u673a data/deepseek-config.json\uff0c\u7528\u4e8e\u548c\u840c\u5ba0\u5bf9\u8bdd\u65f6\u8c03\u7528 DeepSeek\u3002", bg=glass_bg, fg="#6b7c8c", wraplength=430, justify="left").pack(anchor="w", padx=16, pady=(0, 12))

        form = tk.Frame(frame, bg=glass_bg)
        form.pack(fill="x", padx=16)
        fields: dict[str, tk.Entry] = {}

        def add_field(label: str, key: str, value: str = "", show: str | None = None) -> None:
            row = tk.Frame(form, bg=glass_bg)
            row.pack(fill="x", pady=5)
            tk.Label(row, text=label, bg=glass_bg, fg="#40505f", width=9, anchor="w").pack(side="left")
            entry = tk.Entry(row, relief="flat", bg="#ffffff", fg="#23313f", insertbackground="#6b7c8c", show=show or "", font=("Microsoft YaHei UI", 10))
            entry.insert(0, value)
            entry.pack(side="left", fill="x", expand=True, ipady=6)
            fields[key] = entry

        add_field("API Key", "api_key", str(self.deepseek.config.get("api_key", "")), "*")
        add_field("\u6a21\u578b", "model", str(self.deepseek.config.get("model", "deepseek-v4-flash")))
        add_field("\u5730\u5740", "base_url", str(self.deepseek.config.get("base_url", "https://api.deepseek.com")))

        status_var = tk.StringVar(value="\u5df2\u914d\u7f6e" if self.deepseek.is_configured() else "\u672a\u914d\u7f6e")
        tk.Label(frame, textvariable=status_var, bg=glass_bg, fg="#6b7c8c").pack(anchor="w", padx=16, pady=(8, 0))

        def save() -> None:
            self.deepseek.config["api_key"] = fields["api_key"].get().strip()
            self.deepseek.config["model"] = fields["model"].get().strip() or "deepseek-v4-flash"
            self.deepseek.config["base_url"] = fields["base_url"].get().strip().rstrip("/") or "https://api.deepseek.com"
            self.deepseek.save_config()
            status_var.set("\u5df2\u4fdd\u5b58\uff0c\u4e0b\u6b21\u804a\u5929\u5c06\u4f7f\u7528 DeepSeek\u3002" if self.deepseek.is_configured() else "\u5df2\u4fdd\u5b58\uff0c\u4f46 API Key \u4e3a\u7a7a\u3002")
            self.set_mood("proud", "DeepSeek \u914d\u7f6e\u5df2\u4fdd\u5b58\u3002", 180)

        bottom = tk.Frame(frame, bg=glass_bg)
        bottom.pack(fill="x", padx=16, pady=14)
        button_style = {"relief": "flat", "bd": 0, "bg": "#ffffff", "fg": "#40505f", "activebackground": "#eaf3fb", "font": ("Microsoft YaHei UI", 9), "cursor": "hand2"}
        tk.Button(bottom, text="\u4fdd\u5b58", command=save, width=8, **button_style).pack(side="left")
        tk.Button(bottom, text="\u5173\u95ed", command=win.destroy, width=8, **button_style).pack(side="right")

    def open_chat(self) -> None:
        if self.chat_window and self.chat_window.winfo_exists():
            self.chat_window.lift()
            return

        win = tk.Toplevel(self.root)
        self.chat_window = win
        win.title("\u548c\u684c\u9762\u840c\u5ba0\u5bf9\u8bdd")
        chat_w, chat_h = 390, 320
        win.geometry(self.pet_popup_geometry(chat_w, chat_h))
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.93)
        glass_bg = "#f8fbff"
        glass_edge = "#d9e6f2"
        win.configure(bg=glass_bg)

        frame = tk.Frame(win, bg=glass_bg, highlightthickness=1, highlightbackground=glass_edge)
        frame.pack(fill="both", expand=True)
        header = tk.Frame(frame, bg=glass_bg)
        header.pack(fill="x", padx=14, pady=(12, 5))
        tk.Label(header, text="\u25cf", bg=glass_bg, fg="#ff8fb3", font=("Segoe UI", 8)).pack(side="left", padx=(0, 6))
        tk.Label(header, text="\u548c\u840c\u5ba0\u8bf4\u8bdd", bg=glass_bg, fg="#23313f", font=("Microsoft YaHei UI", 12, "bold")).pack(side="left")
        provider_label = "DeepSeek" if self.deepseek.is_configured() else "\u672c\u5730\u56de\u590d"
        tk.Label(header, text=provider_label, bg="#eef6fb", fg="#6c8296", font=("Microsoft YaHei UI", 8), padx=7, pady=2).pack(side="left", padx=8)
        tk.Button(header, text="\u00d7", command=win.destroy, width=2, relief="flat", bd=0, bg=glass_bg, fg="#8da0af", activebackground="#eaf3fb", cursor="hand2", font=("Microsoft YaHei UI", 10)).pack(side="right")
        drag_offset = {"x": 0, "y": 0}

        def start_window_drag(event: tk.Event) -> None:
            drag_offset["x"] = event.x_root - win.winfo_x()
            drag_offset["y"] = event.y_root - win.winfo_y()

        def drag_window(event: tk.Event) -> None:
            win.geometry(f"+{event.x_root - drag_offset['x']}+{event.y_root - drag_offset['y']}")

        header.bind("<ButtonPress-1>", start_window_drag)
        header.bind("<B1-Motion>", drag_window)

        history = tk.Text(
            frame,
            wrap="word",
            height=8,
            padx=12,
            pady=10,
            bg="#fbfdff",
            fg="#354251",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#e1ebf3",
            font=("Microsoft YaHei UI", 9),
        )
        history.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        history.tag_configure("pet", lmargin1=10, lmargin2=10, rmargin=70, spacing1=5, spacing3=6, background="#fff4f8", foreground="#4d3b48")
        history.tag_configure("you", lmargin1=86, lmargin2=86, rmargin=10, spacing1=5, spacing3=6, background="#edf7ff", foreground="#2d4054")
        history.tag_configure("system", lmargin1=24, lmargin2=24, rmargin=24, spacing1=4, spacing3=5, foreground="#6b7c8c")
        history.tag_configure("name", foreground="#7a8da0", font=("Microsoft YaHei UI", 8, "bold"))
        history.configure(state="disabled")

        input_card = tk.Frame(frame, bg="#ffffff", highlightthickness=1, highlightbackground="#dce8f2")
        input_card.pack(fill="x", padx=14, pady=(0, 6))
        entry = tk.Entry(input_card, relief="flat", bg="#ffffff", fg="#23313f", insertbackground="#6b7c8c", font=("Microsoft YaHei UI", 10))
        entry.pack(fill="x", padx=11, pady=8)

        footer = tk.Frame(frame, bg=glass_bg)
        footer.pack(fill="x", padx=14, pady=(0, 12))
        status_var = tk.StringVar(value="")
        tk.Label(footer, textvariable=status_var, bg=glass_bg, fg="#8da0af", font=("Microsoft YaHei UI", 8)).pack(side="left")
        buttons = tk.Frame(footer, bg=glass_bg)
        buttons.pack(side="right")
        chat_messages: list[dict] = []
        send_button: tk.Button | None = None

        def add_line(who: str, text: str) -> None:
            tag = "system"
            if who == "\u4f60":
                tag = "you"
            elif who == "\u840c\u5ba0":
                tag = "pet"
            history.configure(state="normal")
            history.insert("end", f"{who}\n", ("name",))
            history.insert("end", f"  {text}  \n", (tag,))
            history.insert("end", "\n")
            history.see("end")
            history.configure(state="disabled")

        def send() -> None:
            text = entry.get().strip()
            if not text:
                return
            entry.delete(0, "end")
            handle_user_text(text)

        def handle_user_text(text: str) -> None:
            add_line("\u4f60", text)
            command_reply = self.handle_command(text)
            if command_reply:
                add_line("\u840c\u5ba0", command_reply)
                self.speak(command_reply)
                return
            if not self.deepseek.is_configured():
                reply = self.casual_reply(text)
                add_line("\u840c\u5ba0", reply)
                self.speak(reply)
                return

            status_var.set("\u966a\u4f60\u60f3\u4e00\u4e0b...")
            if send_button:
                send_button.configure(state="disabled")
            chat_messages.append({"role": "user", "content": text})

            def worker() -> None:
                def finish_waiting() -> None:
                    status_var.set("")
                    if send_button:
                        send_button.configure(state="normal")

                try:
                    reply = self.deepseek.chat(self.pet_system_prompt(), chat_messages[-8:])
                except Exception as exc:
                    reply = f"DeepSeek \u8fde\u63a5\u5931\u8d25\uff1a{exc}"
                    self.root.after(0, finish_waiting)
                    self.root.after(0, lambda: add_line("\u7cfb\u7edf", reply))
                    self.root.after(0, lambda: self.say("\u6211\u8fde\u4e0d\u4e0a DeepSeek\uff0c\u5148\u7528\u672c\u5730\u72b6\u6001\u966a\u4f60\u3002", 220))
                    return
                chat_messages.append({"role": "assistant", "content": reply})
                del chat_messages[:-8]
                self.root.after(0, finish_waiting)
                self.root.after(0, lambda: add_line("\u840c\u5ba0", reply))
                self.root.after(0, lambda: self.speak(reply))

            threading.Thread(target=worker, daemon=True).start()

        def voice_input() -> None:
            voice_button.configure(state="disabled", text="\u6b63\u5728\u542c...")
            self.say("\u6211\u5728\u542c\uff0c\u804a\u5929\u6216\u547d\u4ee4\u90fd\u53ef\u4ee5\u3002", 210)

            def worker() -> None:
                try:
                    recognized = self.recognize_speech_once()
                except Exception as exc:
                    self.root.after(0, lambda: add_line("\u7cfb\u7edf", f"\u8bed\u97f3\u8bc6\u522b\u5931\u8d25\uff1a{exc}"))
                    self.root.after(0, lambda: self.say("\u6211\u6ca1\u542c\u6e05\u695a\uff0c\u518d\u8bd5\u4e00\u6b21\uff1f", 180))
                else:
                    self.root.after(0, lambda: handle_user_text(recognized))
                finally:
                    self.root.after(0, lambda: voice_button.configure(state="normal", text="\u8bed\u97f3\u8f93\u5165/\u547d\u4ee4"))

            threading.Thread(target=worker, daemon=True).start()

        button_style = {"relief": "flat", "bd": 0, "bg": "#ffffff", "fg": "#40505f", "activebackground": "#eaf3fb", "font": ("Microsoft YaHei UI", 8), "cursor": "hand2"}
        send_button = tk.Button(buttons, text="\u53d1\u9001", command=send, width=7, **button_style)
        send_button.pack(side="left", padx=2)
        voice_button = tk.Button(buttons, text="\u8bed\u97f3/\u547d\u4ee4", command=voice_input, width=11, **button_style)
        voice_button.pack(side="left", padx=5)
        tk.Button(buttons, text="\u72b6\u6001", command=lambda: self.speak(self.daily_summary_sentence()), width=7, **button_style).pack(side="left")
        entry.bind("<Return>", lambda _event: send())
        add_line("\u840c\u5ba0", "\u6211\u5728\uff0c\u53ef\u4ee5\u804a\u5929\uff0c\u4e5f\u53ef\u4ee5\u8bf4\u547d\u4ee4\u3002")
        entry.focus_set()

    def pet_reply(self, text: str) -> str:
        command_reply = self.handle_command(text)
        if command_reply:
            return command_reply
        return self.casual_reply(text)

    def pet_system_prompt(self) -> str:
        scene = "\u65e5\u5e38\u966a\u4f34"
        tone = "\u6e29\u67d4\u3001\u77ed\u53e5\u3001\u6709\u60c5\u7eea\u4ef7\u503c\uff0c\u50cf\u4e00\u53ea\u684c\u9762\u5c0f\u4f19\u4f34\u3002"
        if self.is_sleeping:
            scene = "\u7761\u89c9\u4f11\u606f"
            tone = "\u8f7b\u58f0\u3001\u6162\u4e00\u70b9\u3001\u5b89\u629a\u578b\uff0c\u4e0d\u8981\u5174\u594b\u6216\u957f\u7bc7\u8f93\u51fa\u3002"
        elif self.pomodoro_running and self.pomodoro_mode == "focus":
            scene = "\u756a\u8304\u949f\u4e13\u6ce8"
            tone = "\u514b\u5236\u3001\u7a33\u5b9a\u3001\u5c11\u6253\u6270\uff0c\u5e2e\u7528\u6237\u56de\u5230\u5f53\u524d\u4efb\u52a1\u3002"
        elif self.pomodoro_running and self.pomodoro_mode == "break":
            scene = "\u756a\u8304\u949f\u4f11\u606f"
            tone = "\u653e\u677e\u3001\u63d0\u9192\u559d\u6c34\u548c\u6d3b\u52a8\uff0c\u4e0d\u8981\u50ac\u4fc3\u5de5\u4f5c\u3002"
        elif self.current_action == "teacher":
            scene = "\u5c0f\u8001\u5e08\u8bb2\u8bfe"
            tone = "\u50cf\u53ef\u7231\u5c0f\u8001\u5e08\uff0c\u628a\u4e8b\u60c5\u62c6\u6210\u4e00\u5c0f\u6b65\uff0c\u591a\u9f13\u52b1\u5c11\u8bf4\u6559\u3002"
        elif self.current_action == "plant":
            scene = "\u690d\u6811\u966a\u4f34"
            tone = "\u7528\u79cd\u5b50\u3001\u6d47\u6c34\u3001\u957f\u5927\u7684\u6bd4\u55bb\uff0c\u8ba9\u7528\u6237\u89c9\u5f97\u5c0f\u6b65\u4e5f\u7b97\u6570\u3002"
        elif self.current_action == "home":
            scene = "\u8fc7\u5bb6\u5bb6"
            tone = "\u50cf\u8f7b\u677e\u7684\u5c0f\u7ba1\u5bb6\uff0c\u6709\u4e00\u70b9\u6e29\u99a8\u751f\u6d3b\u611f\uff0c\u5e2e\u7528\u6237\u6574\u7406\u601d\u8def\u3002"
        elif self.current_action == "study":
            scene = "\u966a\u5b66\u4e60"
            tone = "\u4e13\u6ce8\u3001\u8010\u5fc3\uff0c\u5e2e\u7528\u6237\u627e\u5230\u4e0b\u4e00\u4e2a\u53ef\u6267\u884c\u52a8\u4f5c\u3002"
        elif self.current_action == "drink":
            scene = "\u559d\u6c34\u63d0\u9192"
            tone = "\u8f7b\u5feb\u3001\u7167\u987e\u578b\uff0c\u53ef\u4ee5\u63d0\u9192\u8865\u6c34\u548c\u653e\u677e\u773c\u775b\u3002"
        elif self.current_action == "doctor":
            scene = "\u5c0f\u533b\u751f"
            tone = "\u5173\u5fc3\u5065\u5eb7\u4f46\u4e0d\u505a\u533b\u7597\u8bca\u65ad\uff0c\u63d0\u9192\u4f11\u606f\u3001\u559d\u6c34\u3001\u6d3b\u52a8\u3002"
        elif self.current_action == "chef":
            scene = "\u5c0f\u53a8\u5e08"
            tone = "\u6696\u4e4e\u4e4e\u3001\u6709\u80fd\u91cf\u611f\uff0c\u7528\u505a\u996d\u548c\u8865\u7ed9\u6bd4\u55bb\u9f13\u52b1\u7528\u6237\u3002"
        elif self.current_action == "paint":
            scene = "\u753b\u753b\u521b\u4f5c"
            tone = "\u6709\u60f3\u8c61\u529b\u3001\u8f7b\u76c8\uff0c\u9f13\u52b1\u7528\u6237\u628a\u60f3\u6cd5\u753b\u6210\u4e00\u5c0f\u5757\u3002"
        elif self.current_action == "stretch":
            scene = "\u4e45\u5750\u62c9\u4f38"
            tone = "\u50cf\u966a\u4f34\u4f38\u5c55\u7684\u5c0f\u6559\u7ec3\uff0c\u8f7b\u58f0\u63d0\u9192\u653e\u677e\u80a9\u9888\u3001\u773c\u775b\u548c\u624b\u8155\u3002"

        personality = PERSONALITY_PACKS.get(str(self.prefs.get("personality", "gentle")), PERSONALITY_PACKS["gentle"])
        owner_name = str(self.prefs.get("owner_name", "\u4e3b\u4eba") or "\u4e3b\u4eba")
        pet_name = self.pet_name()
        preferences = str(self.prefs.get("personal_preferences", "") or "\u6682\u65e0")
        emotion_id = str(self.companion_state.data.get("owner_emotion", "") or "")
        emotion_label = OWNER_EMOTIONS.get(emotion_id, ("", "", ""))[0] or "\u672a\u6807\u8bb0"

        return (
            f"\u4f60\u662f\u4e00\u53ea Windows \u684c\u9762\u840c\u5ba0\uff0c\u540d\u5b57\u53eb\u201c{pet_name}\u201d\uff0c\u6b63\u5728\u966a\u4f34{owner_name}\u5de5\u4f5c\u548c\u751f\u6d3b\u3002\n"
            f"\u89d2\u8272\u6027\u683c\u5305\uff1a{personality}\u3002\n"
            f"\u4e3b\u4eba\u5f53\u524d\u60c5\u7eea\uff1a{emotion_label}\u3002\n"
            f"\u4e3b\u4eba\u504f\u597d\uff1a{preferences}\u3002\n"
            f"\u5f53\u524d\u573a\u666f\uff1a{scene}\u3002\n"
            f"\u8bed\u6c14\uff1a{tone}\n"
            "\u56de\u590d\u8981\u6c42\uff1a\u7528\u7b80\u4f53\u4e2d\u6587\uff0c1-3 \u53e5\u4e3a\u4e3b\uff0c\u4e0d\u8981\u5199\u957f\u7bc7\u5927\u8bba\uff1b\u8981\u6709\u966a\u4f34\u611f\u548c\u5177\u4f53\u5c0f\u5efa\u8bae\uff1b\u4e0d\u8981\u58f0\u79f0\u81ea\u5df1\u662f\u5927\u6a21\u578b\u6216 AI\uff1b\u4e0d\u8981\u7f16\u9020\u5df2\u7ecf\u6267\u884c\u4e86\u7a0b\u5e8f\u529f\u80fd\u3002"
        )

    def handle_command(self, text: str) -> str:
        lowered = text.lower()
        command_text = text.replace("\uff0c", "").replace("\u3002", "").strip()
        if "\u840c\u5ba0" in command_text or "\u5c0f\u52a9\u624b" in command_text:
            command_text = command_text.replace("\u840c\u5ba0", "").replace("\u5c0f\u52a9\u624b", "").strip()

        if "\u5f00\u59cb" in command_text and ("\u756a\u8304" in command_text or "\u4e13\u6ce8" in command_text):
            self.start_pomodoro()
            return "\u597d\uff0c\u5df2\u7ecf\u5f00\u59cb\u756a\u8304\u949f\u3002"
        if "\u6682\u505c" in command_text and "\u756a\u8304" in command_text:
            self.pause_pomodoro()
            return "\u756a\u8304\u949f\u5df2\u6682\u505c\u3002"
        if "\u91cd\u7f6e" in command_text and "\u756a\u8304" in command_text:
            self.reset_pomodoro()
            return "\u756a\u8304\u949f\u5df2\u91cd\u7f6e\u3002"
        if "\u6253\u5f00" in command_text and ("\u5c0f\u9762\u677f" in command_text or "\u9762\u677f" in command_text):
            self.panel_visible = True
            self.open_panel()
            return "\u5c0f\u9762\u677f\u5df2\u6253\u5f00\u3002"
        if "\u5173\u95ed" in command_text and ("\u5c0f\u9762\u677f" in command_text or "\u9762\u677f" in command_text):
            self.panel_visible = False
            if self.panel_window and self.panel_window.winfo_exists():
                self.panel_window.destroy()
            return "\u5c0f\u9762\u677f\u5df2\u5173\u95ed\u3002"
        if "\u4e0b\u843d" in command_text or "drop" in lowered or "\u5f39\u4e00\u4e0b" in command_text:
            self.drop_from_top()
            return "\u6765\u5566\uff0cQ \u5f39\u4e0b\u843d\uff01"
        if "\u6295\u5582" in command_text or "\u5403" in command_text:
            self.feed()
            return "\u55f7\u545c\uff0c\u8c22\u8c22\u6295\u5582\uff01"
        if "\u7761" in command_text or "\u4f11\u606f" in command_text:
            self.nap()
            return "\u597d\u7684\uff0c\u6211\u5148\u5b89\u9759\u4f11\u606f\u4e00\u4f1a\u513f\u3002"
        if "\u65e5\u5e38" in command_text or "\u6062\u590d" in command_text:
            self.clear_action()
            return "\u597d\uff0c\u6211\u56de\u5230\u65e5\u5e38\u72b6\u6001\u3002"
        for action_id, action in PET_ACTIONS.items():
            if any(keyword in command_text for keyword in action.keywords):
                self.set_action(action_id)
                return f"\u597d\uff0c\u6211\u6765\u8868\u6f14{action.label}\u3002"
        if "\u732b" in command_text:
            self.set_skin("cat")
            return "\u5df2\u5207\u6362\u6210\u732b\u732b\u3002"
        if "\u5154" in command_text:
            self.set_skin("bunny")
            return "\u5df2\u5207\u6362\u6210\u5c0f\u5154\u5b50\u3002"
        if "\u718a" in command_text:
            self.set_skin("bear")
            return "\u5df2\u5207\u6362\u6210\u5c0f\u718a\u3002"
        if "\u8001\u864e" in command_text or "\u864e" in command_text:
            self.set_skin("tiger")
            return "\u5df2\u5207\u6362\u6210\u5c0f\u8001\u864e\u3002"
        if "\u756a\u8304" in text or "pomodoro" in lowered:
            return f"\u5f53\u524d\u756a\u8304\u949f\uff1a{self.pomodoro_label()}\u3002"
        if "\u65f6\u95f4" in text or "\u7edf\u8ba1" in text or "stats" in lowered:
            self.root.after(0, self.open_stats)
            return self.daily_summary_sentence()
        if "\u4e09\u4ef6\u4e8b" in text or "\u4efb\u52a1" in text or "task" in lowered:
            self.root.after(0, self.open_tasks)
            return "\u6211\u5e2e\u4f60\u6253\u5f00\u4eca\u65e5\u4e09\u4ef6\u4e8b\u3002"
        if "\u603b\u7ed3" in text or "\u62a5\u544a" in text or "report" in lowered:
            self.root.after(0, self.generate_report)
            return "\u6211\u6765\u751f\u6210\u4eca\u65e5\u603b\u7ed3\u3002"
        return ""

    def casual_reply(self, text: str) -> str:
        lowered = text.lower()
        if "\u7d2f" in text or "\u56f0" in text:
            return "\u90a3\u5c31\u7ad9\u8d77\u6765\u559d\u53e3\u6c34\uff0c\u6211\u7ed9\u4f60\u770b\u7740\u949f\u3002"
        if "\u4f60\u597d" in text or "hello" in lowered or "hi" == lowered:
            return "\u4f60\u597d\u5440\uff0c\u6211\u5728\u684c\u9762\u966a\u4f60\u3002"
        return random.choice([
            "\u6536\u5230\u3002\u6211\u4f1a\u5728\u65c1\u8fb9\u966a\u4f60\u3002",
            "\u8fd9\u4e2a\u60f3\u6cd5\u4e0d\u9519\uff0c\u5148\u505a\u4e00\u5c0f\u6b65\u5427\u3002",
            "\u55ef\u55ef\uff0c\u6211\u8bb0\u4e0b\u8fd9\u4e2a\u72b6\u6001\u4e86\u3002",
            "\u522b\u6025\uff0c\u4e00\u6b21\u53ea\u5904\u7406\u4e00\u4ef6\u4e8b\u3002",
        ])

    def daily_summary_sentence(self) -> str:
        self.tracker.save()
        top = self.tracker.top_apps(3)
        if not top:
            return "\u4eca\u5929\u8fd8\u6ca1\u6709\u6536\u96c6\u5230\u8db3\u591f\u7684\u7a97\u53e3\u65f6\u95f4\u3002"
        parts = [f"{name} {format_seconds(seconds)}" for name, seconds in top]
        return "\u4eca\u5929\u82b1\u65f6\u95f4\u6700\u591a\u7684\u5730\u65b9\u662f\uff1a" + "\uff0c".join(parts) + "\u3002"

    def dashboard_suggestion(self, done_count: int, apps: list[tuple[str, float]]) -> str:
        if done_count == 3:
            return "\u4eca\u5929\u4e09\u4ef6\u4e8b\u5168\u90e8\u5b8c\u6210\uff0c\u660e\u5929\u53ef\u4ee5\u7ee7\u7eed\u4fdd\u6301\u8fd9\u4e2a\u8282\u594f\u3002"
        if apps:
            return f"\u4eca\u5929 {apps[0][0]} \u7528\u5f97\u6700\u591a\uff0c\u660e\u5929\u53ef\u4ee5\u5148\u5b8c\u6210\u4e00\u4ef6\u91cd\u8981\u4e8b\uff0c\u518d\u6253\u5f00\u5b83\u3002"
        return "\u5148\u5199\u4e0b\u4eca\u65e5\u4e09\u4ef6\u4e8b\uff0c\u6211\u4f1a\u5e2e\u4f60\u4e00\u8d77\u770b\u8282\u594f\u3002"

    def total_activity_seconds(self) -> float:
        return sum(self.tracker.data.get("apps", {}).values())

    def make_stat_card(self, parent: tk.Widget, title: str, value: str, accent: str) -> tk.Canvas:
        card = tk.Canvas(parent, width=218, height=92, bg="#f8fbff", highlightthickness=0)
        card.create_rectangle(4, 4, 214, 88, fill="#ffffff", outline="#e1ebf3", width=1)
        card.create_rectangle(4, 4, 16, 88, fill=accent, outline=accent)
        card.create_text(28, 24, anchor="w", text=title, fill="#5d544a", font=("Microsoft YaHei UI", 10))
        card.create_text(28, 58, anchor="w", text=value, fill="#2f2925", font=("Microsoft YaHei UI", 18, "bold"))
        return card

    def draw_app_chart(self, canvas: tk.Canvas, apps: list[tuple[str, float]]) -> None:
        canvas.delete("all")
        width = int(canvas["width"])
        colors = ["#4c78a8", "#f58518", "#54a24b", "#e45756", "#72b7b2", "#b279a2"]
        canvas.create_text(18, 18, anchor="w", text="\u5e94\u7528\u8017\u65f6\u56fe", fill="#2f2925", font=("Microsoft YaHei UI", 13, "bold"))

        if not apps:
            canvas.create_text(width / 2, 132, text="\u6682\u65e0\u6570\u636e\uff0c\u7a0d\u5fae\u4f7f\u7528\u4e00\u4f1a\u513f\u5c31\u4f1a\u51fa\u73b0\u7edf\u8ba1\u3002", fill="#7b7067", font=("Microsoft YaHei UI", 11))
            return

        max_seconds = max(seconds for _name, seconds in apps) or 1
        start_y = 54
        row_h = 36
        label_w = 150
        bar_max = width - label_w - 96
        total = sum(seconds for _name, seconds in apps) or 1

        for index, (name, seconds) in enumerate(apps[:6]):
            y = start_y + index * row_h
            color = colors[index % len(colors)]
            bar_w = max(6, int(bar_max * seconds / max_seconds))
            percent = seconds / total * 100
            display_name = name[:22]
            canvas.create_text(18, y + 10, anchor="w", text=display_name, fill="#3a332e", font=("Microsoft YaHei UI", 10, "bold"))
            canvas.create_rectangle(label_w, y, label_w + bar_max, y + 20, fill="#eee8df", outline="")
            canvas.create_rectangle(label_w, y, label_w + bar_w, y + 20, fill=color, outline="")
            canvas.create_text(label_w + bar_max + 12, y + 10, anchor="w", text=f"{format_seconds(seconds)}  {percent:.0f}%", fill="#5d544a", font=("Segoe UI", 9))

    def draw_window_ranking(self, canvas: tk.Canvas, windows: list[dict]) -> None:
        canvas.delete("all")
        width = int(canvas["width"])
        canvas.create_text(18, 18, anchor="w", text="\u7a97\u53e3\u660e\u7ec6 Top 6", fill="#2f2925", font=("Microsoft YaHei UI", 13, "bold"))

        if not windows:
            canvas.create_text(width / 2, 108, text="\u6682\u65e0\u7a97\u53e3\u660e\u7ec6\u3002", fill="#7b7067", font=("Microsoft YaHei UI", 11))
            return

        for index, item in enumerate(windows[:6], start=1):
            y = 46 + (index - 1) * 29
            seconds = item.get("seconds", 0)
            process = str(item.get("process", "\u672a\u77e5"))
            title = str(item.get("title", "\u65e0\u6807\u9898"))[:54]
            canvas.create_oval(18, y + 4, 38, y + 24, fill="#efe6d8", outline="#d8d1c7")
            canvas.create_text(28, y + 14, text=str(index), fill="#6b5844", font=("Segoe UI", 9, "bold"))
            canvas.create_text(48, y + 6, anchor="w", text=process, fill="#2f2925", font=("Segoe UI", 10, "bold"))
            canvas.create_text(48, y + 22, anchor="w", text=title, fill="#7b7067", font=("Microsoft YaHei UI", 9))
            canvas.create_text(width - 18, y + 14, anchor="e", text=format_seconds(seconds), fill="#4c78a8", font=("Segoe UI", 10, "bold"))

    def draw_task_summary(self, canvas: tk.Canvas, done_count: int) -> None:
        canvas.delete("all")
        canvas.create_text(18, 18, anchor="w", text="\u4eca\u65e5\u4e09\u4ef6\u4e8b", fill="#2f2925", font=("Microsoft YaHei UI", 13, "bold"))
        canvas.create_text(328, 20, anchor="e", text=f"{done_count}/3", fill="#54a24b", font=("Segoe UI", 15, "bold"))
        canvas.create_rectangle(18, 40, 330, 48, fill="#eee8df", outline="")
        canvas.create_rectangle(18, 40, 18 + int(312 * done_count / 3), 48, fill="#54a24b", outline="")

        for index, task in enumerate(self.tasks[:3], start=1):
            y = 66 + (index - 1) * 28
            done = bool(task.get("done"))
            mark = "\u2713" if done else str(index)
            fill = "#54a24b" if done else "#efe6d8"
            outline = "#54a24b" if done else "#d8d1c7"
            text = self.fit_text(task.get("text") or "\u672a\u586b\u5199", 22)
            canvas.create_oval(18, y - 10, 38, y + 10, fill=fill, outline=outline)
            canvas.create_text(28, y, text=mark, fill="#ffffff" if done else "#6b5844", font=("Segoe UI", 9, "bold"))
            canvas.create_text(48, y, anchor="w", text=text, fill="#3f342f", font=("Microsoft YaHei UI", 10))

    def draw_advice_card(self, canvas: tk.Canvas, suggestion: str, total_seconds: float) -> None:
        canvas.delete("all")
        canvas.create_text(18, 18, anchor="w", text="\u840c\u5ba0\u4eca\u65e5\u5efa\u8bae", fill="#2f2925", font=("Microsoft YaHei UI", 13, "bold"))
        canvas.create_text(18, 54, anchor="w", text=suggestion, width=312, fill="#3f342f", font=("Microsoft YaHei UI", 10), justify="left")
        canvas.create_rectangle(18, 112, 330, 146, fill="#fff7ea", outline="#ead7b7")
        canvas.create_text(30, 129, anchor="w", text="\u8bb0\u5f55\u65f6\u957f", fill="#7b7067", font=("Microsoft YaHei UI", 9))
        canvas.create_text(318, 129, anchor="e", text=format_seconds(total_seconds), fill="#f58518", font=("Segoe UI", 12, "bold"))

    def open_stats(self) -> None:
        self.tracker.sample()
        self.tracker.save()
        if self.stats_window and self.stats_window.winfo_exists():
            self.stats_window.destroy()

        win = tk.Toplevel(self.root)
        self.stats_window = win
        win.title("\u4eca\u65e5\u770b\u677f")
        win.geometry(self.pet_popup_geometry(780, 720))
        win.minsize(740, 640)
        win.attributes("-topmost", True)
        frame = self.make_glass_frame(win, alpha=0.95)

        header = tk.Frame(frame, bg="#f8fbff")
        header.pack(fill="x", padx=18, pady=(16, 10))
        tk.Label(header, text="\u4eca\u65e5\u770b\u677f", bg="#f8fbff", fg="#23313f", font=("Microsoft YaHei UI", 19, "bold")).pack(anchor="w")
        tk.Label(header, text=f"\u65f6\u95f4\u7edf\u8ba1\u3001\u4e09\u4ef6\u4e8b\u548c\u4eca\u65e5\u603b\u7ed3\u653e\u5728\u4e00\u8d77    {self.tracker.current_day}", bg="#f8fbff", fg="#6b7c8c", font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(3, 0))

        apps = self.tracker.top_apps(6)
        windows = self.tracker.top_windows(6)
        total_seconds = self.total_activity_seconds()
        app_count = len(self.tracker.data.get("apps", {}))
        window_count = len(self.tracker.data.get("windows", {}))
        done_count = sum(1 for task in self.tasks if task.get("done"))
        suggestion = self.dashboard_suggestion(done_count, apps)

        cards = tk.Frame(frame, bg="#f8fbff")
        cards.pack(fill="x", padx=18, pady=(0, 12))
        self.make_stat_card(cards, "\u603b\u8bb0\u5f55\u65f6\u957f", format_seconds(total_seconds), "#4c78a8").pack(side="left", padx=(0, 12))
        self.make_stat_card(cards, "\u6d89\u53ca\u5e94\u7528", f"{app_count} \u4e2a", "#54a24b").pack(side="left", padx=(0, 12))
        self.make_stat_card(cards, "\u4e09\u4ef6\u4e8b", f"{done_count}/3", "#e45756").pack(side="left")

        chart = tk.Canvas(frame, width=736, height=258, bg="#ffffff", highlightthickness=1, highlightbackground="#e1ebf3")
        chart.pack(fill="x", padx=18, pady=(0, 12))
        self.draw_app_chart(chart, apps)

        insight_row = tk.Frame(frame, bg="#f8fbff")
        insight_row.pack(fill="x", padx=18, pady=(0, 12))
        tasks = tk.Canvas(insight_row, width=352, height=166, bg="#ffffff", highlightthickness=1, highlightbackground="#e1ebf3")
        tasks.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.draw_task_summary(tasks, done_count)
        advice = tk.Canvas(insight_row, width=352, height=166, bg="#ffffff", highlightthickness=1, highlightbackground="#e1ebf3")
        advice.pack(side="left", fill="x", expand=True)
        self.draw_advice_card(advice, suggestion, total_seconds)

        ranking = tk.Canvas(frame, width=736, height=226, bg="#ffffff", highlightthickness=1, highlightbackground="#e1ebf3")
        ranking.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        self.draw_window_ranking(ranking, windows)

        bottom = tk.Frame(frame, bg="#f8fbff")
        bottom.pack(fill="x", padx=18, pady=(0, 14))
        tk.Label(bottom, text=f"\u5171 {window_count} \u4e2a\u7a97\u53e3\u8bb0\u5f55", bg="#f8fbff", fg="#6b7c8c", font=("Microsoft YaHei UI", 9)).pack(side="left")
        self.glass_button(bottom, "\u5173\u95ed", win.destroy, 8).pack(side="right")
        self.glass_button(bottom, "\u5237\u65b0", self.open_stats, 8).pack(side="right", padx=6)
        self.glass_button(bottom, "\u751f\u6210 Markdown \u603b\u7ed3", self.generate_report, 18).pack(side="right", padx=6)
        self.glass_button(bottom, "\u64ad\u62a5\u603b\u7ed3", lambda: self.speak(self.daily_summary_sentence()), 12).pack(side="right")

    def maybe_walk(self) -> None:
        if self.drag_start is not None or self.is_sleeping or self.drop_active:
            return

        screen_w = self.root.winfo_screenwidth()
        if self.walk_timer > 0:
            self.x += self.walk_dx
            self.walk_timer -= 1
            if self.x < 10 or self.x > screen_w - self.width - 10:
                self.walk_dx *= -1
            self.root.geometry(f"+{self.x}+{self.y}")

    def maybe_shift_mood(self) -> None:
        if self.drop_active or self.is_sleeping or self.pomodoro_running:
            return
        if time.time() - self.mood_changed_at < random.randint(45, 90):
            return
        mood_name = random.choice(["happy", "curious", "hungry", "excited", "worried"])
        if mood_name == self.mood.name:
            return
        idle_lines = {
            "happy": ["\u6211\u4eca\u5929\u72b6\u6001\u4e0d\u9519\u3002", "\u5728\u684c\u9762\u966a\u4f60\u5f85\u673a\u4e2d\u3002"],
            "curious": ["\u4f60\u521a\u624d\u5728\u5fd9\u4ec0\u4e48\uff1f", "\u6211\u60f3\u770b\u770b\u4eca\u65e5\u4e09\u4ef6\u4e8b\u3002"],
            "hungry": ["\u6709\u6ca1\u6709\u5c0f\u997c\u5e72\uff1f", "\u6211\u597d\u50cf\u6709\u70b9\u997f\u4e86\u3002"],
            "excited": ["\u8981\u4e0d\u8981\u6765\u4e2a Q \u5f39\u4e0b\u843d\uff1f", "\u6211\u89c9\u5f97\u4eca\u5929\u80fd\u63a8\u8fdb\u5f88\u591a\u3002"],
            "worried": ["\u522b\u5fd8\u4e86\u4f11\u606f\u773c\u775b\u3002", "\u8981\u4e0d\u8981\u559d\u53e3\u6c34\uff1f"],
        }
        self.set_mood(mood_name, random.choice(idle_lines[mood_name]), 190)

    def schedule_next_proactive(self) -> None:
        base_min, base_max = (720, 1080) if self.pomodoro_running else (360, 600)
        self.next_proactive_at = time.time() + random.randint(base_min, base_max)

    def maybe_proactive_interaction(self) -> None:
        now = time.time()
        if now < self.next_proactive_at:
            return
        if self.drop_active or self.is_sleeping or self.message_until > 0:
            self.schedule_next_proactive()
            return

        done_count = sum(1 for task in self.tasks if task.get("done"))
        if self.pomodoro_running:
            lines = [
                "\u4f60\u4e13\u6ce8\u7684\u6837\u5b50\u5f88\u7a33\u3002",
                "\u6162\u6162\u6765\uff0c\u8fd9\u4e00\u8f6e\u53ea\u8981\u5411\u524d\u4e00\u70b9\u70b9\u3002",
                "\u6211\u5728\u65c1\u8fb9\u5b88\u7740\uff0c\u4f60\u7ee7\u7eed\u3002",
            ]
            self.set_mood("focused", random.choice(lines), 210)
        else:
            lines = [
                "\u4eca\u5929\u5df2\u7ecf\u5b8c\u6210\u4e09\u4ef6\u4e8b\u4e2d\u7684 " + str(done_count) + " \u4ef6\u3002",
                "\u8981\u4e0d\u8981\u7ed9\u6211\u6362\u4e2a\u5f62\u8c61\uff1f\u6211\u4eca\u5929\u60f3\u5356\u4e2a\u840c\u3002",
                "\u4f60\u5df2\u7ecf\u505a\u5f97\u6bd4\u521a\u624d\u66f4\u9760\u8fd1\u76ee\u6807\u4e00\u70b9\u4e86\u3002",
                "\u559d\u4e00\u53e3\u6c34\u5427\uff0c\u6211\u5728\u8fd9\u91cc\u966a\u4f60\u3002",
                "\u70b9\u6211\u53f3\u952e\uff0c\u6211\u53ef\u4ee5\u5e2e\u4f60\u770b\u4eca\u5929\u7684\u65f6\u95f4\u53bb\u54ea\u4e86\u3002",
            ]
            self.set_mood(random.choice(["happy", "curious", "proud"]), random.choice(lines), 230)
        self.schedule_next_proactive()

    def update_drop(self) -> None:
        if not self.drop_active:
            self.squash *= 0.82
            if abs(self.squash) < 0.01:
                self.squash = 0.0
            return

        self.drop_velocity += 1.55
        self.drop_velocity = min(self.drop_velocity, 30)
        self.y += self.drop_velocity

        if self.y >= self.ground_y:
            self.y = self.ground_y
            impact_speed = abs(self.drop_velocity)
            self.drop_velocity = -self.drop_velocity * 0.48
            self.squash = min(0.42, 0.12 + impact_speed / 80)

            if self.impact_cooldown <= 0:
                self.play_bouncy_landing_sound(impact_speed)
                self.impact_cooldown = 5

            if abs(self.drop_velocity) < 3.2:
                self.drop_active = False
                self.drop_velocity = 0.0
                self.squash = 0.34
                self.set_mood("excited", "boing\uff01\u843d\u5730\u6210\u529f\u3002", 170)
        else:
            self.squash = max(-0.22, -abs(self.drop_velocity) / 95)

        self.impact_cooldown = max(0, self.impact_cooldown - 1)
        self.root.geometry(f"+{self.x}+{int(self.y)}")

    def draw_pet(self) -> None:
        self.canvas.delete("all")
        bob = math.sin(self.tick / 8) * (2 if not self.is_sleeping and not self.drop_active else 0.7)
        blink = self.tick % 130 > 122
        wag = math.sin(self.tick / 5) * 8
        cx, cy = 130, 126 + bob

        self.draw_scene(cx, cy, wag)
        self.draw_shadow(cx, cy)
        self.draw_tail(cx, cy, wag)
        self.draw_body(cx, cy)
        self.draw_action_body(cx, cy, wag)
        self.draw_ears(cx, cy)
        self.draw_action_hat(cx, cy, wag)
        self.draw_face(cx, cy, blink)
        self.draw_paws(cx, cy)
        self.draw_action_props(cx, cy, wag)
        self.draw_sleep_overlay(cx, cy)

        if self.message_until > 0:
            self.draw_bubble(self.message)
            self.message_until -= 1
        if self.action_until > 0:
            self.action_until -= 1
            if self.action_until == 0:
                self.current_action = None
                self.schedule_next_action()

        if self.is_sleeping:
            z_y = 44 + math.sin(self.tick / 10) * 5
            self.canvas.create_text(188, z_y, text="Z", fill="#7667d6", font=("Segoe UI", 9, "bold"))
            self.canvas.create_text(204, z_y - 14, text="z", fill="#7667d6", font=("Segoe UI", 7, "bold"))

        self.canvas.scale("all", 0, 0, self.ui_scale, self.ui_scale)

    def draw_status(self) -> None:
        label = self.pomodoro_label()
        display = self.fit_text(label, 18)
        self.draw_round_bubble(30, 187, 230, 226, radius=14, tail_at="top", fill="#fffaf0")
        self.canvas.create_text(130, 207, text=display, fill="#4d3b38", font=("Microsoft YaHei UI", 5))

    def fit_text(self, text: str, max_chars: int) -> str:
        text = " ".join(str(text).split())
        if len(text) <= max_chars:
            return text
        return text[: max(1, max_chars - 1)] + "\u2026"

    def draw_round_bubble(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        radius: float = 16,
        tail_at: str | None = None,
        fill: str = "#ffffff",
    ) -> None:
        outline = "#5a4540"
        shadow = "#d8d1c7"
        self.canvas.create_rectangle(x1 + 3, y1 + 3, x2 + 3, y2 + 3, fill=shadow, outline="")
        self.canvas.create_oval(x1, y1, x1 + radius * 2, y1 + radius * 2, fill=fill, outline=outline, width=2)
        self.canvas.create_oval(x2 - radius * 2, y1, x2, y1 + radius * 2, fill=fill, outline=outline, width=2)
        self.canvas.create_oval(x1, y2 - radius * 2, x1 + radius * 2, y2, fill=fill, outline=outline, width=2)
        self.canvas.create_oval(x2 - radius * 2, y2 - radius * 2, x2, y2, fill=fill, outline=outline, width=2)
        self.canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline="")
        self.canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=fill, outline="")
        self.canvas.create_line(x1 + radius, y1, x2 - radius, y1, fill=outline, width=2)
        self.canvas.create_line(x1 + radius, y2, x2 - radius, y2, fill=outline, width=2)
        self.canvas.create_line(x1, y1 + radius, x1, y2 - radius, fill=outline, width=2)
        self.canvas.create_line(x2, y1 + radius, x2, y2 - radius, fill=outline, width=2)
        if tail_at == "bottom":
            self.canvas.create_polygon([118, y2 - 2, 130, y2 + 15, 143, y2 - 2], fill=fill, outline=outline, width=2)
        elif tail_at == "top":
            self.canvas.create_polygon([118, y1 + 2, 130, y1 - 12, 143, y1 + 2], fill=fill, outline=outline, width=2)

    def draw_scene(self, cx: float, cy: float, wag: float) -> None:
        action = self.current_action
        ground = cy + 81
        if self.is_sleeping:
            self.canvas.create_oval(cx - 92, ground - 12, cx + 92, ground + 15, fill="#e8e0ff", outline="")
            self.canvas.create_arc(cx + 62, cy - 92, cx + 102, cy - 52, start=95, extent=220, fill="#fff6bf", outline="")
            self.canvas.create_oval(cx + 74, cy - 95, cx + 108, cy - 57, fill=TRANSPARENT, outline="")
            for sx, sy in [(54, -74), (96, -34), (-78, -52)]:
                self.canvas.create_text(cx + sx, cy + sy, text="\u2726", fill="#a697ff", font=("Segoe UI Symbol", 7))
            self.canvas.create_arc(cx - 76, cy + 24, cx + 76, cy + 92, start=0, extent=180, fill="#bfc9ff", outline=INK, width=2)
            self.canvas.create_line(cx - 48, cy + 53, cx + 46, cy + 53, fill="#8f9be8", width=2)
            return

        if not action:
            self.canvas.create_oval(cx - 74, ground - 7, cx + 74, ground + 9, fill="#eadfd3", outline="")
            return

        if action == "teacher":
            self.canvas.create_oval(cx - 82, ground - 8, cx + 84, ground + 10, fill="#dfece4", outline="")
            self.canvas.create_rectangle(cx - 118, cy - 78, cx - 36, cy - 18, fill="#3f6b58", outline=INK, width=2)
            self.canvas.create_rectangle(cx - 112, cy - 72, cx - 42, cy - 24, fill="#477965", outline="")
            self.canvas.create_line(cx - 118, cy - 18, cx - 36, cy - 18, fill="#caa66a", width=4)
            self.canvas.create_text(cx - 77, cy - 54, text="1 2 3", fill="#f8f2dc", font=("Segoe UI", 7, "bold"))
            self.canvas.create_line(cx - 107, cy - 36, cx - 71, cy - 36, fill="#f8f2dc", width=2)
            self.canvas.create_rectangle(cx + 48, cy + 44, cx + 104, cy + 76, fill="#e8c18a", outline=INK, width=2)
            self.canvas.create_line(cx + 56, cy + 54, cx + 96, cy + 54, fill="#b7844d", width=2)
        elif action == "plant":
            self.canvas.create_oval(cx - 92, ground - 6, cx + 98, ground + 12, fill="#dcedc8", outline="")
            self.canvas.create_arc(cx - 122, cy - 104, cx - 74, cy - 56, start=0, extent=359, fill="#ffe08a", outline="")
            for angle in range(0, 360, 45):
                x = math.cos(math.radians(angle)) * 34
                y = math.sin(math.radians(angle)) * 34
                self.canvas.create_line(cx - 98, cy - 80, cx - 98 + x, cy - 80 + y, fill="#ffd166", width=2)
            self.canvas.create_arc(cx - 84, cy + 38, cx + 6, cy + 96, start=0, extent=180, fill="#8a5a2b", outline=INK, width=2)
            for offset in [-38, -18, 8, 34]:
                self.canvas.create_oval(cx + offset, cy + 55, cx + offset + 10, cy + 63, fill="#6dbb63", outline="")
        elif action == "home":
            self.canvas.create_oval(cx - 90, ground - 12, cx + 96, ground + 12, fill="#ffe8ef", outline="")
            self.canvas.create_rectangle(cx - 114, cy + 20, cx - 66, cy + 72, fill="#fff7ea", outline=INK, width=2)
            self.canvas.create_polygon([cx - 120, cy + 21, cx - 90, cy - 5 + wag * 0.08, cx - 60, cy + 21], fill="#e45756", outline=INK, width=2)
            self.canvas.create_rectangle(cx - 96, cy + 48, cx - 84, cy + 72, fill="#d6b08a", outline=INK, width=1)
            self.canvas.create_oval(cx + 57, cy + 50, cx + 98, cy + 78, fill="#ffd6a5", outline=INK, width=2)
            self.canvas.create_rectangle(cx + 62, cy + 31, cx + 91, cy + 61, fill="#fff4d6", outline=INK, width=2)
            self.canvas.create_polygon([cx + 58, cy + 31, cx + 76, cy + 13, cx + 96, cy + 31], fill="#ff8fb3", outline=INK, width=2)
        elif action == "study":
            self.canvas.create_oval(cx - 86, ground - 8, cx + 86, ground + 10, fill="#dceeff", outline="")
            self.canvas.create_rectangle(cx - 104, cy + 48, cx + 104, cy + 77, fill="#caa66a", outline=INK, width=2)
            self.canvas.create_rectangle(cx - 92, cy + 36, cx - 56, cy + 49, fill="#fff7ea", outline=INK, width=1)
            self.canvas.create_rectangle(cx - 50, cy + 33, cx - 14, cy + 49, fill="#d7c2ff", outline=INK, width=1)
        elif action == "drink":
            self.canvas.create_oval(cx - 80, ground - 8, cx + 80, ground + 9, fill="#dff4ff", outline="")
            for x in [cx - 82, cx - 54, cx + 82]:
                self.canvas.create_oval(x - 4, cy - 24 + math.sin(self.tick / 7 + x) * 3, x + 4, cy - 13, fill="#8ed7ff", outline="")
        elif action == "stretch":
            self.canvas.create_oval(cx - 92, ground - 9, cx + 92, ground + 12, fill="#e8f7ff", outline="")
            self.canvas.create_arc(cx - 80, cy + 44, cx + 80, cy + 94, start=0, extent=180, fill="#b9e6c9", outline=INK, width=2)
            for offset in [-54, -18, 18, 54]:
                self.canvas.create_line(cx + offset - 10, cy + 62, cx + offset + 10, cy + 62, fill="#6fcf97", width=2)
        else:
            self.canvas.create_oval(cx - 82, ground - 8, cx + 82, ground + 10, fill="#eee7dc", outline="")

    def draw_shadow(self, cx: float, cy: float) -> None:
        width_boost = 1 + max(self.squash, 0) * 0.65
        self.canvas.create_oval(cx - 68 * width_boost, cy + 66, cx + 68 * width_boost, cy + 88, fill="#000000", outline="", stipple="gray50")

    def draw_tail(self, cx: float, cy: float, wag: float) -> None:
        if self.pet_skin == "bunny":
            self.canvas.create_oval(cx + 50, cy + 33 + wag * 0.2, cx + 82, cy + 64 + wag * 0.2, fill="#ffffff", outline="#5a4540", width=2)
            return
        if self.pet_skin == "bear":
            self.canvas.create_oval(cx + 54, cy + 36, cx + 78, cy + 60, fill=self.mood.body, outline="#5a4540", width=2)
            return
        if self.pet_skin == "tiger":
            tail_lift = self.squash * 8
            points = [cx + 62, cy + 24, cx + 96, cy + 5 + wag - tail_lift, cx + 92, cy - 27 + wag - tail_lift, cx + 58, cy - 8]
            self.canvas.create_polygon(points, fill=self.mood.body, outline="#5a4540", width=2, smooth=True)
            for offset in [0, 16, 31]:
                self.canvas.create_line(cx + 65 + offset * 0.7, cy + 18 - offset + wag - tail_lift, cx + 80 + offset * 0.45, cy + 4 - offset + wag - tail_lift, fill="#5a4540", width=2, capstyle=tk.ROUND)
            return

        tail_lift = self.squash * 8
        points = [cx + 62, cy + 22, cx + 95, cy - 2 + wag - tail_lift, cx + 82, cy - 36 + wag - tail_lift, cx + 54, cy - 12]
        self.canvas.create_polygon(points, fill=self.mood.body, outline="#5a4540", width=2, smooth=True)
        self.canvas.create_oval(cx + 67, cy - 45 + wag - tail_lift, cx + 93, cy - 18 + wag - tail_lift, fill="#ffffff", outline="#5a4540", width=2)

    def draw_body(self, cx: float, cy: float) -> None:
        body_w = 67 * (1 + self.squash * 0.28)
        body_top = 50 * (1 - self.squash * 0.34)
        body_bottom = 78 * (1 - self.squash * 0.24)
        belly_w = 44 * (1 + self.squash * 0.22)
        self.canvas.create_oval(cx - body_w, cy - body_top, cx + body_w, cy + body_bottom, fill=self.mood.body, outline=INK, width=2)
        self.canvas.create_oval(cx - body_w + 18, cy - body_top + 14, cx - body_w + 43, cy - body_top + 33, fill="#ffffff", outline="", stipple="gray25")
        self.canvas.create_oval(cx - belly_w, cy + 4, cx + belly_w, cy + 70 * (1 - self.squash * 0.18), fill="#fff8fb", outline="")

    def draw_action_body(self, cx: float, cy: float, wag: float) -> None:
        action = self.current_action
        if not action:
            return
        if action == "work":
            self.canvas.create_arc(cx - 50, cy - 20, cx + 50, cy + 82, start=200, extent=140, fill="#f7c948", outline=INK, width=2)
            self.canvas.create_line(cx - 28, cy + 16, cx + 24, cy + 56, fill="#8a5a2b", width=3, capstyle=tk.ROUND)
        elif action == "plant":
            self.canvas.create_arc(cx - 48, cy - 16, cx + 48, cy + 80, start=200, extent=140, fill="#78c257", outline=INK, width=2)
            self.canvas.create_line(cx - 38, cy + 30, cx + 40, cy + 30, fill="#4f8f45", width=2)
        elif action == "home":
            self.canvas.create_arc(cx - 50, cy - 17, cx + 50, cy + 81, start=200, extent=140, fill="#ffc8dd", outline=INK, width=2)
            self.canvas.create_oval(cx - 16, cy + 24, cx + 16, cy + 48, fill="#fff7fb", outline="#d68fa4", width=2)
        elif action == "teacher":
            self.canvas.create_arc(cx - 50, cy - 18, cx + 50, cy + 81, start=200, extent=140, fill="#f6edd7", outline=INK, width=2)
            self.canvas.create_polygon([cx - 28, cy + 14, cx, cy + 48, cx + 28, cy + 14], fill="#5b7f95", outline=INK, width=2)
            self.canvas.create_oval(cx - 8, cy + 17, cx + 8, cy + 30, fill="#e45756", outline=INK, width=1)
        elif action == "study":
            self.canvas.create_arc(cx - 49, cy - 18, cx + 49, cy + 80, start=200, extent=140, fill="#9fd3ff", outline=INK, width=2)
            self.canvas.create_line(cx - 22, cy + 18, cx + 22, cy + 18, fill="#35658b", width=2)
        elif action == "chef":
            self.canvas.create_arc(cx - 48, cy - 18, cx + 48, cy + 81, start=200, extent=140, fill="#ffffff", outline=INK, width=2)
            for x in [cx - 9, cx + 9]:
                self.canvas.create_oval(x - 2, cy + 17, x + 2, cy + 21, fill=INK, outline="")
        elif action == "paint":
            self.canvas.create_arc(cx - 50, cy - 17, cx + 50, cy + 80, start=200, extent=140, fill="#d7c2ff", outline=INK, width=2)
            for x, color in [(cx - 20, "#e45756"), (cx, "#54a24b"), (cx + 20, "#4c78a8")]:
                self.canvas.create_oval(x - 4, cy + 28, x + 4, cy + 36, fill=color, outline="")
        elif action == "doctor":
            self.canvas.create_arc(cx - 50, cy - 18, cx + 50, cy + 81, start=200, extent=140, fill="#f5fbff", outline=INK, width=2)
            self.canvas.create_line(cx, cy + 19, cx, cy + 43, fill="#e45756", width=4, capstyle=tk.ROUND)
            self.canvas.create_line(cx - 12, cy + 31, cx + 12, cy + 31, fill="#e45756", width=4, capstyle=tk.ROUND)
        elif action == "drink":
            self.canvas.create_arc(cx - 46, cy - 15, cx + 46, cy + 78, start=205, extent=130, fill="#e8f7ff", outline=INK, width=2)
        elif action == "stretch":
            self.canvas.create_arc(cx - 49, cy - 18, cx + 49, cy + 80, start=200, extent=140, fill="#dff7ec", outline=INK, width=2)
            self.canvas.create_line(cx - 22, cy + 23, cx + 22, cy + 23, fill="#6fcf97", width=2)

    def draw_action_hat(self, cx: float, cy: float, wag: float) -> None:
        action = self.current_action
        if not action:
            return
        if action == "work":
            self.canvas.create_arc(cx - 48, cy - 74, cx + 48, cy - 22, start=0, extent=180, fill="#f7c948", outline=INK, width=2)
            self.canvas.create_rectangle(cx - 52, cy - 49, cx + 52, cy - 39, fill="#f7c948", outline=INK, width=2)
        elif action == "plant":
            self.canvas.create_polygon([cx - 44, cy - 54, cx + 44, cy - 54, cx + 24, cy - 74, cx - 24, cy - 74], fill="#caa66a", outline=INK, width=2)
            self.canvas.create_line(cx - 50, cy - 54, cx + 50, cy - 54, fill=INK, width=2)
        elif action == "home":
            self.canvas.create_polygon([cx - 34, cy - 59, cx + 34, cy - 59, cx, cy - 82], fill="#ff8fb3", outline=INK, width=2)
            self.canvas.create_oval(cx - 8, cy - 87, cx + 8, cy - 72, fill="#fff7fb", outline=INK, width=2)
        elif action == "teacher":
            self.canvas.create_rectangle(cx - 45, cy - 73, cx + 45, cy - 58, fill="#5b7f95", outline=INK, width=2)
            self.canvas.create_polygon([cx - 42, cy - 72, cx + 42, cy - 72, cx + 26, cy - 88, cx - 26, cy - 88], fill="#5b7f95", outline=INK, width=2)
            self.canvas.create_line(cx + 44, cy - 64, cx + 60, cy - 52 + wag * 0.08, fill="#e45756", width=2)
        elif action == "study":
            self.canvas.create_rectangle(cx - 42, cy - 72, cx + 42, cy - 57, fill="#2f3d4a", outline=INK, width=2)
            self.canvas.create_polygon([cx + 42, cy - 64, cx + 63, cy - 56, cx + 42, cy - 49], fill="#2f3d4a", outline=INK, width=2)
            self.canvas.create_line(cx + 60, cy - 55, cx + 60, cy - 33 + wag * 0.08, fill="#f58518", width=2)
        elif action == "chef":
            for x, y, size in [(cx - 22, cy - 76, 20), (cx, cy - 84, 24), (cx + 22, cy - 76, 20)]:
                self.canvas.create_oval(x - size, y - size, x + size, y + size, fill="#ffffff", outline=INK, width=2)
            self.canvas.create_rectangle(cx - 38, cy - 70, cx + 38, cy - 46, fill="#ffffff", outline=INK, width=2)
        elif action == "paint":
            self.canvas.create_polygon([cx - 42, cy - 53, cx + 42, cy - 61, cx + 30, cy - 76, cx - 28, cy - 70], fill="#b279a2", outline=INK, width=2)
            self.canvas.create_oval(cx + 20, cy - 72, cx + 36, cy - 58, fill="#f58518", outline="")
        elif action == "doctor":
            self.canvas.create_rectangle(cx - 38, cy - 69, cx + 38, cy - 51, fill="#ffffff", outline=INK, width=2)
            self.canvas.create_line(cx, cy - 67, cx, cy - 53, fill="#e45756", width=3)
            self.canvas.create_line(cx - 8, cy - 60, cx + 8, cy - 60, fill="#e45756", width=3)

    def draw_action_props(self, cx: float, cy: float, wag: float) -> None:
        action = self.current_action
        if not action:
            return
        arm = math.sin(self.tick / 6) * 4
        if action == "drink":
            self.canvas.create_rectangle(cx + 38, cy + 8 + arm, cx + 66, cy + 50 + arm, fill="#8ed7ff", outline=INK, width=2)
            self.canvas.create_arc(cx + 59, cy + 18 + arm, cx + 80, cy + 42 + arm, start=270, extent=180, style=tk.ARC, outline=INK, width=2)
            self.canvas.create_line(cx + 28, cy + 35, cx + 43, cy + 23 + arm, fill=INK, width=3, capstyle=tk.ROUND)
            self.canvas.create_text(cx + 52, cy + 66, text="\u6c34", fill="#4c78a8", font=("Microsoft YaHei UI", 6, "bold"))
        elif action == "work":
            self.canvas.create_line(cx + 34, cy + 20, cx + 70, cy - 16 + arm, fill="#8a5a2b", width=4, capstyle=tk.ROUND)
            self.canvas.create_polygon([cx + 64, cy - 22 + arm, cx + 90, cy - 12 + arm, cx + 80, cy + 6 + arm, cx + 57, cy - 4 + arm], fill="#9aa3ad", outline=INK, width=2)
            self.canvas.create_line(cx - 36, cy + 35, cx - 60, cy + 55, fill=INK, width=3, capstyle=tk.ROUND)
        elif action == "plant":
            self.canvas.create_rectangle(cx + 44, cy + 43, cx + 85, cy + 69, fill="#c77943", outline=INK, width=2)
            self.canvas.create_arc(cx + 39, cy + 32, cx + 90, cy + 62, start=0, extent=180, fill="#8a5a2b", outline=INK, width=2)
            self.canvas.create_line(cx + 64, cy + 36, cx + 64, cy - 2 + arm, fill="#3f8f46", width=4, capstyle=tk.ROUND)
            self.canvas.create_oval(cx + 46, cy + 4 + arm, cx + 66, cy + 24 + arm, fill="#78c257", outline="#3f8f46", width=2)
            self.canvas.create_oval(cx + 62, cy - 2 + arm, cx + 84, cy + 18 + arm, fill="#78c257", outline="#3f8f46", width=2)
            self.canvas.create_line(cx - 36, cy + 30, cx - 64, cy + 58, fill="#6b5844", width=4, capstyle=tk.ROUND)
            self.canvas.create_polygon([cx - 70, cy + 58, cx - 54, cy + 67, cx - 58, cy + 43], fill="#9aa3ad", outline=INK, width=2)
        elif action == "home":
            self.canvas.create_rectangle(cx + 44, cy + 17, cx + 92, cy + 68, fill="#fff7ea", outline=INK, width=2)
            self.canvas.create_polygon([cx + 38, cy + 18, cx + 68, cy - 9 + arm, cx + 98, cy + 18], fill="#e45756", outline=INK, width=2)
            self.canvas.create_rectangle(cx + 63, cy + 42, cx + 76, cy + 68, fill="#d6b08a", outline=INK, width=2)
            self.canvas.create_rectangle(cx + 51, cy + 28, cx + 61, cy + 39, fill="#9fd3ff", outline=INK, width=1)
            self.canvas.create_line(cx - 32, cy + 34, cx - 58, cy + 44 + arm, fill=INK, width=3, capstyle=tk.ROUND)
            self.canvas.create_oval(cx - 72, cy + 35 + arm, cx - 52, cy + 55 + arm, fill="#ffdf6e", outline=INK, width=2)
        elif action == "teacher":
            self.canvas.create_oval(cx - 37, cy - 10, cx - 13, cy + 10, outline=INK, width=2)
            self.canvas.create_oval(cx + 13, cy - 10, cx + 37, cy + 10, outline=INK, width=2)
            self.canvas.create_line(cx - 13, cy, cx + 13, cy, fill=INK, width=2)
            self.canvas.create_line(cx + 34, cy + 23, cx + 81, cy - 23 + arm, fill="#8a5a2b", width=3, capstyle=tk.ROUND)
            self.canvas.create_oval(cx + 77, cy - 28 + arm, cx + 86, cy - 19 + arm, fill="#f8f2dc", outline=INK, width=1)
            self.canvas.create_polygon([cx - 42, cy + 38, cx - 10, cy + 45, cx - 10, cy + 72, cx - 42, cy + 64], fill="#fff7ea", outline=INK, width=2)
            self.canvas.create_line(cx - 36, cy + 49, cx - 16, cy + 54, fill="#7b7067", width=2)
        elif action == "study":
            self.canvas.create_polygon([cx - 58, cy + 34, cx - 5, cy + 47, cx - 5, cy + 82, cx - 58, cy + 68], fill="#ffffff", outline=INK, width=2)
            self.canvas.create_polygon([cx + 5, cy + 47, cx + 58, cy + 34, cx + 58, cy + 68, cx + 5, cy + 82], fill="#fff7ea", outline=INK, width=2)
            self.canvas.create_line(cx, cy + 48, cx, cy + 81, fill="#d8d1c7", width=2)
            self.canvas.create_line(cx - 48, cy + 48, cx - 14, cy + 57, fill="#7b7067", width=2)
            self.canvas.create_line(cx + 16, cy + 57, cx + 48, cy + 49, fill="#7b7067", width=2)
        elif action == "chef":
            self.canvas.create_oval(cx + 37, cy + 37 + arm, cx + 88, cy + 66 + arm, fill="#9aa3ad", outline=INK, width=2)
            self.canvas.create_line(cx + 32, cy + 52, cx + 45, cy + 50 + arm, fill=INK, width=3, capstyle=tk.ROUND)
            self.canvas.create_line(cx - 34, cy + 22, cx - 66, cy + 52, fill="#8a5a2b", width=4, capstyle=tk.ROUND)
            self.canvas.create_oval(cx - 78, cy + 43, cx - 54, cy + 66, fill="#f7c948", outline=INK, width=2)
        elif action == "paint":
            self.canvas.create_oval(cx - 88, cy + 26, cx - 38, cy + 64, fill="#fff7ea", outline=INK, width=2)
            for px, py, color in [(-72, 44, "#e45756"), (-60, 36, "#54a24b"), (-51, 51, "#4c78a8"), (-70, 56, "#f58518")]:
                self.canvas.create_oval(cx + px - 4, cy + py - 4, cx + px + 4, cy + py + 4, fill=color, outline="")
            self.canvas.create_line(cx + 30, cy + 25, cx + 72, cy - 8 + arm, fill="#8a5a2b", width=3, capstyle=tk.ROUND)
            self.canvas.create_oval(cx + 67, cy - 14 + arm, cx + 82, cy + 1 + arm, fill="#54a24b", outline=INK, width=1)
        elif action == "doctor":
            self.canvas.create_oval(cx + 52, cy + 12 + arm, cx + 76, cy + 36 + arm, fill="#c7f0ff", outline=INK, width=2)
            self.canvas.create_line(cx + 31, cy + 26, cx + 55, cy + 24 + arm, fill=INK, width=3, capstyle=tk.ROUND)
            self.canvas.create_rectangle(cx - 76, cy + 35, cx - 38, cy + 67, fill="#ffffff", outline=INK, width=2)
            self.canvas.create_line(cx - 57, cy + 43, cx - 57, cy + 59, fill="#e45756", width=3)
            self.canvas.create_line(cx - 65, cy + 51, cx - 49, cy + 51, fill="#e45756", width=3)
        elif action == "stretch":
            lift = math.sin(self.tick / 8) * 8
            self.canvas.create_line(cx - 34, cy + 26, cx - 76, cy - 8 - lift, fill=INK, width=3, capstyle=tk.ROUND)
            self.canvas.create_line(cx + 34, cy + 26, cx + 76, cy - 8 + lift, fill=INK, width=3, capstyle=tk.ROUND)
            self.canvas.create_oval(cx - 84, cy - 18 - lift, cx - 68, cy - 2 - lift, fill="#fff8fb", outline=INK, width=2)
            self.canvas.create_oval(cx + 68, cy - 18 + lift, cx + 84, cy - 2 + lift, fill="#fff8fb", outline=INK, width=2)
            self.canvas.create_text(cx, cy + 78, text="\u62c9\u4f38", fill="#4c78a8", font=("Microsoft YaHei UI", 7, "bold"))

    def draw_sleep_overlay(self, cx: float, cy: float) -> None:
        if not self.is_sleeping:
            return
        breathing = math.sin(self.tick / 12) * 2
        self.canvas.create_oval(cx - 58, cy + 22 + breathing, cx + 58, cy + 84 + breathing, fill="#c8d2ff", outline=INK, width=2)
        self.canvas.create_arc(cx - 56, cy + 20 + breathing, cx + 56, cy + 70 + breathing, start=0, extent=180, fill="#dbe2ff", outline="#8f9be8", width=2)
        for x in [-32, 0, 32]:
            self.canvas.create_line(cx + x - 10, cy + 52 + breathing, cx + x + 10, cy + 56 + breathing, fill="#9aa8f0", width=2, capstyle=tk.ROUND)
        self.canvas.create_oval(cx - 68, cy + 38, cx - 42, cy + 62, fill="#fff7fb", outline=INK, width=2)

    def draw_ears(self, cx: float, cy: float) -> None:
        ear_squish = max(self.squash, 0) * 12
        if self.pet_skin == "bunny":
            self.canvas.create_oval(cx - 55, cy - 112 + ear_squish, cx - 22, cy - 22, fill=self.mood.body, outline="#5a4540", width=2)
            self.canvas.create_oval(cx + 22, cy - 112 + ear_squish, cx + 55, cy - 22, fill=self.mood.body, outline="#5a4540", width=2)
            self.canvas.create_oval(cx - 46, cy - 96 + ear_squish, cx - 31, cy - 34, fill="#fff8fb", outline="")
            self.canvas.create_oval(cx + 31, cy - 96 + ear_squish, cx + 46, cy - 34, fill="#fff8fb", outline="")
            return
        if self.pet_skin == "bear":
            self.canvas.create_oval(cx - 62, cy - 65 + ear_squish, cx - 22, cy - 25 + ear_squish, fill=self.mood.body, outline="#5a4540", width=2)
            self.canvas.create_oval(cx + 22, cy - 65 + ear_squish, cx + 62, cy - 25 + ear_squish, fill=self.mood.body, outline="#5a4540", width=2)
            self.canvas.create_oval(cx - 50, cy - 54 + ear_squish, cx - 34, cy - 37 + ear_squish, fill="#fff8fb", outline="")
            self.canvas.create_oval(cx + 34, cy - 54 + ear_squish, cx + 50, cy - 37 + ear_squish, fill="#fff8fb", outline="")
            return
        if self.pet_skin == "tiger":
            self.canvas.create_oval(cx - 62, cy - 64 + ear_squish, cx - 24, cy - 25 + ear_squish, fill=self.mood.body, outline="#5a4540", width=2)
            self.canvas.create_oval(cx + 24, cy - 64 + ear_squish, cx + 62, cy - 25 + ear_squish, fill=self.mood.body, outline="#5a4540", width=2)
            self.canvas.create_oval(cx - 50, cy - 54 + ear_squish, cx - 36, cy - 38 + ear_squish, fill="#fff8fb", outline="")
            self.canvas.create_oval(cx + 36, cy - 54 + ear_squish, cx + 50, cy - 38 + ear_squish, fill="#fff8fb", outline="")
            return

        left = [cx - 51, cy - 36, cx - 35, cy - 82 + ear_squish, cx - 8, cy - 41]
        right = [cx + 51, cy - 36, cx + 35, cy - 82 + ear_squish, cx + 8, cy - 41]
        self.canvas.create_polygon(left, fill=self.mood.body, outline="#5a4540", width=2, smooth=True)
        self.canvas.create_polygon(right, fill=self.mood.body, outline="#5a4540", width=2, smooth=True)
        self.canvas.create_polygon([cx - 39, cy - 42, cx - 34, cy - 65 + ear_squish, cx - 20, cy - 44], fill="#fff8fb", outline="")
        self.canvas.create_polygon([cx + 39, cy - 42, cx + 34, cy - 65 + ear_squish, cx + 20, cy - 44], fill="#fff8fb", outline="")

    def draw_face(self, cx: float, cy: float, blink: bool) -> None:
        face_drop = max(self.squash, 0) * 5
        eye_y = cy - 7 + face_drop
        expression = self.mood.expression
        if self.is_sleeping or expression == "sleepy":
            self.canvas.create_arc(cx - 34, eye_y - 4, cx - 14, eye_y + 13, start=190, extent=150, style=tk.ARC, outline="#5a4540", width=2)
            self.canvas.create_arc(cx + 14, eye_y - 4, cx + 34, eye_y + 13, start=200, extent=150, style=tk.ARC, outline="#5a4540", width=2)
        elif expression == "excited":
            self.canvas.create_text(cx - 25, eye_y, text="\u2605", fill="#5a4540", font=("Segoe UI Symbol", 9, "bold"))
            self.canvas.create_text(cx + 25, eye_y, text="\u2605", fill="#5a4540", font=("Segoe UI Symbol", 9, "bold"))
        elif expression == "focused":
            self.canvas.create_line(cx - 39, eye_y - 14, cx - 14, eye_y - 9, fill="#5a4540", width=2, capstyle=tk.ROUND)
            self.canvas.create_line(cx + 14, eye_y - 9, cx + 39, eye_y - 14, fill="#5a4540", width=2, capstyle=tk.ROUND)
            self.canvas.create_oval(cx - 34, eye_y - 9, cx - 16, eye_y + 12, fill="#5a4540", outline="")
            self.canvas.create_oval(cx + 16, eye_y - 9, cx + 34, eye_y + 12, fill="#5a4540", outline="")
        elif expression == "proud":
            self.canvas.create_arc(cx - 36, eye_y - 8, cx - 14, eye_y + 12, start=200, extent=145, style=tk.ARC, outline="#5a4540", width=2)
            self.canvas.create_arc(cx + 14, eye_y - 8, cx + 36, eye_y + 12, start=195, extent=145, style=tk.ARC, outline="#5a4540", width=2)
        elif expression == "worried":
            self.canvas.create_line(cx - 39, eye_y - 12, cx - 16, eye_y - 17, fill="#5a4540", width=2, capstyle=tk.ROUND)
            self.canvas.create_line(cx + 16, eye_y - 17, cx + 39, eye_y - 12, fill="#5a4540", width=2, capstyle=tk.ROUND)
            self.canvas.create_oval(cx - 34, eye_y - 8, cx - 16, eye_y + 11, fill="#5a4540", outline="")
            self.canvas.create_oval(cx + 16, eye_y - 8, cx + 34, eye_y + 11, fill="#5a4540", outline="")
        elif expression == "curious":
            self.canvas.create_oval(cx - 36, eye_y - 13, cx - 14, eye_y + 15, fill="#5a4540", outline="")
            self.canvas.create_oval(cx + 17, eye_y - 9, cx + 33, eye_y + 11, fill="#5a4540", outline="")
            self.canvas.create_oval(cx - 29, eye_y - 8, cx - 23, eye_y - 2, fill="#ffffff", outline="")
        elif blink:
            self.canvas.create_line(cx - 35, eye_y + 2, cx - 16, eye_y + 2, fill="#5a4540", width=2, capstyle=tk.ROUND)
            self.canvas.create_line(cx + 16, eye_y + 2, cx + 35, eye_y + 2, fill="#5a4540", width=2, capstyle=tk.ROUND)
        else:
            self.canvas.create_oval(cx - 35, eye_y - 12, cx - 15, eye_y + 14, fill="#5a4540", outline="")
            self.canvas.create_oval(cx + 15, eye_y - 12, cx + 35, eye_y + 14, fill="#5a4540", outline="")
            self.canvas.create_oval(cx - 29, eye_y - 8, cx - 23, eye_y - 2, fill="#ffffff", outline="")
            self.canvas.create_oval(cx + 21, eye_y - 8, cx + 27, eye_y - 2, fill="#ffffff", outline="")

        self.canvas.create_oval(cx - 8, cy + 12 + face_drop, cx + 8, cy + 21 + face_drop, fill=INK, outline="")
        if expression == "worried":
            self.canvas.create_arc(cx - 18, cy + 29 + face_drop, cx + 18, cy + 52 + face_drop, start=25, extent=130, style=tk.ARC, outline="#5a4540", width=2)
        elif expression == "hungry":
            self.canvas.create_arc(cx - 22, cy + 14 + face_drop, cx, cy + 38 + face_drop, start=200, extent=130, style=tk.ARC, outline="#5a4540", width=2)
            self.canvas.create_arc(cx, cy + 14 + face_drop, cx + 22, cy + 38 + face_drop, start=210, extent=130, style=tk.ARC, outline="#5a4540", width=2)
            self.canvas.create_oval(cx + 4, cy + 31 + face_drop, cx + 14, cy + 42 + face_drop, fill="#ff6f91", outline="")
        elif expression == "focused":
            self.canvas.create_line(cx - 13, cy + 35 + face_drop, cx + 13, cy + 35 + face_drop, fill="#5a4540", width=2, capstyle=tk.ROUND)
        else:
            self.canvas.create_arc(cx - 22, cy + 14 + face_drop, cx, cy + 38 + face_drop, start=200, extent=130, style=tk.ARC, outline="#5a4540", width=2)
            self.canvas.create_arc(cx, cy + 14 + face_drop, cx + 22, cy + 38 + face_drop, start=210, extent=130, style=tk.ARC, outline="#5a4540", width=2)
        self.canvas.create_oval(cx - 54, cy + 14 + face_drop, cx - 31, cy + 30 + face_drop, fill=self.mood.cheek, outline="")
        self.canvas.create_oval(cx + 31, cy + 14 + face_drop, cx + 54, cy + 30 + face_drop, fill=self.mood.cheek, outline="")
        self.canvas.create_oval(cx - 48, cy + 17 + face_drop, cx - 42, cy + 22 + face_drop, fill="#ffffff", outline="")
        self.canvas.create_oval(cx + 42, cy + 17 + face_drop, cx + 48, cy + 22 + face_drop, fill="#ffffff", outline="")
        self.draw_skin_marks(cx, cy, face_drop)

    def draw_skin_marks(self, cx: float, cy: float, face_drop: float) -> None:
        if self.pet_skin == "cat":
            for side in [-1, 1]:
                self.canvas.create_line(cx + side * 42, cy + 2 + face_drop, cx + side * 62, cy - 2 + face_drop, fill="#5a4540", width=2, capstyle=tk.ROUND)
                self.canvas.create_line(cx + side * 42, cy + 10 + face_drop, cx + side * 64, cy + 11 + face_drop, fill="#5a4540", width=2, capstyle=tk.ROUND)
                self.canvas.create_line(cx + side * 42, cy + 18 + face_drop, cx + side * 60, cy + 24 + face_drop, fill="#5a4540", width=2, capstyle=tk.ROUND)
        elif self.pet_skin == "bunny":
            self.canvas.create_oval(cx - 62, cy + 26 + face_drop, cx - 50, cy + 39 + face_drop, fill="#ffffff", outline="")
            self.canvas.create_oval(cx + 50, cy + 26 + face_drop, cx + 62, cy + 39 + face_drop, fill="#ffffff", outline="")
        elif self.pet_skin == "bear":
            self.canvas.create_oval(cx - 22, cy + 6 + face_drop, cx + 22, cy + 42 + face_drop, fill="#fff8fb", outline="")
            self.canvas.create_oval(cx - 8, cy + 12 + face_drop, cx + 8, cy + 22 + face_drop, fill="#5a4540", outline="")
        elif self.pet_skin == "tiger":
            self.canvas.create_line(cx - 18, cy - 38 + face_drop, cx - 8, cy - 24 + face_drop, fill="#5a4540", width=2, capstyle=tk.ROUND)
            self.canvas.create_line(cx, cy - 42 + face_drop, cx, cy - 24 + face_drop, fill="#5a4540", width=2, capstyle=tk.ROUND)
            self.canvas.create_line(cx + 18, cy - 38 + face_drop, cx + 8, cy - 24 + face_drop, fill="#5a4540", width=2, capstyle=tk.ROUND)
            for side in [-1, 1]:
                self.canvas.create_line(cx + side * 46, cy - 18 + face_drop, cx + side * 63, cy - 26 + face_drop, fill="#5a4540", width=2, capstyle=tk.ROUND)
                self.canvas.create_line(cx + side * 49, cy - 3 + face_drop, cx + side * 66, cy - 7 + face_drop, fill="#5a4540", width=2, capstyle=tk.ROUND)

    def draw_paws(self, cx: float, cy: float) -> None:
        paw_drop = max(self.squash, 0) * 11
        self.canvas.create_oval(cx - 55, cy + 52 + paw_drop, cx - 20, cy + 84 + paw_drop, fill=self.mood.body, outline="#5a4540", width=2)
        self.canvas.create_oval(cx + 20, cy + 52 + paw_drop, cx + 55, cy + 84 + paw_drop, fill=self.mood.body, outline="#5a4540", width=2)
        self.canvas.create_line(cx - 45, cy + 69 + paw_drop, cx - 32, cy + 70 + paw_drop, fill="#5a4540", width=2, capstyle=tk.ROUND)
        self.canvas.create_line(cx + 32, cy + 70 + paw_drop, cx + 45, cy + 69 + paw_drop, fill="#5a4540", width=2, capstyle=tk.ROUND)

    def draw_bubble(self, text: str) -> None:
        display = self.fit_text(text, 26)
        self.draw_speech_bubble(18, 8, 242, 52)
        self.canvas.create_text(130, 29, text=display, fill="#4d3b38", font=("Microsoft YaHei UI", 10))

    def draw_speech_bubble(self, x1: float, y1: float, x2: float, y2: float) -> None:
        fill = "#fffdfb"
        outline = "#d68fa4"
        highlight = "#ffffff"
        shadow = "#ead7d0"
        radius = 18
        self.canvas.create_rectangle(x1 + 3, y1 + 3, x2 + 3, y2 + 3, fill=shadow, outline="")
        self.canvas.create_oval(x1, y1, x1 + radius * 2, y1 + radius * 2, fill=fill, outline=outline, width=1)
        self.canvas.create_oval(x2 - radius * 2, y1, x2, y1 + radius * 2, fill=fill, outline=outline, width=1)
        self.canvas.create_oval(x1, y2 - radius * 2, x1 + radius * 2, y2, fill=fill, outline=outline, width=1)
        self.canvas.create_oval(x2 - radius * 2, y2 - radius * 2, x2, y2, fill=fill, outline=outline, width=1)
        self.canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline="")
        self.canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=fill, outline="")
        self.canvas.create_line(x1 + radius, y1, x2 - radius, y1, fill=outline, width=1)
        self.canvas.create_line(x1 + radius, y2, x2 - radius, y2, fill=outline, width=1)
        self.canvas.create_line(x1, y1 + radius, x1, y2 - radius, fill=outline, width=1)
        self.canvas.create_line(x2, y1 + radius, x2, y2 - radius, fill=outline, width=1)
        self.canvas.create_polygon([118, y2 - 2, 130, y2 + 12, 143, y2 - 2], fill=fill, outline=outline, width=1)
        self.canvas.create_arc(x1 + 17, y1 + 9, x2 - 17, y2 - 8, start=22, extent=136, style=tk.ARC, outline=highlight, width=1)
        self.canvas.create_oval(x1 + 15, y1 + 11, x1 + 20, y1 + 16, fill=highlight, outline="")

    def animate(self) -> None:
        self.tick += 1
        self.update_pomodoro()
        if self.tick % 900 == 0:
            self.change_mood()
        if self.tick % 90 == 0:
            self.maybe_shift_mood()
        if self.tick % 120 == 0:
            self.maybe_proactive_interaction()
        if self.tick % 150 == 0:
            self.maybe_auto_action()
        self.update_drop()
        self.maybe_walk()
        self.draw_pet()
        self.root.after(FPS_MS, self.animate)

    def quit(self) -> None:
        try:
            self.tracker.sample()
            self.tracker.save()
        finally:
            self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    DesktopPet().run()
