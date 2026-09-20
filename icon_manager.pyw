"""Standalone GitHub icon catalog manager for Chibi Crosshair Studio."""

import json
import threading
import tkinter as tk
from queue import Empty, Queue
from tkinter import ttk

from PIL import Image, ImageTk
from tkinterdnd2 import TkinterDnD

from cursor_core import APP_DIR, DOWNLOADED_ICONS_DIR, NAMES
from icon_catalog import (download_icon, fetch_catalog, install_icon, install_package,
                          load_selections, update_installed)
from icon_publisher_ui import PublisherDialog

BG = "#17151d"
PANEL = "#24212d"
INK = "#fff5f8"
PINK = "#ff6790"
MUTED = "#beb4c0"
CONFIG = APP_DIR / "icon_manager.json"
DEFAULT_REPOSITORY = "https://github.com/novax1213/chibi-crosshair-studio"


class IconManager:
    def __init__(self):
        self.root = TkinterDnD.Tk()
        self.root.title("Chibi Simge Güncelleyici")
        self.root.geometry("820x680")
        self.root.minsize(720, 620)
        self.root.configure(bg=BG)
        self.events = Queue()
        self.icons = []
        self.visible_icons = []
        self.packages = {}
        self.photo = None
        self.preview_token = 0
        self.busy = False
        self.address = tk.StringVar(value=DEFAULT_REPOSITORY)
        self.branch = tk.StringVar(value="main")
        self.role = tk.StringVar(value=NAMES[0])
        self.package_name = tk.StringVar()
        self.status = tk.StringVar(value="Paketler yükleniyor...")
        self._load_config()
        self._build()
        self.root.after(100, self._poll)
        self.root.after(250, self.check)

    def _load_config(self):
        try:
            data = json.loads(CONFIG.read_text(encoding="utf-8"))
            self.address.set(data.get("address") or DEFAULT_REPOSITORY)
            self.branch.set(data.get("branch", "main"))
        except (OSError, ValueError, TypeError):
            pass

    def _save_config(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps({"address": self.address.get().strip(),
                                      "branch": self.branch.get().strip()},
                                     ensure_ascii=False, indent=2), encoding="utf-8")

    def _button(self, parent, label, command, accent=False):
        return tk.Button(parent, text=label, command=command, font=("Segoe UI", 10, "bold"),
                         bg=PINK if accent else "#393340", fg="#21141c" if accent else INK,
                         activebackground="#ff8daa" if accent else "#504757",
                         relief="flat", bd=0, padx=14, pady=8)

    def _build(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=24, pady=(18, 2))
        tk.Label(header, text="Chibi Simge Güncelleyici", bg=BG, fg=INK,
                 font=("Segoe UI", 20, "bold")).pack(side="left")
        self._button(header, "GitHub'a simge yükle", self.open_publisher).pack(side="right")
        tk.Label(self.root, text="Paket seçip bütün imleçleri indir veya tek bir simgeyi uygula.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=24)

        source = tk.Frame(self.root, bg=PANEL)
        source.pack(fill="x", padx=24, pady=(18, 12))
        tk.Label(source, text="GitHub depo veya icons.json adresi", bg=PANEL, fg=INK).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(10, 2))
        tk.Entry(source, textvariable=self.address, bg="#393340", fg=INK, insertbackground=INK,
                 relief="flat", font=("Segoe UI", 10)).grid(row=1, column=0, sticky="ew", padx=(12, 8), pady=(0, 12), ipady=6)
        tk.Label(source, text="Dal", bg=PANEL, fg=INK).grid(row=0, column=1, sticky="w")
        tk.Entry(source, textvariable=self.branch, width=9, bg="#393340", fg=INK,
                 insertbackground=INK, relief="flat").grid(row=1, column=1, padx=(0, 8), pady=(0, 12), ipady=7)
        self.check_button = self._button(source, "Katalogu kontrol et", self.check, True)
        self.check_button.grid(row=1, column=2, padx=(0, 12), pady=(0, 12))
        source.columnconfigure(0, weight=1)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=24)
        left = tk.Frame(body, bg=PANEL)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        tk.Label(left, text="Paketler", bg=PANEL, fg=INK,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=14, pady=(12, 8))
        self.package_picker = ttk.Combobox(left, textvariable=self.package_name, state="readonly")
        self.package_picker.pack(fill="x", padx=14, pady=(0, 8))
        self.package_picker.bind("<<ComboboxSelected>>", self._show_package)
        self.package_button = self._button(left, "Paketi indir ve uygula", self.install_selected_package, True)
        self.package_button.pack(fill="x", padx=14, pady=(0, 12))
        tk.Label(left, text="Paketteki simgeler", bg=PANEL, fg=INK,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(0, 8))
        list_frame = tk.Frame(left, bg=PANEL)
        list_frame.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.listbox = tk.Listbox(list_frame, bg="#302b37", fg=INK, selectbackground=PINK,
                                  selectforeground="#21141c", relief="flat", bd=0,
                                  font=("Segoe UI", 10), activestyle="none")
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._select)
        scrollbar = tk.Scrollbar(list_frame, command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scrollbar.set)

        right = tk.Frame(body, bg=PANEL, width=290)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        tk.Label(right, text="Seçili simge", bg=PANEL, fg=INK,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=14, pady=(12, 8))
        self.preview = tk.Canvas(right, width=180, height=180, bg="#19171e", highlightthickness=0)
        self.preview.pack(pady=(0, 8))
        self.icon_name = tk.StringVar(value="Katalogu kontrol et")
        tk.Label(right, textvariable=self.icon_name, bg=PANEL, fg=PINK,
                 font=("Segoe UI", 11, "bold"), wraplength=255).pack(padx=10)
        tk.Label(right, text="Kullanılacak imleç türü", bg=PANEL, fg=INK).pack(anchor="w", padx=16, pady=(12, 4))
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Chibi.TCombobox", fieldbackground="#393340", background="#393340",
                        foreground=INK, arrowcolor=INK)
        self.roles = ttk.Combobox(right, textvariable=self.role, values=NAMES, state="readonly",
                                   style="Chibi.TCombobox")
        self.roles.pack(fill="x", padx=16)
        self.install_button = self._button(right, "İndir ve imlece uygula", self.install, True)
        self.install_button.pack(fill="x", padx=16, pady=(14, 8))
        self.refresh_button = self._button(right, "Yüklü simgeleri güncelle", self.refresh)
        self.refresh_button.pack(fill="x", padx=16)

        tk.Label(self.root, textvariable=self.status, bg=BG, fg=MUTED, anchor="w",
                 font=("Segoe UI", 9), wraplength=730).pack(fill="x", padx=26, pady=(12, 14))

    def _run(self, operation, worker):
        if self.busy:
            return
        self.busy = True
        self.status.set("İşleniyor...")
        for control in (self.check_button, self.install_button, self.refresh_button, self.package_button):
            control.configure(state="disabled")

        def task():
            try:
                self.events.put((operation, True, worker()))
            except Exception as error:
                self.events.put((operation, False, str(error)))

        threading.Thread(target=task, daemon=True).start()

    def _poll(self):
        try:
            while True:
                operation, success, result = self.events.get_nowait()
                if operation == "preview":
                    token, icon_id, value = result
                    current = self._current()
                    if token == self.preview_token and current and current["id"] == icon_id:
                        if success:
                            self._draw_preview(value)
                        elif self.photo is None:
                            self.preview.delete("all")
                            self.preview.create_text(90, 90, text="Önizleme yüklenemedi", fill=MUTED)
                            self.status.set(f"Önizleme yüklenemedi: {value}")
                    continue
                self.busy = False
                for control in (self.check_button, self.install_button, self.refresh_button, self.package_button):
                    control.configure(state="normal")
                if not success:
                    self.status.set(f"Hata: {result}")
                elif operation == "check":
                    self.icons, _ = result
                    self.packages = {}
                    for icon in self.icons:
                        self.packages.setdefault(icon["package_name"], []).append(icon)
                    names = list(self.packages)
                    self.package_picker.configure(values=names)
                    self.package_name.set(names[0] if names else "")
                    self._show_package()
                    self.status.set(f"{len(names)} paket, {len(self.icons)} simge bulundu.")
                elif operation == "install":
                    self.status.set("Simge indirildi ve Windows imlecine uygulandı." if result else
                                    "Simge zaten günceldi; Windows imlecine uygulandı.")
                    current_role = self.role.get()
                    self._select(reset_role=False)
                    self.role.set(current_role)
                    index = self.listbox.curselection()
                    if index:
                        icon = self.visible_icons[index[0]]
                        self.listbox.delete(index[0])
                        self.listbox.insert(index[0], f"{icon['name']}  [{icon['role']}] ✓")
                        self.listbox.selection_set(index[0])
                elif operation == "package":
                    self._show_package()
                    self.status.set(f"Paket indirildi ve {len(self.visible_icons)} imlece uygulandı.")
                elif operation == "refresh":
                    self.status.set(f"{len(result)} yüklü imleç güncellendi." if result else
                                    "Yüklü simgelerin hepsi güncel.")
        except Empty:
            pass
        self.root.after(100, self._poll)

    def _current(self):
        selection = self.listbox.curselection()
        return self.visible_icons[selection[0]] if selection else None

    def _show_package(self, _event=None):
        self.visible_icons = self.packages.get(self.package_name.get(), [])
        selected = load_selections()
        self.listbox.delete(0, "end")
        for icon in self.visible_icons:
            installed = " ✓" if icon["id"] in selected.values() else ""
            self.listbox.insert("end", f"{icon['name']}  [{icon['role']}]{installed}")
        if self.visible_icons:
            self.listbox.selection_set(0)
            self._select()

    def install_selected_package(self):
        icons = list(self.visible_icons)
        if not icons:
            self.status.set("Önce bir paket seç.")
            return
        self._run("package", lambda: install_package(icons))

    def _select(self, _event=None, reset_role=True):
        self.preview_token += 1
        token = self.preview_token
        icon = self._current()
        self.preview.delete("all")
        self.photo = None
        if not icon:
            return
        self.icon_name.set(icon["name"])
        if reset_role:
            self.role.set(icon["role"])
        path = DOWNLOADED_ICONS_DIR / f"{icon['id']}.png"
        if path.exists():
            self._draw_preview(path)
        else:
            self.preview.create_text(90, 90, text="Önizleme yükleniyor...", fill=MUTED)

        def load_preview():
            try:
                saved_path, _ = download_icon(icon)
                self.events.put(("preview", True, (token, icon["id"], saved_path)))
            except Exception as error:
                self.events.put(("preview", False, (token, icon["id"], str(error))))

        threading.Thread(target=load_preview, daemon=True).start()

    def _draw_preview(self, path):
        try:
            with Image.open(path) as source:
                image = source.convert("RGBA")
            image.thumbnail((165, 165), Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(image)
            self.preview.delete("all")
            self.preview.create_image(90, 90, image=self.photo)
        except OSError:
            self.photo = None
            self.preview.delete("all")
            self.preview.create_text(90, 90, text="Önizleme açılamadı", fill=MUTED)

    def check(self):
        address = self.address.get().strip()
        branch = self.branch.get().strip() or "main"
        self._save_config()
        self._run("check", lambda: fetch_catalog(address, branch))

    def install(self):
        icon = self._current()
        if not icon:
            self.status.set("Önce katalogdan bir simge seç.")
            return
        role = self.role.get()
        self._run("install", lambda: install_icon(icon, role))

    def refresh(self):
        if not self.icons:
            self.status.set("Önce kataloğu kontrol et.")
            return
        self._run("refresh", lambda: update_installed(self.icons))

    def open_publisher(self):
        PublisherDialog(self.root)


if __name__ == "__main__":
    IconManager().root.mainloop()
