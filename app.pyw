"""Chibi Crosshair Studio: Windows cursor theme and adjustable screen crosshair."""

import sys
import subprocess
import tkinter as tk
import queue
import threading
from pathlib import Path
from tkinter import colorchooser, messagebox
from PIL import Image, ImageTk
from cursor_core import NAMES, apply_cursor, apply_cursors, load_settings, make_canvas, save_settings, set_startup
from icon_catalog import download_icon, fetch_catalog, install_package, load_selections
from owner_access import is_repository_owner
from overlay_win32 import CrosshairOverlay

BG = "#17151d"
PANEL = "#24212d"
INK = "#fff5f8"
MUTED = "#beb4c0"
PINK = "#ff6790"
CATALOG_ADDRESS = "https://github.com/novax1213/chibi-crosshair-studio"


def button(parent, label, command, accent=False):
    return tk.Button(parent, text=label, command=command, font=("Segoe UI", 11, "bold"),
                     bg=PINK if accent else "#393340", fg="#21141c" if accent else INK,
                     activebackground="#ff8daa" if accent else "#504757", activeforeground=INK,
                     relief="flat", bd=0, cursor="hand2", padx=16, pady=9)


class Studio:
    def __init__(self):
        self.settings = load_settings()
        self.root = tk.Tk()
        self.root.title("Chibi Crosshair Studio")
        self.root.geometry("880x690")
        self.root.minsize(760, 640)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<FocusIn>", self.refresh_preview_on_focus)
        self.overlay = None
        self.preview_photo = None
        self.selected = tk.StringVar(value=NAMES[0])
        self.committed_cursor_settings = {name: dict(self.settings["cursor_settings"][name]) for name in NAMES}
        self.cursor_drafts = {name: dict(values) for name, values in self.committed_cursor_settings.items()}
        self._loading_cursor = False
        self.size = tk.IntVar(value=self.cursor_drafts[NAMES[0]]["size"])
        self.image_scale = tk.IntVar(value=self.cursor_drafts[NAMES[0]]["image_scale"])
        self.hotspot_x = tk.IntVar(value=self.cursor_drafts[NAMES[0]]["hotspot_x"])
        self.hotspot_y = tk.IntVar(value=self.cursor_drafts[NAMES[0]]["hotspot_y"])
        self.startup = tk.BooleanVar(value=self.settings["start_with_windows"])
        self.color = tk.StringVar(value=self.settings["crosshair_color"])
        self.length = tk.IntVar(value=self.settings["crosshair_length"])
        self.gap = tk.IntVar(value=self.settings["crosshair_gap"])
        self.thickness = tk.IntVar(value=self.settings["crosshair_thickness"])
        self.opacity = tk.IntVar(value=self.settings["crosshair_opacity"])
        self.dot = tk.BooleanVar(value=self.settings["crosshair_dot"])
        self.offset_x = tk.IntVar(value=self.settings["crosshair_offset_x"])
        self.offset_y = tk.IntVar(value=self.settings["crosshair_offset_y"])
        self.overlay_enabled = tk.BooleanVar(value=self.settings["overlay_enabled"])
        self.package_events = queue.Queue()
        self.package_groups = {}
        self.package_keys = []
        self.package_preview_photo = None
        self.package_preview_token = 0
        self.package_busy = False
        self.packages_loaded = False
        self.owner_check_started = False
        self.build()
        self.update_cursor_preview()
        self.update_crosshair()
        if self.overlay_enabled.get():
            self.show_overlay()

    def build(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=24, pady=(20, 8))
        tk.Label(header, text="✦  Chibi Crosshair Studio", font=("Segoe UI", 22, "bold"), bg=BG, fg=INK).pack(anchor="w")
        tk.Label(header, text="Karakter imleçlerini ve ekran ortası nişangâhını ayarla", font=("Segoe UI", 10), bg=BG, fg=MUTED).pack(anchor="w", pady=(2, 0))

        nav = tk.Frame(self.root, bg=BG)
        nav.pack(fill="x", padx=24, pady=(10, 10))
        button(nav, "Fare imleçleri", lambda: self.show_tab("cursor")).pack(side="left", padx=(0, 8))
        button(nav, "Nişangâh", lambda: self.show_tab("crosshair")).pack(side="left", padx=(0, 8))
        button(nav, "Paketler", lambda: self.show_tab("packages")).pack(side="left")

        self.content = tk.Frame(self.root, bg=BG)
        self.content.pack(fill="both", expand=True, padx=24, pady=(0, 14))
        self.cursor_tab = tk.Frame(self.content, bg=PANEL)
        self.crosshair_tab = tk.Frame(self.content, bg=PANEL)
        self.packages_tab = tk.Frame(self.content, bg=PANEL)
        for frame in (self.cursor_tab, self.crosshair_tab, self.packages_tab):
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.build_cursor_tab()
        self.build_crosshair_tab()
        self.build_packages_tab()
        self.show_tab("cursor")

        self.status = tk.StringVar(value="Hazır")
        tk.Label(self.root, textvariable=self.status, bg=BG, fg=MUTED, anchor="w", font=("Segoe UI", 9)).pack(fill="x", padx=26, pady=(0, 12))
        self.root.after(100, self.poll_package_events)

    def show_tab(self, name):
        {"cursor": self.cursor_tab, "crosshair": self.crosshair_tab,
         "packages": self.packages_tab}[name].tkraise()
        if name == "packages" and not self.packages_loaded and not self.package_busy:
            self.refresh_packages()
        if name == "packages" and not self.owner_check_started:
            self.owner_check_started = True
            threading.Thread(target=lambda: self.package_events.put(("owner", is_repository_owner())),
                             daemon=True).start()

    def build_packages_tab(self):
        left = tk.Frame(self.packages_tab, bg=PANEL)
        left.pack(side="left", fill="y", padx=(22, 12), pady=20)
        tk.Label(left, text="İmleç paketleri", bg=PANEL, fg=INK,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self.package_list = tk.Listbox(left, width=21, height=17, font=("Segoe UI", 10),
                                       bg="#302b37", fg=INK, selectbackground=PINK,
                                       selectforeground="#1f141c", relief="flat", bd=0,
                                       highlightthickness=0, activestyle="none",
                                       exportselection=False)
        self.package_list.pack(fill="y", pady=(12, 10))
        self.package_list.bind("<<ListboxSelect>>", self.choose_package)
        button(left, "Paketleri yenile", self.refresh_packages).pack(fill="x")
        self.add_package_button = button(left, "Yeni paket ekle", lambda: self.open_icon_manager(True))

        middle = tk.Frame(self.packages_tab, bg=PANEL)
        middle.pack(side="left", fill="y", padx=(0, 12), pady=20)
        tk.Label(middle, text="Paket içeriği", bg=PANEL, fg=INK,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self.package_icon_list = tk.Listbox(middle, width=20, height=17, font=("Segoe UI", 10),
                                            bg="#302b37", fg=INK, selectbackground=PINK,
                                            selectforeground="#1f141c", relief="flat", bd=0,
                                            highlightthickness=0, activestyle="none",
                                            exportselection=False)
        self.package_icon_list.pack(fill="y", pady=(12, 0))
        self.package_icon_list.bind("<<ListboxSelect>>", self.choose_package_icon)

        right = tk.Frame(self.packages_tab, bg=PANEL)
        right.pack(side="left", fill="both", expand=True, padx=(0, 22), pady=20)
        tk.Label(right, text="Simge önizlemesi", bg=PANEL, fg=INK,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self.package_preview = tk.Canvas(right, width=200, height=200, bg="#19171e",
                                         highlightthickness=0)
        self.package_preview.pack(pady=(12, 10), anchor="w")
        self.package_preview.create_text(100, 100, text="Paket seçin", fill=MUTED)
        self.package_title = tk.StringVar(value="Paket seçin")
        tk.Label(right, textvariable=self.package_title, bg=PANEL, fg=PINK,
                 font=("Segoe UI", 11, "bold"), wraplength=230).pack(anchor="w")
        self.package_info = tk.StringVar(value="GitHub'daki paketler burada görünecek.")
        tk.Label(right, textvariable=self.package_info, bg=PANEL, fg=MUTED,
                 justify="left", wraplength=230).pack(anchor="w", pady=(6, 12))
        self.package_install_button = button(right, "Paketi indir ve uygula",
                                             self.apply_selected_package, accent=True)
        self.package_install_button.pack(anchor="w")
        self.package_install_button.configure(state="disabled")

    def refresh_packages(self):
        if self.package_busy:
            return
        self.package_busy = True
        self.package_info.set("Paketler yükleniyor…")
        self.package_install_button.configure(state="disabled")
        def worker():
            try:
                icons, _ = fetch_catalog(CATALOG_ADDRESS)
                self.package_events.put(("catalog", icons))
            except Exception as error:
                self.package_events.put(("error", str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def selected_package_icons(self):
        selection = self.package_list.curselection()
        if not selection or selection[0] >= len(self.package_keys):
            return []
        return self.package_groups[self.package_keys[selection[0]]]

    def choose_package(self, _event=None):
        icons = self.selected_package_icons()
        self.package_preview_token += 1
        self.package_icon_list.delete(0, "end")
        self.package_preview.delete("all")
        self.package_preview_photo = None
        if not icons:
            self.package_install_button.configure(state="disabled")
            return
        for icon in icons:
            self.package_icon_list.insert("end", icon["name"])
        self.package_title.set(icons[0]["package_name"])
        selections = load_selections()
        installed = all(selections.get(icon["role"]) == icon["id"] for icon in icons)
        self.package_info.set(f"{len(icons)} simge · " + ("Yüklü" if installed else "İndirilebilir"))
        self.package_install_button.configure(state="disabled" if self.package_busy else "normal")
        self.package_icon_list.selection_set(0)
        self.choose_package_icon()

    def choose_package_icon(self, _event=None):
        selection = self.package_icon_list.curselection()
        icons = self.selected_package_icons()
        if not selection or selection[0] >= len(icons):
            return
        icon = icons[selection[0]]
        self.package_preview_token += 1
        token = self.package_preview_token
        self.package_preview.delete("all")
        self.package_preview.create_text(100, 100, text="Önizleme yükleniyor…", fill=MUTED)
        def worker():
            try:
                path, _ = download_icon(icon)
                self.package_events.put(("preview", token, path))
            except Exception as error:
                self.package_events.put(("preview_error", token, str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def apply_selected_package(self):
        icons = self.selected_package_icons()
        if not icons or self.package_busy:
            return
        self.package_busy = True
        self.package_install_button.configure(state="disabled")
        self.package_info.set(f"{icons[0]['package_name']} yükleniyor…")
        def worker():
            try:
                downloaded = install_package(icons)
                self.package_events.put(("installed", icons[0]["package_name"], downloaded))
            except Exception as error:
                self.package_events.put(("error", str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll_package_events(self):
        try:
            while True:
                event = self.package_events.get_nowait()
                kind = event[0]
                if kind == "owner":
                    if event[1]:
                        self.add_package_button.pack(fill="x", pady=(8, 0))
                elif kind == "catalog":
                    groups = {}
                    for icon in event[1]:
                        groups.setdefault(icon["package"], []).append(icon)
                    prior = self.package_list.curselection()
                    previous_key = self.package_keys[prior[0]] if prior and prior[0] < len(self.package_keys) else None
                    self.package_groups = groups
                    self.package_keys = list(groups)
                    self.package_list.delete(0, "end")
                    for key in self.package_keys:
                        self.package_list.insert("end", groups[key][0]["package_name"])
                    self.packages_loaded = True
                    self.package_busy = False
                    if self.package_keys:
                        index = self.package_keys.index(previous_key) if previous_key in groups else 0
                        self.package_list.selection_set(index)
                        self.choose_package()
                    else:
                        self.package_info.set("Henüz paket bulunamadı.")
                elif kind == "preview" and event[1] == self.package_preview_token:
                    with Image.open(event[2]) as source:
                        image = source.convert("RGBA")
                        image.thumbnail((184, 184), Image.Resampling.LANCZOS)
                    self.package_preview_photo = ImageTk.PhotoImage(image)
                    self.package_preview.delete("all")
                    self.package_preview.create_image(100, 100, image=self.package_preview_photo)
                elif kind == "preview_error" and event[1] == self.package_preview_token:
                    self.package_preview.delete("all")
                    self.package_preview.create_text(100, 100, text="Önizleme açılamadı", fill=MUTED)
                elif kind == "installed":
                    self.package_busy = False
                    self.choose_package()
                    self.update_cursor_preview()
                    self.status.set(f"{event[1]} uygulandı · {event[2]} yeni simge indirildi")
                elif kind == "error":
                    self.package_busy = False
                    self.package_install_button.configure(state="normal" if self.selected_package_icons() else "disabled")
                    self.package_info.set("İşlem tamamlanamadı.")
                    messagebox.showerror("Paket işlemi başarısız", event[1], parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self.poll_package_events)

    def slider(self, parent, text, variable, from_, to, callback, row):
        tk.Label(parent, text=text, bg=PANEL, fg=INK, font=("Segoe UI", 10)).grid(row=row, column=0, sticky="w", pady=(8, 0))
        tk.Scale(parent, variable=variable, from_=from_, to=to, orient="horizontal", resolution=1,
                 showvalue=True, command=lambda _value: callback(), bg=PANEL, fg=INK, troughcolor="#534653",
                 activebackground=PINK, highlightthickness=0, length=255, bd=0).grid(row=row + 1, column=0, sticky="ew")

    def build_cursor_tab(self):
        left = tk.Frame(self.cursor_tab, bg=PANEL)
        left.pack(side="left", fill="both", padx=22, pady=20)
        tk.Label(left, text=f"{len(NAMES)} karakter pozu", bg=PANEL, fg=INK, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        list_frame = tk.Frame(left, bg=PANEL)
        list_frame.pack(fill="y", pady=(12, 0))
        self.listbox = tk.Listbox(list_frame, height=15, width=18, font=("Segoe UI", 11), bg="#302b37", fg=INK,
                                  selectbackground=PINK, selectforeground="#1f141c", relief="flat", bd=0,
                                  highlightthickness=0, activestyle="none")
        self.listbox.pack(side="left", fill="y")
        scrollbar = tk.Scrollbar(list_frame, command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scrollbar.set)
        for name in NAMES:
            self.listbox.insert("end", name)
        self.listbox.selection_set(0)
        self.listbox.bind("<<ListboxSelect>>", self.choose_cursor)

        middle = tk.Frame(self.cursor_tab, bg=PANEL)
        middle.pack(side="left", fill="both", expand=True, pady=20)
        tk.Label(middle, text="Önizleme", bg=PANEL, fg=INK, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self.cursor_preview = tk.Canvas(middle, width=230, height=230, bg="#19171e", highlightthickness=0)
        self.cursor_preview.pack(pady=(12, 6))
        tk.Label(middle, textvariable=self.selected, bg=PANEL, fg=PINK, font=("Segoe UI", 12, "bold")).pack()
        button(middle, "Yeni simgeleri indir", self.open_icon_manager).pack(pady=(14, 0))

        right = tk.Frame(self.cursor_tab, bg=PANEL)
        right.pack(side="right", fill="y", padx=(0, 24), pady=20)
        tk.Label(right, text="Seçili imleç ayarları", bg=PANEL, fg=INK, font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        self.slider(right, "Boyut (piksel)", self.size, 32, 192, self.update_cursor_preview, 1)
        self.slider(right, "Resim boyutu (%)", self.image_scale, 20, 100, self.update_cursor_preview, 3)
        self.slider(right, "Tıklama noktası X", self.hotspot_x, 0, 150, self.update_cursor_preview, 5)
        self.slider(right, "Tıklama noktası Y", self.hotspot_y, 0, 50, self.update_cursor_preview, 7)
        tk.Checkbutton(right, text="Windows açılınca imleçleri uygula", variable=self.startup, bg=PANEL,
                       fg=INK, selectcolor="#393340", activebackground=PANEL, activeforeground=INK,
                       font=("Segoe UI", 9)).grid(row=9, column=0, sticky="w", pady=(14, 8))
        button(right, "Seçili imleci uygula", self.apply_cursor_settings, accent=True).grid(row=10, column=0, sticky="ew", pady=(6, 0))

    def build_crosshair_tab(self):
        preview_side = tk.Frame(self.crosshair_tab, bg=PANEL)
        preview_side.pack(side="left", fill="both", expand=True, padx=22, pady=20)
        tk.Label(preview_side, text="Nişangâh önizlemesi", bg=PANEL, fg=INK, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self.crosshair_preview = tk.Canvas(preview_side, width=320, height=320, bg="#19171e", highlightthickness=0)
        self.crosshair_preview.pack(pady=(12, 14))
        button(preview_side, "Rengi seç", self.choose_color).pack(anchor="center")

        settings_side = tk.Frame(self.crosshair_tab, bg=PANEL)
        settings_side.pack(side="right", fill="y", padx=(0, 26), pady=20)
        tk.Label(settings_side, text="Nişangâh ayarları", bg=PANEL, fg=INK, font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        self.slider(settings_side, "Çizgi uzunluğu", self.length, 2, 60, self.update_crosshair, 1)
        self.slider(settings_side, "Orta boşluk", self.gap, 0, 40, self.update_crosshair, 3)
        self.slider(settings_side, "Kalınlık", self.thickness, 1, 12, self.update_crosshair, 5)
        self.slider(settings_side, "Saydamlık (%)", self.opacity, 20, 100, self.update_crosshair, 7)
        tk.Checkbutton(settings_side, text="Orta nokta", variable=self.dot, command=self.update_crosshair,
                       bg=PANEL, fg=INK, selectcolor="#393340", activebackground=PANEL,
                       activeforeground=INK).grid(row=9, column=0, sticky="w", pady=(5, 0))
        tk.Checkbutton(settings_side, text="Ekranda göster", variable=self.overlay_enabled, command=self.toggle_overlay,
                       bg=PANEL, fg=INK, selectcolor="#393340", activebackground=PANEL,
                       activeforeground=INK).grid(row=10, column=0, sticky="w", pady=(2, 0))
        offset_row = tk.Frame(settings_side, bg=PANEL)
        offset_row.grid(row=11, column=0, sticky="w", pady=(8, 0))
        for label, variable in (("Konum X", self.offset_x), ("Konum Y", self.offset_y)):
            tk.Label(offset_row, text=label, bg=PANEL, fg=INK).pack(side="left", padx=(0, 4))
            field = tk.Spinbox(offset_row, from_=-500, to=500, width=5, textvariable=variable,
                               command=self.update_crosshair, bg="#393340", fg=INK,
                               buttonbackground="#534653", relief="flat")
            field.pack(side="left", padx=(0, 12))
            field.bind("<KeyRelease>", lambda _event: self.update_crosshair())
        button(settings_side, "Ayarları kaydet", self.save, accent=True).grid(row=12, column=0, sticky="ew", pady=(10, 0))

    def choose_cursor(self, _event=None):
        selected = self.listbox.curselection()
        if selected:
            self.remember_cursor_controls()
            name = NAMES[selected[0]]
            self._loading_cursor = True
            self.selected.set(name)
            draft = self.cursor_drafts[name]
            self.size.set(draft["size"])
            self.image_scale.set(draft["image_scale"])
            self.hotspot_x.set(draft["hotspot_x"])
            self.hotspot_y.set(draft["hotspot_y"])
            self._loading_cursor = False
            self.update_cursor_preview()

    def remember_cursor_controls(self):
        self.cursor_drafts[self.selected.get()] = {
            "size": self.size.get(),
            "image_scale": self.image_scale.get(),
            "hotspot_x": self.hotspot_x.get(),
            "hotspot_y": self.hotspot_y.get(),
        }

    def update_cursor_preview(self):
        if not self._loading_cursor:
            self.remember_cursor_controls()
        image = make_canvas(self.selected.get(), max(32, min(192, self.size.get())), self.image_scale.get())
        self.preview_photo = ImageTk.PhotoImage(image)
        self.cursor_preview.delete("all")
        self.cursor_preview.create_image(115, 115, image=self.preview_photo)
        center_x = 115 - image.width // 2 + min(self.hotspot_x.get(), image.width - 1)
        center_y = 115 - image.height // 2 + min(self.hotspot_y.get(), image.height - 1)
        self.cursor_preview.create_oval(center_x - 3, center_y - 3, center_x + 3, center_y + 3, outline=PINK, width=2)

    def refresh_preview_on_focus(self, event):
        if event.widget == self.root and hasattr(self, "cursor_preview"):
            self.update_cursor_preview()

    def open_icon_manager(self, publish=False):
        if getattr(sys, "frozen", False):
            command = [str(Path(sys.executable).with_name("Chibi Simge Güncelleyici.exe"))]
        else:
            command = [sys.executable, str(Path(__file__).with_name("icon_manager.pyw"))]
        if publish:
            command.append("--publish")
        try:
            subprocess.Popen(command, cwd=str(Path(command[-1]).parent))
        except OSError as error:
            messagebox.showerror("Güncelleyici açılamadı", str(error), parent=self.root)

    def values(self):
        values = dict(self.settings)
        values.update(cursor_settings={name: dict(config) for name, config in self.committed_cursor_settings.items()},
                      start_with_windows=self.startup.get(), crosshair_color=self.color.get(),
                      crosshair_length=self.length.get(), crosshair_gap=self.gap.get(),
                      crosshair_thickness=self.thickness.get(), crosshair_opacity=self.opacity.get(),
                      crosshair_dot=self.dot.get(), crosshair_offset_x=self.offset_x.get(),
                      crosshair_offset_y=self.offset_y.get(), overlay_enabled=self.overlay_enabled.get())
        return values

    def save(self):
        self.settings = self.values()
        save_settings(self.settings)
        set_startup(self.startup.get())
        self.status.set("Ayarlar kaydedildi")

    def apply_cursor_settings(self):
        try:
            self.remember_cursor_controls()
            name = self.selected.get()
            config = dict(self.cursor_drafts[name])
            apply_cursor(name, config)
            self.committed_cursor_settings[name] = config
            roles = set(self.settings.get("applied_roles", []))
            roles.add(name)
            self.settings["applied_roles"] = [role for role in NAMES if role in roles]
            self.save()
            self.status.set(f"Yalnızca {name} imleci uygulandı · {config['size']} piksel · resim %{config['image_scale']}")
        except Exception as error:
            messagebox.showerror("İmleç uygulanamadı", str(error), parent=self.root)

    def draw_crosshair(self, canvas, cx, cy):
        canvas.delete("all")
        gap, length, width = self.gap.get(), self.length.get(), self.thickness.get()
        color = self.color.get()
        for x1, y1, x2, y2 in ((cx - gap - length, cy, cx - gap, cy),
                               (cx + gap, cy, cx + gap + length, cy),
                               (cx, cy - gap - length, cx, cy - gap),
                               (cx, cy + gap, cx, cy + gap + length)):
            canvas.create_line(x1, y1, x2, y2, fill=color, width=width, capstyle=tk.ROUND)
        if self.dot.get():
            radius = max(1, width // 2)
            canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill=color, outline=color)

    def update_crosshair(self):
        self.draw_crosshair(self.crosshair_preview, 160, 160)
        if self.overlay:
            self.overlay.update(self.color.get(), self.length.get(), self.gap.get(),
                                self.thickness.get(), self.opacity.get(), self.dot.get(),
                                self.offset_x.get(), self.offset_y.get())

    def choose_color(self):
        choice = colorchooser.askcolor(color=self.color.get(), parent=self.root)
        if choice[1]:
            self.color.set(choice[1])
            self.update_crosshair()

    def show_overlay(self):
        if self.overlay:
            return
        try:
            self.overlay = CrosshairOverlay(self.root.winfo_screenwidth(),
                                            self.root.winfo_screenheight())
            self.update_crosshair()
        except Exception as error:
            if self.overlay:
                self.overlay.close()
                self.overlay = None
            self.overlay_enabled.set(False)
            self.status.set(f"Nişangâh gösterilemedi: {error}")

    def toggle_overlay(self):
        if self.overlay_enabled.get():
            self.show_overlay()
        elif self.overlay:
            self.overlay.close()
            self.overlay = None
        self.save()

    def close(self):
        self.save()
        if self.overlay:
            self.overlay.close()
        self.root.destroy()


if __name__ == "__main__":
    if "--apply-only" in sys.argv:
        apply_cursors(load_settings())
    else:
        app = Studio()
        app.root.mainloop()
