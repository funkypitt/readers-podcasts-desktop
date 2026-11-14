"""What is passed over: an opening and a closing per podcast, the sponsors of a YouTube video."""
import hashlib
import json
import os
import sys
from urllib.parse import unquote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import readers_podcasts as rp  # noqa: E402

VIDEO = "dQw4w9WgXcQ"


# ---- the opening and the closing ----

def test_skip_seconds_reads_the_feed_and_defaults_to_nothing():
    assert rp.skip_seconds({}) == (0, 0)
    assert rp.skip_seconds(None) == (0, 0)
    assert rp.skip_seconds({"skipStart": 30, "skipEnd": 15}) == (30, 15)
    assert rp.skip_seconds({"skipStart": "x", "skipEnd": -4}) == (0, 0)


def test_playing_from_zero_starts_past_the_opening():
    assert rp.opening_position(0, 3_600_000, 30) == 30_000
    assert rp.opening_position(600, 3_600_000, 30) == 30_000      # under a second: the beginning
    assert rp.opening_position(0, 0, 30) == 30_000          # length not known yet


def test_a_place_left_beyond_the_opening_stays():
    assert rp.opening_position(600_000, 3_600_000, 30) == 600_000
    assert rp.opening_position(45_000, 3_600_000, 30) == 45_000


def test_nothing_skipped_when_off():
    assert rp.opening_position(0, 3_600_000, 0) == 0
    assert rp.opening_position(120_000, 3_600_000, 0, 0) == 120_000


def test_heard_to_the_end_starts_again_past_the_opening():
    assert rp.opening_position(3_599_000, 3_600_000, 30) == 30_000
    # left inside the skipped closing: that is the end, so it starts again
    assert rp.opening_position(3_570_000, 3_600_000, 30, 60) == 30_000


def test_an_opening_longer_than_the_episode_is_ignored():
    assert rp.opening_position(0, 20_000, 30) == 0


def test_playing_into_the_closing_is_the_end():
    end = rp.end_ms(3_600_000, 60)
    assert end == 3_540_000
    assert rp.skip_action(3_539_800, 3_540_050, [], end=end) == ("end", None)
    assert rp.skip_action(3_539_000, 3_539_250, [], end=end) is None
    assert rp.skip_action(3_539_800, 3_540_050, [], end=0) is None         # off


def test_the_closing_sought_into_by_hand_plays():
    end = rp.end_ms(3_600_000, 60)
    assert rp.skip_action(3_000_000, 3_560_000, [], end=end) is None       # the jump
    assert rp.skip_action(3_560_000, 3_560_250, [], end=end) is None       # and playing on


def test_lengths_unknown_or_too_short_skip_no_closing():
    assert rp.end_ms(0, 60) == 0
    assert rp.end_ms(3_600_000, 0) == 3_600_000
    # 90 s episode, 30 s opening, 70 s closing: nothing would be left
    assert rp.end_ms(90_000, 70, 30) == 90_000
    assert rp.end_ms(90_000, 50, 30) == 40_000


# ---- chapters ----

def test_next_chapter():
    chapters = [(0, "a"), (60_000, "b"), (300_000, "c")]
    assert rp.next_chapter(chapters, 0) == 60_000
    assert rp.next_chapter(chapters, 59_500) == 300_000      # just at its start: the one after
    assert rp.next_chapter(chapters, 120_000) == 300_000
    assert rp.next_chapter(chapters, 400_000) is None
    assert rp.next_chapter([], 0) is None


# ---- SponsorBlock ----

def test_only_a_prefix_of_the_hash_is_sent():
    url = rp.sponsor_url(VIDEO)
    prefix = hashlib.sha256(VIDEO.encode()).hexdigest()[:4]
    assert url.startswith("https://sponsor.ajay.app/api/skipSegments/" + prefix + "?")
    assert VIDEO not in url
    assert hashlib.sha256(VIDEO.encode()).hexdigest()[:5] not in url
    query = url.split("?", 1)[1]
    assert query.startswith("categories=")
    assert "[" not in query and '"' not in query                  # encoded
    assert json.loads(unquote(query.split("=", 1)[1])) == ["sponsor", "selfpromo", "interaction"]


ANSWER = [
    {"videoID": "other00000", "segments": [
        {"category": "sponsor", "actionType": "skip", "segment": [1.0, 2.0], "UUID": "x"}]},
    {"videoID": VIDEO, "segments": [
        {"category": "selfpromo", "actionType": "skip", "segment": [300.5, 320.0], "UUID": "b"},
        {"category": "sponsor", "actionType": "skip", "segment": [10, 40.25], "UUID": "a"},
        {"category": "sponsor", "actionType": "mute", "segment": [100, 110], "UUID": "c"},
        {"category": "music_offtopic", "actionType": "skip", "segment": [120, 130], "UUID": "d"},
        {"category": "interaction", "actionType": "skip", "segment": [500, 505], "UUID": "e"},
        {"category": "sponsor", "actionType": "skip", "segment": [600, 600], "UUID": "f"},
        {"category": "sponsor", "actionType": "skip", "segment": None, "UUID": "g"},
    ]},
]


def test_parse_keeps_this_video_and_skips_only():
    assert rp.parse_sponsor(ANSWER, VIDEO) == [
        {"category": "sponsor", "start": 10_000, "end": 40_250, "uuid": "a"},
        {"category": "selfpromo", "start": 300_500, "end": 320_000, "uuid": "b"},
        {"category": "interaction", "start": 500_000, "end": 505_000, "uuid": "e"},
    ]
    assert rp.parse_sponsor(ANSWER, "absent0000") == []
    assert rp.parse_sponsor({"not": "a list"}, VIDEO) == []


