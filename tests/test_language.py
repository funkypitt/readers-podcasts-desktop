"""The spoken language: where to listen, which passages, the average, when to ask, and what the
script's lines say about it."""
import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("rp", os.path.join(HERE, "readers_podcasts.py"))
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)
L = rp.LANGUAGE
W = L["WINDOW"]


class Language(unittest.TestCase):
    def test_short_sound_is_one_window(self):
        self.assertEqual(L["candidates"](W // 2), [0])

    def test_nine_places_inside_the_sound(self):
        places = L["candidates"](40 * W)
        self.assertEqual(len(places), 9)
        self.assertTrue(all(0 < p and p + W < 40 * W for p in places))

    def test_the_most_spoken_passages(self):
        shares = [(0, 0.1), (1, 0.9), (2, 0.5), (3, 0.0), (4, 0.8), (5, 0.7)]
        self.assertEqual(L["choose"](shares), [1, 4, 5])
        self.assertEqual(L["choose"]([(0, 0.0), (1, 0.01)]), [])
        self.assertEqual(L["choose"]([(i, None) for i in range(9)]), [1, 4, 7])

    def test_average(self):
        heard = L["combine"]([{"en": 0.9, "fr": 0.1}, {"en": 0.7, "fr": 0.3}, {}])
        self.assertEqual((heard["language"], heard["passages"]), ("en", 2))
        self.assertAlmostEqual(heard["confidence"], 0.8)

    def test_question_only_when_plain(self):
        sure = {"language": "en", "confidence": 0.95, "probs": {"en": 0.95, "fr": 0.02}, "passages": 3}
        self.assertEqual(L["suggest"]("fr", sure), "en")
        self.assertIsNone(L["suggest"]("en", sure))
        self.assertIsNone(L["suggest"]("", sure))
        mixed = {"language": "en", "confidence": 0.75, "probs": {"en": 0.75, "fr": 0.2}, "passages": 3}
        self.assertIsNone(L["suggest"]("fr", mixed))

    def test_script_lines(self):
        rows = ['{"listening": true}', '{"heard": {"language": "en", "confidence": 0.99, "probs": {"en": 0.99}, "passages": 3}}',
                '{"doubt": "en"}']
        heard, doubt = rp.parse_heard(rows)
        self.assertEqual((heard["language"], doubt), ("en", "en"))
        self.assertEqual(rp.parse_heard(['{"d": 3.0}', '{"lang": "fr"}']), (None, None))
        # the transcript itself reads past the detection's lines
        rows = ['{"heard": {"language": "fr", "confidence": 0.9, "probs": {}, "passages": 1}}', '{"d": 3.0}',
                '{"a": 0.0, "b": 1.0, "t": "Bonjour."}', '{"lang": "fr"}']
        self.assertEqual(rp.parse_faster(rows), ("fr", [(0, 1000, "Bonjour.")]))

    def test_names_inside_a_sentence(self):
        self.assertEqual(rp.spoken_name("en"), rp._("English"))
        self.assertEqual(rp.spoken_name(""), rp._("recognised automatically"))


if __name__ == "__main__":
    unittest.main()
