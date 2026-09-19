"""Download and install PNG cursor art from a public GitHub catalog."""

from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen
import hashlib
import json
import os
import re
import tempfile

from PIL import Image

from cursor_core import (APP_DIR, DOWNLOADED_ICONS_DIR, ICON_SELECTIONS_PATH,
                         NAMES, apply_cursor, load_settings)

MAX_MANIFEST_BYTES = 1024 * 1024
MAX_ICON_BYTES = 12 * 1024 * 1024
ICON_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")


def manifest_url(value, branch="main"):
    """Accept a public GitHub repository URL or a direct HTTPS JSON URL."""
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("GitHub adresi https:// ile başlamalı.")
    if parsed.hostname.lower() == "github.com":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) == 2:
            owner, repo = parts
            repo = repo.removesuffix(".git")
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
                raise ValueError("GitHub depo adresi geçersiz.")
            if not re.fullmatch(r"[A-Za-z0-9_./-]+", branch) or ".." in branch:
                raise ValueError("Dal adı geçersiz.")
            return (f"https://raw.githubusercontent.com/{owner}/{repo}/"
                    f"{quote(branch, safe='/')}/icons.json")
        if len(parts) >= 5 and parts[2] == "blob":
            owner, repo, _, ref = parts[:4]
            rest = "/".join(parts[4:])
            return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{rest}"
        raise ValueError("GitHub depo bağlantısını veya icons.json bağlantısını gir.")
    if not parsed.path.lower().endswith(".json"):
        raise ValueError("Doğrudan bağlantı bir JSON dosyasına gitmeli.")
    return value


def _read_limited(url, limit):
    request = Request(url, headers={"User-Agent": "Chibi-Crosshair-Icon-Manager/1.0"})
    with urlopen(request, timeout=20) as response:
        if urlparse(response.geturl()).scheme != "https":
            raise ValueError("Güvenli HTTPS bağlantısı gerekli.")
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Dosya izin verilen boyuttan büyük.")
    return data


def parse_catalog(data, source_url):
    document = json.loads(data)
    if not isinstance(document, dict) or document.get("schema") != 1:
        raise ValueError("Katalog biçimi geçersiz: schema değeri 1 olmalı.")
    raw_icons = document.get("icons")
    if not isinstance(raw_icons, list) or len(raw_icons) > 500:
        raise ValueError("Katalogda geçerli bir icons listesi olmalı (en çok 500).")
    icons = []
    seen = set()
    for item in raw_icons:
        if not isinstance(item, dict):
            raise ValueError("Katalogdaki simge kaydı geçersiz.")
        icon_id = item.get("id")
        title = item.get("name")
        file = item.get("file")
        checksum = item.get("sha256")
        role = item.get("role", "Normal")
        package = item.get("package", "base")
        package_name = item.get("package_name", "Temel Paket")
        if not isinstance(icon_id, str) or not ICON_ID.fullmatch(icon_id) or icon_id.lower() in seen:
            raise ValueError("Simge kimliği geçersiz veya tekrarlanmış.")
        if not isinstance(title, str) or not title.strip() or len(title) > 100:
            raise ValueError(f"{icon_id}: görünen ad geçersiz.")
        if not isinstance(checksum, str) or not SHA256.fullmatch(checksum):
            raise ValueError(f"{icon_id}: SHA-256 değeri eksik veya geçersiz.")
        if role not in NAMES:
            raise ValueError(f"{icon_id}: Windows imleç türü geçersiz.")
        if not isinstance(package, str) or not re.fullmatch(r"[a-z0-9-]{1,48}", package):
            raise ValueError(f"{icon_id}: paket kimliği geçersiz.")
        if not isinstance(package_name, str) or not package_name.strip() or len(package_name) > 80:
            raise ValueError(f"{icon_id}: paket adı geçersiz.")
        if not isinstance(file, str) or "\\" in file or "?" in file or "#" in file:
            raise ValueError(f"{icon_id}: dosya yolu geçersiz.")
        path = PurePosixPath(file)
        if (path.is_absolute() or not file.lower().endswith(".png") or
                any(part in (".", "..") for part in path.parts) or file.startswith("//")):
            raise ValueError(f"{icon_id}: dosya yolu geçersiz.")
        icon_url = urljoin(source_url, quote(file, safe="/"))
        if urlparse(icon_url).scheme != "https" or urlparse(icon_url).hostname != urlparse(source_url).hostname:
            raise ValueError(f"{icon_id}: dosya katalog alanının dışında.")
        icons.append({"id": icon_id, "name": title.strip(), "file": file,
                      "sha256": checksum.lower(), "role": role, "url": icon_url,
                      "package": package, "package_name": package_name.strip()})
        seen.add(icon_id.lower())
    return icons


