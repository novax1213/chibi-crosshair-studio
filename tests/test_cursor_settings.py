"""Saved per-role cursor sizes must survive a restart."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cursor_core import apply_cursors, load_settings, save_settings


class CursorSettingsTest(unittest.TestCase):
    def test_saved_normal_size_survives_reload(self):
        with tempfile.TemporaryDirectory(prefix="chibi-settings-") as folder:
            path = Path(folder) / "settings.json"
            with patch("cursor_core.CONFIG_PATH", path):
                settings = load_settings()
                settings["cursor_settings"]["Normal"]["size"] = 65
                settings["cursor_settings"]["Normal"]["image_scale"] = 74
                settings["applied_roles"] = ["Normal"]
                save_settings(settings)
                loaded = load_settings()
            self.assertEqual(loaded["cursor_settings"]["Normal"]["size"], 65)
            self.assertEqual(loaded["cursor_settings"]["Normal"]["image_scale"], 74)
            self.assertEqual(loaded["applied_roles"], ["Normal"])

    def test_old_defaults_do_not_reapply_all_roles(self):
        with tempfile.TemporaryDirectory(prefix="chibi-settings-") as folder:
            path = Path(folder) / "settings.json"
            path.write_text(json.dumps({"size": 120, "image_scale": 100,
                                        "hotspot_x": 42, "hotspot_y": 9,
                                        "cursor_settings": {
                                            "Normal": {"size": 65, "image_scale": 74,
                                                       "hotspot_x": 42, "hotspot_y": 9},
                                            "Help": {"size": 120, "image_scale": 100,
                                                     "hotspot_x": 42, "hotspot_y": 9}}}),
                            encoding="utf-8")
            with patch("cursor_core.CONFIG_PATH", path):
                loaded = load_settings()
            self.assertEqual(loaded["applied_roles"], ["Normal"])
            self.assertEqual(loaded["cursor_settings"]["Help"]["size"], 64)

    def test_startup_only_reapplies_selected_roles(self):
        with tempfile.TemporaryDirectory(prefix="chibi-settings-") as folder:
            selections = Path(folder) / "icon_selections.json"
            settings = load_settings()
            settings["applied_roles"] = ["Normal"]
            with (patch("cursor_core.ICON_SELECTIONS_PATH", selections),
                  patch("cursor_core.apply_cursor", side_effect=lambda name, config: name) as apply):
                self.assertEqual(apply_cursors(settings), {"Normal": "Normal"})
            self.assertEqual(apply.call_count, 1)


if __name__ == "__main__":
    unittest.main()
