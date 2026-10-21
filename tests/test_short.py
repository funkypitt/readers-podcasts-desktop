"""The setting that leaves out the episodes under ten minutes."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import readers_podcasts as rp  # noqa: E402


class Short(unittest.TestCase):
    def test_short_ones_go_unknown_lengths_stay(self):
        eps = [{"id": "trailer", "durationMs": 120_000}, {"id": "talk", "durationMs": 2700_000}, {"id": "unknown"},
               {"id": "nine", "durationMs": 9 * 60_000}, {"id": "ten", "durationMs": 600_000}, {"id": "zero", "durationMs": 0}]
        self.assertEqual(["talk", "unknown", "ten", "zero"], [e["id"] for e in rp.without_short(eps)])

    def test_lengths_come_from_the_listing_by_video_id(self):
        def ep(eid, vid, ms=0):
            return {"id": eid, "mediaUrl": "https://www.youtube.com/watch?v=" + vid, "durationMs": ms}
        eps = [ep("a", "v1"), ep("b", "v2", 500), ep("c", "v3"), {"id": "d", "mediaUrl": "https://x.org/a.mp3", "durationMs": 0},
               {"id": "s", "mediaUrl": "https://www.youtube.com/shorts/v5", "durationMs": 0}]
        listed = [("v1", "one", 741_000), ("v2", "two", 1000), ("v3", "three", 0), ("v9", "nine", 10)]
        self.assertEqual(["a", "c", "s"], [e["id"] for e in rp.lacking_lengths(eps)])
        self.assertEqual("gDQB1rGT4pg", rp.youtube_video_id("https://www.youtube.com/shorts/gDQB1rGT4pg"))
        self.assertEqual("gDQB1rGT4pg", rp.youtube_video_id("https://youtu.be/gDQB1rGT4pg?t=2"))
        self.assertEqual({"a": 741_000}, rp.lengths_from_listing(eps, listed))
        self.assertEqual("abc_123", rp.youtube_video_id("https://www.youtube.com/watch?feature=x&v=abc_123&t=3"))

    def test_strings_translated(self):
        for lang in ("fr", "de", "es", "pt", "ru"):
            self.assertIn("hide episodes under 10 minutes", rp.STRINGS[lang])


if __name__ == "__main__":
    unittest.main()
