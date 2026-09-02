from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw, ImageFont


# ============================================================
# HAN LAUNCHER
# Clean, keyboard-first Windows launcher
# Python 3.13+
# Dependencies:
#     pip install customtkinter pillow
# ============================================================


APP_TITLE = "HAN LAUNCHER"
APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "HanLauncher"
DATA_FILE = APP_DIR / "apps.json"
SETTINGS_FILE = APP_DIR / "settings.json"
ICON_DIR = APP_DIR / "icons"

APP_DIR.mkdir(parents=True, exist_ok=True)
ICON_DIR.mkdir(parents=True, exist_ok=True)


THEMES = {
    "dark": {
        "bg": "#080B0F",
        "surface": "#0F141A",
        "card": "#141A21",
        "card_hover": "#1A222B",
        "card_selected": "#17283A",
        "border": "#242D36",
        "border_selected": "#4DA3FF",
        "text": "#F4F7FA",
        "muted": "#8A96A3",
        "accent": "#4DA3FF",
        "accent_hover": "#6AB5FF",
        "button": "#171E26",
        "button_hover": "#242D37",
        "danger": "#E05A63",
        "input": "#10161D",
    },
    "light": {
        "bg": "#EEF2F6",
        "surface": "#F8FAFC",
        "card": "#FFFFFF",
        "card_hover": "#F3F6F9",
        "card_selected": "#E4F1FF",
        "border": "#D4DCE5",
        "border_selected": "#2688FF",
        "text": "#14191F",
        "muted": "#687481",
        "accent": "#2688FF",
        "accent_hover": "#4B9BFF",
        "button": "#FFFFFF",
        "button_hover": "#E9EEF3",
        "danger": "#D74C57",
        "input": "#FFFFFF",
    },
}


DEFAULT_SETTINGS = {
    "theme": "dark",
    "animations": True,
    "card_size": "medium",
    "columns": 4,
}


@dataclass
class AppEntry:
    name: str
    path: str


def load_json(path: Path, default):
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def atomic_write_json(path: Path, data) -> bool:
    temp = path.with_suffix(path.suffix + ".tmp")
    try:
        with temp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp, path)
        return True
    except OSError:
        try:
            if temp.exists():
                temp.unlink()
        except OSError:
            pass
        return False


def load_apps() -> list[AppEntry]:
    raw = load_json(DATA_FILE, [])
    if not isinstance(raw, list):
        return []

    result: list[AppEntry] = []
    seen = set()

    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        path = str(item.get("path", "")).strip()
        if not name or not path:
            continue

        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen:
            continue

        seen.add(normalized)
        result.append(AppEntry(name=name, path=path))

    return result


def save_apps(apps: list[AppEntry]) -> bool:
    return atomic_write_json(
        DATA_FILE,
        [asdict(app) for app in apps]
    )


def load_settings() -> dict:
    data = load_json(SETTINGS_FILE, {})
    result = dict(DEFAULT_SETTINGS)

    if isinstance(data, dict):
        result.update(data)

    if result["theme"] not in {"dark", "light"}:
        result["theme"] = "dark"
    if result["card_size"] not in {"small", "medium", "large"}:
        result["card_size"] = "medium"

    try:
        result["columns"] = max(2, min(6, int(result["columns"])))
    except (ValueError, TypeError):
        result["columns"] = 4

    result["animations"] = bool(result["animations"])
    return result


def save_settings(settings: dict) -> bool:
    return atomic_write_json(SETTINGS_FILE, settings)


def theme_colors(settings: dict) -> dict:
    return THEMES["light" if settings["theme"] == "light" else "dark"]


def clean_cache_name(path: str) -> str:
    return hashlib.sha256(
        os.path.abspath(path).lower().encode("utf-8", errors="ignore")
    ).hexdigest()


def create_fallback_icon(name: str) -> Image.Image:
    cache = ICON_DIR / f"fallback_{clean_cache_name(name)}.png"

    if cache.exists():
        try:
            return Image.open(cache).convert("RGBA")
        except OSError:
            pass

    image = Image.new("RGBA", (256, 256), "#202832")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (10, 10, 246, 246),
        radius=54,
        fill="#2B3744",
    )

    letter = (name.strip()[:1] or "A").upper()

    try:
        font = ImageFont.truetype("segoeuib.ttf", 118)
    except OSError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), letter, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    draw.text(
        ((256 - tw) / 2, (256 - th) / 2 - 8),
        letter,
        font=font,
        fill="white",
    )

    try:
        image.save(cache, "PNG")
    except OSError:
        pass

    return image


