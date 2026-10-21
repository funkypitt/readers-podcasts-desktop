"""The colour themes: the two inks, then the Plume palettes, and the old `dark` still understood."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import readers_podcasts as rp  # noqa: E402


class Themes(unittest.TestCase):
    def test_the_cycle_starts_with_the_inks_and_comes_round(self):
        self.assertEqual(rp.THEMES[:2], ["DARK", "LIGHT"])
        self.assertEqual(rp.next_theme("DARK"), "LIGHT")
        self.assertEqual(rp.next_theme("LIGHT"), "LAVANDE")
        self.assertEqual(rp.next_theme("NATURE"), "DARK")
        self.assertEqual(rp.next_theme("nonsense"), "DARK")
        self.assertEqual(len(rp.PALETTES), 10)

    def test_the_inks_keep_their_accent_as_the_text_colour(self):
        for key in ("DARK", "LIGHT"):
            _k, bg, fg, accent, on_accent = rp.palette(key)[:5]
            self.assertEqual((accent, on_accent), (fg, bg))

    def test_the_inks_have_no_cards_and_every_palette_has_its_three_roles(self):
        for key in ("DARK", "LIGHT"):
            _k, bg, _fg, _a, _oa, tile, tile2, press, tiles = rp.palette(key)
            self.assertFalse(tiles)
            self.assertEqual((tile, tile2, press), (bg, bg, bg))
        for key in rp.THEMES[2:]:
            _k, bg, _fg, _a, _oa, tile, tile2, press, tiles = rp.palette(key)
            self.assertTrue(tiles, key)
            self.assertNotEqual(tile, bg, key)
        self.assertEqual(rp.palette("TERRACOTTA")[5:], ("#FCF7F1", "#C8B6A5", "#C8B6A5", True))
        self.assertEqual(rp.palette("LAVANDE")[5:], ("#3B3352", "#2B2540", "#5A4F78", True))
        self.assertFalse(rp.palette("nonsense")[8])

    def test_an_old_config_with_only_dark_keeps_its_ink(self):
        self.assertEqual(rp.theme_of({"dark": False}), "LIGHT")
        self.assertEqual(rp.theme_of({"dark": True}), "DARK")
        self.assertEqual(rp.theme_of({}), "DARK")
        self.assertEqual(rp.theme_of({"theme": "SAUGE", "dark": True}), "SAUGE")

    def test_dark_is_written_beside_the_theme_for_the_older_versions(self):
        cfg = {}
        rp.set_theme(cfg, "TERRACOTTA")
        self.assertEqual(cfg, {"theme": "TERRACOTTA", "dark": False})
        rp.set_theme(cfg, "NORDIQUE")
        self.assertTrue(cfg["dark"])

    def test_the_backup_carries_the_new_names_and_takes_the_old(self):
        self.assertEqual(rp.settings_for_backup({"theme": "COQUETTE"})["theme"], "COQUETTE")
        self.assertEqual(rp.settings_for_backup({"dark": False})["theme"], "LIGHT")
        cfg = rp.settings_from_backup({}, {"theme": "LIGHT"})
        self.assertEqual((cfg["theme"], cfg["dark"]), ("LIGHT", False))
        cfg = rp.settings_from_backup({}, {"theme": "TORRIDE"})
        self.assertEqual((cfg["theme"], cfg["dark"]), ("TORRIDE", True))
        cfg = rp.settings_from_backup({}, {"theme": "SYSTEM"})
        self.assertEqual(cfg["theme"], "DARK")

    def test_dim_and_rule_come_from_the_text_colour(self):
        self.assertEqual(rp.rgba("#ffffff", 0.55), "rgba(255,255,255,0.55)")
        self.assertEqual(rp.blend("#ffffff", "#000000", 0.55), "#8c8c8c")
        self.assertEqual(rp.blend("#000000", "#ffffff", 0.55), "#737373")

    def test_every_language_names_every_theme(self):
        for lang, table in rp.STRINGS.items():
            for key, label in rp.THEME_LABELS.items():
                self.assertIn(label, table, (lang, key))


if __name__ == "__main__":
    unittest.main()
