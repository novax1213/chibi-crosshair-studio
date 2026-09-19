"""Publish a folder of named cursor PNGs without asking for a Git project."""

from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata

from PIL import Image

from build_icon_catalog import build as build_catalog
from cursor_core import NAMES

REMOTE = "https://github.com/novax1213/chibi-crosshair-studio.git"
MAX_ICON_BYTES = 12 * 1024 * 1024


def _digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def package_slug(name):
    normalized = unicodedata.normalize("NFKD", name).replace("ı", "i").replace("İ", "I")
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")[:48].rstrip("-")
    if not slug or slug == "base":
        raise ValueError("Paket adına en az bir harf veya rakam yaz.")
    return slug


def scan_folder(folder, project=None, slug=None):
    """List the 17 expected file names; optionally compare against a checkout."""
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError("Seçilen klasör bulunamadı.")
    files = {path.name.lower(): path for path in folder.iterdir() if path.is_file()}
    rows = []
    for name in NAMES:
        source = files.get(f"{name.lower()}.png")
        if source is None:
            rows.append({"name": name, "path": None, "status": "Yok", "error": None})
            continue
        error = None
        try:
            if source.is_symlink() or source.stat().st_size > MAX_ICON_BYTES:
                raise ValueError("Dosya bağlantı veya 12 MB sınırını aşıyor")
            with Image.open(source) as image:
                if image.format != "PNG" or not (16 <= image.width <= 4096 and 16 <= image.height <= 4096):
                    raise ValueError("Geçerli boyutta PNG olmalı")
                image.verify()
            if project is None:
                status = "Seçildi"
            else:
                target = Path(project) / "packs" / slug / f"{name}.png"
                status = "Aynı" if target.is_file() and _digest(source) == _digest(target) else "Yeni / değişti"
        except (OSError, ValueError) as exc:
            status, error = "Hatalı", str(exc)
        rows.append({"name": name, "path": source, "status": status, "error": error})
    return rows


def _git(folder, *args):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(["git", *args], cwd=folder, text=True, encoding="utf-8",
                                errors="replace", capture_output=True, timeout=180, creationflags=flags)
    except FileNotFoundError as error:
        raise RuntimeError("Git bulunamadı. Git for Windows kurulmalı.") from error
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"GitHub'a gönderilemedi: {detail or 'bilinmeyen hata'}")
    return result.stdout.strip()


def publish_folder(folder, package_name=None, remote=REMOTE):
    """Clone the latest repository, copy icons, rebuild the catalog, push."""
    rows = scan_folder(folder)
    errors = [f"{row['name']}: {row['error']}" for row in rows if row["status"] == "Hatalı"]
    if errors:
        raise ValueError("Hatalı resimler: " + "; ".join(errors))
    present = [row for row in rows if row["path"]]
    if not present:
        raise ValueError("Klasörde Normal.png gibi tanınan bir imleç resmi bulunamadı.")
    name = (package_name or Path(folder).name).strip()
    if len(name) > 80:
        raise ValueError("Paket adı en çok 80 karakter olabilir.")
    slug = package_slug(name)

    with tempfile.TemporaryDirectory(prefix="chibi-cursor-") as temporary:
        checkout = Path(temporary) / "project"
        _git(temporary, "clone", "--depth=1", "--branch", "main", remote, str(checkout))
        rows = scan_folder(folder, checkout, slug)
        changed = [row for row in rows if row["status"] == "Yeni / değişti"]
        pack_dir = checkout / "packs" / slug
        metadata = pack_dir / "pack.json"
        old_name = json.loads(metadata.read_text(encoding="utf-8")).get("name") if metadata.exists() else None
        if not changed and old_name == name:
            return {"changed": [], "pushed": False}
        pack_dir.mkdir(parents=True, exist_ok=True)
        for row in changed:
            target = pack_dir / f"{row['name']}.png"
            shutil.copyfile(row["path"], target)
        metadata.write_text(json.dumps({"name": name}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        build_catalog(checkout, announce=False)
        _git(checkout, "add", "--", *[f"packs/{slug}/{row['name']}.png" for row in changed],
             f"packs/{slug}/pack.json", "icons.json")
        _git(checkout, "-c", "user.name=Chibi Simge Güncelleyici",
             "-c", "user.email=chibi-icons@users.noreply.github.com",
             "commit", "-m", "Update cursor icons")
        _git(checkout, "push", "origin", "main")
        return {"changed": [row["name"] for row in changed], "pushed": True, "package": name}
