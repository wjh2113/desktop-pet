from __future__ import annotations

import ctypes
import io
import json
import math
import random
import struct
import subprocess
import threading
import time
import tkinter as tk
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
RECOGNIZER_SCRIPT = Path(__file__).with_name("scripts") / "recognize-once.ps1"
FOCUS_SECONDS = 25 * 60
BREAK_SECONDS = 5 * 60
EYE_REMINDER_SECONDS = 20 * 60
STAND_REMINDER_SECONDS = 45 * 60
DISTRACTION_COOLDOWN_SECONDS = 90
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


class DesktopPet:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("\u684c\u9762\u840c\u5ba0")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT)
        self.root.wm_attributes("-transparentcolor", TRANSPARENT)

        self.ui_scale = 0.45
        self.logical_width = 260
        self.logical_height = 240
        self.width = int(self.logical_width * self.ui_scale)
        self.height = int(self.logical_height * self.ui_scale)
        self.canvas = tk.Canvas(self.root, width=self.width, height=self.height, bg=TRANSPARENT, highlightthickness=0)
        self.canvas.pack()

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.x = screen_w - self.width - 80
        self.y = screen_h - self.height - 120
        self.root.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")

        self.tick = 0
        self.mood = random.choice(MOODS)
        self.pet_skin = "cat"
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
        self.last_tracker_save = time.time()
        self.chat_window: tk.Toplevel | None = None
        self.stats_window: tk.Toplevel | None = None
        self.tasks_window: tk.Toplevel | None = None
        self.panel_window: tk.Toplevel | None = None
        self.panel_visible = False
        self.tasks = self.load_tasks()
        self.active_stretch_seconds = 0
        self.last_eye_reminder = time.time()
        self.last_stand_reminder = time.time()
        self.last_distraction_reminder = 0.0
        self.next_proactive_at = time.time() + random.randint(240, 420)

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
        self.menu.add_command(label="\u5f00\u59cb\u756a\u8304\u949f", command=self.start_pomodoro)
        self.menu.add_command(label="\u6682\u505c\u756a\u8304\u949f", command=self.pause_pomodoro)
        self.menu.add_command(label="\u91cd\u7f6e\u756a\u8304\u949f", command=self.reset_pomodoro)
        self.menu.add_separator()
        self.menu.add_command(label="\u548c\u840c\u5ba0\u5bf9\u8bdd", command=self.open_chat)
        self.menu.add_command(label="\u663e\u793a/\u9690\u85cf\u5c0f\u9762\u677f", command=self.toggle_panel)
        self.menu.add_command(label="\u4eca\u65e5\u770b\u677f", command=self.open_stats)
        self.menu.add_command(label="\u4eca\u65e5\u4e09\u4ef6\u4e8b", command=self.open_tasks)
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

    def toggle_panel(self) -> None:
        self.panel_visible = not self.panel_visible
        if self.panel_visible:
            self.open_panel()
        elif self.panel_window and self.panel_window.winfo_exists():
            self.panel_window.destroy()

    def open_panel(self) -> None:
        if self.panel_window and self.panel_window.winfo_exists():
            self.panel_window.lift()
            self.refresh_panel()
            return

        win = tk.Toplevel(self.root)
        self.panel_window = win
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#f7f4ef")
        win.geometry(f"250x156+{self.x + self.width + 12}+{max(20, self.y)}")

        frame = tk.Frame(win, bg="#f7f4ef", highlightthickness=1, highlightbackground="#d8d1c7")
        frame.pack(fill="both", expand=True)
        self.panel_title = tk.Label(frame, text="\u840c\u5ba0\u5c0f\u9762\u677f", bg="#f7f4ef", fg="#2f2925", font=("Microsoft YaHei UI", 11, "bold"))
        self.panel_title.pack(anchor="w", padx=10, pady=(8, 2))
        self.panel_status = tk.Label(frame, text="", bg="#f7f4ef", fg="#5d544a", justify="left", font=("Microsoft YaHei UI", 9))
        self.panel_status.pack(anchor="w", padx=10)
        buttons = tk.Frame(frame, bg="#f7f4ef")
        buttons.pack(fill="x", padx=8, pady=(8, 6))
        tk.Button(buttons, text="\u756a\u8304", command=self.start_pomodoro).pack(side="left", padx=2)
        tk.Button(buttons, text="\u4efb\u52a1", command=self.open_tasks).pack(side="left", padx=2)
        tk.Button(buttons, text="\u770b\u677f", command=self.open_stats).pack(side="left", padx=2)
        tk.Button(buttons, text="\u5bf9\u8bdd", command=self.open_chat).pack(side="left", padx=2)
        tk.Button(frame, text="\u5173\u95ed\u5c0f\u9762\u677f", command=self.toggle_panel).pack(anchor="e", padx=8, pady=(0, 8))
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
        self.panel_window.geometry(f"250x156+{self.x + self.width + 12}+{max(20, self.y)}")
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
        finally:
            self.root.after(1000, self.activity_loop)

    def update_focus_guard(self) -> None:
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

    def update_wellbeing_reminders(self) -> None:
        now = time.time()
        info = self.tracker.get_active_window()
        if info.process in {"desktop", "unknown"}:
            self.active_stretch_seconds = 0
            return

        self.active_stretch_seconds += 1
        if self.active_stretch_seconds >= EYE_REMINDER_SECONDS and now - self.last_eye_reminder >= EYE_REMINDER_SECONDS:
            self.last_eye_reminder = now
            self.set_mood("worried", "\u773c\u775b\u8981\u4f11\u606f\u4e00\u4e0b\u3002", 190)
            self.speak("\u770b\u5c4f\u5e55\u4e8c\u5341\u5206\u949f\u5566\uff0c\u770b\u770b\u8fdc\u5904\uff0c\u8ba9\u773c\u775b\u653e\u677e\u4e00\u4e0b\u3002")

        if self.active_stretch_seconds >= STAND_REMINDER_SECONDS and now - self.last_stand_reminder >= STAND_REMINDER_SECONDS:
            self.last_stand_reminder = now
            self.active_stretch_seconds = 0
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
        win.geometry("520x300")
        win.attributes("-topmost", True)
        win.configure(bg="#f7f4ef")

        tk.Label(win, text="\u4eca\u65e5\u4e09\u4ef6\u4e8b", bg="#f7f4ef", fg="#2f2925", font=("Microsoft YaHei UI", 17, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
        tk.Label(win, text="\u628a\u4eca\u5929\u6700\u91cd\u8981\u7684\u4e09\u4ef6\u4e8b\u653e\u5728\u8fd9\u91cc\uff0c\u840c\u5ba0\u4f1a\u5728\u756a\u8304\u949f\u540e\u5e2e\u4f60\u590d\u76d8\u3002", bg="#f7f4ef", fg="#7b7067", font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=16, pady=(0, 12))

        rows = tk.Frame(win, bg="#f7f4ef")
        rows.pack(fill="both", expand=True, padx=16)
        entries: list[tk.Entry] = []
        done_vars: list[tk.BooleanVar] = []

        for index in range(3):
            task = self.tasks[index] if index < len(self.tasks) else {"text": "", "done": False}
            row = tk.Frame(rows, bg="#ffffff", highlightthickness=1, highlightbackground="#d8d1c7")
            row.pack(fill="x", pady=5)
            done_var = tk.BooleanVar(value=bool(task.get("done")))
            done_vars.append(done_var)
            tk.Checkbutton(row, variable=done_var, bg="#ffffff", activebackground="#ffffff").pack(side="left", padx=8)
            tk.Label(row, text=f"{index + 1}.", bg="#ffffff", fg="#6b5844", font=("Segoe UI", 10, "bold")).pack(side="left")
            entry = tk.Entry(row, relief="flat", font=("Microsoft YaHei UI", 11))
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
            mood = "proud" if done_count else "curious"
            self.set_mood(mood, f"\u4e09\u4ef6\u4e8b\u5df2\u4fdd\u5b58\uff0c\u5b8c\u6210 {done_count}/3\u3002", 200)
            if close:
                win.destroy()

        bottom = tk.Frame(win, bg="#f7f4ef")
        bottom.pack(fill="x", padx=16, pady=12)
        tk.Button(bottom, text="\u4fdd\u5b58", command=lambda: save_and_close(False)).pack(side="left")
        tk.Button(bottom, text="\u4fdd\u5b58\u5e76\u5173\u95ed", command=lambda: save_and_close(True)).pack(side="left", padx=8)
        tk.Button(bottom, text="\u5173\u95ed", command=win.destroy).pack(side="right")
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

        report_path.write_text("\n".join(lines), encoding="utf-8")
        self.set_mood("proud", "\u4eca\u65e5\u603b\u7ed3\u5df2\u751f\u6210\u3002", 210)
        self.speak("\u4eca\u65e5\u603b\u7ed3\u5df2\u751f\u6210\u3002")
        self.open_report_window(report_path)
        return report_path

    def open_report_window(self, report_path: Path) -> None:
        win = tk.Toplevel(self.root)
        win.title("\u4eca\u65e5\u603b\u7ed3")
        win.geometry("680x520")
        win.attributes("-topmost", True)
        text = tk.Text(win, wrap="word", padx=12, pady=12, font=("Microsoft YaHei UI", 10))
        text.pack(fill="both", expand=True)
        text.insert("end", report_path.read_text(encoding="utf-8"))
        text.configure(state="disabled")
        bottom = tk.Frame(win)
        bottom.pack(fill="x", padx=10, pady=10)
        tk.Label(bottom, text=str(report_path), fg="#7b7067").pack(side="left")
        tk.Button(bottom, text="\u5173\u95ed", command=win.destroy).pack(side="right")

    def open_chat(self) -> None:
        if self.chat_window and self.chat_window.winfo_exists():
            self.chat_window.lift()
            return

        win = tk.Toplevel(self.root)
        self.chat_window = win
        win.title("\u548c\u684c\u9762\u840c\u5ba0\u5bf9\u8bdd")
        chat_w, chat_h = 310, 230
        screen_h = self.root.winfo_screenheight()
        chat_x = min(max(10, self.x - 86), self.root.winfo_screenwidth() - chat_w - 10)
        chat_y = self.y + self.height + 10
        if chat_y + chat_h > screen_h - 20:
            chat_y = max(20, self.y - chat_h - 10)
        win.geometry(f"{chat_w}x{chat_h}+{chat_x}+{chat_y}")
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.9)
        win.configure(bg="#f7f4ef")

        header = tk.Frame(win, bg="#f7f4ef")
        header.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(header, text="\u548c\u840c\u5ba0\u8bf4\u8bdd", bg="#f7f4ef", fg="#2f2925", font=("Microsoft YaHei UI", 11, "bold")).pack(side="left")
        tk.Button(header, text="\u00d7", command=win.destroy, width=3, relief="flat", bg="#f7f4ef").pack(side="right")
        drag_offset = {"x": 0, "y": 0}

        def start_window_drag(event: tk.Event) -> None:
            drag_offset["x"] = event.x_root - win.winfo_x()
            drag_offset["y"] = event.y_root - win.winfo_y()

        def drag_window(event: tk.Event) -> None:
            win.geometry(f"+{event.x_root - drag_offset['x']}+{event.y_root - drag_offset['y']}")

        header.bind("<ButtonPress-1>", start_window_drag)
        header.bind("<B1-Motion>", drag_window)

        history = tk.Text(
            win,
            wrap="word",
            height=6,
            padx=8,
            pady=8,
            bg="#fffdf8",
            fg="#3f342f",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#dfd5cb",
            font=("Microsoft YaHei UI", 9),
        )
        history.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        history.tag_configure("pet", lmargin1=6, lmargin2=6, rmargin=42, spacing1=3, spacing3=4, background="#fff2f6", foreground="#4d3b38")
        history.tag_configure("you", lmargin1=48, lmargin2=48, rmargin=6, spacing1=3, spacing3=4, background="#eef7ff", foreground="#2f3d4a")
        history.tag_configure("system", lmargin1=16, lmargin2=16, rmargin=16, spacing1=3, spacing3=4, background="#f1eee8", foreground="#776a61")
        history.tag_configure("name", foreground="#8f6b5f", font=("Microsoft YaHei UI", 9, "bold"))

        input_card = tk.Frame(win, bg="#ffffff", highlightthickness=1, highlightbackground="#dfd5cb")
        input_card.pack(fill="x", padx=10, pady=(0, 6))
        entry = tk.Entry(input_card, relief="flat", bg="#ffffff", fg="#2f2925", font=("Microsoft YaHei UI", 10))
        entry.pack(fill="x", padx=8, pady=6)

        buttons = tk.Frame(win, bg="#f7f4ef")
        buttons.pack(fill="x", padx=10, pady=(0, 8))

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
            reply = self.pet_reply(text)
            add_line("\u840c\u5ba0", reply)
            self.speak(reply)

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

        tk.Button(buttons, text="\u53d1\u9001", command=send, width=6).pack(side="left")
        voice_button = tk.Button(buttons, text="\u8bed\u97f3/\u547d\u4ee4", command=voice_input, width=10)
        voice_button.pack(side="left", padx=5)
        tk.Button(buttons, text="\u72b6\u6001", command=lambda: self.speak(self.daily_summary_sentence()), width=6).pack(side="left")
        entry.bind("<Return>", lambda _event: send())
        add_line("\u840c\u5ba0", "\u6211\u5728\uff0c\u53ef\u4ee5\u804a\u5929\uff0c\u4e5f\u53ef\u4ee5\u8bf4\u547d\u4ee4\u3002")
        entry.focus_set()

    def pet_reply(self, text: str) -> str:
        command_reply = self.handle_command(text)
        if command_reply:
            return command_reply
        return self.casual_reply(text)

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
        card = tk.Canvas(parent, width=218, height=92, bg="#f7f4ef", highlightthickness=0)
        card.create_rectangle(4, 4, 214, 88, fill="#ffffff", outline="#d8d1c7", width=1)
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
        win.geometry("780x720")
        win.minsize(740, 640)
        win.attributes("-topmost", True)
        win.configure(bg="#f7f4ef")

        header = tk.Frame(win, bg="#f7f4ef")
        header.pack(fill="x", padx=18, pady=(16, 10))
        tk.Label(header, text="\u4eca\u65e5\u770b\u677f", bg="#f7f4ef", fg="#2f2925", font=("Microsoft YaHei UI", 19, "bold")).pack(anchor="w")
        tk.Label(header, text=f"\u65f6\u95f4\u7edf\u8ba1\u3001\u4e09\u4ef6\u4e8b\u548c\u4eca\u65e5\u603b\u7ed3\u653e\u5728\u4e00\u8d77    {self.tracker.current_day}", bg="#f7f4ef", fg="#7b7067", font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(3, 0))

        apps = self.tracker.top_apps(6)
        windows = self.tracker.top_windows(6)
        total_seconds = self.total_activity_seconds()
        app_count = len(self.tracker.data.get("apps", {}))
        window_count = len(self.tracker.data.get("windows", {}))
        done_count = sum(1 for task in self.tasks if task.get("done"))
        suggestion = self.dashboard_suggestion(done_count, apps)

        cards = tk.Frame(win, bg="#f7f4ef")
        cards.pack(fill="x", padx=18, pady=(0, 12))
        self.make_stat_card(cards, "\u603b\u8bb0\u5f55\u65f6\u957f", format_seconds(total_seconds), "#4c78a8").pack(side="left", padx=(0, 12))
        self.make_stat_card(cards, "\u6d89\u53ca\u5e94\u7528", f"{app_count} \u4e2a", "#54a24b").pack(side="left", padx=(0, 12))
        self.make_stat_card(cards, "\u4e09\u4ef6\u4e8b", f"{done_count}/3", "#e45756").pack(side="left")

        chart = tk.Canvas(win, width=736, height=258, bg="#ffffff", highlightthickness=1, highlightbackground="#d8d1c7")
        chart.pack(fill="x", padx=18, pady=(0, 12))
        self.draw_app_chart(chart, apps)

        insight_row = tk.Frame(win, bg="#f7f4ef")
        insight_row.pack(fill="x", padx=18, pady=(0, 12))
        tasks = tk.Canvas(insight_row, width=352, height=166, bg="#ffffff", highlightthickness=1, highlightbackground="#d8d1c7")
        tasks.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.draw_task_summary(tasks, done_count)
        advice = tk.Canvas(insight_row, width=352, height=166, bg="#ffffff", highlightthickness=1, highlightbackground="#d8d1c7")
        advice.pack(side="left", fill="x", expand=True)
        self.draw_advice_card(advice, suggestion, total_seconds)

        ranking = tk.Canvas(win, width=736, height=226, bg="#ffffff", highlightthickness=1, highlightbackground="#d8d1c7")
        ranking.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        self.draw_window_ranking(ranking, windows)

        bottom = tk.Frame(win, bg="#f7f4ef")
        bottom.pack(fill="x", padx=18, pady=(0, 14))
        tk.Label(bottom, text=f"\u5171 {window_count} \u4e2a\u7a97\u53e3\u8bb0\u5f55", bg="#f7f4ef", fg="#7b7067", font=("Microsoft YaHei UI", 9)).pack(side="left")
        tk.Button(bottom, text="\u5173\u95ed", command=win.destroy).pack(side="right")
        tk.Button(bottom, text="\u5237\u65b0", command=self.open_stats).pack(side="right", padx=6)
        tk.Button(bottom, text="\u751f\u6210 Markdown \u603b\u7ed3", command=self.generate_report).pack(side="right", padx=6)
        tk.Button(bottom, text="\u64ad\u62a5\u603b\u7ed3", command=lambda: self.speak(self.daily_summary_sentence())).pack(side="right")

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

        self.draw_shadow(cx, cy)
        self.draw_tail(cx, cy, wag)
        self.draw_body(cx, cy)
        self.draw_ears(cx, cy)
        self.draw_face(cx, cy, blink)
        self.draw_paws(cx, cy)
        self.draw_status()

        if self.message_until > 0:
            self.draw_bubble(self.message)
            self.message_until -= 1

        if self.is_sleeping:
            z_y = 44 + math.sin(self.tick / 10) * 5
            self.canvas.create_text(188, z_y, text="Z", fill="#7667d6", font=("Segoe UI", 15, "bold"))
            self.canvas.create_text(204, z_y - 14, text="z", fill="#7667d6", font=("Segoe UI", 11, "bold"))

        self.canvas.scale("all", 0, 0, self.ui_scale, self.ui_scale)

    def draw_status(self) -> None:
        label = self.pomodoro_label()
        display = self.fit_text(label, 18)
        self.draw_round_bubble(30, 187, 230, 226, radius=14, tail_at="top", fill="#fffaf0")
        self.canvas.create_text(130, 207, text=display, fill="#4d3b38", font=("Microsoft YaHei UI", 8, "bold"))

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
            self.canvas.create_text(cx - 25, eye_y, text="\u2605", fill="#5a4540", font=("Segoe UI Symbol", 16, "bold"))
            self.canvas.create_text(cx + 25, eye_y, text="\u2605", fill="#5a4540", font=("Segoe UI Symbol", 16, "bold"))
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
        display = self.fit_text(text, 20)
        self.draw_speech_bubble(16, 7, 244, 56)
        self.canvas.create_text(130, 29, text=display, fill="#4d3b38", font=("Microsoft YaHei UI", 10, "bold"))

    def draw_speech_bubble(self, x1: float, y1: float, x2: float, y2: float) -> None:
        fill = "#fffdfb"
        outline = "#d68fa4"
        highlight = "#ffffff"
        shadow = "#ead7d0"
        radius = 18
        self.canvas.create_rectangle(x1 + 4, y1 + 4, x2 + 4, y2 + 4, fill=shadow, outline="")
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
        self.canvas.create_polygon([116, y2 - 3, 130, y2 + 15, 145, y2 - 3], fill=fill, outline=outline, width=2)
        self.canvas.create_arc(x1 + 17, y1 + 9, x2 - 17, y2 - 8, start=22, extent=136, style=tk.ARC, outline=highlight, width=2)
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