class _Answer:
    def __init__(self, status, data=None):
        self.status_code, self.data = status, data

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_lookup_404_is_none_found_and_errors_raise():
    asked = []

    def get(url, **kw):
        asked.append(url)
        return _Answer(404)
    assert rp.sponsor_lookup(VIDEO, get) == []
    assert asked == [rp.sponsor_url(VIDEO)]
    assert len(rp.sponsor_lookup(VIDEO, lambda url, **kw: _Answer(200, ANSWER))) == 3
    try:
        rp.sponsor_lookup(VIDEO, lambda url, **kw: _Answer(503))
    except RuntimeError:
        pass
    else:
        raise AssertionError("a failure must not pass for « no sponsor »")


def test_wants_lookup_once_for_a_video_when_on():
    video = {"mediaUrl": "https://www.youtube.com/watch?v=" + VIDEO}
    assert rp.wants_sponsor_lookup(video, True)
    assert not rp.wants_sponsor_lookup(video, False)
    assert not rp.wants_sponsor_lookup(dict(video, skipSegments=[]), True)
    assert not rp.wants_sponsor_lookup({"mediaUrl": "https://example.org/a.mp3"}, True)


SEGMENTS = [{"category": "sponsor", "start": 10_000, "end": 40_000},
            {"category": "selfpromo", "start": 300_000, "end": 320_000}]


def test_playing_into_a_segment_skips_it():
    assert rp.skip_action(9_800, 10_050, SEGMENTS) == ("skip", 0)
    assert rp.skip_action(299_900, 300_000, SEGMENTS) == ("skip", 1)
    assert rp.skip_action(9_000, 9_250, SEGMENTS) is None       # not there yet
    # from the very beginning (the window starts one before): a sponsor at 0 is played into
    assert rp.skip_action(-1, 0, [{"category": "sponsor", "start": 0, "end": 5_000}]) == ("skip", 0)


def test_a_segment_sought_into_by_hand_is_not_skipped():
    # the tick after a seek starts inside the segment
    assert rp.skip_action(20_000, 20_250, SEGMENTS) is None
    # a jump across the start (−5 s, +30 s, the line) is a seek, not playing
    assert rp.skip_action(1_000, 15_000, SEGMENTS) is None
    # backwards
    assert rp.skip_action(50_000, 10_100, SEGMENTS) is None
    assert rp.skip_action(None, 10_100, SEGMENTS) is None


def test_a_segment_gone_back_to_plays():
    assert rp.skip_action(9_800, 10_050, SEGMENTS, spared={0}) is None
    assert rp.skip_action(299_900, 300_000, SEGMENTS, spared={0}) == ("skip", 1)


def test_a_sponsor_running_into_the_closing_ends_the_episode():
    segments = [{"category": "selfpromo", "start": 3_500_000, "end": 3_600_000}]
    assert rp.skip_action(3_499_900, 3_500_100, segments, end=3_540_000) == ("end", None)
    assert rp.skip_action(3_499_900, 3_500_100, segments) == ("skip", 0)


def test_every_category_has_its_words_in_six_languages():
    for key in rp.SPONSOR_SKIPPED.values():
        for lang in ("fr", "de", "es", "pt", "ru"):
            assert key in rp.STRINGS[lang], (lang, key)
    for key in ("next chapter", "go back", "skip the start and the end…", "seconds skipped at the start",
                "seconds skipped at the end", "skip sponsors in YouTube videos",
                "For an introduction or a closing that is the same in every episode. 0 skips nothing.",
                "SponsorBlock, a list kept by its users, is asked where they are. Only part of a fingerprint of the video's address is sent."):
        for lang in ("fr", "de", "es", "pt", "ru"):
            assert key in rp.STRINGS[lang], (lang, key)


def test_settings_travel_in_the_settings_file():
    feeds = [{"id": "f", "url": "https://example.org/f.xml", "skipStart": 30, "skipEnd": 12},
             {"id": "g", "url": "https://example.org/g.xml"}]
    data = json.loads(rp.backup_export(rp.settings_for_backup({"skip_sponsors": False}), feeds, []))
    # the phone's keys (Backup.kt): seconds, written only when set
    assert data["feeds"][0]["skipStart"] == 30 and data["feeds"][0]["skipEnd"] == 12
    assert "skipStart" not in data["feeds"][1] and "skipEnd" not in data["feeds"][1]
    assert data["settings"]["skip_sponsors"] is False
    assert rp.settings_from_backup({}, {"skip_sponsors": False})["skip_sponsors"] is False
    assert rp.settings_for_backup({})["skip_sponsors"] is True       # on by default


def test_merge_keeps_the_segments_found():
    import threading
    store = object.__new__(rp.Store)
    store.lock = threading.RLock()
    store.feeds = [{"id": "f", "url": "u", "keepCount": 50}]
    old = {"id": "e1", "feedId": "f", "title": "t", "published": 1, "durationMs": 0, "localPath": "",
           "positionMs": 0, "state": "NEW", "lastPlayed": 0, "starred": False, "skipSegments": SEGMENTS}
    store.episodes = [old]
    store._save_episodes = lambda fid: None
    fresh = {"id": "e1", "title": "t2", "published": 1, "durationMs": 0, "localPath": "",
             "positionMs": 0, "state": "NEW", "lastPlayed": 0, "starred": False}
    store.merge("f", [fresh])
    assert store.episode("e1")["skipSegments"] == SEGMENTS
    assert store.episode("e1")["title"] == "t2"
