"""The setting that leaves out the episodes under ten minutes."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import readers_podcasts as rp  # noqa: E402


class Short(unittest.TestCase):
    def test_short_ones_go_unknown_lengths_stay(self):
        eps = [{"id": "trailer", "duration": 120}, {"id": "talk", "duration": 2700}, {"id": "unknown"},
               {"id": "nine", "duration": 9 * 60}, {"id": "ten", "duration": 600}]
        self.assertEqual(["talk", "unknown", "ten"], [e["id"] for e in rp.without_short(eps)])

    def test_strings_translated(self):
        for lang in ("fr", "de", "es", "pt", "ru"):
            self.assertIn("hide episodes under 10 minutes", rp.STRINGS[lang])


if __name__ == "__main__":
    unittest.main()
