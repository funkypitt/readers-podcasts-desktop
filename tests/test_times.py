"""Times written in a description point into the sound (as Chapters.times on the phone)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import readers_podcasts as rp  # noqa: E402


class TimesTest(unittest.TestCase):
    def test_times_in_prose(self):
        text = "À 12:34 il parle du souffle, puis à 1:02:03 des questions; 123:45 et 9:75 non."
        self.assertEqual([754000, 3723000], [ms for _, _, ms in rp.times_in(text, 2 * 3600000)])

    def test_clock_time_past_the_end_stays_text(self):
        self.assertEqual([754000], [ms for _, _, ms in rp.times_in("12:34 et 14:30", 800000)])

    def test_links_and_times(self):
        out = rp.linkify("à 12:34, voir www.example.org/a?t=1:02", 3600000, times=True)
        self.assertIn('<a href="chap:754000">12:34</a>', out)
        self.assertIn('href="https://www.example.org/a?t=1:02"', out)
        self.assertNotIn("chap:62000", out)

    def test_without_times_nothing_changes(self):
        self.assertNotIn("chap:", rp.linkify("à 12:34", 3600000))


if __name__ == "__main__":
    unittest.main()
