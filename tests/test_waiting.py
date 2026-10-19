"""The play button while the sound is on its way."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import readers_podcasts as rp  # noqa: E402


class Waiting(unittest.TestCase):
    def test_the_dots_come_and_go_after_the_glyph(self):
        seen = {rp.waiting_label(t / 10) for t in range(0, 20)}
        self.assertEqual(seen, {"▶ ·", "▶ · ·", "▶ · · ·"})
        self.assertTrue(all(label.startswith("▶ ·") for label in seen))


if __name__ == "__main__":
    unittest.main()
