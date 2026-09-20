"""Windows cursor generation and settings for Chibi Crosshair Studio."""

from pathlib import Path
import ctypes
import json
import os
import struct
import sys
import winreg
from PIL import Image

NAMES = ["Normal", "Help", "Working", "Busy", "Precision", "Text", "Handwriting", "Unavailable", "Move", "Horizontal", "Diagonal", "Alternate", "Vertical", "Diagonal2", "Link", "Location", "Person"]
REGISTRY_NAMES = ["Arrow", "Help", "AppStarting", "Wait", "Crosshair", "IBeam", "NWPen", "No", "SizeAll", "SizeWE", "SizeNWSE", "UpArrow", "SizeNS", "SizeNESW", "Hand", "Pin", "Person"]
CURSOR_IDS = [32512, 32651, 32650, 32514, 32515, 32513, 32631, 32648, 32646, 32644, 32642, 32516, 32645, 32643, 32649, 32671, 32672]
APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ChibiCrosshairStudio"
CONFIG_PATH = APP_DIR / "settings.json"
ICON_SELECTIONS_PATH = APP_DIR / "icon_selections.json"
DOWNLOADED_ICONS_DIR = APP_DIR / "icons"
RUN_NAME = "ChibiCrosshairStudio"
DEFAULTS = {
    "size": 64, "hotspot_x": 10, "hotspot_y": 10, "image_scale": 80,
    "crosshair_color": "#ff5b83", "crosshair_length": 16,
    "crosshair_gap": 6, "crosshair_thickness": 3,
    "crosshair_opacity": 90, "crosshair_dot": True,
    "crosshair_offset_x": 0, "crosshair_offset_y": 0,
    "overlay_enabled": False, "start_with_windows": True,
    "applied_roles": [],
}


def asset_dir():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "assets"


def icon_path(name):
    """Prefer an installed catalog icon; fall back to the bundled pose."""
    try:
        selected = json.loads(ICON_SELECTIONS_PATH.read_text(encoding="utf-8"))
        icon_id = selected.get(name)
        if isinstance(icon_id, str) and icon_id and all(
                char.isascii() and (char.isalnum() or char in "_-") for char in icon_id):
            candidate = DOWNLOADED_ICONS_DIR / f"{icon_id}.png"
            if candidate.is_file():
                return candidate
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return asset_dir() / f"{name}.png"


def load_settings():
    settings = dict(DEFAULTS)
    data = {}
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            settings.update({key: value for key, value in data.items() if key in settings})
        else:
            data = {}
    except (OSError, ValueError, TypeError):
        pass
    legacy = {key: int(settings[key]) for key in ("size", "hotspot_x", "hotspot_y", "image_scale")}
    saved = data.get("cursor_settings") if isinstance(data, dict) else None
    if not isinstance(saved, dict):
        saved = {}
    settings["cursor_settings"] = {
        name: {key: int(saved.get(name, {}).get(key, legacy[key])) for key in legacy}
        if isinstance(saved.get(name), dict) else dict(legacy)
        for name in NAMES
    }
    if "applied_roles" not in data:
        # Older versions applied every default 120px cursor at login. Only roles
        # whose per-role settings differ from those defaults were deliberately tuned.
        defaults_before_migration = {"size": 120, "image_scale": 100,
                                     "hotspot_x": int(data.get("hotspot_x", 10)),
                                     "hotspot_y": int(data.get("hotspot_y", 10))}
        settings["applied_roles"] = [name for name in NAMES
                                     if settings["cursor_settings"][name] != defaults_before_migration]
        for name in NAMES:
            config = settings["cursor_settings"][name]
            if config == defaults_before_migration:
                config["size"] = 64
                config["image_scale"] = 80
    else:
        roles = settings["applied_roles"]
        settings["applied_roles"] = [name for name in NAMES if isinstance(roles, list) and name in roles]
    return settings


def save_settings(settings):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def make_canvas(name, size, image_scale=100):
    with Image.open(icon_path(name)) as source:
        sprite = source.convert("RGBA")
    scale = max(20, min(100, int(image_scale)))
    artwork_size = max(1, round((size - 4) * scale / 100))
    sprite.thumbnail((artwork_size, artwork_size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(sprite, ((size - sprite.width) // 2, (size - sprite.height) // 2))
    return canvas


def cursor_bytes(canvas, hotspot_x, hotspot_y):
    """Encode a 32-bit classic Windows CUR with a color bitmap and AND mask."""
    size = canvas.width
    mask_stride = ((size + 31) // 32) * 4
    pixels = canvas.load()
    xor = bytearray()
    and_mask = bytearray()
    for y in range(size - 1, -1, -1):
        mask_row = bytearray(mask_stride)
        for x in range(size):
            red, green, blue, alpha = pixels[x, y]
            xor.extend((blue, green, red, alpha))
            if alpha < 128:
                mask_row[x // 8] |= 0x80 >> (x % 8)
        and_mask.extend(mask_row)
    bitmap_header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, len(xor) + len(and_mask), 0, 0, 0, 0)
    payload = bitmap_header + xor + and_mask
    icon_dir = struct.pack("<HHH", 0, 2, 1)
    entry = struct.pack("<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0, 0, 0,
                        min(max(0, hotspot_x), size - 1), min(max(0, hotspot_y), size - 1), len(payload), 22)
    return icon_dir + entry + payload


def generate_cursor(name, cursor_settings):
    if name not in NAMES:
        raise ValueError(f"Unknown cursor: {name}")
    size = max(32, min(192, int(cursor_settings["size"])))
    output = APP_DIR / "cursors"
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"{name}.cur"
    path.write_bytes(cursor_bytes(make_canvas(name, size, cursor_settings["image_scale"]), int(cursor_settings["hotspot_x"]), int(cursor_settings["hotspot_y"])))
    return path


def apply_cursor(name, cursor_settings):
    path = generate_cursor(name, cursor_settings)
    index = NAMES.index(name)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors") as key:
        winreg.SetValueEx(key, REGISTRY_NAMES[index], 0, winreg.REG_SZ, str(path))
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Chibi Crosshair Studio")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    user32.LoadImageW.restype = ctypes.c_void_p
    user32.SetSystemCursor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    user32.SetSystemCursor.restype = ctypes.c_int
    user32.DestroyCursor.argtypes = [ctypes.c_void_p]
    handle = user32.LoadImageW(None, str(path), 2, 0, 0, 0x10)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if not user32.SetSystemCursor(handle, CURSOR_IDS[index]):
        user32.DestroyCursor(handle)
        raise ctypes.WinError(ctypes.get_last_error())
    return path


def apply_cursors(settings):
    roles = set(settings.get("applied_roles", []))
    try:
        selections = json.loads(ICON_SELECTIONS_PATH.read_text(encoding="utf-8"))
        if isinstance(selections, dict):
            roles.update(name for name in selections if name in NAMES)
    except (OSError, ValueError):
        pass
    return {name: apply_cursor(name, settings["cursor_settings"][name])
            for name in NAMES if name in roles}


def set_startup(enabled):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
        if enabled:
            if getattr(sys, "frozen", False):
                command = f'"{sys.executable}" --apply-only'
            else:
                command = f'"{sys.executable}" "{Path(__file__).parent / "app.pyw"}" --apply-only'
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, RUN_NAME)
            except FileNotFoundError:
                pass
