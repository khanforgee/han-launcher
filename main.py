import customtkinter as ctk
from tkinter import filedialog, messagebox
from pathlib import Path
from PIL import Image, ImageDraw
import json
import subprocess
import uuid

import win32api
import win32con
import win32gui
import win32ui


# ============================================================
# AYARLAR
# ============================================================

APP_NAME = "Han Launcher"

DATA_DIR = Path.home() / ".hanlauncher"
DATA_FILE = DATA_DIR / "apps.json"
PROFILE_FILE = DATA_DIR / "profile.json"

DATA_DIR.mkdir(exist_ok=True)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ============================================================
# VERİLER
# ============================================================

def load_apps():

    if not DATA_FILE.exists():
        return []

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    except Exception:
        return []


def save_apps(apps):

    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(
            apps,
            file,
            ensure_ascii=False,
            indent=4
        )


def get_anonymous_id():

    id_file = DATA_DIR / "anonymous_id.txt"

    if id_file.exists():

        saved_id = id_file.read_text(
            encoding="utf-8"
        ).strip()

        if saved_id:
            return saved_id

    anonymous_id = (
        "HAN-" +
        uuid.uuid4().hex[:8].upper()
    )

    id_file.write_text(
        anonymous_id,
        encoding="utf-8"
    )

    return anonymous_id


