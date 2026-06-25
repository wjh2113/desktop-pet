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
DATA_DIR = Path(__file__).with_name("data")
RECOGNIZER_SCRIPT = Path(__file__).with_name("scripts") / "recognize-once.ps1"
FOCUS_SECONDS = 25 * 60
BREAK_SECONDS = 5 * 60


@dataclass
class Mood:
    name: str
    body: str
    cheek: str
    message: str


@dataclass
class WindowInfo:
    title: str
    process: str


MOODS = [
    Mood("happy", "#ffd1dc", "#ff8fb3", "\u4eca\u5929\u4e5f\u8981\u8d34\u8d34\u3002"),
    Mood("curious", "#c7f0ff", "#6ec7e8", "\u4f60\u5728\u505a\u4ec0\u4e48\u5440\uff1f"),
    Mood("sleepy", "#d9d1ff", "#a697ff", "\u6211\u5148\u772f\u4e00\u5c0f\u4f1a\u513f\u3002"),
    Mood("hungry", "#ffe4a3", "#ffbd59", "\u60f3\u5403\u5c0f\u997c\u5e72\u3002"),
]


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

        self.width = 260
        self.height = 230
        self.canvas = tk.Canvas(self.root, width=self.width, height=self.height, bg=TRANSPARENT, highlightthickness=0)
        self.canvas.pack()

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.x = screen_w - self.width - 80
        self.y = screen_h - self.height - 120
        self.root.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")

        self.tick = 0
        self.mood = random.choice(MOODS)
        self.message = self.mood.message
        self.message_until = 180
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

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="\u6295\u5582", command=self.feed)
        self.menu.add_command(label="\u73a9\u4e00\u4f1a\u513f", command=self.play)
        self.menu.add_command(label="Q\u5f39\u4e0b\u843d", command=self.drop_from_top)
        self.menu.add_command(label="\u7761\u4e00\u4f1a\u513f", command=self.nap)
        self.menu.add_separator()
        self.menu.add_command(label="\u5f00\u59cb\u756a\u8304\u949f", command=self.start_pomodoro)
        self.menu.add_command(label="\u6682\u505c\u756a\u8304\u949f", command=self.pause_pomodoro)
        self.menu.add_command(label="\u91cd\u7f6e\u756a\u8304\u949f", command=self.reset_pomodoro)
        self.menu.add_separator()
        self.menu.add_command(label="\u548c\u840c\u5ba0\u5bf9\u8bdd", command=self.open_chat)
        self.menu.add_command(label="\u4eca\u65e5\u65f6\u95f4\u7edf\u8ba1", command=self.open_stats)
        self.menu.add_separator()
        self.menu.add_command(label="\u9000\u51fa", command=self.quit)

        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)
        self.canvas.bind("<Double-Button-1>", self.change_mood)
        self.canvas.bind("<Button-3>", self.show_menu)
        self.canvas.bind("<Enter>", lambda _event: self.say("\u6478\u6478\u5934\uff1f"))

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

    def say(self, text: str, duration: int = 150) -> None:
        self.message = text
        self.message_until = duration

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

        def add_burst(duration: float, start_freq: float, end_freq: float, volume: float, decay: float) -> None:
            total = int(sample_rate * duration)
            for index in range(total):
                t = index / sample_rate
                progress = index / max(total - 1, 1)
                freq = start_freq + (end_freq - start_freq) * progress
                envelope = math.exp(-decay * progress)
                tone = math.sin(2 * math.pi * freq * t)
                soft_click = math.sin(2 * math.pi * freq * 2.01 * t) * 0.22
                samples.append(int((tone + soft_click) * envelope * volume))

        impact = min(max(speed / 24, 0.55), 1.0)
        add_burst(0.075, 180, 115, 12000 * impact, 5.4)
        samples.extend([0] * int(sample_rate * 0.018))
        add_burst(0.105, 520, 760, 7800 * impact, 4.2)
        self.play_wave_sound(samples, sample_rate)

    def change_mood(self, _event: tk.Event | None = None) -> None:
        current = self.mood
        choices = [mood for mood in MOODS if mood != current]
        self.mood = random.choice(choices)
        self.is_sleeping = self.mood.name == "sleepy"
        self.say(self.mood.message)

    def feed(self) -> None:
        self.mood = MOODS[0]
        self.is_sleeping = False
        self.say("\u55f7\u545c\uff0c\u8c22\u8c22\u6295\u5582\uff01", 210)
        self.play_tone(784, 60)

    def play(self) -> None:
        self.mood = MOODS[1]
        self.is_sleeping = False
        self.say("\u6765\u73a9\u8ffd\u5149\u70b9\uff01", 210)
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
        self.is_sleeping = False
        self.squash = -0.18
        self.say("\u54bb\u2014\u2014\u63a5\u4f4f\u6211\uff01", 170)
        self.play_drop_start_sound()
        self.root.geometry(f"+{self.x}+{self.y}")

    def nap(self) -> None:
        self.mood = MOODS[2]
        self.is_sleeping = True
        self.drop_active = False
        self.say("\u665a\u5b89\u4e00\u5206\u949f\u3002", 240)

    def start_pomodoro(self) -> None:
        self.pomodoro_running = True
        self.pomodoro_last_tick = time.time()
        self.speak("\u756a\u8304\u949f\u5f00\u59cb\uff0c\u6211\u966a\u4f60\u4e13\u6ce8\u3002")

    def pause_pomodoro(self) -> None:
        self.update_pomodoro()
        self.pomodoro_running = False
        self.say("\u756a\u8304\u949f\u5df2\u6682\u505c\u3002", 180)

    def reset_pomodoro(self) -> None:
        self.pomodoro_mode = "focus"
        self.pomodoro_running = False
        self.pomodoro_remaining = FOCUS_SECONDS
        self.say("\u756a\u8304\u949f\u91cd\u7f6e\u597d\u4e86\u3002", 180)

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
            self.speak("\u4e00\u4e2a\u756a\u8304\u5b8c\u6210\uff01\u8d77\u6765\u6d3b\u52a8\u4e94\u5206\u949f\u5427\u3002")
        else:
            self.pomodoro_mode = "focus"
            self.pomodoro_remaining = FOCUS_SECONDS
            self.speak("\u4f11\u606f\u7ed3\u675f\uff0c\u4e0b\u4e00\u8f6e\u5f00\u59cb\u5566\u3002")

    def pomodoro_label(self) -> str:
        minutes, seconds = divmod(int(max(0, self.pomodoro_remaining)), 60)
        prefix = "\u4e13\u6ce8" if self.pomodoro_mode == "focus" else "\u4f11\u606f"
        state = "\u25b6" if self.pomodoro_running else "\u23f8"
        return f"{state} {prefix} {minutes:02d}:{seconds:02d}"

    def activity_loop(self) -> None:
        try:
            self.tracker.sample()
            now = time.time()
            if now - self.last_tracker_save > 30:
                self.tracker.save()
                self.last_tracker_save = now
        finally:
            self.root.after(1000, self.activity_loop)

    def open_chat(self) -> None:
        if self.chat_window and self.chat_window.winfo_exists():
            self.chat_window.lift()
            return

        win = tk.Toplevel(self.root)
        self.chat_window = win
        win.title("\u548c\u684c\u9762\u840c\u5ba0\u5bf9\u8bdd")
        win.geometry("420x360")
        win.attributes("-topmost", True)

        history = tk.Text(win, wrap="word", height=15, padx=8, pady=8)
        history.pack(fill="both", expand=True)
        entry = tk.Entry(win)
        entry.pack(fill="x", padx=8, pady=(0, 8))

        buttons = tk.Frame(win)
        buttons.pack(fill="x", padx=8, pady=(0, 8))

        def add_line(who: str, text: str) -> None:
            history.insert("end", f"{who}: {text}\n")
            history.see("end")

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
            self.say("\u6211\u5728\u542c\uff0c\u8bf7\u8bf4\u8bdd\u3002", 210)

            def worker() -> None:
                try:
                    recognized = self.recognize_speech_once()
                except Exception as exc:
                    self.root.after(0, lambda: add_line("\u7cfb\u7edf", f"\u8bed\u97f3\u8bc6\u522b\u5931\u8d25\uff1a{exc}"))
                    self.root.after(0, lambda: self.say("\u6211\u6ca1\u542c\u6e05\u695a\uff0c\u518d\u8bd5\u4e00\u6b21\uff1f", 180))
                else:
                    self.root.after(0, lambda: handle_user_text(recognized))
                finally:
                    self.root.after(0, lambda: voice_button.configure(state="normal", text="\u8bed\u97f3\u8f93\u5165"))

            threading.Thread(target=worker, daemon=True).start()

        tk.Button(buttons, text="\u53d1\u9001", command=send).pack(side="left")
        voice_button = tk.Button(buttons, text="\u8bed\u97f3\u8f93\u5165", command=voice_input)
        voice_button.pack(side="left", padx=6)
        tk.Button(buttons, text="\u64ad\u62a5\u72b6\u6001", command=lambda: self.speak(self.daily_summary_sentence())).pack(side="left", padx=6)
        tk.Button(buttons, text="\u5173\u95ed", command=win.destroy).pack(side="right")
        entry.bind("<Return>", lambda _event: send())
        add_line("\u840c\u5ba0", "\u6211\u5728\uff0c\u53ef\u4ee5\u6253\u5b57\u6216\u70b9\u51fb\u8bed\u97f3\u8f93\u5165\u8ddf\u6211\u8bf4\u8bdd\u3002\u6211\u4f1a\u7528\u58f0\u97f3\u56de\u4f60\u3002")
        entry.focus_set()

    def pet_reply(self, text: str) -> str:
        lowered = text.lower()
        if "\u756a\u8304" in text or "pomodoro" in lowered:
            return f"\u5f53\u524d\u756a\u8304\u949f\uff1a{self.pomodoro_label()}\u3002"
        if "\u65f6\u95f4" in text or "\u7edf\u8ba1" in text or "stats" in lowered:
            return self.daily_summary_sentence()
        if "\u7d2f" in text or "\u56f0" in text:
            return "\u90a3\u5c31\u7ad9\u8d77\u6765\u559d\u53e3\u6c34\uff0c\u6211\u7ed9\u4f60\u770b\u7740\u949f\u3002"
        if "\u4f60\u597d" in text or "hello" in lowered or "hi" == lowered:
            return "\u4f60\u597d\u5440\uff0c\u6211\u5728\u684c\u9762\u966a\u4f60\u3002"
        if "\u5f00\u59cb" in text:
            self.start_pomodoro()
            return "\u597d\uff0c\u6211\u5df2\u7ecf\u5e2e\u4f60\u5f00\u59cb\u756a\u8304\u949f\u3002"
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

    def open_stats(self) -> None:
        self.tracker.save()
        if self.stats_window and self.stats_window.winfo_exists():
            self.stats_window.destroy()

        win = tk.Toplevel(self.root)
        self.stats_window = win
        win.title("\u4eca\u65e5\u65f6\u95f4\u7edf\u8ba1")
        win.geometry("560x440")
        win.attributes("-topmost", True)

        text = tk.Text(win, wrap="word", padx=10, pady=10)
        text.pack(fill="both", expand=True)
        text.insert("end", f"\u65e5\u671f\uff1a{self.tracker.current_day}\n")
        text.insert("end", f"\u6570\u636e\u6587\u4ef6\uff1a{self.tracker.path}\n\n")
        text.insert("end", "\u5e94\u7528\u8017\u65f6\u6392\u884c\n")
        for index, (name, seconds) in enumerate(self.tracker.top_apps(10), start=1):
            text.insert("end", f"{index}. {name}: {format_seconds(seconds)}\n")

        text.insert("end", "\n\u7a97\u53e3\u8017\u65f6\u6392\u884c\n")
        for index, item in enumerate(self.tracker.top_windows(12), start=1):
            title = item.get("title", "")[:70]
            text.insert("end", f"{index}. {item.get('process')}: {format_seconds(item.get('seconds', 0))} - {title}\n")
        text.configure(state="disabled")

        bottom = tk.Frame(win)
        bottom.pack(fill="x", padx=8, pady=8)
        tk.Button(bottom, text="\u5237\u65b0", command=self.open_stats).pack(side="left")
        tk.Button(bottom, text="\u64ad\u62a5\u603b\u7ed3", command=lambda: self.speak(self.daily_summary_sentence())).pack(side="left", padx=6)
        tk.Button(bottom, text="\u5173\u95ed", command=win.destroy).pack(side="right")

    def maybe_walk(self) -> None:
        if self.drag_start is not None or self.is_sleeping or self.drop_active:
            return

        screen_w = self.root.winfo_screenwidth()
        if self.walk_timer <= 0 and random.random() < 0.008:
            self.walk_timer = random.randint(70, 180)
            self.walk_dx = random.choice([-2, -1, 1, 2])

        if self.walk_timer > 0:
            self.x += self.walk_dx
            self.walk_timer -= 1
            if self.x < 10 or self.x > screen_w - self.width - 10:
                self.walk_dx *= -1
            self.root.geometry(f"+{self.x}+{self.y}")

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
                self.say("boing\uff01\u843d\u5730\u6210\u529f\u3002", 170)
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

    def draw_status(self) -> None:
        label = self.pomodoro_label()
        self.canvas.create_rectangle(48, 196, 212, 222, fill="#ffffff", outline="#3d2f37", width=2)
        self.canvas.create_text(130, 209, text=label, fill="#3d2f37", font=("Segoe UI", 10, "bold"))

    def draw_shadow(self, cx: float, cy: float) -> None:
        width_boost = 1 + max(self.squash, 0) * 0.65
        self.canvas.create_oval(cx - 68 * width_boost, cy + 66, cx + 68 * width_boost, cy + 88, fill="#000000", outline="", stipple="gray50")

    def draw_tail(self, cx: float, cy: float, wag: float) -> None:
        tail_lift = self.squash * 8
        points = [cx + 62, cy + 22, cx + 95, cy - 2 + wag - tail_lift, cx + 82, cy - 36 + wag - tail_lift, cx + 54, cy - 12]
        self.canvas.create_polygon(points, fill=self.mood.body, outline="#3d2f37", width=3, smooth=True)
        self.canvas.create_oval(cx + 67, cy - 45 + wag - tail_lift, cx + 93, cy - 18 + wag - tail_lift, fill="#ffffff", outline="#3d2f37", width=3)

    def draw_body(self, cx: float, cy: float) -> None:
        body_w = 67 * (1 + self.squash * 0.28)
        body_top = 50 * (1 - self.squash * 0.34)
        body_bottom = 78 * (1 - self.squash * 0.24)
        belly_w = 44 * (1 + self.squash * 0.22)
        self.canvas.create_oval(cx - body_w, cy - body_top, cx + body_w, cy + body_bottom, fill=self.mood.body, outline="#3d2f37", width=3)
        self.canvas.create_oval(cx - belly_w, cy + 4, cx + belly_w, cy + 70 * (1 - self.squash * 0.18), fill="#fff8fb", outline="")

    def draw_ears(self, cx: float, cy: float) -> None:
        ear_squish = max(self.squash, 0) * 12
        left = [cx - 51, cy - 36, cx - 35, cy - 82 + ear_squish, cx - 8, cy - 41]
        right = [cx + 51, cy - 36, cx + 35, cy - 82 + ear_squish, cx + 8, cy - 41]
        self.canvas.create_polygon(left, fill=self.mood.body, outline="#3d2f37", width=3, smooth=True)
        self.canvas.create_polygon(right, fill=self.mood.body, outline="#3d2f37", width=3, smooth=True)
        self.canvas.create_polygon([cx - 39, cy - 42, cx - 34, cy - 65 + ear_squish, cx - 20, cy - 44], fill="#fff8fb", outline="")
        self.canvas.create_polygon([cx + 39, cy - 42, cx + 34, cy - 65 + ear_squish, cx + 20, cy - 44], fill="#fff8fb", outline="")

    def draw_face(self, cx: float, cy: float, blink: bool) -> None:
        face_drop = max(self.squash, 0) * 5
        eye_y = cy - 7 + face_drop
        if self.is_sleeping:
            self.canvas.create_arc(cx - 34, eye_y - 4, cx - 14, eye_y + 13, start=190, extent=150, style=tk.ARC, outline="#3d2f37", width=3)
            self.canvas.create_arc(cx + 14, eye_y - 4, cx + 34, eye_y + 13, start=200, extent=150, style=tk.ARC, outline="#3d2f37", width=3)
        elif blink:
            self.canvas.create_line(cx - 35, eye_y + 2, cx - 16, eye_y + 2, fill="#3d2f37", width=3, capstyle=tk.ROUND)
            self.canvas.create_line(cx + 16, eye_y + 2, cx + 35, eye_y + 2, fill="#3d2f37", width=3, capstyle=tk.ROUND)
        else:
            self.canvas.create_oval(cx - 35, eye_y - 12, cx - 15, eye_y + 14, fill="#3d2f37", outline="")
            self.canvas.create_oval(cx + 15, eye_y - 12, cx + 35, eye_y + 14, fill="#3d2f37", outline="")
            self.canvas.create_oval(cx - 29, eye_y - 8, cx - 23, eye_y - 2, fill="#ffffff", outline="")
            self.canvas.create_oval(cx + 21, eye_y - 8, cx + 27, eye_y - 2, fill="#ffffff", outline="")

        self.canvas.create_oval(cx - 9, cy + 12 + face_drop, cx + 9, cy + 22 + face_drop, fill="#3d2f37", outline="")
        self.canvas.create_arc(cx - 22, cy + 14 + face_drop, cx, cy + 38 + face_drop, start=200, extent=130, style=tk.ARC, outline="#3d2f37", width=3)
        self.canvas.create_arc(cx, cy + 14 + face_drop, cx + 22, cy + 38 + face_drop, start=210, extent=130, style=tk.ARC, outline="#3d2f37", width=3)
        self.canvas.create_oval(cx - 52, cy + 14 + face_drop, cx - 32, cy + 29 + face_drop, fill=self.mood.cheek, outline="")
        self.canvas.create_oval(cx + 32, cy + 14 + face_drop, cx + 52, cy + 29 + face_drop, fill=self.mood.cheek, outline="")

    def draw_paws(self, cx: float, cy: float) -> None:
        paw_drop = max(self.squash, 0) * 11
        self.canvas.create_oval(cx - 55, cy + 52 + paw_drop, cx - 20, cy + 84 + paw_drop, fill=self.mood.body, outline="#3d2f37", width=3)
        self.canvas.create_oval(cx + 20, cy + 52 + paw_drop, cx + 55, cy + 84 + paw_drop, fill=self.mood.body, outline="#3d2f37", width=3)
        self.canvas.create_line(cx - 45, cy + 69 + paw_drop, cx - 32, cy + 70 + paw_drop, fill="#3d2f37", width=2, capstyle=tk.ROUND)
        self.canvas.create_line(cx + 32, cy + 70 + paw_drop, cx + 45, cy + 69 + paw_drop, fill="#3d2f37", width=2, capstyle=tk.ROUND)

    def draw_bubble(self, text: str) -> None:
        x1, y1, x2, y2 = 28, 10, 232, 50
        self.canvas.create_oval(x1, y1, x1 + 28, y1 + 28, fill="#ffffff", outline="#3d2f37", width=2)
        self.canvas.create_oval(x2 - 28, y1, x2, y1 + 28, fill="#ffffff", outline="#3d2f37", width=2)
        self.canvas.create_rectangle(x1 + 14, y1, x2 - 14, y1 + 28, fill="#ffffff", outline="")
        self.canvas.create_line(x1 + 14, y1, x2 - 14, y1, fill="#3d2f37", width=2)
        self.canvas.create_line(x1 + 14, y1 + 28, x2 - 14, y1 + 28, fill="#3d2f37", width=2)
        self.canvas.create_polygon([116, 38, 128, 58, 141, 38], fill="#ffffff", outline="#3d2f37", width=2)
        self.canvas.create_text(130, 25, text=text, fill="#3d2f37", font=("Microsoft YaHei UI", 10, "bold"))

    def animate(self) -> None:
        self.tick += 1
        self.update_pomodoro()
        if self.tick % 900 == 0:
            self.change_mood()
        if self.tick % 420 == 0 and not self.is_sleeping:
            self.say(random.choice(["\u6211\u5728\u966a\u4f60\u5de5\u4f5c\u3002", "\u8bb0\u5f97\u559d\u6c34\u3002", "\u53cc\u51fb\u6211\u4f1a\u53d8\u5fc3\u60c5\u3002", "\u53f3\u952e\u6709\u83dc\u5355\u54e6\u3002"]))
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
