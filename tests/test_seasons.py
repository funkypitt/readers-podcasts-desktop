"""Seasons, serials, and the OPML files other programs really write."""
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("rp", os.path.join(HERE, "readers_podcasts.py"))
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)

ITEM = """<item><title>%s</title><guid>%s</guid><pubDate>%s</pubDate>
<enclosure url="https://example.org/%s.mp3" type="audio/mpeg" length="1"/>%s</item>"""


def feed(kind, items):
    return ("""<?xml version="1.0"?><rss version="2.0"
 xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:podcast="https://podcastindex.org/namespace/1.0">
<channel><title>Une série</title>%s%s</channel></rss>""" % (kind, "".join(items))).encode()


def item(n, season=None, number=None, extra=""):
    tags = extra
    if season is not None:
        tags += "<itunes:season>%d</itunes:season>" % season
    if number is not None:
        tags += "<itunes:episode>%d</itunes:episode><itunes:episodeType>full</itunes:episodeType>" % number
    return ITEM % ("Titre %d" % n, "g%d" % n, "Mon, 06 Jul 2026 %02d:00:00 +0000" % n, "e%d" % n, tags)


class Seasons(unittest.TestCase):
    def test_the_feed_says_serial_and_the_items_their_place(self):
        data = feed("<itunes:type>serial</itunes:type>", [item(1, 1, 1), item(2, 1, 2), item(3, 2, 1)])
        title, _author, episodes, serial = rp.parse_feed("f", "RSS", data)
        self.assertEqual(title, "Une série")
        self.assertTrue(serial)
        self.assertEqual([(e["season"], e["number"]) for e in episodes], [(1, 1), (1, 2), (2, 1)])

    def test_a_feed_that_says_nothing_is_not_a_serial(self):
        _t, _a, episodes, serial = rp.parse_feed("f", "RSS", feed("", [item(1)]))
        self.assertFalse(serial)
        self.assertEqual((episodes[0]["season"], episodes[0]["number"]), (0, 0))
        self.assertEqual(rp.shelves(episodes, serial), [])

    def test_a_season_may_carry_a_name(self):
        data = feed("", [item(1, None, 1, '<podcast:season name="Les soirs">2</podcast:season>'), item(2, 1, 1)])
        _t, _a, episodes, _s = rp.parse_feed("f", "RSS", data)
        self.assertEqual((episodes[0]["season"], episodes[0]["seasonName"]), (2, "Les soirs"))
        self.assertEqual([(s, name) for s, name, _rows in rp.shelves(episodes, False)], [(2, "Les soirs"), (1, "")])

    def test_a_serial_is_read_from_its_first_season_down(self):
        data = feed("<itunes:type>serial</itunes:type>",
                    [item(1, 1, 1), item(2, 1, 2), item(3, 2, 1), item(4, 2, 2), item(5)])
        _t, _a, episodes, serial = rp.parse_feed("f", "RSS", data)
        found = rp.shelves(list(reversed(episodes)), serial)
        self.assertEqual([s for s, _n, _r in found], [1, 2, 0])
        self.assertEqual([e["title"] for e in found[0][2]], ["Titre 1", "Titre 2"])
        self.assertEqual([e["title"] for e in found[1][2]], ["Titre 3", "Titre 4"])

    def test_a_show_in_seasons_has_the_current_one_at_the_top(self):
        _t, _a, episodes, serial = rp.parse_feed("f", "RSS", feed("", [item(1, 1, 1), item(2, 1, 2), item(3, 2, 1)]))
        found = rp.shelves(episodes, serial)
        self.assertEqual([s for s, _n, _r in found], [2, 1])
        self.assertEqual([e["title"] for e in found[1][2]], ["Titre 2", "Titre 1"])

    def test_one_season_alone_needs_no_heading(self):
        _t, _a, episodes, _s = rp.parse_feed("f", "RSS", feed("", [item(1, 1, 1), item(2, 1, 2)]))
        self.assertEqual(rp.shelves(episodes, False), [])

    def test_the_season_shown_open(self):
        _t, _a, episodes, _s = rp.parse_feed("f", "RSS", feed("", [item(1, 1, 1), item(2, 2, 1), item(3, 3, 1)]))
        found = rp.shelves(episodes, True)
        self.assertEqual(rp.open_season(found, episodes), 1)
        episodes[1]["lastPlayed"] = 5
        self.assertEqual(rp.open_season(found, episodes), 2)


class Opml(unittest.TestCase):
    GOOD = rp.opml_export([{"url": "https://example.org/a.xml?x=1&y=2", "title": "L'un & l'autre"},
                           {"url": "https://example.org/b.xml", "title": "Deux"}])

    def expect(self, data):
        self.assertEqual(rp.opml_parse(data), [("https://example.org/a.xml?x=1&y=2", "L'un & l'autre"),
                                               ("https://example.org/b.xml", "Deux")])

    def test_what_the_app_writes(self):
        self.expect(self.GOOD.encode())

    def test_a_byte_order_mark(self):
        self.expect(b"\xef\xbb\xbf" + self.GOOD.encode())

    def test_a_control_character_in_a_title(self):
        self.expect(self.GOOD.replace("Deux", "De\x03ux").encode())

    def test_what_was_left_of_a_longer_file(self):
        self.expect((self.GOOD + '    <outline type="rss" text="Trois" xmlUrl="https://exam').encode())

    def test_an_address_not_escaped(self):
        self.expect(self.GOOD.replace("&amp;y", "&y").encode())

    def test_a_title_that_cannot_be_written_is_written_without_what_cannot(self):
        text = rp.opml_export([{"url": "https://example.org/b.xml", "title": "De\x03ux"}])
        self.assertEqual(rp.opml_parse(text.encode()), [("https://example.org/b.xml", "Deux")])


class Keeping(unittest.TestCase):
    def test_a_serial_is_kept_whole_and_a_show_in_seasons_is_not(self):
        store = rp.Store.__new__(rp.Store)
        import threading
        store.lock = threading.RLock()
        store.feeds = [{"id": "f", "url": "u", "keepCount": 50}]
        store.episodes = []
        store._save_episodes = lambda fid: None
        items = [item(i % 24, 1 + i // 24, 1 + i % 24).replace("g%d" % (i % 24), "g%d" % i) for i in range(120)]
        _t, _a, episodes, _s = rp.parse_feed("f", "RSS", feed("", items))
        store.merge("f", episodes)
        self.assertEqual(len(store.episodes), 50)
        store.feeds[0]["serial"] = True
        store.merge("f", episodes)
        self.assertEqual(len(store.episodes), 120)


if __name__ == "__main__":
    unittest.main()
