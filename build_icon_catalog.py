"""Generate icons.json from every PNG in assets/ for GitHub publishing."""

from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent
ROLES = {"Normal", "Help", "Working", "Busy", "Precision", "Text",
         "Handwriting", "Unavailable", "Move", "Horizontal", "Diagonal",
         "Alternate", "Vertical", "Diagonal2", "Link", "Location", "Person"}


def build(root=ROOT, announce=True):
    root = Path(root)
    assets = root / "assets"
    icons = []
    seen = set()
    for path in sorted(assets.glob("*.png"), key=lambda p: p.name.lower()):
        icon_id = path.stem
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", icon_id):
            raise ValueError(f"Dosya adında yalnızca A-Z, 0-9, _ ve - kullan: {path.name}")
        if icon_id.lower() in seen:
            raise ValueError(f"Tekrarlanan simge adı: {path.name}")
        seen.add(icon_id.lower())
        icons.append({"id": icon_id, "name": icon_id.replace("_", " ").replace("-", " "),
                      "file": f"assets/{path.name}",
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "role": icon_id if icon_id in ROLES else "Normal",
                      "package": "base", "package_name": "Temel Paket"})
    for directory in sorted((root / "packs").glob("*")):
        if not directory.is_dir():
            continue
        slug = directory.name
        if not re.fullmatch(r"[a-z0-9-]{1,48}", slug):
            raise ValueError(f"Paket klasörü adı geçersiz: {slug}")
        metadata = directory / "pack.json"
        title = json.loads(metadata.read_text(encoding="utf-8")).get("name", slug) if metadata.exists() else slug
        if not isinstance(title, str) or not title.strip() or len(title) > 80:
            raise ValueError(f"Paket adı geçersiz: {slug}")
        for role in sorted(ROLES):
            path = directory / f"{role}.png"
            if not path.is_file():
                continue
            icon_id = f"{slug}__{role}"
            if len(icon_id) > 64 or icon_id.lower() in seen:
                raise ValueError(f"Paket simge adı geçersiz veya tekrarlanmış: {icon_id}")
            seen.add(icon_id.lower())
            icons.append({"id": icon_id, "name": role, "file": f"packs/{slug}/{path.name}",
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "role": role, "package": slug, "package_name": title.strip()})
    if len(icons) > 500:
        raise ValueError("Katalog en çok 500 simge içerebilir.")
    if not icons:
        raise ValueError("assets klasöründe PNG bulunamadı.")
    output = root / "icons.json"
    output.write_text(json.dumps({"schema": 1, "icons": icons}, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    if announce:
        print(f"{len(icons)} simge kataloglandı: {output}")


if __name__ == "__main__":
    build()
