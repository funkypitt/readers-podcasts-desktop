#!/usr/bin/env python3
"""Reads what the Android app writes, and writes what the Android app reads.

There is no server between the two apps: abonnements.opml and reglages.json are the whole of
the synchronisation. This script closes the loop from the desktop side — run the phone's
`./gradlew :app:testPriveDebugUnitTest` first, which parses the fixtures this writes and leaves
its own files in app/build/interop/.

    python3 tools/check-interop.py ../readers-podcasts
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("rp", os.path.join(HERE, "readers_podcasts.py"))
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)

FEEDS = [
    {"id": rp.feed_id("https://example.org/grande-table.xml"), "url": "https://example.org/grande-table.xml",
     "title": "La Grande Table", "kind": "RSS", "autoDownload": True, "keepCount": 20},
    {"id": rp.feed_id("https://example.org/cours.xml"), "url": "https://example.org/cours.xml",
     "title": "Le Cours de l'histoire & suite", "kind": "RSS", "autoDownload": False, "keepCount": 50},
]


def write_fixtures(android_repo):
    """The desktop's own writing, for the phone's InteropTest to read."""
    out = os.path.join(android_repo, "app/src/test/resources")
    os.makedirs(out, exist_ok=True)
    fid = FEEDS[0]["id"]
    episodes = [
        {"id": rp.episode_id(fid, "episode-42"), "feedId": fid, "title": "Le temps des orages",
         "positionMs": 754000, "state": "STARTED", "lastPlayed": 1758200000000},
        {"id": rp.episode_id(fid, "episode-43"), "feedId": fid, "title": "Une brève",
         "positionMs": 0, "state": "NEW", "lastPlayed": 0},
        # Untouched but starred: it has to travel all the same, or a favourite kept here would
        # vanish on the phone the first time the file crossed.
        {"id": rp.episode_id(fid, "episode-44"), "feedId": fid, "title": "Un favori",
         "positionMs": 0, "state": "NEW", "lastPlayed": 0, "starred": True},
    ]
    settings = rp.settings_for_backup({"dark": False, "font": "serif", "speed": 1.5,
                                       "auto_refresh": False, "delete_when_played": True})
    with open(os.path.join(out, "desktop-abonnements.opml"), "w", encoding="utf-8") as fh:
        fh.write(rp.opml_export(FEEDS))
    with open(os.path.join(out, "desktop-reglages.json"), "w", encoding="utf-8") as fh:
        fh.write(rp.backup_export(settings, FEEDS, episodes))
    return out


def read_phone(android_repo):
    """What the phone left in app/build/interop, read the way an import would read it."""
    folder = os.path.join(android_repo, "app/build/interop")
    opml = os.path.join(folder, "phone-abonnements.opml")
    backup = os.path.join(folder, "phone-reglages.json")
    if not (os.path.exists(opml) and os.path.exists(backup)):
        sys.exit("run the phone's unit tests first: ./gradlew :app:testPriveDebugUnitTest")

    with open(opml, "rb") as fh:
        lines = rp.opml_parse(fh.read())
    assert len(lines) == 1, lines
    url, title = lines[0]
    assert url == "https://example.org/phone.xml", url
    assert title == "Une chaîne « à part »", title

    with open(backup, encoding="utf-8") as fh:
        data = json.load(fh)
    settings = data["settings"]
    assert settings["theme"] == "DARK", settings
    assert settings["delete_when_played"] is False, settings
    feed = data["feeds"][0]
    assert feed["autoDownload"] is True and feed["keepCount"] == 30, feed
    # The id the phone wrote for an episode is the id this side works out for the same one.
    fid = rp.feed_id(feed["url"])
    started = [e for e in data["episodes"] if e["state"] == "STARTED"]
    assert len(started) == 1, data["episodes"]
    assert started[0]["id"] == rp.episode_id(fid, "p-1"), started
    assert started[0]["positionMs"] == 321000, started
    starred = [e for e in data["episodes"] if e.get("starred")]
    assert len(starred) == 1 and starred[0]["id"] == rp.episode_id(fid, "p-3"), data["episodes"]
    # An episode neither begun nor starred is left out of the file by both sides.
    assert len(data["episodes"]) == 2, data["episodes"]
    return url, title


if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(HERE), "readers-podcasts")
    written = write_fixtures(repo)
    read_phone(repo)
    print("fixtures written to", written)
    print("the phone's opml and reglages.json read back as expected")