def load_profile():

    if not PROFILE_FILE.exists():

        return {
            "display_name": "",
            "theme": "dark"
        }

    try:

        with open(
            PROFILE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

            if not isinstance(data, dict):
                raise ValueError

            return {
                "display_name": data.get(
                    "display_name",
                    ""
                ),
                "theme": data.get(
                    "theme",
                    "dark"
                )
            }

    except Exception:

        return {
            "display_name": "",
            "theme": "dark"
        }


def save_profile(profile):

    with open(
        PROFILE_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            profile,
            file,
            ensure_ascii=False,
            indent=4
        )


# ============================================================
# WINDOWS İKONLARI
# ============================================================

def extract_exe_icon(exe_path, save_path):

    """
    Windows EXE ikonunu PNG olarak çıkarmaya çalışır.
    Birçok Windows uygulamasında çalışır.
    """

    large_icons = []
    small_icons = []

    try:

        large_icons, small_icons = win32api.ExtractIconEx(
            exe_path,
            0
        )

        if not large_icons:
            return False

        hicon = large_icons[0]

        # ----------------------------------------------------
        # İkon bilgilerini al
        # ----------------------------------------------------

        icon_info = win32gui.GetIconInfo(hicon)

        hbm_color = icon_info[4]
        hbm_mask = icon_info[3]

        # ----------------------------------------------------
        # Bitmap oluştur
        # ----------------------------------------------------

        screen_dc = win32gui.GetDC(0)

        dc = win32ui.CreateDCFromHandle(
            screen_dc
        )

        mem_dc = dc.CreateCompatibleDC()

        bitmap = win32ui.CreateBitmap()

        bitmap.CreateCompatibleBitmap(
            dc,
            48,
            48
        )

        mem_dc.SelectObject(bitmap)

        mem_dc.FillSolidRect(
            (0, 0, 48, 48),
            win32api.RGB(0, 0, 0)
        )

        # ----------------------------------------------------
        # İkonu çiz
        # ----------------------------------------------------

        win32gui.DrawIconEx(
            mem_dc.GetSafeHdc(),
            0,
            0,
            hicon,
            48,
            48,
            0,
            0,
            win32con.DI_NORMAL
        )

        # ----------------------------------------------------
        # Bitmap verisini al
        # ----------------------------------------------------

        bmp_info = bitmap.GetInfo()

        bmp_bits = bitmap.GetBitmapBits(
            True
        )

        image = Image.frombuffer(
            "RGBA",
            (
                bmp_info["bmWidth"],
                bmp_info["bmHeight"]
            ),
            bmp_bits,
            "raw",
            "BGRA",
            0,
            1
        )

        image = image.transpose(
            Image.Transpose.FLIP_TOP_BOTTOM
        )

        image.save(
            save_path,
            "PNG"
        )

        # ----------------------------------------------------
        # Temizlik
        # ----------------------------------------------------

        try:
            mem_dc.DeleteDC()
        except Exception:
            pass

        try:
            dc.DeleteDC()
        except Exception:
            pass

        try:
            win32gui.ReleaseDC(
                0,
                screen_dc
            )
        except Exception:
            pass

        try:
            win32gui.DestroyIcon(
                hicon
            )
        except Exception:
            pass

        return True

    except Exception:

        return False

    finally:

        # ExtractIconEx tarafından alınan
        # kullanılmayan ikonları temizle

        try:

            for icon in large_icons[1:]:
                win32gui.DestroyIcon(icon)

        except Exception:
            pass

        try:

            for icon in small_icons:
                win32gui.DestroyIcon(icon)

        except Exception:
            pass


def create_default_icon(save_path):

    image = Image.new(
        "RGBA",
        (128, 128),
        (20, 30, 45, 255)
    )

    draw = ImageDraw.Draw(
        image
    )

    draw.rounded_rectangle(
        (10, 10, 118, 118),
        radius=25,
        fill=(20, 110, 245, 255)
    )

    draw.text(
        (48, 38),
        "H",
        fill="white"
    )

    image.save(
        save_path
    )


# ============================================================
# HAN LAUNCHER
# ============================================================

class HanLauncher(ctk.CTk):

    def __init__(self):

        super().__init__()

        self.title(
            APP_NAME
        )

        self.geometry(
            "1100x650"
        )

        self.minsize(
            900,
            550
        )

        self.configure(
            fg_color="#070A0F"
        )

        self.apps = load_apps()

        self.profile = load_profile()

        self.selected_index = 0

        self.card_widgets = []

        # Tema
        saved_theme = self.profile.get(
            "theme",
            "dark"
        )

        if saved_theme not in (
            "dark",
            "light",
            "system"
        ):
            saved_theme = "dark"

        ctk.set_appearance_mode(
            saved_theme
        )

        self.profile["theme"] = saved_theme

        save_profile(
            self.profile
        )

        self.build_ui()

        self.bind_keys()

        self.refresh_apps()

    # ========================================================
    # KULLANICI ADI
    # ========================================================

    def get_display_name(self):

        name = self.profile.get(
            "display_name",
            ""
        ).strip()

        if name:
            return name

        return get_anonymous_id()

    # ========================================================
    # ARAYÜZ
    # ========================================================

    def build_ui(self):

        # ----------------------------------------------------
        # ÜST BAR
        # ----------------------------------------------------

        self.topbar = ctk.CTkFrame(
            self,
            height=65,
            corner_radius=0,
            fg_color="#0B0F16"
        )

        self.topbar.pack(
            fill="x"
        )

        # Logo

        self.logo = ctk.CTkLabel(
            self.topbar,
            text="H",
            font=("Segoe UI", 26, "bold"),
            text_color="#1683FF"
        )

        self.logo.pack(
            side="left",
            padx=(25, 8)
        )

        # Başlık

        self.title_text = ctk.CTkLabel(
            self.topbar,
            text="Han Launcher",
            font=("Segoe UI", 17, "bold"),
            text_color="#EAF0F8"
        )

        self.title_text.pack(
            side="left"
        )

        # Kullanıcı

        self.user_label = ctk.CTkLabel(
            self.topbar,
            text=self.get_display_name(),
            font=("Segoe UI", 11),
            text_color="#687486"
        )

        self.user_label.pack(
            side="right",
            padx=(10, 18)
        )

        # ----------------------------------------------------
        # HAMBURGER MENÜ
        # ----------------------------------------------------

        self.settings_button = ctk.CTkButton(
            self.topbar,
            text="☰",
            width=45,
            height=40,
            corner_radius=10,
            fg_color="transparent",
            hover_color="#151D29",
            font=("Segoe UI Symbol", 24),
            text_color="#EAF0F8",
            command=self.open_settings
        )

        self.settings_button.pack(
            side="right",
            padx=(5, 10)
        )

        # ----------------------------------------------------
        # ANA ALAN
        # ----------------------------------------------------

        self.main = ctk.CTkFrame(
            self,
            fg_color="#070A0F",
            corner_radius=0
        )

        self.main.pack(
            fill="both",
            expand=True
        )

        self.heading = ctk.CTkLabel(
            self.main,
            text="Uygulamalar",
            font=("Segoe UI", 28, "bold"),
            text_color="#EDF3FA"
        )

        self.heading.pack(
            pady=(35, 5)
        )

        self.subtitle = ctk.CTkLabel(
            self.main,
            text="Kendi uygulamalarını ekle ve tek yerden başlat.",
            font=("Segoe UI", 13),
            text_color="#6F7B8C"
        )

        self.subtitle.pack(
            pady=(0, 25)
        )

        # ----------------------------------------------------
        # UYGULAMA KARTLARI
        # ----------------------------------------------------

        self.cards_frame = ctk.CTkScrollableFrame(
            self.main,
            fg_color="transparent",
            orientation="horizontal"
        )

        self.cards_frame.pack(
            fill="x",
            padx=35,
            pady=10
        )

        # ----------------------------------------------------
        # ALT BUTONLAR
        # ----------------------------------------------------

        self.buttons_frame = ctk.CTkFrame(
            self.main,
            fg_color="transparent"
        )

        self.buttons_frame.pack(
            pady=20
        )

        self.add_button = ctk.CTkButton(
            self.buttons_frame,
            text="+  Uygulama Ekle",
            width=180,
            height=42,
            corner_radius=12,
            fg_color="#146EF5",
            hover_color="#0E5ACB",
            font=("Segoe UI", 13, "bold"),
            command=self.add_app
        )

        self.add_button.pack(
            side="left",
            padx=6
        )

        self.remove_button = ctk.CTkButton(
            self.buttons_frame,
            text="−  Uygulamayı Sil",
            width=180,
            height=42,
            corner_radius=12,
            fg_color="#151B24",
            hover_color="#202936",
            font=("Segoe UI", 13),
            command=self.remove_selected
        )

        self.remove_button.pack(
            side="left",
            padx=6
        )

        # ----------------------------------------------------
        # DURUM
        # ----------------------------------------------------

        self.status = ctk.CTkLabel(
            self.main,
            text="Hazır",
            font=("Segoe UI", 12),
            text_color="#667386"
        )

        self.status.pack(
            pady=(0, 15)
        )

        # ----------------------------------------------------
        # ALT BAR
        # ----------------------------------------------------

        self.bottom = ctk.CTkFrame(
            self,
            height=45,
            corner_radius=0,
            fg_color="#0B0F16"
        )

        self.bottom.pack(
            fill="x",
            side="bottom"
        )

        self.help_text = ctk.CTkLabel(
            self.bottom,
            text="← → Gezin    Enter Aç    R Yenile    Esc Çıkış",
            font=("Segoe UI", 11),
            text_color="#687486"
        )

        self.help_text.pack(
            pady=12
        )

    # ========================================================
    # KARTLARI YENİLE
    # ========================================================

    def refresh_apps(self):

        for widget in self.cards_frame.winfo_children():
            widget.destroy()

        self.card_widgets.clear()

        if not self.apps:

            empty = ctk.CTkFrame(
                self.cards_frame,
                width=300,
                height=160,
                fg_color="#10151D",
                corner_radius=16,
                border_width=1,
                border_color="#1B2533"
            )

            empty.pack(
                padx=10,
                pady=10
            )

            empty.pack_propagate(False)

            text = ctk.CTkLabel(
                empty,
                text="Henüz uygulama yok\n\n+ Uygulama Ekle'ye bas",
                font=("Segoe UI", 14),
                text_color="#738096"
            )

            text.pack(
                expand=True
            )

            self.card_widgets.append(
                empty
            )

            self.status.configure(
                text="Henüz uygulama eklenmedi."
            )

            return

        if self.selected_index >= len(self.apps):

            self.selected_index = (
                len(self.apps) - 1
            )

        for index, app in enumerate(self.apps):

            self.create_card(
                index,
                app
            )

        self.update_selection()

    # ========================================================
    # KART OLUŞTUR
    # ========================================================

    def create_card(
        self,
        index,
        app
    ):

        card = ctk.CTkFrame(
            self.cards_frame,
            width=190,
            height=190,
            corner_radius=16,
            fg_color="#10151D",
            border_width=1,
            border_color="#1B2533"
        )

        card.pack(
            side="left",
            padx=8,
            pady=10
        )

        card.pack_propagate(False)

        # ----------------------------------------------------
        # İKON
        # ----------------------------------------------------

        icon_path = app.get(
            "icon"
        )

        icon_label = None

        if (
            icon_path
            and Path(icon_path).exists()
        ):

            try:

                image = Image.open(
                    icon_path
                ).convert(
                    "RGBA"
                )

                image.thumbnail(
                    (72, 72),
                    Image.Resampling.LANCZOS
                )

                icon_image = ctk.CTkImage(
                    light_image=image,
                    dark_image=image,
                    size=(72, 72)
                )

                icon_label = ctk.CTkLabel(
                    card,
                    text="",
                    image=icon_image
                )

                # Referansı koru
                icon_label.image = icon_image

            except Exception:

                icon_label = ctk.CTkLabel(
                    card,
                    text="▣",
                    font=("Segoe UI", 45),
                    text_color="#1683FF"
                )

        else:

            icon_label = ctk.CTkLabel(
                card,
                text="▣",
                font=("Segoe UI", 45),
                text_color="#1683FF"
            )

        icon_label.pack(
            pady=(22, 10)
        )

        # ----------------------------------------------------
        # İSİM
        # ----------------------------------------------------

        name_label = ctk.CTkLabel(
            card,
            text=app.get(
                "name",
                "Bilinmeyen"
            ),
            font=("Segoe UI", 12, "bold"),
            text_color="#E2E9F2"
        )

        name_label.pack(
            padx=10
        )

        # ----------------------------------------------------
        # TIKLAMA
        # ----------------------------------------------------

        # Tek tıklayınca uygulama açılır.

        for widget in (
            card,
            icon_label,
            name_label
        ):

            widget.bind(
                "<Button-1>",
                lambda event, i=index:
                self.click_app(i)
            )

        self.card_widgets.append(
            card
        )

    # ========================================================
    # KARTA TIKLAMA
    # ========================================================

    def click_app(self, index):

        self.selected_index = index

        self.update_selection()

        self.launch_selected()

    # ========================================================
    # SEÇİM
    # ========================================================

    def select_app(
        self,
        index
    ):

        self.selected_index = index

        self.update_selection()

    def update_selection(self):

        if not self.apps:
            return

        for index, card in enumerate(
            self.card_widgets
        ):

            if index == self.selected_index:

                card.configure(
                    fg_color="#101D2D",
                    border_width=2,
                    border_color="#1683FF"
                )

            else:

                card.configure(
                    fg_color="#10151D",
                    border_width=1,
                    border_color="#1B2533"
                )

        selected = self.apps[
            self.selected_index
        ]

        self.status.configure(
            text=f"Seçili: {selected.get('name', 'Bilinmeyen')}"
        )

    # ========================================================
    # UYGULAMA EKLE
    # ========================================================

    def add_app(self):

        exe_path = filedialog.askopenfilename(
            title="Uygulama seç",
            filetypes=[
                (
                    "Windows uygulaması",
                    "*.exe"
                ),
                (
                    "Tüm dosyalar",
                    "*.*"
                )
            ]
        )

        if not exe_path:
            return

        exe_path = str(
            Path(exe_path).resolve()
        )

        name = Path(
            exe_path
        ).stem

        # ----------------------------------------------------
        # İKON KLASÖRÜ
        # ----------------------------------------------------

        icon_dir = DATA_DIR / "icons"

        icon_dir.mkdir(
            exist_ok=True
        )

        icon_path = (
            icon_dir /
            f"{uuid.uuid4().hex}.png"
        )

        # ----------------------------------------------------
        # EXE İKONU
        # ----------------------------------------------------

        icon_created = extract_exe_icon(
            exe_path,
            str(icon_path)
        )

        if not icon_created:

            create_default_icon(
                str(icon_path)
            )

        # ----------------------------------------------------
        # UYGULAMA VERİSİ
        # ----------------------------------------------------

        app = {
            "id": str(
                uuid.uuid4()
            ),
            "name": name,
            "path": exe_path,
            "icon": str(icon_path)
        }

        self.apps.append(
            app
        )

        save_apps(
            self.apps
        )

        self.selected_index = (
            len(self.apps) - 1
        )

        self.refresh_apps()

        self.status.configure(
            text=f"{name} eklendi!"
        )

    # ========================================================
    # UYGULAMA SİL
    # ========================================================

    def remove_selected(self):

        if not self.apps:
            return

        app = self.apps[
            self.selected_index
        ]

        answer = messagebox.askyesno(
            "Uygulamayı Sil",
            f"{app.get('name', 'Bu uygulama')} "
            f"uygulama listesinden silinsin mi?"
        )

        if not answer:
            return

        self.apps.pop(
            self.selected_index
        )

        if self.selected_index >= len(
            self.apps
        ):

            self.selected_index = max(
                0,
                len(self.apps) - 1
            )

        save_apps(
            self.apps
        )

        self.refresh_apps()

        self.status.configure(
            text="Uygulama kaldırıldı."
        )

    # ========================================================
    # UYGULAMA AÇ
    # ========================================================

    def launch_selected(self):

        if not self.apps:
            return

        app = self.apps[
            self.selected_index
        ]

        path = app.get(
            "path",
            ""
        )

        if not Path(path).exists():

            messagebox.showerror(
                "Han Launcher",
                "Bu uygulamanın .exe dosyası artık bulunamıyor."
            )

            return

        try:

            subprocess.Popen(
                [path],
                cwd=str(
                    Path(path).parent
                )
            )

            self.status.configure(
                text=f"{app.get('name', 'Uygulama')} açılıyor..."
            )

        except Exception as error:

            messagebox.showerror(
                "Başlatma hatası",
                str(error)
            )

    # ========================================================
    # AYARLAR
    # ========================================================

    def open_settings(self):

        self.settings_window = ctk.CTkToplevel(
            self
        )

        self.settings_window.title(
            "Ayarlar - Han Launcher"
        )

        self.settings_window.geometry(
            "600x450"
        )

        self.settings_window.minsize(
            600,
            450
        )

        self.settings_window.configure(
            fg_color="#070A0F"
        )

        self.settings_window.transient(
            self
        )

        self.settings_window.grab_set()

        # ----------------------------------------------------
        # BAŞLIK
        # ----------------------------------------------------

        title = ctk.CTkLabel(
            self.settings_window,
            text="Ayarlar",
            font=("Segoe UI", 26, "bold"),
            text_color="#EDF3FA"
        )

        title.pack(
            pady=(25, 20)
        )

        # ----------------------------------------------------
        # SEÇENEKLER
        # ----------------------------------------------------

        options = ctk.CTkFrame(
            self.settings_window,
            fg_color="transparent"
        )

        options.pack(
            fill="x",
            padx=35
        )

        account_button = ctk.CTkButton(
            options,
            text="👤  Hesap",
            height=55,
            corner_radius=12,
            fg_color="#10151D",
            hover_color="#182333",
            anchor="w",
            font=("Segoe UI", 14, "bold"),
            command=self.open_account_settings
        )

        account_button.pack(
            fill="x",
            pady=6
        )

        theme_button = ctk.CTkButton(
            options,
            text="🎨  Tema",
            height=55,
            corner_radius=12,
            fg_color="#10151D",
            hover_color="#182333",
            anchor="w",
            font=("Segoe UI", 14, "bold"),
            command=self.open_theme_settings
        )

        theme_button.pack(
            fill="x",
            pady=6
        )

        # ----------------------------------------------------
        # ALT BİLGİ
        # ----------------------------------------------------

        info = ctk.CTkLabel(
            self.settings_window,
            text="Han Launcher",
            font=("Segoe UI", 11),
            text_color="#566274"
        )

        info.pack(
            side="bottom",
            pady=20
        )

    # ========================================================
    # HESAP AYARLARI
    # ========================================================

    def open_account_settings(self):

        window = ctk.CTkToplevel(
            self.settings_window
        )

        window.title(
            "Hesap"
        )

        window.geometry(
            "500x400"
        )

        window.minsize(
            500,
            400
        )

        window.configure(
            fg_color="#070A0F"
        )

        window.transient(
            self.settings_window
        )

        window.grab_set()

        # Başlık

        ctk.CTkLabel(
            window,
            text="Hesap",
            font=("Segoe UI", 25, "bold"),
            text_color="#EDF3FA"
        ).pack(
            pady=(30, 20)
        )

        # Anonim ID

        anonymous_id = get_anonymous_id()

        ctk.CTkLabel(
            window,
            text="Anonim ID",
            font=("Segoe UI", 12),
            text_color="#718096"
        ).pack(
            pady=(5, 2)
        )

        ctk.CTkLabel(
            window,
            text=anonymous_id,
            font=("Segoe UI", 16, "bold"),
            text_color="#1683FF"
        ).pack(
            pady=(0, 20)
        )

        # Mevcut isim

        current_name = self.get_display_name()

        ctk.CTkLabel(
            window,
            text="Hesap ID / İsim",
            font=("Segoe UI", 12),
            text_color="#718096"
        ).pack(
            pady=(5, 2)
        )

        current_label = ctk.CTkLabel(
            window,
            text=current_name,
            font=("Segoe UI", 17, "bold"),
            text_color="#EAF0F8"
        )

        current_label.pack(
            pady=(0, 15)
        )

        # Değiştir

        change_button = ctk.CTkButton(
            window,
            text="✎  Değiştir",
            width=180,
            height=42,
            corner_radius=11,
            fg_color="#146EF5",
            hover_color="#0E5ACB",
            font=("Segoe UI", 13, "bold"),
            command=lambda:
            self.change_account_name(
                window
            )
        )

        change_button.pack(
            pady=10
        )

    # ========================================================
    # HESAP ADI DEĞİŞTİR
    # ========================================================

    def change_account_name(
        self,
        parent
    ):

        dialog = ctk.CTkToplevel(
            parent
        )

        dialog.title(
            "Hesap ID Değiştir"
        )

        dialog.geometry(
            "420x250"
        )

        dialog.resizable(
            False,
            False
        )

        dialog.configure(
            fg_color="#070A0F"
        )

        dialog.transient(
            parent
        )

        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="Yeni hesap ID'n",
            font=("Segoe UI", 20, "bold"),
            text_color="#EDF3FA"
        ).pack(
            pady=(30, 15)
        )

        entry = ctk.CTkEntry(
            dialog,
            width=300,
            height=42,
            corner_radius=10,
            placeholder_text="Örn: Han",
            font=("Segoe UI", 13)
        )

        entry.pack(
            pady=10
        )

        entry.focus()

        def save_name():

            new_name = entry.get().strip()

            if not new_name:

                messagebox.showwarning(
                    "Han Launcher",
                    "Lütfen bir isim veya ID gir.",
                    parent=dialog
                )

                return

            if len(new_name) > 30:

                messagebox.showwarning(
                    "Han Launcher",
                    "İsim en fazla 30 karakter olabilir.",
                    parent=dialog
                )

                return

            self.profile[
                "display_name"
            ] = new_name

            save_profile(
                self.profile
            )

            self.user_label.configure(
                text=new_name
            )

            self.status.configure(
                text=f"Hesap ID değiştirildi: {new_name}"
            )

            dialog.destroy()

            # Hesap penceresini yenile
            parent.destroy()

            self.open_account_settings()

        save_button = ctk.CTkButton(
            dialog,
            text="Kaydet",
            width=150,
            height=40,
            corner_radius=10,
            fg_color="#146EF5",
            hover_color="#0E5ACB",
            command=save_name
        )

        save_button.pack(
            pady=10
        )

        dialog.bind(
            "<Return>",
            lambda event:
            save_name()
        )

    # ========================================================
    # TEMA AYARLARI
    # ========================================================

    def open_theme_settings(self):

        window = ctk.CTkToplevel(
            self.settings_window
        )

        window.title(
            "Tema"
        )

        window.geometry(
            "450x330"
        )

        window.resizable(
            False,
            False
        )

        window.configure(
            fg_color="#070A0F"
        )

        window.transient(
            self.settings_window
        )

        window.grab_set()

        ctk.CTkLabel(
            window,
            text="Tema",
            font=("Segoe UI", 25, "bold"),
            text_color="#EDF3FA"
        ).pack(
            pady=(30, 20)
        )

        ctk.CTkLabel(
            window,
            text="Han Launcher görünümünü seç",
            font=("Segoe UI", 12),
            text_color="#718096"
        ).pack(
            pady=(0, 15)
        )

        theme_var = ctk.StringVar(
            value=self.profile.get(
                "theme",
                "dark"
            )
        )

        theme_menu = ctk.CTkOptionMenu(
            window,
            width=250,
            height=42,
            corner_radius=10,
            variable=theme_var,
            values=[
                "dark",
                "light",
                "system"
            ],
            command=self.change_theme
        )

        theme_menu.pack(
            pady=10
        )

        ctk.CTkLabel(
            window,
            text="dark = Koyu\nlight = Açık\nsystem = Windows ayarı",
            font=("Segoe UI", 11),
            text_color="#667386"
        ).pack(
            pady=15
        )

    # ========================================================
    # TEMA DEĞİŞTİR
    # ========================================================

    def change_theme(
        self,
        theme
    ):

        if theme not in (
            "dark",
            "light",
            "system"
        ):
            theme = "dark"

        ctk.set_appearance_mode(
            theme
        )

        self.profile[
            "theme"
        ] = theme

        save_profile(
            self.profile
        )

        self.status.configure(
            text=f"Tema değiştirildi: {theme}"
        )

    # ========================================================
    # KLAVYE
    # ========================================================

    def bind_keys(self):

        self.bind(
            "<Left>",
            lambda event:
            self.previous_app()
        )

        self.bind(
            "<Right>",
            lambda event:
            self.next_app()
        )

        self.bind(
            "<Return>",
            lambda event:
            self.launch_selected()
        )

        self.bind(
            "<Escape>",
            lambda event:
            self.destroy()
        )

        self.bind(
            "r",
            lambda event:
            self.refresh_apps()
        )

        self.bind(
            "R",
            lambda event:
            self.refresh_apps()
        )

    def next_app(self):

        if not self.apps:
            return

        self.selected_index += 1

        if self.selected_index >= len(
            self.apps
        ):

            self.selected_index = 0

        self.update_selection()

    def previous_app(self):

        if not self.apps:
            return

        self.selected_index -= 1

        if self.selected_index < 0:

            self.selected_index = (
                len(self.apps) - 1
            )

        self.update_selection()


# ============================================================
# BAŞLAT
# ============================================================

if __name__ == "__main__":

    app = HanLauncher()

    app.update_idletasks()

    width = app.winfo_width()
    height = app.winfo_height()

    screen_width = app.winfo_screenwidth()
    screen_height = app.winfo_screenheight()

    x = (
        screen_width - width
    ) // 2

    y = (
        screen_height - height
    ) // 2

    app.geometry(
        f"{width}x{height}+{x}+{y}"
    )

    app.mainloop()