def fetch_catalog(address, branch="main"):
    url = manifest_url(address, branch)
    return parse_catalog(_read_limited(url, MAX_MANIFEST_BYTES), url), url


def _atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".chibi-", delete=False) as tmp:
        temp_path = tmp.name
        try:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
        except Exception:
            os.unlink(temp_path)
            raise
    try:
        os.replace(temp_path, path)
    except Exception:
        os.unlink(temp_path)
        raise


def download_icon(icon):
    """Return (local path, downloaded). Only changed and verified PNGs are saved."""
    path = DOWNLOADED_ICONS_DIR / f"{icon['id']}.png"
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == icon["sha256"]:
        return path, False
    data = _read_limited(icon["url"], MAX_ICON_BYTES)
    if hashlib.sha256(data).hexdigest() != icon["sha256"]:
        raise ValueError(f"{icon['name']}: SHA-256 uyuşmuyor. İndirme kaydedilmedi.")
    with Image.open(BytesIO(data)) as image:
        if image.format != "PNG" or not (16 <= image.width <= 4096 and 16 <= image.height <= 4096):
            raise ValueError(f"{icon['name']}: geçerli boyutta PNG olmalı.")
        image.verify()
    _atomic_write(path, data)
    return path, True


def load_selections():
    try:
        result = json.loads(ICON_SELECTIONS_PATH.read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}


def install_icon(icon, role):
    """Download, assign to a Windows cursor role, and apply immediately."""
    if role not in NAMES:
        raise ValueError("Windows imleç türü geçersiz.")
    _, downloaded = download_icon(icon)
    selected = load_selections()
    previous = selected.get(role)
    selected[role] = icon["id"]
    _atomic_write(ICON_SELECTIONS_PATH, json.dumps(selected, ensure_ascii=False, indent=2).encode("utf-8"))
    try:
        apply_cursor(role, load_settings()["cursor_settings"][role])
    except Exception:
        if previous is None:
            selected.pop(role, None)
        else:
            selected[role] = previous
        _atomic_write(ICON_SELECTIONS_PATH, json.dumps(selected, ensure_ascii=False, indent=2).encode("utf-8"))
        raise
    return downloaded


def install_package(icons):
    """Download all icons in one package, then apply their Windows cursor roles."""
    if not icons:
        raise ValueError("Pakette imleç bulunamadı.")
    package_ids = {icon["package"] for icon in icons}
    roles = [icon["role"] for icon in icons]
    if len(package_ids) != 1 or len(roles) != len(set(roles)):
        raise ValueError("Paket içeriği geçersiz.")
    downloaded = sum(download_icon(icon)[1] for icon in icons)
    selected = load_selections()
    previous = dict(selected)
    for icon in icons:
        selected[icon["role"]] = icon["id"]
    _atomic_write(ICON_SELECTIONS_PATH, json.dumps(selected, ensure_ascii=False, indent=2).encode("utf-8"))
    settings = load_settings()["cursor_settings"]
    try:
        for role in roles:
            apply_cursor(role, settings[role])
    except Exception:
        _atomic_write(ICON_SELECTIONS_PATH, json.dumps(previous, ensure_ascii=False, indent=2).encode("utf-8"))
        for role in roles:
            try:
                apply_cursor(role, settings[role])
            except Exception:
                pass
        raise
    return downloaded


def update_installed(icons):
    """Refresh already selected icons when a publisher changes their checksums."""
    catalog = {icon["id"]: icon for icon in icons}
    selected = load_selections()
    refreshed = []
    for role, icon_id in selected.items():
        if role in NAMES and icon_id in catalog:
            _, changed = download_icon(catalog[icon_id])
            if changed:
                apply_cursor(role, load_settings()["cursor_settings"][role])
                refreshed.append(role)
    return refreshed