def extract_windows_exe_icon(path: str, name: str) -> Image.Image:
    """
    Uses Windows PowerShell/System.Drawing to extract an EXE icon.
    The result is cached. If extraction fails, a safe fallback icon is used.
    """
    if sys.platform != "win32":
        return create_fallback_icon(name)

    source = Path(path)
    cache = ICON_DIR / f"{clean_cache_name(str(source))}.png"

    if cache.exists():
        try:
            return Image.open(cache).convert("RGBA")
        except OSError:
            pass

    ps_source = str(source.resolve()).replace("'", "''")
    ps_cache = str(cache.resolve()).replace("'", "''")

    script = f"""
Add-Type -AssemblyName System.Drawing
$exe = '{ps_source}'
$out = '{ps_cache}'
try {{
    $icon = [System.Drawing.Icon]::ExtractAssociatedIcon($exe)
    if ($null -ne $icon) {{
        $bitmap = $icon.ToBitmap()
        $bitmap.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
        $bitmap.Dispose()
        $icon.Dispose()
    }}
}} catch {{}}
"""

    try:
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=6,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return create_fallback_icon(name)

    if cache.exists():
        try:
            return Image.open(cache).convert("RGBA")
        except OSError:
            pass

    return create_fallback_icon(name)


def load_icon(path: str, name: str) -> Image.Image:
    file = Path(path)
    suffix = file.suffix.lower()

    if suffix == ".exe":
        return extract_windows_exe_icon(path, name)

    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".ico"}:
        try:
            return Image.open(file).convert("RGBA")
        except (OSError, ValueError):
            pass

    return create_fallback_icon(name)


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent: "HanLauncher"):
        super().__init__(parent)
        self.parent = parent
        self.colors = theme_colors(parent.settings)

        self.title("Han Launcher • Ayarlar")
        self.geometry("440x470")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build()

    def _build(self):
        c = self.colors

        title = ctk.CTkLabel(
            self,
            text="Ayarlar",
            text_color=c["text"],
            font=ctk.CTkFont(
                family="Segoe UI",
                size=28,
                weight="bold",
            ),
        )
        title.pack(anchor="w", padx=28, pady=(28, 18))

        theme_label = ctk.CTkLabel(
            self,
            text="Tema",
            text_color=c["text"],
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        theme_label.pack(anchor="w", padx=28)

        self.theme_var = ctk.StringVar(
            value=self.parent.settings["theme"]
        )
        theme_menu = ctk.CTkOptionMenu(
            self,
            values=["dark", "light"],
            variable=self.theme_var,
            width=190,
        )
        theme_menu.pack(anchor="w", padx=28, pady=(6, 16))

        self.anim_var = ctk.BooleanVar(
            value=self.parent.settings["animations"]
        )
        anim = ctk.CTkSwitch(
            self,
            text="Yumuşak animasyonlar",
            variable=self.anim_var,
        )
        anim.pack(anchor="w", padx=28, pady=7)

        size_label = ctk.CTkLabel(
            self,
            text="Kart boyutu",
            text_color=c["text"],
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        size_label.pack(anchor="w", padx=28, pady=(16, 0))

        self.size_var = ctk.StringVar(
            value=self.parent.settings["card_size"]
        )
        size_menu = ctk.CTkOptionMenu(
            self,
            values=["small", "medium", "large"],
            variable=self.size_var,
            width=190,
        )
        size_menu.pack(anchor="w", padx=28, pady=(6, 16))

        columns_label = ctk.CTkLabel(
            self,
            text="Kart sütun sayısı",
            text_color=c["text"],
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        columns_label.pack(anchor="w", padx=28)

        self.columns_var = ctk.StringVar(
            value=str(self.parent.settings["columns"])
        )
        columns_menu = ctk.CTkOptionMenu(
            self,
            values=["2", "3", "4", "5", "6"],
            variable=self.columns_var,
            width=190,
        )
        columns_menu.pack(anchor="w", padx=28, pady=(6, 20))

        save_button = ctk.CTkButton(
            self,
            text="Değişiklikleri Kaydet",
            height=43,
            corner_radius=12,
            fg_color=c["accent"],
            hover_color=c["accent_hover"],
            command=self._save,
        )
        save_button.pack(fill="x", padx=28, pady=(4, 8))

        reset_button = ctk.CTkButton(
            self,
            text="Ayarları Sıfırla",
            height=38,
            corner_radius=11,
            fg_color="transparent",
            hover_color=c["button_hover"],
            border_width=1,
            border_color=c["border"],
            command=self._reset,
        )
        reset_button.pack(fill="x", padx=28)

    def _save(self):
        self.parent.settings["theme"] = self.theme_var.get()
        self.parent.settings["animations"] = bool(self.anim_var.get())
        self.parent.settings["card_size"] = self.size_var.get()
        self.parent.settings["columns"] = int(self.columns_var.get())

        if not save_settings(self.parent.settings):
            messagebox.showerror(
                "Ayarlar",
                "Ayarlar kaydedilemedi.",
                parent=self,
            )
            return

        self.destroy()
        self.parent.apply_theme_and_refresh()

    def _reset(self):
        self.parent.settings = dict(DEFAULT_SETTINGS)
        save_settings(self.parent.settings)

        self.destroy()
        self.parent.apply_theme_and_refresh()


class HanLauncher(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode(
            "Light" if SETTINGS["theme"] == "light" else "Dark"
        )
        super().__init__()

        self.settings = dict(SETTINGS)
        self.apps = load_apps()

        self.selected_index: Optional[int] = 0 if self.apps else None
        self.cards: dict[int, dict] = {}
        self.animation_jobs: dict[int, str] = {}
        self.status_job: Optional[str] = None

        self.title(APP_TITLE)
        self.geometry("1100x720")
        self.minsize(820, 540)
        self.configure(fg_color=self.colors["bg"])

        self._build_ui()
        self._render()

        self.bind_all("<Left>", self._on_left)
        self.bind_all("<Right>", self._on_right)
        self.bind_all("<Up>", self._on_up)
        self.bind_all("<Down>", self._on_down)
        self.bind_all("<Return>", self._on_enter)
        self.bind_all("<Delete>", self._on_delete)
        self.bind_all("<Escape>", self._on_escape)

        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.after(150, self.focus_force)

    @property
    def colors(self) -> dict:
        return theme_colors(self.settings)

    def _build_ui(self):
        c = self.colors

        self.header = ctk.CTkFrame(
            self,
            fg_color=c["surface"],
            corner_radius=0,
        )
        self.header.pack(fill="x")

        top = ctk.CTkFrame(
            self.header,
            fg_color="transparent",
        )
        top.pack(fill="x", padx=30, pady=20)

        self.brand = ctk.CTkLabel(
            top,
            text="HAN",
            text_color=c["text"],
            font=ctk.CTkFont(
                family="Segoe UI",
                size=30,
                weight="bold",
            ),
        )
        self.brand.pack(side="left")

        self.brand_sub = ctk.CTkLabel(
            top,
            text="LAUNCHER",
            text_color=c["muted"],
            font=ctk.CTkFont(
                family="Segoe UI",
                size=12,
                weight="bold",
            ),
        )
        self.brand_sub.pack(side="left", padx=(10, 0), pady=(8, 0))

        self.settings_button = ctk.CTkButton(
            top,
            text="⚙",
            width=42,
            height=40,
            corner_radius=11,
            fg_color=c["button"],
            hover_color=c["button_hover"],
            border_width=1,
            border_color=c["border"],
            font=ctk.CTkFont(size=18),
            command=self.open_settings,
        )
        self.settings_button.pack(side="right")

        self.add_button = ctk.CTkButton(
            top,
            text="+  Uygulama Ekle",
            width=158,
            height=40,
            corner_radius=11,
            fg_color=c["button"],
            hover_color=c["button_hover"],
            border_width=1,
            border_color=c["border"],
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.add_application,
        )
        self.add_button.pack(side="right", padx=(0, 8))

        tools = ctk.CTkFrame(
            self.header,
            fg_color="transparent",
        )
        tools.pack(fill="x", padx=30, pady=(0, 14))

        self.search_var = ctk.StringVar()

        self.search_entry = ctk.CTkEntry(
            tools,
            textvariable=self.search_var,
            height=38,
            corner_radius=11,
            placeholder_text="Uygulama ara...",
            fg_color=c["input"],
            border_color=c["border"],
            text_color=c["text"],
        )
        self.search_entry.pack(
            side="left",
            fill="x",
            expand=True,
        )

        self.search_var.trace_add(
            "write",
            lambda *_: self._render()
        )

        self.count_label = ctk.CTkLabel(
            tools,
            text="",
            text_color=c["muted"],
            font=ctk.CTkFont(size=11),
        )
        self.count_label.pack(side="right", padx=(12, 0))

        self.content = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=c["border"],
            scrollbar_button_hover_color=c["button_hover"],
        )
        self.content.pack(
            fill="both",
            expand=True,
            padx=22,
            pady=18,
        )

        self.footer = ctk.CTkLabel(
            self,
            text="← ↑ ↓ →  gezin   •   Enter  aç   •   Delete  kaldır",
            text_color=c["muted"],
            font=ctk.CTkFont(size=11),
        )
        self.footer.pack(pady=(0, 10))

    def _card_dimensions(self):
        value = self.settings["card_size"]
        if value == "small":
            return 190, 162
        if value == "large":
            return 240, 192
        return 215, 178

    def _filtered_indices(self) -> list[int]:
        query = self.search_var.get().strip().lower()

        if not query:
            return list(range(len(self.apps)))

        return [
            i for i, app in enumerate(self.apps)
            if query in app.name.lower()
            or query in Path(app.path).name.lower()
        ]

    def _render(self):
        for job in self.animation_jobs.values():
            try:
                self.after_cancel(job)
            except Exception:
                pass

        self.animation_jobs.clear()

        for widget in self.content.winfo_children():
            widget.destroy()

        self.cards.clear()

        indices = self._filtered_indices()
        self.count_label.configure(
            text=f"{len(indices)} uygulama"
        )

        if not indices:
            self._show_empty(
                "Aramaya uygun uygulama yok."
                if self.apps
                else "Henüz uygulama eklenmedi."
            )
            return

        if self.selected_index not in indices:
            self.selected_index = indices[0]

        columns = self.settings["columns"]
        for col in range(columns):
            self.content.grid_columnconfigure(
                col,
                weight=1,
            )

        width, height = self._card_dimensions()

        for position, app_index in enumerate(indices):
            row = position // columns
            col = position % columns

            self._create_card(
                app_index,
                self.apps[app_index],
                row,
                col,
                width,
                height,
            )

        self.after(40, self._refresh_selection)

    def _create_card(
        self,
        app_index: int,
        app: AppEntry,
        row: int,
        col: int,
        width: int,
        height: int,
    ):
        c = self.colors

        frame = ctk.CTkFrame(
            self.content,
            width=width,
            height=height,
            fg_color=c["card"],
            corner_radius=20,
            border_width=1,
            border_color=c["border"],
        )
        frame.grid(
            row=row,
            column=col,
            padx=8,
            pady=8,
            sticky="nsew",
        )
        frame.grid_propagate(False)

        image = load_icon(app.path, app.name)
        image.thumbnail(
            (84, 84),
            Image.Resampling.LANCZOS,
        )

        icon_image = ctk.CTkImage(
            light_image=image,
            dark_image=image,
            size=(68, 68),
        )

        icon = ctk.CTkLabel(
            frame,
            text="",
            image=icon_image,
        )
        icon.place(
            relx=0.5,
            y=18,
            anchor="n",
        )

        name = ctk.CTkLabel(
            frame,
            text=app.name,
            text_color=c["text"],
            font=ctk.CTkFont(
                family="Segoe UI",
                size=15,
                weight="bold",
            ),
        )
        name.place(
            relx=0.5,
            y=98,
            anchor="n",
        )

        file_label = ctk.CTkLabel(
            frame,
            text=Path(app.path).name,
            text_color=c["muted"],
            font=ctk.CTkFont(size=10),
        )
        file_label.place(
            relx=0.5,
            y=124,
            anchor="n",
        )

        hint = ctk.CTkLabel(
            frame,
            text="ENTER  •  AÇ",
            text_color=c["muted"],
            font=ctk.CTkFont(
                size=10,
                weight="bold",
            ),
        )
        hint.place(
            relx=0.5,
            y=150,
            anchor="n",
        )

        self.cards[app_index] = {
            "frame": frame,
            "icon": icon,
            "icon_image": icon_image,
            "hover": False,
            "scale": 1.0,
            "target": 1.0,
            "widgets": [frame, icon, name, file_label, hint],
        }

        for widget in self.cards[app_index]["widgets"]:
            widget.bind(
                "<Button-1>",
                lambda _e, i=app_index: self.select_app(i)
            )
            widget.bind(
                "<Double-Button-1>",
                lambda _e, i=app_index: self.launch_app(i)
            )
            widget.bind(
                "<Enter>",
                lambda _e, i=app_index: self._hover(i, True)
            )
            widget.bind(
                "<Leave>",
                lambda _e, i=app_index: self._hover(i, False)
            )

    def _refresh_selection(self):
        if self.selected_index is not None:
            self._set_selected(
                self.selected_index,
                True,
            )

    def _set_selected(self, index: int, selected: bool):
        card = self.cards.get(index)
        if not card:
            return

        c = self.colors

        if selected:
            card["frame"].configure(
                fg_color=c["card_selected"],
                border_color=c["border_selected"],
            )
        elif card["hover"]:
            card["frame"].configure(
                fg_color=c["card_hover"],
                border_color=c["border"],
            )
        else:
            card["frame"].configure(
                fg_color=c["card"],
                border_color=c["border"],
            )

    def _hover(self, index: int, state: bool):
        card = self.cards.get(index)
        if not card:
            return

        card["hover"] = state
        self._set_selected(
            index,
            index == self.selected_index,
        )

        if self.settings["animations"]:
            self._animate_icon(
                index,
                1.045 if state else 1.0,
            )

    def _animate_icon(self, index: int, target: float):
        card = self.cards.get(index)
        if not card:
            return

        card["target"] = target

        old = self.animation_jobs.get(index)
        if old is not None:
            try:
                self.after_cancel(old)
            except Exception:
                pass

        self._animation_step(index)

    def _animation_step(self, index: int):
        card = self.cards.get(index)
        if not card:
            return

        current = card["scale"]
        target = card["target"]
        delta = target - current

        if abs(delta) < 0.002:
            card["scale"] = target
            self._resize_icon(index)
            self.animation_jobs.pop(index, None)
            return

        card["scale"] = current + delta * 0.24
        self._resize_icon(index)

        self.animation_jobs[index] = self.after(
            12,
            lambda i=index: self._animation_step(i),
        )

    def _resize_icon(self, index: int):
        card = self.cards.get(index)
        if not card:
            return

        size = int(68 * card["scale"])
        size = max(62, min(74, size))

        card["icon_image"].configure(
            size=(size, size)
        )

    def select_app(self, index: int):
        if index < 0 or index >= len(self.apps):
            return
        if index not in self.cards:
            return

        old = self.selected_index
        self.selected_index = index

        if old is not None and old in self.cards:
            self._set_selected(old, False)

        self._set_selected(index, True)

        if self.settings["animations"]:
            self._animate_icon(index, 1.06)

        self._scroll_to_selected()
        self.focus_force()

    def _movement_target(self, direction: str) -> Optional[int]:
        visible = self._filtered_indices()
        if not visible or self.selected_index not in visible:
            return visible[0] if visible else None

        pos = visible.index(self.selected_index)
        columns = self.settings["columns"]

        if direction == "left":
            return visible[pos - 1] if pos > 0 else visible[pos]
        if direction == "right":
            return visible[pos + 1] if pos + 1 < len(visible) else visible[pos]
        if direction == "up":
            target = pos - columns
            return visible[target] if target >= 0 else visible[pos]
        if direction == "down":
            target = pos + columns
            return visible[target] if target < len(visible) else visible[pos]

        return None

    def _on_left(self, _event=None):
        target = self._movement_target("left")
        if target is not None:
            self.select_app(target)
        return "break"

    def _on_right(self, _event=None):
        target = self._movement_target("right")
        if target is not None:
            self.select_app(target)
        return "break"

    def _on_up(self, _event=None):
        target = self._movement_target("up")
        if target is not None:
            self.select_app(target)
        return "break"

    def _on_down(self, _event=None):
        target = self._movement_target("down")
        if target is not None:
            self.select_app(target)
        return "break"

    def _on_enter(self, _event=None):
        if self.selected_index is not None:
            self.launch_app(self.selected_index)
        return "break"

    def _on_delete(self, _event=None):
        if self.selected_index is not None:
            self.delete_app(self.selected_index)
        return "break"

    def _on_escape(self, _event=None):
        self.search_entry.delete(0, "end")
        self.focus_force()
        return "break"

    def _scroll_to_selected(self):
        card = self.cards.get(self.selected_index)
        if not card:
            return

        try:
            canvas = self.content._parent_canvas
            y = card["frame"].winfo_y()
            view_height = self.content.winfo_height()

            if y < 0:
                canvas.yview_moveto(0)
            elif y > view_height - 170:
                fraction = y / max(1, self.content.winfo_reqheight())
                canvas.yview_moveto(min(1.0, max(0.0, fraction)))
        except Exception:
            pass

    def add_application(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Uygulama seç",
            filetypes=[
                ("Windows Uygulamaları", "*.exe"),
                ("Tüm Dosyalar", "*.*"),
            ],
        )

        if not path:
            return

        path = str(Path(path).resolve())
        normalized = os.path.normcase(os.path.abspath(path))

        for app in self.apps:
            if os.path.normcase(os.path.abspath(app.path)) == normalized:
                messagebox.showinfo(
                    "Zaten ekli",
                    "Bu uygulama zaten launcher'da.",
                    parent=self,
                )
                return

        name = Path(path).stem.strip() or "Uygulama"
        self.apps.append(
            AppEntry(name=name, path=path)
        )

        if not save_apps(self.apps):
            self.apps.pop()
            messagebox.showerror(
                "Kaydetme hatası",
                "Uygulama kaydedilemedi.",
                parent=self,
            )
            return

        self.selected_index = len(self.apps) - 1
        self._render()
        self._show_status(f"{name} eklendi")

    def launch_app(self, index: int):
        if index < 0 or index >= len(self.apps):
            return

        path = self.apps[index].path

        if not os.path.isfile(path):
            messagebox.showerror(
                "Dosya bulunamadı",
                f"Uygulama artık bulunamıyor:\n\n{path}",
                parent=self,
            )
            return

        try:
            os.startfile(path)
        except OSError as exc:
            messagebox.showerror(
                "Başlatma hatası",
                str(exc),
                parent=self,
            )

    def delete_app(self, index: int):
        if index < 0 or index >= len(self.apps):
            return

        app = self.apps[index]

        if not messagebox.askyesno(
            "Uygulamayı kaldır",
            f"'{app.name}' launcher'dan kaldırılsın mı?",
            parent=self,
        ):
            return

        self.apps.pop(index)

        if not save_apps(self.apps):
            self.apps.insert(index, app)
            messagebox.showerror(
                "Kaydetme hatası",
                "Değişiklik kaydedilemedi.",
                parent=self,
            )
            return

        if not self.apps:
            self.selected_index = None
        else:
            self.selected_index = min(index, len(self.apps) - 1)

        self._render()
        self._show_status(f"{app.name} kaldırıldı")

    def open_settings(self):
        SettingsDialog(self)

    def apply_theme_and_refresh(self):
        ctk.set_appearance_mode(
            "Light" if self.settings["theme"] == "light" else "Dark"
        )

        for widget in self.winfo_children():
            widget.destroy()

        self.cards.clear()
        self.animation_jobs.clear()

        self.configure(
            fg_color=self.colors["bg"]
        )

        self._build_ui()
        self._render()
        self.focus_force()

    def _show_empty(self, message: str):
        c = self.colors

        box = ctk.CTkFrame(
            self.content,
            fg_color="transparent",
        )
        box.grid(
            row=0,
            column=0,
            columnspan=self.settings["columns"],
            pady=150,
        )

        icon = ctk.CTkLabel(
            box,
            text="＋",
            text_color="#3B4754",
            font=ctk.CTkFont(
                size=58,
                weight="bold",
            ),
        )
        icon.pack()

        title = ctk.CTkLabel(
            box,
            text=message,
            text_color=c["text"],
            font=ctk.CTkFont(
                size=20,
                weight="bold",
            ),
        )
        title.pack(pady=(0, 7))

        subtitle = ctk.CTkLabel(
            box,
            text="Yukarıdaki butondan bir uygulama ekleyebilirsin.",
            text_color=c["muted"],
            font=ctk.CTkFont(size=13),
        )
        subtitle.pack()

    def _show_status(self, text: str):
        if self.status_job is not None:
            try:
                self.after_cancel(self.status_job)
            except Exception:
                pass

        label = ctk.CTkLabel(
            self,
            text=text,
            text_color=self.colors["accent"],
            font=ctk.CTkFont(
                size=12,
                weight="bold",
            ),
        )
        label.place(
            relx=0.5,
            rely=0.965,
            anchor="center",
        )

        self.status_job = self.after(
            1600,
            label.destroy,
        )


# Keep a single settings object for startup defaults.
SETTINGS = load_settings()


if __name__ == "__main__":
    app = HanLauncher()
    app.mainloop()