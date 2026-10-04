"""A YouTube channel in the desktop: the page behind a feed, the shape of an older video, and
what an imported or pasted address stands for."""
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("rp", os.path.join(HERE, "readers_podcasts.py"))
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)

FEED = "https://www.youtube.com/feeds/videos.xml?channel_id=UCabcdefghijklmnopqrstuv"


class YouTube(unittest.TestCase):
    def test_page_of_a_channel_and_a_playlist(self):
        self.assertEqual(rp.youtube_page_of(FEED), "https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv/videos")
        self.assertEqual(rp.youtube_page_of("https://www.youtube.com/feeds/videos.xml?playlist_id=PL123"),
                         "https://www.youtube.com/playlist?list=PL123")
        self.assertIsNone(rp.youtube_page_of("https://example.org/feed.xml"))

    def test_an_older_video_has_the_feed_s_id(self):
        fid = rp.feed_id(FEED)
        e = rp.older_episode(fid, "dQw4w9WgXcQ", "Titre", 212_000)
        # The Atom feed names the same video yt:video:ID: one id, whichever way it arrived.
        self.assertEqual(e["id"], rp.episode_id(fid, "yt:video:dQw4w9WgXcQ"))
        self.assertEqual(e["mediaUrl"], "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(e["published"], 0)
        self.assertTrue(rp.is_youtube_episode(e))
        self.assertFalse(rp.auto_deletable(e))

    def test_what_an_address_stands_for(self):
        self.assertEqual(rp.resolve_address("https://example.org/feed.xml"), ("https://example.org/feed.xml", "RSS"))
        # The phone writes a channel's Atom feed in abonnements.opml: it stays itself.
        self.assertEqual(rp.resolve_address(FEED), (FEED, "YOUTUBE"))
        # A channel page is turned into that same feed, without touching the network.
        self.assertEqual(rp.resolve_address("https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv"), (FEED, "YOUTUBE"))
        self.assertEqual(rp.resolve_address("https://www.youtube.com/playlist?list=PL123"),
                         ("https://www.youtube.com/feeds/videos.xml?playlist_id=PL123", "YOUTUBE"))

    def test_add_older_keeps_them_past_the_feed_s_fifteen(self):
        store = rp.Store.__new__(rp.Store)
        import threading
        store.lock = threading.RLock()
        fid = rp.feed_id(FEED)
        store.feeds = [{"id": fid, "url": FEED, "kind": "YOUTUBE", "keepCount": 50}]
        store.episodes = [dict(rp.older_episode(fid, "a%010d" % i, "v%d" % i, 1000), feedId=fid) for i in range(48)]
        store._save_feeds = lambda: None
        store._save_episodes = lambda _fid: None
        older = [rp.older_episode(fid, "b%010d" % i, "w%d" % i, 1000) for i in range(25)]
        self.assertEqual(store.add_older(fid, older + older[:3]), 25)   # repeats do not count twice
        self.assertEqual(store.add_older(fid, older), 0)
        self.assertGreaterEqual(store.feeds[0]["keepCount"], 48 + 25)


if __name__ == "__main__":
    unittest.main()
