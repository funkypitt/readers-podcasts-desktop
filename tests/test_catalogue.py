#!/usr/bin/env python3
"""The directories behind "+ a feed", as the phone's CatalogueTest checks them: answers they
really gave (trimmed, saved 2026-09-23, the same files as the phone's), put together, and the
dialog driven offscreen with the network replaced.

    QT_QPA_PLATFORM=offscreen python3 tests/test_catalogue.py
    ONLINE=1 …   also asks the two real directories once
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
# Never the reader's own subscriptions: the store and the settings go to a throwaway place.
_tmp = tempfile.mkdtemp()
os.environ["XDG_CONFIG_HOME"] = os.path.join(_tmp, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_tmp, "data")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.makedirs(os.path.join(_tmp, "config", "readers-podcasts"))
with open(os.path.join(_tmp, "config", "readers-podcasts", "config.json"), "w") as _fh:
    json.dump({"auto_refresh": False}, _fh)
spec = importlib.util.spec_from_file_location("rp", os.path.join(os.path.dirname(HERE), "readers_podcasts.py"))
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)


def fixture(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def F(title, url, author="", episodes=0):
    return {"title": title, "author": author, "url": url, "episodes": episodes}


class Parsing(unittest.TestCase):
    def test_apple(self):
        found = rp.parse_apple(fixture("catalogue-apple.json"))
        self.assertEqual(4, len(found))
        self.assertEqual("https://www.dharmaseed.org/feeds/recordings/", found[0]["url"])
        self.assertTrue(found[0]["title"].startswith("Dharma Seed"))
        self.assertTrue(found[0]["author"])
        self.assertGreater(found[0]["episodes"], 0)

    def test_fyyd(self):
        found = rp.parse_fyyd(fixture("catalogue-fyyd.json"))
        self.assertEqual(6, len(found))
        self.assertEqual("Dharmabytes from free buddhist audio", found[0]["title"])
        self.assertEqual("Free Buddhist Audio", found[0]["author"])
        # A licence where the author should be is no author.
        self.assertEqual("", next(f for f in found if "zbb.dharmaseed" in f["url"])["author"])

    def test_entries_without_feed(self):
        self.assertEqual(["A"], [f["title"] for f in rp.parse_apple(
            {"results": [{"collectionName": "No feed"}, {"collectionName": "A", "feedUrl": "https://a.example/f"}]})])
        self.assertEqual([], rp.parse_fyyd({"status": 0, "msg": "error"}))


class Merging(unittest.TestCase):
    def test_key(self):
        self.assertEqual(rp.catalogue_key("https://AV.dharmaseed.org/feeds/recordings/"),
                         rp.catalogue_key("http://av.dharmaseed.org/feeds/recordings"))
        self.assertEqual(rp.catalogue_key("https://www.dharmaseed.org/feeds/recordings/"),
                         rp.catalogue_key("https://dharmaseed.org/feeds/recordings/"))
        self.assertNotEqual(rp.catalogue_key("https://x.org/Feed"), rp.catalogue_key("https://x.org/feed"))

    def test_turns_and_one_of_each(self):
        apple = rp.parse_apple(fixture("catalogue-apple.json"))
        fyyd = rp.parse_fyyd(fixture("catalogue-fyyd.json"))
        merged = rp.catalogue_merge("", apple, fyyd)
        self.assertEqual(2 + 6, len(merged))
        self.assertEqual(apple[0]["url"], merged[0]["url"])
        self.assertEqual(fyyd[0]["url"], merged[1]["url"])

    def test_fills_what_one_side_lacks(self):
        merged = rp.catalogue_merge("show", [F("Show", "https://s.example/feed")],
                                    [F("Show", "http://www.s.example/feed/", "Someone", 12)])
        self.assertEqual([F("Show", "https://s.example/feed", "Someone", 12)], merged)

    def test_query_first(self):
        a = [F("Sleep stories", "https://1"), F("Les Causeries de Léna", "https://2")]
        b = [F("Causeries méditées", "https://3"), F("Méditation causeries", "https://4")]
        self.assertEqual(["https://3", "https://4", "https://1", "https://2"],
                         [f["url"] for f in rp.catalogue_merge("causeries medit", a, b)])

    def test_same_as_the_phone(self):
        """Kotlin and Python must agree, or a feed followed on one side is offered again."""
        self.assertTrue(rp.apple_search_url("das podcast ufo", "CH").endswith("&term=das+podcast+ufo&country=ch"))
        self.assertTrue(rp.fyyd_search_url("méditation").endswith("term=m%C3%A9ditation"))
        for s in ("https://dharmaseed.org/feeds/recordings/", "feed://example.org/rss", "example.com",
                  "dharmaseed.org/feeds/recordings"):
            self.assertTrue(rp.looks_like_address(s), s)
        for s in ("dharma seed", "causeries", "Mr. Robot", ""):
            self.assertFalse(rp.looks_like_address(s), s)
        self.assertEqual(44, len(rp.cut("x" * 60)))


class Searching(unittest.TestCase):
    def test_one_failing_is_not_both(self):
        real = rp._get_json
        try:
            def fake(url):
                if "fyyd" in url:
                    raise OSError("down")
                return fixture("catalogue-apple.json")
            rp._get_json = fake
            found, failed = rp.catalogue_search("dharma", "CH")
            self.assertEqual(["fyyd"], failed)
            self.assertEqual(2, len(found))
            rp._get_json = lambda url: (_ for _ in ()).throw(OSError("offline"))
            self.assertEqual(([], ["Apple Podcasts", "fyyd"]), rp.catalogue_search("dharma"))
        finally:
            rp._get_json = real

    def test_unknown_country_falls_back(self):
        real = rp._get_json
        asked = []
        try:
            def fake(url):
                asked.append(url)
                if "country=xx" in url:
                    raise OSError("400")
                return fixture("catalogue-apple.json") if "itunes" in url else fixture("catalogue-fyyd.json")
            rp._get_json = fake
            found, failed = rp.catalogue_search("dharma", "XX")
            self.assertEqual([], failed)
            self.assertTrue(any("itunes" in u and "country" not in u for u in asked))
        finally:
            rp._get_json = real

    @unittest.skipUnless(os.environ.get("ONLINE"), "ONLINE=1 to ask the real directories")
    def test_real_directories(self):
        found, failed = rp.catalogue_search("dharma seed", "CH")
        self.assertEqual([], failed)
        self.assertTrue(any("dharmaseed.org" in f["url"] for f in found))
        found, failed = rp.catalogue_search("Das Podcast UFO", "CH")
        self.assertEqual([], failed)
        self.assertTrue(found and "ufo" in found[0]["title"].lower())


class Dialog(unittest.TestCase):
    """The + window, driven: pasting still works, the clipboard is still offered, a name searches."""

    @classmethod
    def setUpClass(cls):
        from PyQt5 import QtWidgets
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        cls.main = rp.Main()
        cls.main.store.add_feed({"id": rp.feed_id("https://dharmaseed.org/feeds/recordings/"),
                                 "url": "https://dharmaseed.org/feeds/recordings/", "title": "Dharma Seed",
                                 "author": "", "kind": "RSS", "addedAt": 0, "lastFetch": 0,
                                 "autoDownload": False, "keepCount": 50, "lastError": ""})

    @classmethod
    def tearDownClass(cls):
        cls.main.close()          # waits for the threads still in flight

    def wait(self, dialog, ms=3000):
        from PyQt5 import QtCore
        timer = QtCore.QElapsedTimer()
        timer.start()
        while timer.elapsed() < ms:
            self.app.processEvents(QtCore.QEventLoop.AllEvents, 50)
            if dialog.status.text() != rp._("searching the directories…") and not self.main.threads:
                return

    def rows(self, dialog):
        from PyQt5 import QtCore
        return [dialog.list.itemWidget(dialog.list.item(i)).text() for i in range(dialog.list.count())], \
               [dialog.list.item(i).data(QtCore.Qt.UserRole) for i in range(dialog.list.count())]

    def test_clipboard_address_is_offered_selected(self):
        from PyQt5 import QtWidgets
        QtWidgets.QApplication.clipboard().setText("https://example.org/feed.xml")
        offered = rp.clipboard_url(QtWidgets.QApplication.clipboard().text())
        self.assertEqual("https://example.org/feed.xml", offered)
        d = rp.AddDialog(self.main, offered)
        self.assertEqual("https://example.org/feed.xml", d.field.selectedText())
        texts, actions = self.rows(d)
        self.assertEqual([("subscribe", "https://example.org/feed.xml")], actions)
        # Something else on the clipboard is not offered.
        QtWidgets.QApplication.clipboard().setText("a sentence from an e-mail")
        self.assertEqual("", rp.clipboard_url(QtWidgets.QApplication.clipboard().text()))

    def test_pasted_address_subscribes(self):
        d = rp.AddDialog(self.main, "")
        d.field.setText("feed://example.net/podcast.rss")
        subscribed = []
        real = self.main.subscribe
        self.main.subscribe = subscribed.append
        try:
            d.entered()
        finally:
            self.main.subscribe = real
        self.assertEqual(["feed://example.net/podcast.rss"], subscribed)

    def test_name_searches_and_marks_followed(self):
        real = rp._get_json
        rp._get_json = lambda url: fixture("catalogue-apple.json") if "itunes" in url else fixture("catalogue-fyyd.json")
        try:
            d = rp.AddDialog(self.main, "")
            d.field.setText("dharma")
            d.entered()
            self.wait(d)
        finally:
            rp._get_json = real
        texts, actions = self.rows(d)
        self.assertEqual(8, len(actions))
        # dharmaseed.org is followed (www. or not): it opens, and says so.
        self.assertEqual(("open", rp.feed_id("https://dharmaseed.org/feeds/recordings/")), actions[0])
        self.assertIn(rp._("already followed"), texts[0])
        self.assertEqual("subscribe", actions[1][0])
        self.assertIn(rp._("found in Apple Podcasts and fyyd"), d.status.text())

    def test_nothing_and_offline(self):
        real = rp._get_json
        try:
            rp._get_json = lambda url: {"results": []} if "itunes" in url else {"data": []}
            d = rp.AddDialog(self.main, "")
            d.field.setText("zzqxv")
            d.entered()
            self.wait(d)
            self.assertEqual(rp._("no podcast of that name in the directories"), d.status.text())
            rp._get_json = lambda url: (_ for _ in ()).throw(OSError("offline"))
            d.field.setText("zzqxw")
            d.entered()
            self.wait(d)
            self.assertEqual(rp._("the directories do not answer — is the computer online?"), d.status.text())
        finally:
            rp._get_json = real


if __name__ == "__main__":
    unittest.main(verbosity=1)
