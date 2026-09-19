"""Drag-and-drop folder publisher with a named cursor checklist."""

from pathlib import Path
from queue import Empty, Queue
import threading
import tkinter as tk
from tkinter import filedialog

from PIL import Image, ImageTk
from tkinterdnd2 import DND_FILES

from cursor_core import NAMES
from icon_publisher import publish_folder, scan_folder

BG = "#17151d"
PANEL = "#24212d"
INK = "#fff5f8"
MUTED = "#beb4c0"
PINK = "#ff6790"


class PublisherDialog:
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("Yeni paket yayınla")
        self.window.geometry("800x690")
        self.window.minsize(720, 620)
        self.window.configure(bg=BG)
        self.window.transient(parent)
        self.folder = tk.StringVar()
        self.package_name = tk.StringVar()
        self.status = tk.StringVar(value="Resim klasörünü sürükleyip bırak veya Klasör seç'e bas.")
        self.rows = [{"name": name, "path": None, "status": "Bekliyor", "error": None} for name in NAMES]
        self.photo = None
        self.events = Queue()
        self.busy = False
        self._build()
        self._fill_rows()
        self.drop_zone.drop_target_register(DND_FILES)
        self.drop_zone.dnd_bind("<<Drop>>", self._dropped)
        self.window.after(100, self._poll)

    def _button(self, parent, label, command, accent=False):
        return tk.Button(parent, text=label, command=command, font=("Segoe UI", 10, "bold"),
                         bg=PINK if accent else "#393340", fg="#21141c" if accent else INK,
                         relief="flat", bd=0, padx=14, pady=8)

    def _build(self):
        tk.Label(self.window, text="Yeni imleç paketi", bg=BG, fg=INK,
                 font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=24, pady=(18, 2))
        tk.Label(self.window, text="Klasörü bırak, paket adını yaz, GitHub'a yükle.",
                 bg=BG, fg=MUTED).pack(anchor="w", padx=24)

        source = tk.Frame(self.window, bg=PANEL)
        source.pack(fill="x", padx=24, pady=(16, 12))
        self.drop_zone = tk.Label(source, text="📁  PNG klasörünü buraya sürükleyip bırak",
                                  bg="#393340", fg=INK, font=("Segoe UI", 12, "bold"),
                                  height=3, relief="solid", bd=1)
        self.drop_zone.pack(fill="x", padx=12, pady=(12, 8))
        self.folder_button = self._button(source, "Klasör seç", self.choose_folder, True)
        self.folder_button.pack(side="right", padx=(8, 12), pady=(0, 12))
        tk.Entry(source, textvariable=self.folder, state="readonly", readonlybackground="#393340",
                 fg=INK, relief="flat").pack(side="left", fill="x", expand=True,
                                               padx=(12, 0), pady=(0, 12), ipady=7)

        pack_row = tk.Frame(self.window, bg=BG)
        pack_row.pack(fill="x", padx=24, pady=(0, 12))
        tk.Label(pack_row, text="Paket adı", bg=BG, fg=INK).pack(side="left", padx=(0, 12))
        tk.Entry(pack_row, textvariable=self.package_name, bg="#393340", fg=INK,
                 insertbackground=INK, relief="flat").pack(side="left", fill="x", expand=True, ipady=7)

        body = tk.Frame(self.window, bg=BG)
        body.pack(fill="both", expand=True, padx=24)
        left = tk.Frame(body, bg=PANEL)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        tk.Label(left, text="Paket içindeki imleçler", bg=PANEL, fg=INK,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=14, pady=(12, 8))
        self.listbox = tk.Listbox(left, bg="#302b37", fg=INK, selectbackground=PINK,
                                  selectforeground="#21141c", relief="flat", bd=0,
                                  font=("Segoe UI", 10), activestyle="none")
        self.listbox.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.listbox.bind("<<ListboxSelect>>", self._preview)

        right = tk.Frame(body, bg=PANEL, width=260)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        tk.Label(right, text="Seçili resim", bg=PANEL, fg=INK,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=14, pady=(12, 8))
        self.preview = tk.Canvas(right, width=200, height=200, bg="#19171e", highlightthickness=0)
        self.preview.pack(pady=(0, 10))
        self.detail = tk.StringVar(value="Klasör seç")
        tk.Label(right, textvariable=self.detail, bg=PANEL, fg=PINK,
                 font=("Segoe UI", 11, "bold"), wraplength=235).pack(padx=12)
        self.publish_button = self._button(right, "Paketi GitHub'a yükle", self.publish, True)
        self.publish_button.pack(fill="x", padx=14, pady=(20, 0))
        self.publish_button.configure(state="disabled")

        tk.Label(self.window, textvariable=self.status, bg=BG, fg=MUTED,
                 anchor="w", wraplength=750).pack(fill="x", padx=26, pady=(12, 14))

    def _fill_rows(self):
        selection = self.listbox.curselection()
        index = selection[0] if selection else 0
        self.listbox.delete(0, "end")
        for row in self.rows:
            self.listbox.insert("end", f"{row['name']}.png    —    {row['status']}")
        self.listbox.selection_set(min(index, len(self.rows) - 1))
        self._preview()

    def _preview(self, _event=None):
        selection = self.listbox.curselection()
        if not selection:
            return
        row = self.rows[selection[0]]
        self.detail.set(f"{row['name']}.png · {row['status']}")
        self.preview.delete("all")
        self.photo = None
        if row["path"] and row["status"] != "Hatalı":
            try:
                with Image.open(row["path"]) as source:
                    image = source.convert("RGBA")
                image.thumbnail((185, 185), Image.Resampling.LANCZOS)
                self.photo = ImageTk.PhotoImage(image)
                self.preview.create_image(100, 100, image=self.photo)
            except OSError:
                self.preview.create_text(100, 100, text="Önizleme açılamadı", fill=MUTED)
        else:
            self.preview.create_text(100, 100, text=row["error"] or "Dosya yok", fill=MUTED,
                                     width=180)

    def _dropped(self, event):
        paths = [Path(value) for value in self.window.tk.splitlist(event.data)]
        folders = {path if path.is_dir() else path.parent for path in paths}
        if len(folders) != 1:
            self.status.set("Tek bir klasör veya aynı klasördeki PNG dosyalarını bırak.")
        elif not self.busy:
            self._set_folder(next(iter(folders)))

    def _set_folder(self, folder):
        self.folder.set(str(folder))
        self.package_name.set(Path(folder).name)
        self._scan()

    def choose_folder(self):
        folder = filedialog.askdirectory(parent=self.window, title="İmleç PNG klasörünü seç")
        if folder:
            self._set_folder(folder)

    def _scan(self):
        try:
            self.rows = scan_folder(self.folder.get())
            chosen = sum(row["status"] == "Seçildi" for row in self.rows)
            invalid = sum(row["status"] == "Hatalı" for row in self.rows)
            self.publish_button.configure(state="normal" if chosen and not invalid else "disabled")
            self.status.set(f"{chosen} resim bulundu, {invalid} hatalı. Paket adını kontrol edip yükle.")
            self._fill_rows()
        except Exception as error:
            self.publish_button.configure(state="disabled")
            self.status.set(str(error))

    def publish(self):
        if self.busy or not self.folder.get():
            return
        if not self.package_name.get().strip():
            self.status.set("Paket adı yaz.")
            return
        self.busy = True
        self.publish_button.configure(state="disabled")
        self.folder_button.configure(state="disabled")
        self.status.set("Paket hazırlanıyor ve GitHub'a yükleniyor...")
        folder, name = self.folder.get(), self.package_name.get().strip()

        def work():
            try:
                self.events.put((True, publish_folder(folder, name)))
            except Exception as error:
                self.events.put((False, str(error)))

        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        if not self.window.winfo_exists():
            return
        try:
            success, result = self.events.get_nowait()
            self.busy = False
            self.folder_button.configure(state="normal")
            self._scan()
            if success:
                self.status.set(f"{result.get('package', self.package_name.get())} paketi GitHub'a yüklendi."
                                if result["pushed"] else "Paket zaten güncel.")
            else:
                self.status.set(f"Yükleme başarısız: {result}")
        except Empty:
            pass
        self.window.after(100, self._poll)
