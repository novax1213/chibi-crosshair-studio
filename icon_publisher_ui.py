"""Folder picker and named cursor checklist for GitHub publishing."""

from pathlib import Path
from queue import Empty, Queue
import threading
import tkinter as tk
from tkinter import filedialog

from PIL import Image, ImageTk

from cursor_core import NAMES
from icon_publisher import find_project, publish_folder, scan_folder

BG = "#17151d"
PANEL = "#24212d"
INK = "#fff5f8"
MUTED = "#beb4c0"
PINK = "#ff6790"


class PublisherDialog:
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("GitHub'a simge yükle")
        self.window.geometry("800x680")
        self.window.minsize(720, 620)
        self.window.configure(bg=BG)
        self.window.transient(parent)
        self.project = find_project()
        self.folder = tk.StringVar()
        self.status = tk.StringVar(value="PNG resimlerinin olduğu klasörü seç. Dosya adları listedeki imleç adlarıyla eşleşmeli.")
        self.rows = [{"name": name, "path": None, "status": "Klasör seç", "error": None} for name in NAMES]
        self.photo = None
        self.events = Queue()
        self.busy = False
        self._build()
        self._fill_rows()
        self.window.after(100, self._poll)

    def _button(self, parent, label, command, accent=False):
        return tk.Button(parent, text=label, command=command, font=("Segoe UI", 10, "bold"),
                         bg=PINK if accent else "#393340", fg="#21141c" if accent else INK,
                         relief="flat", bd=0, padx=14, pady=8)

    def _build(self):
        tk.Label(self.window, text="GitHub'a simge yükle", bg=BG, fg=INK,
                 font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=24, pady=(18, 2))
        tk.Label(self.window, text="Normal.png, Help.png gibi adlandırılmış resimleri tek işlemle yayınla.",
                 bg=BG, fg=MUTED).pack(anchor="w", padx=24)

        source = tk.Frame(self.window, bg=PANEL)
        source.pack(fill="x", padx=24, pady=(18, 12))
        tk.Label(source, text="Resim klasörü", bg=PANEL, fg=INK).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))
        tk.Entry(source, textvariable=self.folder, state="readonly", readonlybackground="#393340",
                 fg=INK, relief="flat").grid(row=1, column=0, sticky="ew", padx=(12, 8), pady=(0, 12), ipady=7)
        self.folder_button = self._button(source, "Klasör seç", self.choose_folder, True)
        self.folder_button.grid(row=1, column=1, padx=(0, 12), pady=(0, 12))
        source.columnconfigure(0, weight=1)

        project_row = tk.Frame(self.window, bg=BG)
        project_row.pack(fill="x", padx=24, pady=(0, 10))
        self.project_label = tk.StringVar(value=f"GitHub projesi: {self.project or 'bulunamadı'}")
        tk.Label(project_row, textvariable=self.project_label, bg=BG, fg=MUTED,
                 anchor="w", wraplength=640).pack(side="left", fill="x", expand=True)
        self.project_button = self._button(project_row, "Proje seç", self.choose_project)
        self.project_button.pack(side="right")

        body = tk.Frame(self.window, bg=BG)
        body.pack(fill="both", expand=True, padx=24)
        left = tk.Frame(body, bg=PANEL)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        tk.Label(left, text="İmleç adları ve dosya durumu", bg=PANEL, fg=INK,
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
        self.publish_button = self._button(right, "Değişenleri GitHub'a gönder", self.publish, True)
        self.publish_button.pack(fill="x", padx=14, pady=(20, 0))

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

    def choose_folder(self):
        folder = filedialog.askdirectory(parent=self.window, title="İmleç PNG klasörünü seç")
        if folder:
            self.folder.set(folder)
            self._scan()

    def choose_project(self):
        folder = filedialog.askdirectory(parent=self.window, title="Chibi Crosshair Studio Git projesini seç")
        if folder:
            self.project = Path(folder)
            self.project_label.set(f"GitHub projesi: {self.project}")
            self._scan()

    def _scan(self):
        if not self.folder.get():
            return
        try:
            if not self.project:
                raise ValueError("GitHub proje klasörü bulunamadı; Proje seç düğmesini kullan.")
            self.rows = scan_folder(self.folder.get(), self.project)
            changed = sum(row["status"] == "Değişti" for row in self.rows)
            invalid = sum(row["status"] == "Hatalı" for row in self.rows)
            self.status.set(f"{changed} değişen resim, {invalid} hatalı resim. İsimler solda görünüyor.")
            self._fill_rows()
        except Exception as error:
            self.status.set(str(error))

    def publish(self):
        if self.busy:
            return
        if not self.folder.get() or not self.project:
            self.status.set("Önce resim klasörünü ve GitHub proje klasörünü seç.")
            return
        if any(row["status"] == "Hatalı" for row in self.rows):
            self.status.set("Hatalı PNG dosyalarını düzeltip klasörü yeniden seç.")
            return
        self.busy = True
        self.publish_button.configure(state="disabled")
        self.folder_button.configure(state="disabled")
        self.project_button.configure(state="disabled")
        self.status.set("Katalog hazırlanıyor ve GitHub'a gönderiliyor...")
        folder, project = self.folder.get(), self.project

        def work():
            try:
                self.events.put((True, publish_folder(folder, project)))
            except Exception as error:
                self.events.put((False, str(error)))

        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            success, result = self.events.get_nowait()
            self.busy = False
            for control in (self.publish_button, self.folder_button, self.project_button):
                control.configure(state="normal")
            if success:
                self._scan()
                names = ", ".join(result["changed"])
                self.status.set(f"GitHub'a gönderildi: {names}" if result["pushed"] and names else
                                "GitHub'a bekleyen değişiklikler gönderildi." if result["pushed"] else
                                "Resimler zaten güncel; gönderilecek değişiklik yok.")
            else:
                self.status.set(f"Yükleme başarısız: {result}")
        except Empty:
            pass
        if self.window.winfo_exists():
            self.window.after(100, self._poll)
