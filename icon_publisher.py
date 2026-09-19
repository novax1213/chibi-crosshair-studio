"""Publish a folder of named cursor PNGs to the project's GitHub repository."""

from pathlib import Path
import hashlib
import os
import re
import subprocess
import sys

from PIL import Image

from build_icon_catalog import build as build_catalog
from cursor_core import NAMES

EXPECTED_REMOTE = "https://github.com/novax1213/chibi-crosshair-studio.git"
MAX_ICON_BYTES = 12 * 1024 * 1024


def find_project():
    """Find the source checkout beside the release EXE or Python script."""
    starts = [Path(sys.executable).resolve().parent, Path(__file__).resolve().parent, Path.cwd()]
    for start in starts:
        for candidate in (start, *start.parents):
            if (candidate / ".git").exists() and (candidate / "build_icon_catalog.py").is_file():
                return candidate
    return None


def _digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def scan_folder(folder, project):
    """Return one row per Windows cursor name with file status and local path."""
    folder = Path(folder)
    project = Path(project)
    if not folder.is_dir():
        raise ValueError("Seçilen klasör bulunamadı.")
    files = {path.name.lower(): path for path in folder.iterdir() if path.is_file()}
    dirty = set()
    if (project / ".git").exists():
        result = _git(project, "status", "--porcelain", "-uall", "--", "assets", check=False)
        if result.returncode == 0:
            dirty = {line[3:].replace("\\", "/") for line in result.stdout.splitlines()}
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
            target = project / "assets" / f"{name}.png"
            status = ("Aynı" if target.is_file() and _digest(source) == _digest(target)
                      and f"assets/{name}.png" not in dirty else "Değişti")
        except (OSError, ValueError) as exc:
            status, error = "Hatalı", str(exc)
        rows.append({"name": name, "path": source, "status": status, "error": error})
    return rows


def _git(project, *args, check=True):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(["git", *args], cwd=project, text=True, encoding="utf-8",
                            errors="replace", capture_output=True, timeout=120, creationflags=flags)
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Git işlemi başarısız: {detail or 'bilinmeyen hata'}")
    return result


def _check_project(project):
    project = Path(project).resolve()
    if not (project / ".git").exists() or not (project / "assets").is_dir():
        raise ValueError("Geçerli proje klasörü seçilmedi.")
    branch = _git(project, "branch", "--show-current").stdout.strip()
    if branch != "main":
        raise ValueError("Proje main dalında olmalı.")
    remote = _git(project, "remote", "get-url", "origin").stdout.strip().rstrip("/")
    if remote.lower().removesuffix(".git") != EXPECTED_REMOTE.lower().removesuffix(".git"):
        raise ValueError("Projenin origin adresi Chibi Crosshair Studio GitHub deposu değil.")
    return project


def publish_folder(folder, project):
    """Copy changed named PNGs, regenerate icons.json, commit and push main."""
    project = _check_project(project)
    rows = scan_folder(folder, project)
    errors = [f"{row['name']}: {row['error']}" for row in rows if row["status"] == "Hatalı"]
    if errors:
        raise ValueError("Hatalı resimler: " + "; ".join(errors))
    present = [row for row in rows if row["path"]]
    if not present:
        raise ValueError("Klasörde Normal.png gibi tanınan bir imleç resmi bulunamadı.")

    staged = _git(project, "diff", "--cached", "--name-only").stdout.strip()
    if staged:
        raise ValueError("Projede önceden hazırlanmış Git değişiklikleri var; bu yayınla karıştırılamaz.")
    allowed = {f"assets/{row['name']}.png" for row in present} | {"icons.json"}
    status = _git(project, "status", "--porcelain", "-uall").stdout.splitlines()
    unrelated = []
    for line in status:
        path = line[3:].replace("\\", "/")
        if path not in allowed:
            unrelated.append(path)
    if unrelated:
        raise ValueError("Projede başka değişiklikler var: " + ", ".join(unrelated[:5]))

    _git(project, "fetch", "origin", "main")
    behind = int(_git(project, "rev-list", "--count", "HEAD..origin/main").stdout.strip())
    if behind:
        if status:
            raise ValueError("GitHub'da yeni değişiklik var; proje klasöründe yerel resim değişiklikleri de var.")
        _git(project, "pull", "--ff-only", "origin", "main")
        rows = scan_folder(folder, project)
        present = [row for row in rows if row["path"]]

    changed = [row for row in present if row["status"] == "Değişti"]
    for row in changed:
        target = project / "assets" / f"{row['name']}.png"
        data = row["path"].read_bytes()
        temporary = target.with_name(f".{target.name}.new")
        temporary.write_bytes(data)
        os.replace(temporary, target)
    build_catalog(project, announce=False)
    _git(project, "add", "--", *[f"assets/{row['name']}.png" for row in present], "icons.json")
    if _git(project, "diff", "--cached", "--quiet", check=False).returncode == 1:
        _git(project, "-c", "user.name=Chibi Simge Güncelleyici",
             "-c", "user.email=chibi-icons@users.noreply.github.com",
             "commit", "-m", "Update cursor icons")
    ahead = int(_git(project, "rev-list", "--count", "origin/main..HEAD").stdout.strip())
    if ahead:
        _git(project, "push", "origin", "main")
    return {"changed": [row["name"] for row in changed], "pushed": bool(ahead)}
