"""Exercise folder publishing against a local Git remote."""

from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from build_icon_catalog import build
from icon_catalog import install_package, parse_catalog
from icon_publisher import publish_folder, scan_folder


def git(folder, *args):
    subprocess.run(["git", *args], cwd=folder, check=True, capture_output=True, text=True)


class PackageWorkflowTest(unittest.TestCase):
    def test_install_package_applies_each_role(self):
        icons = [{"id": "sample__Normal", "role": "Normal", "package": "sample"},
                 {"id": "sample__Help", "role": "Help", "package": "sample"}]
        writes = []
        applied = []
        with (patch("icon_catalog.download_icon", return_value=(None, True)),
              patch("icon_catalog.load_selections", return_value={}),
              patch("icon_catalog._atomic_write", side_effect=lambda path, data: writes.append(data)),
              patch("icon_catalog.load_settings", return_value={"cursor_settings": {
                  "Normal": {}, "Help": {}}}),
              patch("icon_catalog.apply_cursor", side_effect=lambda role, settings: applied.append(role))):
            self.assertEqual(install_package(icons), 2)
        self.assertEqual(applied, ["Normal", "Help"])
        self.assertEqual(json.loads(writes[-1]), {"Normal": "sample__Normal", "Help": "sample__Help"})

    def test_publish_and_republish_named_package(self):
        with tempfile.TemporaryDirectory(prefix="chibi-package-test-") as temp:
            root = Path(temp)
            remote = root / "remote.git"
            remote.mkdir()
            git(root, "init", "--bare", "--initial-branch=main", str(remote))
            seed = root / "seed"
            git(root, "clone", str(remote), str(seed))
            (seed / "assets").mkdir()
            Image.new("RGBA", (32, 32), "pink").save(seed / "assets" / "Normal.png")
            build(seed, announce=False)
            git(seed, "add", ".")
            git(seed, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                "commit", "-m", "Initial")
            git(seed, "push", "origin", "main")

            images = root / "Yeni Karakter"
            images.mkdir()
            Image.new("RGBA", (48, 48), "red").save(images / "Normal.png")
            Image.new("RGBA", (48, 48), "blue").save(images / "Help.png")
            self.assertEqual(len(scan_folder(images)), 17)
            result = publish_folder(images, "Yeni Karakter", remote=str(remote))
            self.assertTrue(result["pushed"])
            self.assertEqual(set(result["changed"]), {"Normal", "Help"})
            self.assertFalse(publish_folder(images, "Yeni Karakter", remote=str(remote))["pushed"])

            check = root / "check"
            git(root, "clone", str(remote), str(check))
            document = json.loads((check / "icons.json").read_text(encoding="utf-8"))
            icons = parse_catalog(json.dumps(document),
                                  "https://raw.githubusercontent.com/example/test/main/icons.json")
            self.assertEqual({icon["id"] for icon in icons},
                             {"Normal", "yeni-karakter__Normal", "yeni-karakter__Help"})
            self.assertEqual({icon["package_name"] for icon in icons if icon["package"] != "base"},
                             {"Yeni Karakter"})


if __name__ == "__main__":
    unittest.main()
