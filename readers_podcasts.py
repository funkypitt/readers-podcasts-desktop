#!/usr/bin/env python3
"""Reader's Podcasts — black-and-white podcasts for the desktop, in step with the Android app.
Subscriptions travel as OPML, settings and listening positions as reglages.json: there is no
server, those two files are the synchronisation. One file, PyQt5 + requests. MIT licence."""

import html
import json
import locale
import os
import re
import sys
import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha1
from urllib.parse import urljoin, urlparse

import requests
from PyQt5 import QtCore, QtGui, QtWidgets

APP = "readers-podcasts"
VERSION = "0.1.0"
AGENT = "Readers-Podcasts/%s (+https://gallaz.ch/eink)" % VERSION

# Playback is the one thing this app cannot do by itself. QtMultimedia ships in its own package
# on Linux (python3-pyqt5.qtmultimedia); without it everything else still works, and the player
# row says what is missing instead of the window failing to open at all.
try:
    from PyQt5 import QtMultimedia
    HAVE_AUDIO = True
except ImportError:
    QtMultimedia = None
    HAVE_AUDIO = False


def _app_dirs():
    if sys.platform == "win32":
        base = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Readers Podcasts")
        return base, base
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support/" + APP)
        return base, base
    return (os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), APP),
            os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), APP))


CONFIG_DIR, DATA_DIR = _app_dirs()
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
FEEDS_FILE = os.path.join(DATA_DIR, "feeds.json")
FEEDS_DIR = os.path.join(DATA_DIR, "feeds")
AUDIO_DIR = os.path.join(DATA_DIR, "audio")

VIEW_QUEUE = "queue"
VIEW_NEW = "new"

# ------------------------------------------------------------------------------------------
# Six languages, the English text as the key — the same wording as the phone
# ------------------------------------------------------------------------------------------

STRINGS = {
 "fr": {
  "to hear": "à écouter", "new": "nouveautés", "channels": "chaînes", "+ a feed": "+ un flux",
  "the address of a feed": "l'adresse d'un flux", "subscribe": "s'abonner", "unsubscribe": "se désabonner",
  "refresh": "actualiser", "refreshing…": "actualisation…", "reading the feed…": "lecture du flux…",
  "subscribed to %s": "abonné à %s", "that feed could not be read. %s": "ce flux n'a pas pu être lu. %s",
  "no connection": "pas de connexion",
  "no subscriptions yet. + a feed below takes the address of one.":
      "aucun abonnement. « + un flux » ci-dessous prend l'adresse d'un flux.",
  "nothing on this computer yet.": "rien sur cet ordinateur pour l'instant.",
  "nothing here yet.": "rien ici pour l'instant.",
  "download": "télécharger", "downloading %d %%": "téléchargement %d %%", "waiting": "en attente",
  "stop the download": "arrêter le téléchargement",
  "remove from this computer": "retirer de cet ordinateur", "on this computer": "sur cet ordinateur",
  "heard": "écouté", "begun": "commencé", "%s left": "il reste %s",
  "mark as heard": "marquer écouté", "mark as unheard": "marquer non écouté",
  "copy the link": "copier le lien", "open the channel": "aller à la chaîne",
  "automatic download": "téléchargement automatique",
  "import subscriptions": "importer des abonnements", "export the subscriptions": "exporter les abonnements",
  "import settings": "importer des réglages", "export the settings": "exporter les réglages",
  "subscriptions exported": "abonnements exportés", "no subscription in that file": "aucun abonnement dans ce fichier",
  "settings exported": "réglages exportés", "settings imported": "réglages importés",
  "that file could not be read": "ce fichier n'a pas pu être lu", "could not write the file": "écriture impossible",
  "%d feeds added": "%d flux ajoutés",
  "settings": "réglages", "colours": "couleurs", "white on black": "blanc sur noir",
  "black on white": "noir sur blanc", "text size": "taille du texte", "font": "police",
  "refresh on opening": "actualiser à l'ouverture", "delete once heard": "effacer une fois écouté",
  "on": "actif", "off": "inactif", "today": "aujourd'hui", "yesterday": "hier",
  "speed": "vitesse", "play": "lire", "pause": "pause",
  "audio is missing: install python3-pyqt5.qtmultimedia": "audio manquant : installez python3-pyqt5.qtmultimedia",
  "nothing playing": "rien en écoute", "cancel": "annuler", "ok": "ok", "close": "fermer",
  "podcasts, kept on this computer.": "des podcasts, gardés sur cet ordinateur.",
 },
 "de": {
  "to hear": "zu hören", "new": "neu", "channels": "Kanäle", "+ a feed": "+ ein Feed",
  "the address of a feed": "die Adresse eines Feeds", "subscribe": "abonnieren", "unsubscribe": "abbestellen",
  "refresh": "aktualisieren", "refreshing…": "wird aktualisiert…", "reading the feed…": "Feed wird gelesen…",
  "subscribed to %s": "%s abonniert", "that feed could not be read. %s": "dieser Feed konnte nicht gelesen werden. %s",
  "no connection": "keine Verbindung",
  "no subscriptions yet. + a feed below takes the address of one.":
      "noch keine Abos. « + ein Feed » unten nimmt die Adresse eines Feeds.",
  "nothing on this computer yet.": "noch nichts auf diesem Rechner.",
  "nothing here yet.": "noch nichts hier.",
  "download": "herunterladen", "downloading %d %%": "wird geladen %d %%", "waiting": "wartet",
  "stop the download": "Download anhalten",
  "remove from this computer": "vom Rechner nehmen", "on this computer": "auf diesem Rechner",
  "heard": "gehört", "begun": "begonnen", "%s left": "noch %s",
  "mark as heard": "als gehört merken", "mark as unheard": "als ungehört merken",
  "copy the link": "Link kopieren", "open the channel": "zum Kanal",
  "automatic download": "automatisch laden",
  "import subscriptions": "Abos einlesen", "export the subscriptions": "Abos ausgeben",
  "import settings": "Einstellungen einlesen", "export the settings": "Einstellungen ausgeben",
  "subscriptions exported": "Abos ausgegeben", "no subscription in that file": "kein Abo in dieser Datei",
  "settings exported": "Einstellungen ausgegeben", "settings imported": "Einstellungen eingelesen",
  "that file could not be read": "diese Datei konnte nicht gelesen werden", "could not write the file": "Schreiben nicht möglich",
  "%d feeds added": "%d Feeds hinzugefügt",
  "settings": "Einstellungen", "colours": "Farben", "white on black": "weiss auf schwarz",
  "black on white": "schwarz auf weiss", "text size": "Textgrösse", "font": "Schrift",
  "refresh on opening": "beim Öffnen aktualisieren", "delete once heard": "nach dem Hören löschen",
  "on": "an", "off": "aus", "today": "heute", "yesterday": "gestern",
  "speed": "Tempo", "play": "abspielen", "pause": "Pause",
  "audio is missing: install python3-pyqt5.qtmultimedia": "Audio fehlt: python3-pyqt5.qtmultimedia installieren",
  "nothing playing": "nichts läuft", "cancel": "abbrechen", "ok": "ok", "close": "schliessen",
  "podcasts, kept on this computer.": "Podcasts, auf diesem Rechner behalten.",
 },
 "es": {
  "to hear": "por escuchar", "new": "novedades", "channels": "canales", "+ a feed": "+ una fuente",
  "the address of a feed": "la dirección de una fuente", "subscribe": "suscribirse", "unsubscribe": "darse de baja",
  "refresh": "actualizar", "refreshing…": "actualizando…", "reading the feed…": "leyendo la fuente…",
  "subscribed to %s": "suscrito a %s", "that feed could not be read. %s": "no se pudo leer esa fuente. %s",
  "no connection": "sin conexión",
  "no subscriptions yet. + a feed below takes the address of one.":
      "ninguna suscripción. « + una fuente » abajo toma la dirección de una fuente.",
  "nothing on this computer yet.": "nada en este ordenador todavía.",
  "nothing here yet.": "nada aquí todavía.",
  "download": "descargar", "downloading %d %%": "descargando %d %%", "waiting": "en espera",
  "stop the download": "parar la descarga",
  "remove from this computer": "quitar de este ordenador", "on this computer": "en este ordenador",
  "heard": "escuchado", "begun": "empezado", "%s left": "quedan %s",
  "mark as heard": "marcar escuchado", "mark as unheard": "marcar no escuchado",
  "copy the link": "copiar el enlace", "open the channel": "ir al canal",
  "automatic download": "descarga automática",
  "import subscriptions": "importar suscripciones", "export the subscriptions": "exportar las suscripciones",
  "import settings": "importar ajustes", "export the settings": "exportar los ajustes",
  "subscriptions exported": "suscripciones exportadas", "no subscription in that file": "ninguna suscripción en ese archivo",
  "settings exported": "ajustes exportados", "settings imported": "ajustes importados",
  "that file could not be read": "no se pudo leer ese archivo", "could not write the file": "no se pudo escribir",
  "%d feeds added": "%d fuentes añadidas",
  "settings": "ajustes", "colours": "colores", "white on black": "blanco sobre negro",
  "black on white": "negro sobre blanco", "text size": "tamaño del texto", "font": "tipografía",
  "refresh on opening": "actualizar al abrir", "delete once heard": "borrar una vez escuchado",
  "on": "activo", "off": "inactivo", "today": "hoy", "yesterday": "ayer",
  "speed": "velocidad", "play": "reproducir", "pause": "pausa",
  "audio is missing: install python3-pyqt5.qtmultimedia": "falta el audio: instale python3-pyqt5.qtmultimedia",
  "nothing playing": "nada en escucha", "cancel": "cancelar", "ok": "ok", "close": "cerrar",
  "podcasts, kept on this computer.": "podcasts, guardados en este ordenador.",
 },
 "pt": {
  "to hear": "por ouvir", "new": "novidades", "channels": "canais", "+ a feed": "+ uma fonte",
  "the address of a feed": "o endereço de uma fonte", "subscribe": "subscrever", "unsubscribe": "anular a subscrição",
  "refresh": "atualizar", "refreshing…": "a atualizar…", "reading the feed…": "a ler a fonte…",
  "subscribed to %s": "subscrito %s", "that feed could not be read. %s": "não foi possível ler essa fonte. %s",
  "no connection": "sem ligação",
  "no subscriptions yet. + a feed below takes the address of one.":
      "nenhuma subscrição. « + uma fonte » abaixo aceita o endereço de uma fonte.",
  "nothing on this computer yet.": "ainda nada neste computador.",
  "nothing here yet.": "ainda nada aqui.",
  "download": "transferir", "downloading %d %%": "a transferir %d %%", "waiting": "em espera",
  "stop the download": "parar a transferência",
  "remove from this computer": "retirar deste computador", "on this computer": "neste computador",
  "heard": "ouvido", "begun": "começado", "%s left": "faltam %s",
  "mark as heard": "marcar ouvido", "mark as unheard": "marcar não ouvido",
  "copy the link": "copiar a ligação", "open the channel": "ir ao canal",
  "automatic download": "transferência automática",
  "import subscriptions": "importar subscrições", "export the subscriptions": "exportar as subscrições",
  "import settings": "importar definições", "export the settings": "exportar as definições",
  "subscriptions exported": "subscrições exportadas", "no subscription in that file": "nenhuma subscrição nesse ficheiro",
  "settings exported": "definições exportadas", "settings imported": "definições importadas",
  "that file could not be read": "não foi possível ler esse ficheiro", "could not write the file": "não foi possível escrever",
  "%d feeds added": "%d fontes adicionadas",
  "settings": "definições", "colours": "cores", "white on black": "branco sobre preto",
  "black on white": "preto sobre branco", "text size": "tamanho do texto", "font": "tipo de letra",
  "refresh on opening": "atualizar ao abrir", "delete once heard": "apagar depois de ouvido",
  "on": "ativa", "off": "inativa", "today": "hoje", "yesterday": "ontem",
  "speed": "velocidade", "play": "reproduzir", "pause": "pausa",
  "audio is missing: install python3-pyqt5.qtmultimedia": "falta o áudio: instale python3-pyqt5.qtmultimedia",
  "nothing playing": "nada em audição", "cancel": "cancelar", "ok": "ok", "close": "fechar",
  "podcasts, kept on this computer.": "podcasts, guardados neste computador.",
 },
 "ru": {
  "to hear": "послушать", "new": "новое", "channels": "каналы", "+ a feed": "+ лента",
  "the address of a feed": "адрес ленты", "subscribe": "подписаться", "unsubscribe": "отписаться",
  "refresh": "обновить", "refreshing…": "обновление…", "reading the feed…": "чтение ленты…",
  "subscribed to %s": "подписка на %s", "that feed could not be read. %s": "эту ленту не удалось прочитать. %s",
  "no connection": "нет связи",
  "no subscriptions yet. + a feed below takes the address of one.":
      "подписок пока нет. « + лента » внизу принимает адрес ленты.",
  "nothing on this computer yet.": "на этом компьютере пока ничего нет.",
  "nothing here yet.": "здесь пока пусто.",
  "download": "загрузить", "downloading %d %%": "загрузка %d %%", "waiting": "в очереди",
  "stop the download": "остановить загрузку",
  "remove from this computer": "убрать с компьютера", "on this computer": "на этом компьютере",
  "heard": "прослушано", "begun": "начато", "%s left": "осталось %s",
  "mark as heard": "отметить прослушанным", "mark as unheard": "отметить непрослушанным",
  "copy the link": "скопировать ссылку", "open the channel": "к каналу",
  "automatic download": "автоматическая загрузка",
  "import subscriptions": "импортировать подписки", "export the subscriptions": "экспортировать подписки",
  "import settings": "импортировать настройки", "export the settings": "экспортировать настройки",
  "subscriptions exported": "подписки экспортированы", "no subscription in that file": "в этом файле нет подписок",
  "settings exported": "настройки экспортированы", "settings imported": "настройки импортированы",
  "that file could not be read": "этот файл не удалось прочитать", "could not write the file": "не удалось записать файл",
  "%d feeds added": "добавлено каналов: %d",
  "settings": "настройки", "colours": "цвета", "white on black": "белое на чёрном",
  "black on white": "чёрное на белом", "text size": "размер текста", "font": "шрифт",
  "refresh on opening": "обновлять при открытии", "delete once heard": "удалять после прослушивания",
  "on": "вкл", "off": "выкл", "today": "сегодня", "yesterday": "вчера",
  "speed": "скорость", "play": "воспроизвести", "pause": "пауза",
  "audio is missing: install python3-pyqt5.qtmultimedia": "нет аудио: установите python3-pyqt5.qtmultimedia",
  "nothing playing": "ничего не играет", "cancel": "отмена", "ok": "ок", "close": "закрыть",
  "podcasts, kept on this computer.": "подкасты, которые остаются на этом компьютере.",
 },
}


def _lang():
    for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(name)
        if v:
            code = v.split(":")[0].split(".")[0].split("_")[0].lower()
            if code in STRINGS:
                return code
            if code == "en":
                return "en"
    try:
        code = (locale.getdefaultlocale()[0] or "en").split("_")[0].lower()
    except Exception:
        code = "en"
    return code if code in STRINGS else "en"


LANG = _lang()


def _(key, *args):
    text = STRINGS.get(LANG, {}).get(key, key)
    return text % args if args else text


# ------------------------------------------------------------------------------------------
# The model, with the phone's ids: the same episode gets the same id on both sides, which is
# what lets reglages.json carry a listening position across without either knowing the other.
# ------------------------------------------------------------------------------------------

def _sha1(text):
    return sha1(text.encode("utf-8")).hexdigest()


def feed_id(url):
    return _sha1(url.strip().rstrip("/"))


def episode_id(fid, guid):
    return _sha1("%s|%s" % (fid, guid))


def spoken(ms):
    """`47 min`, `1 h 12`, `12 s` — never `00:47:00`, and never a rounded `0 min`."""
    if ms < 60000:
        return "%d s" % (max(0, ms) // 1000)
    minutes = (ms + 30000) // 60000
    return "%d h %02d" % (minutes // 60, minutes % 60) if minutes >= 60 else "%d min" % minutes


def clock(ms):
    s = max(0, ms) // 1000
    return "%d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60) if s >= 3600 else "%02d:%02d" % (s // 60, s % 60)


def relative_date(ms):
    if not ms:
        return ""
    then = datetime.fromtimestamp(ms / 1000)
    now = datetime.now()
    days = (now.date() - then.date()).days
    if days <= 0:
        return _("today")
    if days == 1:
        return _("yesterday")
    if days < 7:
        return then.strftime("%A").lower()
    return then.strftime("%-d %b") if then.year == now.year else then.strftime("%-d %b %Y")


# ------------------------------------------------------------------------------------------
# Feeds: RSS, Atom and Media RSS, read the way the phone reads them
# ------------------------------------------------------------------------------------------

BLOCKS = re.compile(r"(?i)<br\s*/?>|</(p|div|h[1-6]|li|ul|ol|blockquote|tr|section|article)>")


def strip_html(text):
    if not text:
        return ""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = BLOCKS.sub("\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [line.strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _local(tag):
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def _duration(raw):
    raw = (raw or "").strip()
    if not raw:
        return 0
    if ":" not in raw:
        try:
            return int(float(raw)) * 1000
        except ValueError:
            return 0
    parts = []
    for bit in raw.split(":"):
        try:
            parts.append(int(bit))
        except ValueError:
            return 0
    if len(parts) == 3:
        return (parts[0] * 3600 + parts[1] * 60 + parts[2]) * 1000
    if len(parts) == 2:
        return (parts[0] * 60 + parts[1]) * 1000
    return 0


def _date(raw):
    raw = (raw or "").strip()
    if not raw:
        return 0
    try:
        return int(parsedate_to_datetime(raw).timestamp() * 1000)
    except Exception:
        pass
    try:
        text = raw.replace("Z", "+00:00")
        d = datetime.fromisoformat(text)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return int(d.timestamp() * 1000)
    except Exception:
        return 0


def parse_feed(fid, kind, data):
    """Returns (title, author, [episode dicts]). An item without playable media is not an
    episode; a YouTube entry points at its page, which is what yt-dlp would be handed."""
    root = ET.fromstring(data)
    items = [n for n in root.iter() if _local(n.tag) in ("item", "entry")]
    # Atom repeats <title> and <author> inside every entry: only what lies outside one belongs
    # to the feed itself.
    within = {id(sub) for item in items for sub in item.iter()}
    title = author = ""
    for node in root.iter():
        if id(node) in within:
            continue
        tag = _local(node.tag)
        if tag == "title" and not title:
            title = (node.text or "").strip()
        elif tag in ("managingEditor", "name") and not author:
            author = (node.text or "").strip()
    episodes = [e for e in (_build(fid, kind, item) for item in items) if e]
    return title, author, episodes


def _build(fid, kind, item):
    title = guid = media = mime = link = description = ""
    published = duration = 0
    size = 0
    for node in item.iter():
        tag = _local(node.tag)
        text = (node.text or "").strip()
        if tag == "title" and not title:
            title = text
        elif tag in ("guid", "id", "videoId") and not guid:
            guid = text
        elif tag in ("pubDate", "published", "updated", "date") and not published:
            published = _date(text)
        elif tag == "enclosure":
            media = node.get("url") or media
            mime = node.get("type") or mime
            try:
                size = int(node.get("length") or 0)
            except ValueError:
                size = 0
        elif tag == "content" and node.get("url") and not media:
            media = node.get("url")
            mime = node.get("type") or mime
        elif tag == "link" and not link:
            href = node.get("href")
            if href and node.get("rel") in (None, "alternate"):
                link = href
            elif not href:
                link = text
        elif tag == "duration" and not duration:
            duration = _duration(text)
        elif tag in ("description", "summary") and not description:
            description = strip_html(text)
    if not media and kind == "YOUTUBE" and link:
        media = link
    if not media or not title:
        return None
    return {
        "id": episode_id(fid, guid or media or (title + str(published))),
        "title": title, "published": published or int(datetime.now().timestamp() * 1000),
        "mediaUrl": media, "mime": mime or "audio/*", "bytes": size, "durationMs": duration,
        "localPath": "", "positionMs": 0, "state": "NEW", "lastPlayed": 0,
        "description": description[:2000],
    }


# ---- OPML and the backup file, byte for byte what the phone writes ----

def opml_export(feeds):
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<opml version="2.0">', "  <head>",
           "    <title>Reader's Podcasts</title>", "  </head>", "  <body>"]
    for f in feeds:
        title = _xml_escape(f.get("title") or f["url"])
        out.append('    <outline type="rss" text="%s" title="%s" xmlUrl="%s" />'
                   % (title, title, _xml_escape(f["url"])))
    out += ["  </body>", "</opml>", ""]
    return "\n".join(out)


def _xml_escape(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))


def opml_parse(data):
    root = ET.fromstring(data)
    lines = []
    seen = set()
    for node in root.iter():
        if _local(node.tag).lower() != "outline":
            continue
        url = node.get("xmlUrl") or node.get("xmlurl")
        if not url or url.strip() in seen:
            continue
        seen.add(url.strip())
        lines.append((url.strip(), (node.get("title") or node.get("text") or url).strip()))
    return lines


def backup_export(settings, feeds, episodes):
    return json.dumps({
        "app": APP, "version": 1, "exported": int(datetime.now().timestamp() * 1000),
        "settings": settings,
        "feeds": [{"url": f["url"], "title": f.get("title", ""), "kind": f.get("kind", "RSS"),
                   "autoDownload": f.get("autoDownload", False), "keepCount": f.get("keepCount", 50)}
                  for f in feeds],
        "episodes": [{"id": e["id"], "feed": e["feedId"], "title": e["title"],
                      "positionMs": e.get("positionMs", 0), "state": e.get("state", "NEW"),
                      "lastPlayed": e.get("lastPlayed", 0)}
                     for e in episodes if e.get("state", "NEW") != "NEW" or e.get("positionMs", 0) > 0],
    }, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------------------------------
# The store: feeds.json and one feeds/<id>.json per subscription, as on the phone
# ------------------------------------------------------------------------------------------

class Store:
    def __init__(self):
        os.makedirs(FEEDS_DIR, exist_ok=True)
        os.makedirs(AUDIO_DIR, exist_ok=True)
        self.lock = threading.RLock()
        self.feeds = self._load_feeds()
        self.episodes = []
        for f in self.feeds:
            self.episodes += self._load_episodes(f["id"])

    # ---- reading ----

    def feed(self, fid):
        return next((f for f in self.feeds if f["id"] == fid), None)

    def episode(self, eid):
        return next((e for e in self.episodes if e["id"] == eid), None)

    def episodes_of(self, fid):
        return sorted([e for e in self.episodes if e["feedId"] == fid],
                      key=lambda e: e["published"], reverse=True)

    def queue(self):
        ready = [e for e in self.episodes
                 if e["state"] != "PLAYED" and (e["localPath"] or e["state"] == "STARTED")]
        return sorted(ready, key=lambda e: (e["lastPlayed"] if e["state"] == "STARTED" else 0, e["published"]),
                      reverse=True)

    def recent(self):
        return sorted([e for e in self.episodes if e["state"] != "PLAYED"],
                      key=lambda e: e["published"], reverse=True)

    def unplayed(self, fid):
        return len([e for e in self.episodes if e["feedId"] == fid and e["state"] != "PLAYED"])

    # ---- writing ----

    def add_feed(self, feed):
        with self.lock:
            known = self.feed(feed["id"])
            if known:
                return known
            self.feeds.append(feed)
            self._save_feeds()
            return feed

    def update_feed(self, fid, **fields):
        with self.lock:
            f = self.feed(fid)
            if f:
                f.update(fields)
                self._save_feeds()

    def remove_feed(self, fid):
        with self.lock:
            for e in [e for e in self.episodes if e["feedId"] == fid]:
                self._delete_file(e)
            self.episodes = [e for e in self.episodes if e["feedId"] != fid]
            self.feeds = [f for f in self.feeds if f["id"] != fid]
            path = os.path.join(FEEDS_DIR, fid + ".json")
            if os.path.exists(path):
                os.remove(path)
            self._save_feeds()

    def update_episode(self, eid, **fields):
        with self.lock:
            e = self.episode(eid)
            if not e:
                return
            e.update(fields)
            self._save_episodes(e["feedId"])

    def delete_file(self, eid):
        with self.lock:
            e = self.episode(eid)
            if e:
                self._delete_file(e)
                e["localPath"] = ""
                self._save_episodes(e["feedId"])

    def _delete_file(self, e):
        if e.get("localPath") and os.path.exists(e["localPath"]):
            try:
                os.remove(e["localPath"])
            except OSError:
                pass

    def merge(self, fid, fresh):
        """What is ours stays ours — the position, the file, whether it was heard; the feed only
        brings back its own: the title, the date, the media."""
        with self.lock:
            keep = (self.feed(fid) or {}).get("keepCount", 50)
            mine = {e["id"]: e for e in self.episodes if e["feedId"] == fid}
            merged = []
            for new in fresh:
                new = dict(new, feedId=fid)
                old = mine.get(new["id"])
                if old:
                    new.update({k: old[k] for k in ("localPath", "positionMs", "state", "lastPlayed")})
                    if not new["durationMs"]:
                        new["durationMs"] = old["durationMs"]
                merged.append(new)
            fresh_ids = {e["id"] for e in merged}
            # A feed that lists only its last ten items must not delete what one is listening to.
            orphans = [e for e in mine.values()
                       if e["id"] not in fresh_ids and (e["localPath"] or e["state"] == "STARTED")]
            allofthem = sorted(merged + orphans, key=lambda e: e["published"], reverse=True)
            trimmed = [e for i, e in enumerate(allofthem)
                       if i < keep or e["localPath"] or e["state"] == "STARTED"]
            self.episodes = [e for e in self.episodes if e["feedId"] != fid] + trimmed
            self._save_episodes(fid)

    # ---- json ----

    def _load_feeds(self):
        try:
            with open(FEEDS_FILE, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return []

    def _save_feeds(self):
        try:
            with open(FEEDS_FILE, "w", encoding="utf-8") as fh:
                json.dump(self.feeds, fh, ensure_ascii=False)
        except OSError:
            pass

    def _load_episodes(self, fid):
        try:
            with open(os.path.join(FEEDS_DIR, fid + ".json"), encoding="utf-8") as fh:
                items = json.load(fh)
        except Exception:
            return []
        out = []
        for e in items:
            e["feedId"] = fid
            e.setdefault("localPath", "")
            # A file deleted from outside must not leave a row claiming to be here.
            if e["localPath"] and not os.path.exists(e["localPath"]):
                e["localPath"] = ""
            out.append(e)
        return out

    def _save_episodes(self, fid):
        rows = sorted([e for e in self.episodes if e["feedId"] == fid],
                      key=lambda e: e["published"], reverse=True)
        try:
            with open(os.path.join(FEEDS_DIR, fid + ".json"), "w", encoding="utf-8") as fh:
                json.dump([{k: v for k, v in e.items() if k != "feedId"} for e in rows],
                          fh, ensure_ascii=False)
        except OSError:
            pass


# ------------------------------------------------------------------------------------------
# The network, off the interface thread
# ------------------------------------------------------------------------------------------

def fetch_feed(url, fid, kind):
    r = requests.get(url, headers={"User-Agent": AGENT}, timeout=30)
    r.raise_for_status()
    return parse_feed(fid, kind, r.content)


def normalise(raw):
    s = (raw or "").strip()
    for prefix in ("feed://", "podcast://", "pcast://"):
        if s.lower().startswith(prefix):
            s = "https://" + s[len(prefix):]
    if not s.lower().startswith(("http://", "https://")):
        s = "https://" + s
    return s


class Worker(QtCore.QObject):
    """One job on a thread of its own, reporting back to the window."""
    done = QtCore.pyqtSignal(object, object)     # result, error
    progress = QtCore.pyqtSignal(int)

    def __init__(self, job):
        super().__init__()
        self.job = job

    @QtCore.pyqtSlot()
    def run(self):
        try:
            self.done.emit(self.job(self.progress.emit), None)
        except Exception as exc:  # the row says what went wrong; nothing is swallowed
            self.done.emit(None, exc)


def download(episode, on_progress, cancelled):
    """Resumable: what an interrupted attempt brought down waits in a .part file."""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    target = os.path.join(AUDIO_DIR, episode["id"] + "." + _extension(episode))
    part = target + ".part"
    have = os.path.getsize(part) if os.path.exists(part) else 0
    headers = {"User-Agent": AGENT}
    if have:
        headers["Range"] = "bytes=%d-" % have
    r = requests.get(episode["mediaUrl"], headers=headers, stream=True, timeout=60)
    r.raise_for_status()
    resuming = r.status_code == 206
    if not resuming:
        have = 0
    total = int(r.headers.get("Content-Length") or 0) + have or episode.get("bytes", 0)
    done = have
    with open(part, "ab" if resuming else "wb") as fh:
        for chunk in r.iter_content(256 * 1024):
            if cancelled():
                return None
            fh.write(chunk)
            done += len(chunk)
            if total:
                on_progress(min(100, int(done * 100 / total)))
    os.replace(part, target)
    return target


def _extension(episode):
    tail = episode["mediaUrl"].split("?")[0].rsplit(".", 1)[-1].lower()
    if 2 <= len(tail) <= 4 and tail.isalnum():
        return tail
    mime = episode.get("mime", "")
    if "mpeg" in mime:
        return "mp3"
    if "mp4" in mime or "m4a" in mime:
        return "m4a"
    if "ogg" in mime or "opus" in mime:
        return "opus"
    return "audio"


# ------------------------------------------------------------------------------------------
# Settings
# ------------------------------------------------------------------------------------------

DEFAULTS = {"dark": True, "font": "sans", "font_size": 12, "view": VIEW_QUEUE,
            "auto_refresh": True, "delete_when_played": True, "speed": 1.0}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass


def settings_for_backup(cfg):
    """The keys the phone writes, so one file serves both."""
    return {"theme": "DARK" if cfg.get("dark", True) else "LIGHT",
            "font": {"sans": "SANS", "serif": "SERIF", "mono": "MONO"}.get(cfg.get("font", "sans"), "SANS"),
            "auto_refresh": bool(cfg.get("auto_refresh", True)),
            "delete_when_played": bool(cfg.get("delete_when_played", True)),
            "speed": float(cfg.get("speed", 1.0))}


def settings_from_backup(cfg, settings):
    if "theme" in settings:
        cfg["dark"] = settings["theme"] != "LIGHT"
    if "font" in settings:
        cfg["font"] = {"SANS": "sans", "SERIF": "serif", "MONO": "mono"}.get(settings["font"], "sans")
    for key in ("auto_refresh", "delete_when_played"):
        if key in settings:
            cfg[key] = bool(settings[key])
    if "speed" in settings:
        try:
            cfg["speed"] = float(settings["speed"])
        except (TypeError, ValueError):
            pass
    return cfg


# ------------------------------------------------------------------------------------------
# The look: two colours, text only, the selection inverted — the phone's rules on a window
# ------------------------------------------------------------------------------------------

class Clickable(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal()

    def __init__(self, text="", name=None):
        super().__init__(text)
        if name:
            self.setObjectName(name)
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()


class Line(QtWidgets.QWidget):
    """The position, as a hairline one can click anywhere on — the phone's rule."""
    seek = QtCore.pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.fraction = 0.0
        self.fg, self.rule = QtGui.QColor("#fff"), QtGui.QColor(255, 255, 255, 64)
        self.setFixedHeight(24)
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def set_fraction(self, f):
        self.fraction = max(0.0, min(1.0, f))
        self.update()

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        y = self.height() // 2
        p.fillRect(0, y, self.width(), 1, self.rule)
        p.fillRect(0, y - 1, int(self.width() * self.fraction), 3, self.fg)

    def mousePressEvent(self, e):
        if self.width():
            self.seek.emit(e.x() / self.width())


class EpisodeDelegate(QtWidgets.QStyledItemDelegate):
    """An episode: its title, then a dim line saying where it stands. The chosen one is drawn
    inverted, like every selection in the Reader's apps."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fg, self.bg = QtGui.QColor("#fff"), QtGui.QColor("#000")
        self.big, self.small = QtGui.QFont(), QtGui.QFont()

    def sizeHint(self, option, index):
        two = index.data(QtCore.Qt.UserRole) is not None
        lines = QtGui.QFontMetrics(self.big).height() * (2 if two else 1)
        return QtCore.QSize(100, lines + QtGui.QFontMetrics(self.small).height() + 22)

    def paint(self, p, option, index):
        p.save()
        r = option.rect.adjusted(22, 10, -22, -10)
        sel = bool(option.state & QtWidgets.QStyle.State_Selected)
        fg, bg = (self.bg, self.fg) if sel else (self.fg, self.bg)
        p.fillRect(option.rect, bg)
        dim = QtGui.QColor(fg)
        dim.setAlphaF(0.6 if sel else 0.55)
        fb, fs = QtGui.QFontMetrics(self.big), QtGui.QFontMetrics(self.small)
        title = index.data(QtCore.Qt.DisplayRole)
        status = index.data(QtCore.Qt.UserRole + 1) or ""
        if index.data(QtCore.Qt.UserRole) is None:      # the empty-list message
            p.setFont(self.small)
            p.setPen(dim)
            p.drawText(r, QtCore.Qt.TextWordWrap | QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, title)
            p.restore()
            return
        # A podcast title does not fit on one line; it gets two, then it is cut.
        p.setFont(self.big)
        p.setPen(fg)
        box = QtCore.QRect(r.left(), r.top(), r.width(), fb.height() * 2)
        layout = QtGui.QTextLayout(title, self.big)
        layout.beginLayout()
        y = box.top()
        drawn = 0
        while drawn < 2:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(box.width())
            rest = title[line.textStart() + line.textLength():]
            if drawn == 1 and rest:
                p.drawText(QtCore.QRect(box.left(), y, box.width(), fb.height()),
                           QtCore.Qt.AlignLeft,
                           fb.elidedText(title[line.textStart():], QtCore.Qt.ElideRight, box.width()))
            else:
                p.drawText(QtCore.QRect(box.left(), y, box.width(), fb.height()), QtCore.Qt.AlignLeft,
                           title[line.textStart():line.textStart() + line.textLength()])
            y += fb.height()
            drawn += 1
        layout.endLayout()
        p.setFont(self.small)
        p.setPen(dim)
        p.drawText(QtCore.QRect(r.left(), y, r.width(), fs.height()), QtCore.Qt.AlignLeft,
                   fs.elidedText(status, QtCore.Qt.ElideRight, r.width()))
        p.restore()


class FeedDelegate(QtWidgets.QStyledItemDelegate):
    """A channel: its name, and how many are unheard, right against the edge. Drawn rather than
    styled, because a stylesheet's item padding only reaches the row that carries a background —
    which left every unselected name pressed against the left edge."""

    RULE = "rule"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fg, self.bg = QtGui.QColor("#fff"), QtGui.QColor("#000")
        self.font = QtGui.QFont()

    def sizeHint(self, option, index):
        if index.data(QtCore.Qt.UserRole) == self.RULE:
            return QtCore.QSize(10, 17)
        return QtCore.QSize(100, QtGui.QFontMetrics(self.font).height() + 24)

    def paint(self, p, option, index):
        p.save()
        sel = bool(option.state & QtWidgets.QStyle.State_Selected)
        fg, bg = (self.bg, self.fg) if sel else (self.fg, self.bg)
        p.fillRect(option.rect, bg)
        if index.data(QtCore.Qt.UserRole) == self.RULE:
            rule = QtGui.QColor(self.fg)
            rule.setAlphaF(0.25)
            y = option.rect.center().y()
            p.fillRect(option.rect.left() + 22, y, option.rect.width() - 44, 1, rule)
            p.restore()
            return
        r = option.rect.adjusted(22, 0, -22, 0)
        metrics = QtGui.QFontMetrics(self.font)
        count = index.data(QtCore.Qt.UserRole + 1) or ""
        width = metrics.horizontalAdvance(count) + 12 if count else 0
        p.setFont(self.font)
        p.setPen(fg)
        p.drawText(QtCore.QRect(r.left(), r.top(), r.width() - width, r.height()),
                   QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                   metrics.elidedText(index.data(QtCore.Qt.DisplayRole), QtCore.Qt.ElideRight, r.width() - width))
        if count:
            dim = QtGui.QColor(fg)
            dim.setAlphaF(0.6 if sel else 0.55)
            p.setPen(dim)
            p.drawText(r, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, count)
        p.restore()


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent, cfg):
        super().__init__(parent)
        self.setWindowTitle(_("settings"))
        form = QtWidgets.QFormLayout(self)
        self.colours = QtWidgets.QComboBox()
        self.colours.addItem(_("white on black"), True)
        self.colours.addItem(_("black on white"), False)
        self.colours.setCurrentIndex(0 if cfg.get("dark", True) else 1)
        form.addRow(_("colours"), self.colours)
        self.font = QtWidgets.QComboBox()
        for key, label in (("sans", "sans-serif"), ("serif", "serif"), ("mono", "mono")):
            self.font.addItem(label, key)
        self.font.setCurrentIndex(max(0, self.font.findData(cfg.get("font", "sans"))))
        form.addRow(_("font"), self.font)
        self.size = QtWidgets.QSpinBox()
        self.size.setRange(9, 24)
        self.size.setValue(int(cfg.get("font_size", 12)))
        form.addRow(_("text size"), self.size)
        self.auto = QtWidgets.QCheckBox()
        self.auto.setChecked(bool(cfg.get("auto_refresh", True)))
        form.addRow(_("refresh on opening"), self.auto)
        self.delete_played = QtWidgets.QCheckBox()
        self.delete_played.setChecked(bool(cfg.get("delete_when_played", True)))
        form.addRow(_("delete once heard"), self.delete_played)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self):
        return {"dark": self.colours.currentData(), "font": self.font.currentData(),
                "font_size": self.size.value(), "auto_refresh": self.auto.isChecked(),
                "delete_when_played": self.delete_played.isChecked()}


# ------------------------------------------------------------------------------------------
# The window: the channels on the left, the episodes on the right, the player along the bottom
# ------------------------------------------------------------------------------------------

class Main(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.store = Store()
        self.dark = bool(self.cfg.get("dark", True))
        self.font_size = int(self.cfg.get("font_size", 12))
        self.view = self.cfg.get("view", VIEW_QUEUE)
        self.threads = []            # kept referenced: a QThread garbage-collected mid-job dies
        self.downloading = None      # id of the episode coming down
        self.download_queue = []
        self.download_percent = 0
        self.cancel_download = False
        self.busy = ""               # a line at the top while something is happening

        self.setWindowTitle("Reader's Podcasts")
        self.resize(1000, 680)
        self._build()
        self._player()
        self.apply_style()
        self.refresh_all_lists()
        if self.cfg.get("auto_refresh", True) and self.store.feeds:
            QtCore.QTimer.singleShot(200, self.refresh_feeds)

    # ---- building ----

    def _build(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        outer = QtWidgets.QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, 1)

        self.feeds_list = QtWidgets.QListWidget()
        self.feeds_list.setObjectName("feeds")
        # Nothing here ever scrolls sideways: a list of names that could slide left is a list
        # whose first letters go missing.
        self.feeds_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.feed_delegate = FeedDelegate(self)
        self.feeds_list.setItemDelegate(self.feed_delegate)
        self.feeds_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.feeds_list.customContextMenuRequested.connect(self.feed_menu)
        self.feeds_list.itemClicked.connect(self.choose_view)

        self.add_row = Clickable(_("+ a feed"), "newrow")
        self.add_row.clicked.connect(self.add_feed)

        left = QtWidgets.QWidget()
        left_box = QtWidgets.QVBoxLayout(left)
        left_box.setContentsMargins(0, 0, 0, 0)
        left_box.setSpacing(0)
        left_box.addWidget(self.feeds_list, 1)
        left_box.addWidget(self.add_row)
        self.left = left
        body.addWidget(left)

        right = QtWidgets.QWidget()
        right_box = QtWidgets.QVBoxLayout(right)
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.setSpacing(0)

        head = QtWidgets.QHBoxLayout()
        head.setContentsMargins(22, 14, 22, 14)
        self.head_label = QtWidgets.QLabel("")
        self.head_label.setObjectName("dim")
        head.addWidget(self.head_label, 1)
        more = Clickable("⋯", "more")
        more.clicked.connect(self.page_menu)
        head.addWidget(more)
        right_box.addLayout(head)
        right_box.addWidget(self._separator())

        self.episodes_list = QtWidgets.QListWidget()
        self.episodes_list.setObjectName("episodes")
        self.episodes_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.delegate = EpisodeDelegate(self)
        self.episodes_list.setItemDelegate(self.delegate)
        self.episodes_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.episodes_list.customContextMenuRequested.connect(self.episode_menu)
        self.episodes_list.itemActivated.connect(self.play_selected)
        self.episodes_list.itemDoubleClicked.connect(self.play_selected)
        right_box.addWidget(self.episodes_list, 1)
        body.addWidget(right, 1)

        outer.addWidget(self._separator())
        outer.addWidget(self._player_bar())

    def _separator(self):
        line = QtWidgets.QFrame()
        line.setObjectName("sep")
        line.setFixedHeight(1)
        return line

    def _player_bar(self):
        bar = QtWidgets.QWidget()
        box = QtWidgets.QVBoxLayout(bar)
        box.setContentsMargins(22, 12, 22, 14)
        box.setSpacing(4)

        top = QtWidgets.QHBoxLayout()
        self.clock_label = QtWidgets.QLabel("")
        self.clock_label.setObjectName("clock")
        top.addWidget(self.clock_label)
        self.now_label = QtWidgets.QLabel(_("nothing playing"))
        self.now_label.setObjectName("dim")
        top.addWidget(self.now_label, 1)
        box.addLayout(top)

        self.line = Line()
        self.line.seek.connect(self.seek_fraction)
        box.addWidget(self.line)

        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(24)
        self.back_row = Clickable("−5 s")
        self.back_row.clicked.connect(lambda: self.seek_by(-5000))
        self.play_row = Clickable("▶")
        self.play_row.clicked.connect(self.toggle)
        self.fwd_row = Clickable("+10 s")
        self.fwd_row.clicked.connect(lambda: self.seek_by(10000))
        for w in (self.back_row, self.play_row, self.fwd_row):
            controls.addWidget(w)
        controls.addStretch(1)
        self.speed_row = Clickable("")
        self.speed_row.clicked.connect(self.next_speed)
        controls.addWidget(self.speed_row)
        box.addLayout(controls)
        return bar

    def _player(self):
        self.current = None
        self.player = None
        if HAVE_AUDIO:
            self.player = QtMultimedia.QMediaPlayer(self)
            self.player.setNotifyInterval(250)
            self.player.positionChanged.connect(self.on_position)
            self.player.durationChanged.connect(lambda _d: self.update_player())
            self.player.stateChanged.connect(lambda _s: self.update_player())
            self.player.mediaStatusChanged.connect(self.on_media_status)
        else:
            self.now_label.setText(_("audio is missing: install python3-pyqt5.qtmultimedia"))
        self.saver = QtCore.QTimer(self)
        self.saver.setInterval(5000)
        self.saver.timeout.connect(self.save_position)
        self.saver.start()
        self.update_player()

    # ---- the two lists ----

    def refresh_all_lists(self):
        self.refresh_feeds_list()
        self.refresh_episodes_list()

    def refresh_feeds_list(self):
        self.feeds_list.blockSignals(True)
        self.feeds_list.clear()
        def row(label, key, count, tooltip=None):
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, key)
            item.setData(QtCore.Qt.UserRole + 1, str(count) if count else "")
            if tooltip:
                item.setToolTip(tooltip)
            self.feeds_list.addItem(item)
            if key == self.view:
                item.setSelected(True)

        row(_("to hear"), VIEW_QUEUE, len(self.store.queue()))
        row(_("new"), VIEW_NEW, len(self.store.recent()))
        if self.store.feeds:
            rule = QtWidgets.QListWidgetItem("")
            rule.setData(QtCore.Qt.UserRole, FeedDelegate.RULE)
            rule.setFlags(QtCore.Qt.NoItemFlags)
            self.feeds_list.addItem(rule)
        for f in sorted(self.store.feeds, key=lambda f: (f.get("title") or "").lower()):
            row(f.get("title") or f["url"], f["id"], self.store.unplayed(f["id"]), f.get("lastError"))
        self.feeds_list.blockSignals(False)

    def current_episodes(self):
        if self.view == VIEW_NEW:
            return self.store.recent()
        if self.store.feed(self.view):
            return self.store.episodes_of(self.view)
        return self.store.queue()

    def refresh_episodes_list(self):
        keep = self.selected_id()
        self.episodes_list.clear()
        feed = self.store.feed(self.view)
        self.head_label.setText(self.busy or (feed.get("title") if feed else
                                              (_("new") if self.view == VIEW_NEW else _("to hear"))))
        episodes = self.current_episodes()
        if not episodes:
            hint = (_("no subscriptions yet. + a feed below takes the address of one.") if not self.store.feeds
                    else _("nothing on this computer yet.") if self.view == VIEW_QUEUE
                    else _("nothing here yet."))
            item = QtWidgets.QListWidgetItem(hint)
            item.setFlags(QtCore.Qt.NoItemFlags)
            self.episodes_list.addItem(item)
            return
        mixed = feed is None
        for e in episodes:
            item = QtWidgets.QListWidgetItem(e["title"])
            item.setData(QtCore.Qt.UserRole, e["id"])
            item.setData(QtCore.Qt.UserRole + 1, self.status_of(e, mixed))
            self.episodes_list.addItem(item)
            if e["id"] == keep:
                item.setSelected(True)

    def status_of(self, e, with_feed):
        """The one line under a title: the channel when the list mixes them, when it came out,
        and the single thing worth knowing right now."""
        playing = self.current and self.current["id"] == e["id"]
        position = self.player.position() if (playing and self.player) else e.get("positionMs", 0)
        duration = e.get("durationMs", 0)
        if playing and self.player and self.player.duration() > 0:
            duration = self.player.duration()
        if self.downloading == e["id"]:
            state = _("downloading %d %%", self.download_percent)
        elif e["id"] in self.download_queue:
            state = _("waiting")
        elif e.get("state") == "PLAYED":
            state = _("heard")
        elif position > 0 and duration > 0:
            state = _("%s left", spoken(duration - position))
        elif position > 0:
            state = _("begun")
        elif e.get("localPath"):
            state = _("on this computer")
        else:
            state = ""
        channel = ""
        if with_feed:
            feed = self.store.feed(e["feedId"])
            channel = (feed or {}).get("title", "")
        length = spoken(duration) if duration else ""
        return " · ".join(p for p in (channel, relative_date(e.get("published", 0)), state or length) if p)

    def selected_id(self):
        items = self.episodes_list.selectedItems()
        return items[0].data(QtCore.Qt.UserRole) if items else None

    def selected_episode(self):
        eid = self.selected_id()
        return self.store.episode(eid) if eid else None

    def choose_view(self, item):
        key = item.data(QtCore.Qt.UserRole)
        if not key or key == FeedDelegate.RULE:
            return
        self.view = key
        self.cfg["view"] = key
        save_config(self.cfg)
        self.refresh_episodes_list()

    # ---- menus ----

    def page_menu(self):
        menu = QtWidgets.QMenu(self)
        menu.addAction(_("refresh"), self.refresh_feeds)
        menu.addAction(_("+ a feed"), self.add_feed)
        menu.addSeparator()
        menu.addAction(_("import subscriptions"), self.import_opml)
        menu.addAction(_("export the subscriptions"), self.export_opml)
        menu.addAction(_("import settings"), self.import_settings)
        menu.addAction(_("export the settings"), self.export_settings)
        menu.addSeparator()
        menu.addAction(_("white on black") if not self.dark else _("black on white"), self.toggle_theme)
        menu.addAction(_("settings"), self.open_settings)
        menu.exec_(QtGui.QCursor.pos())

    def feed_menu(self, point):
        item = self.feeds_list.itemAt(point)
        fid = item.data(QtCore.Qt.UserRole) if item else None
        feed = self.store.feed(fid) if fid else None
        if not feed:
            return
        menu = QtWidgets.QMenu(self)
        menu.addAction(_("refresh"), lambda: self.refresh_feeds([feed]))
        auto = menu.addAction(_("automatic download"))
        auto.setCheckable(True)
        auto.setChecked(bool(feed.get("autoDownload")))
        auto.triggered.connect(lambda on: self.store.update_feed(fid, autoDownload=bool(on)))
        menu.addSeparator()
        menu.addAction(_("unsubscribe"), lambda: self.unsubscribe(fid))
        menu.exec_(self.feeds_list.viewport().mapToGlobal(point))

    def episode_menu(self, point):
        item = self.episodes_list.itemAt(point)
        if not item:
            return
        item.setSelected(True)
        e = self.store.episode(item.data(QtCore.Qt.UserRole))
        if not e:
            return
        menu = QtWidgets.QMenu(self)
        menu.addAction(_("play"), lambda: self.play(e))
        if self.downloading == e["id"] or e["id"] in self.download_queue:
            menu.addAction(_("stop the download"), lambda: self.stop_download(e))
        elif e.get("localPath"):
            menu.addAction(_("remove from this computer"), lambda: self.remove_file(e))
        else:
            menu.addAction(_("download"), lambda: self.queue_download(e))
        heard = e.get("state") == "PLAYED"
        menu.addAction(_("mark as unheard") if heard else _("mark as heard"),
                       lambda: self.mark_played(e, not heard))
        menu.addSeparator()
        menu.addAction(_("copy the link"), lambda: QtWidgets.QApplication.clipboard().setText(e["mediaUrl"]))
        feed = self.store.feed(e["feedId"])
        if feed and self.view != feed["id"]:
            menu.addAction(_("open the channel"), lambda: self.open_feed(feed["id"]))
        menu.exec_(self.episodes_list.viewport().mapToGlobal(point))

    def open_feed(self, fid):
        self.view = fid
        self.cfg["view"] = fid
        save_config(self.cfg)
        self.refresh_all_lists()

    # ---- subscriptions ----

    def add_feed(self):
        url, ok = QtWidgets.QInputDialog.getText(self, _("+ a feed"), _("the address of a feed"))
        if ok and url.strip():
            self.subscribe(url)

    def subscribe(self, raw):
        url = normalise(raw)
        if self.store.feed(feed_id(url)):
            self.open_feed(feed_id(url))
            return
        self.set_busy(_("reading the feed…"))

        def job(_progress):
            fid = feed_id(url)
            title, author, episodes = fetch_feed(url, fid, "RSS")
            return fid, url, title, author, episodes

        def done(result, error):
            self.set_busy("")
            if error:
                self.say(_("that feed could not be read. %s", str(error)[:80]))
                return
            fid, url_, title, author, episodes = result
            self.store.add_feed({"id": fid, "url": url_, "title": title or url_, "author": author,
                                 "kind": "RSS", "addedAt": int(datetime.now().timestamp() * 1000),
                                 "lastFetch": int(datetime.now().timestamp() * 1000),
                                 "autoDownload": False, "keepCount": 50, "lastError": ""})
            self.store.merge(fid, episodes)
            self.view = fid
            self.cfg["view"] = fid
            save_config(self.cfg)
            self.refresh_all_lists()
            self.say(_("subscribed to %s", title or url_))

        self.run(job, done)

    def unsubscribe(self, fid):
        if self.current and self.current["feedId"] == fid:
            self.stop()
        self.store.remove_feed(fid)
        if self.view == fid:
            self.view = VIEW_QUEUE
        self.refresh_all_lists()

    def refresh_feeds(self, feeds=None):
        feeds = feeds if feeds else list(self.store.feeds)
        if not feeds:
            return
        self.set_busy(_("refreshing…"))

        def job(_progress):
            out = []
            for f in feeds:
                try:
                    out.append((f["id"], fetch_feed(f["url"], f["id"], f.get("kind", "RSS")), None))
                except Exception as exc:
                    out.append((f["id"], None, str(exc)[:120]))
            return out

        def done(result, error):
            self.set_busy("")
            if error:
                self.say(str(error)[:120])
                return
            for fid, parsed, failure in result:
                if failure:
                    self.store.update_feed(fid, lastError=failure)
                    continue
                title, author, episodes = parsed
                self.store.merge(fid, episodes)
                feed = self.store.feed(fid) or {}
                self.store.update_feed(
                    fid, lastError="", lastFetch=int(datetime.now().timestamp() * 1000),
                    title=feed.get("title") if feed.get("title") not in ("", feed.get("url")) else (title or feed.get("title")),
                    author=author or feed.get("author", ""))
                if feed.get("autoDownload"):
                    for e in self.store.episodes_of(fid)[:3]:
                        if e["state"] == "NEW" and not e["localPath"]:
                            self.queue_download(e, quiet=True)
            self.refresh_all_lists()

        self.run(job, done)

    # ---- downloads, one at a time ----

    def queue_download(self, episode, quiet=False):
        if episode["id"] == self.downloading or episode["id"] in self.download_queue:
            return
        self.download_queue.append(episode["id"])
        self.refresh_episodes_list()
        self.next_download()

    def stop_download(self, episode):
        if episode["id"] in self.download_queue:
            self.download_queue.remove(episode["id"])
        if self.downloading == episode["id"]:
            self.cancel_download = True
        self.refresh_episodes_list()

    def next_download(self):
        if self.downloading or not self.download_queue:
            return
        eid = self.download_queue.pop(0)
        episode = self.store.episode(eid)
        if not episode:
            self.next_download()
            return
        self.downloading = eid
        self.download_percent = 0
        self.cancel_download = False

        def job(progress):
            return download(episode, progress, lambda: self.cancel_download)

        def done(path, error):
            self.downloading = None
            if error:
                self.say(str(error)[:120])
                print("download failed:", error, file=sys.stderr)
            elif path:
                self.store.update_episode(eid, localPath=path, bytes=os.path.getsize(path))
            self.refresh_all_lists()
            self.next_download()

        def progress(percent):
            self.download_percent = percent
            self.refresh_episodes_list()

        self.run(job, done, progress)

    def remove_file(self, episode):
        if self.current and self.current["id"] == episode["id"]:
            self.stop()
        self.store.delete_file(episode["id"])
        self.refresh_all_lists()

    def mark_played(self, episode, played):
        if played and self.current and self.current["id"] == episode["id"]:
            self.stop()
        self.store.update_episode(episode["id"], state="PLAYED" if played else "NEW", positionMs=0)
        if played and self.cfg.get("delete_when_played", True):
            self.store.delete_file(episode["id"])
        self.refresh_all_lists()

    # ---- the two files that carry everything ----

    def export_opml(self):
        path, _sel = QtWidgets.QFileDialog.getSaveFileName(self, _("export the subscriptions"),
                                                           os.path.expanduser("~/abonnements.opml"))
        if path:
            self.write_file(path, opml_export(self.store.feeds), _("subscriptions exported"))

    def import_opml(self):
        path, _sel = QtWidgets.QFileDialog.getOpenFileName(self, _("import subscriptions"), os.path.expanduser("~"))
        if not path:
            return
        try:
            with open(path, "rb") as fh:
                lines = opml_parse(fh.read())
        except Exception:
            self.say(_("that file could not be read"))
            return
        fresh = [(url, title) for url, title in lines if not self.store.feed(feed_id(url))]
        if not fresh:
            self.say(_("no subscription in that file"))
            return
        self.set_busy(_("reading the feed…"))

        def job(_progress):
            out = []
            for url, title in fresh:
                fid = feed_id(url)
                try:
                    out.append((fid, url, fetch_feed(url, fid, "RSS")))
                except Exception:
                    out.append((fid, url, None))
            return out

        def done(result, error):
            self.set_busy("")
            if error:
                self.say(str(error)[:120])
                return
            added = 0
            for fid, url, parsed in result:
                if not parsed:
                    continue
                title, author, episodes = parsed
                self.store.add_feed({"id": fid, "url": url, "title": title or url, "author": author,
                                     "kind": "RSS", "addedAt": int(datetime.now().timestamp() * 1000),
                                     "lastFetch": int(datetime.now().timestamp() * 1000),
                                     "autoDownload": False, "keepCount": 50, "lastError": ""})
                self.store.merge(fid, episodes)
                added += 1
            self.refresh_all_lists()
            self.say(_("%d feeds added", added))

        self.run(job, done)

    def export_settings(self):
        path, _sel = QtWidgets.QFileDialog.getSaveFileName(self, _("export the settings"),
                                                           os.path.expanduser("~/reglages.json"))
        if path:
            text = backup_export(settings_for_backup(self.cfg), self.store.feeds, self.store.episodes)
            self.write_file(path, text, _("settings exported"))

    def import_settings(self):
        path, _sel = QtWidgets.QFileDialog.getOpenFileName(self, _("import settings"), os.path.expanduser("~"))
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            self.say(_("that file could not be read"))
            return
        self.cfg = settings_from_backup(self.cfg, data.get("settings") or {})
        self.dark = bool(self.cfg.get("dark", True))
        save_config(self.cfg)
        states = data.get("episodes") or []
        self.apply_states(states)
        missing = [(f.get("url"), f.get("title") or f.get("url"), f)
                   for f in (data.get("feeds") or []) if f.get("url")]
        self.apply_feed_settings(missing)
        self.apply_style()
        self.refresh_all_lists()
        self.say(_("settings imported"))
        self.pending_states = states
        fresh = [(url, title) for url, title, _f in missing if not self.store.feed(feed_id(url))]
        if fresh:
            self.fetch_missing(fresh)

    def apply_feed_settings(self, rows):
        for url, _title, f in rows:
            fid = feed_id(url)
            if self.store.feed(fid):
                self.store.update_feed(fid, autoDownload=bool(f.get("autoDownload")),
                                       keepCount=int(f.get("keepCount", 50)))

    def apply_states(self, states):
        """The newer of the two sides wins, so importing an older file never undoes listening
        done since."""
        for s in states:
            e = self.store.episode(s.get("id"))
            if not e:
                continue
            if e.get("lastPlayed", 0) > s.get("lastPlayed", 0):
                continue
            self.store.update_episode(e["id"], positionMs=int(s.get("positionMs", 0)),
                                      state=s.get("state", "NEW"), lastPlayed=int(s.get("lastPlayed", 0)))

    def fetch_missing(self, fresh):
        """Subscriptions named in an imported file that are not here yet; their positions are
        applied again once their episodes have arrived."""
        self.set_busy(_("reading the feed…"))

        def job(_progress):
            out = []
            for url, title in fresh:
                fid = feed_id(url)
                try:
                    out.append((fid, url, fetch_feed(url, fid, "RSS")))
                except Exception:
                    out.append((fid, url, None))
            return out

        def done(result, error):
            self.set_busy("")
            if not error:
                for fid, url, parsed in result:
                    if not parsed:
                        continue
                    title, author, episodes = parsed
                    self.store.add_feed({"id": fid, "url": url, "title": title or url, "author": author,
                                         "kind": "RSS", "addedAt": int(datetime.now().timestamp() * 1000),
                                         "lastFetch": int(datetime.now().timestamp() * 1000),
                                         "autoDownload": False, "keepCount": 50, "lastError": ""})
                    self.store.merge(fid, episodes)
                self.apply_states(getattr(self, "pending_states", []))
            self.refresh_all_lists()

        self.run(job, done)

    def write_file(self, path, text, ok_message):
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            self.say(ok_message)
        except OSError:
            self.say(_("could not write the file"))

    # ---- playback ----

    def play_selected(self, item=None):
        e = self.store.episode(item.data(QtCore.Qt.UserRole)) if item else self.selected_episode()
        if e:
            self.play(e)

    def play(self, episode):
        if not self.player:
            self.say(_("audio is missing: install python3-pyqt5.qtmultimedia"))
            return
        if self.current and self.current["id"] == episode["id"]:
            self.toggle()
            return
        self.save_position()
        self.current = episode
        source = (QtCore.QUrl.fromLocalFile(episode["localPath"]) if episode.get("localPath")
                  else QtCore.QUrl(episode["mediaUrl"]))
        self.player.setMedia(QtMultimedia.QMediaContent(source))
        self.player.setPlaybackRate(float(self.cfg.get("speed", 1.0)))
        start = episode.get("positionMs", 0)
        if episode.get("durationMs") and start > episode["durationMs"] - 3000:
            start = 0
        if start:
            self.player.setPosition(start)
        self.player.play()
        self.store.update_episode(episode["id"], lastPlayed=int(datetime.now().timestamp() * 1000),
                                  state="STARTED" if episode.get("state") == "NEW" else episode.get("state", "NEW"))
        self.refresh_all_lists()
        self.update_player()

    def toggle(self):
        if not self.player:
            return
        if self.player.state() == QtMultimedia.QMediaPlayer.PlayingState:
            self.player.pause()
            self.save_position()
        elif self.current:
            self.player.play()
        self.update_player()

    def stop(self):
        if self.player:
            self.save_position()
            self.player.stop()
        self.current = None
        self.update_player()

    def seek_by(self, ms):
        if self.player and self.current:
            self.player.setPosition(max(0, self.player.position() + ms))

    def seek_fraction(self, fraction):
        if self.player and self.current and self.player.duration() > 0:
            self.player.setPosition(int(self.player.duration() * fraction))

    def next_speed(self):
        speeds = [0.8, 1.0, 1.25, 1.5, 1.75, 2.0]
        current = float(self.cfg.get("speed", 1.0))
        nearest = min(range(len(speeds)), key=lambda i: abs(speeds[i] - current))
        speed = speeds[(nearest + 1) % len(speeds)]
        self.cfg["speed"] = speed
        save_config(self.cfg)
        if self.player:
            self.player.setPlaybackRate(speed)
        self.update_player()

    def on_position(self, _ms):
        self.update_player()

    def on_media_status(self, status):
        if not self.player or status != QtMultimedia.QMediaPlayer.EndOfMedia or not self.current:
            return
        # An episode heard through: marked, put back to its beginning, and its file let go if
        # that is the setting. A phone or a desk that fills up with what was already heard is
        # something one stops trusting.
        eid = self.current["id"]
        self.store.update_episode(eid, state="PLAYED", positionMs=0)
        if self.cfg.get("delete_when_played", True):
            self.store.delete_file(eid)
        self.current = None
        self.refresh_all_lists()
        self.update_player()

    def save_position(self):
        if not (self.player and self.current):
            return
        if self.player.state() == QtMultimedia.QMediaPlayer.StoppedState:
            return
        position = self.player.position()
        duration = self.player.duration()
        fields = {"positionMs": position, "lastPlayed": int(datetime.now().timestamp() * 1000)}
        if duration > 0:
            fields["durationMs"] = duration
        if self.current.get("state") == "NEW" and position > 0:
            fields["state"] = "STARTED"
        self.store.update_episode(self.current["id"], **fields)

    def update_player(self):
        speeds = float(self.cfg.get("speed", 1.0))
        self.speed_row.setText(("%g" % speeds) + "×  " + _("speed"))
        if not self.current:
            self.clock_label.setText("")
            self.now_label.setText(_("audio is missing: install python3-pyqt5.qtmultimedia")
                                   if not HAVE_AUDIO else _("nothing playing"))
            self.play_row.setText("▶")
            self.line.set_fraction(0)
            return
        position = self.player.position() if self.player else 0
        duration = self.player.duration() if self.player else 0
        self.clock_label.setText(clock(position))
        feed = self.store.feed(self.current["feedId"])
        tail = " · ".join(p for p in (clock(duration) if duration else "", (feed or {}).get("title", "")) if p)
        self.now_label.setText(self.current["title"] + ("   " + tail if tail else ""))
        playing = self.player and self.player.state() == QtMultimedia.QMediaPlayer.PlayingState
        self.play_row.setText("❚❚" if playing else "▶")
        self.line.set_fraction(position / duration if duration else 0)

    # ---- the rest ----

    def run(self, job, done, progress=None):
        """One job on a thread of its own. The thread and its worker are kept in a list: a
        QThread that Python collects half way through simply stops, silently."""
        thread = QtCore.QThread(self)
        worker = Worker(job)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        if progress:
            worker.progress.connect(progress)

        def finished(result, error):
            done(result, error)
            thread.quit()

        worker.done.connect(finished)
        thread.finished.connect(lambda: self.threads.remove(pair) if pair in self.threads else None)
        pair = (thread, worker)
        self.threads.append(pair)
        thread.start()

    def set_busy(self, text):
        self.busy = text
        self.refresh_episodes_list()

    def say(self, text):
        self.statusBar().showMessage(text, 6000)

    def open_settings(self):
        dialog = SettingsDialog(self, self.cfg)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        self.cfg.update(dialog.values())
        self.dark = bool(self.cfg["dark"])
        self.font_size = int(self.cfg["font_size"])
        save_config(self.cfg)
        self.apply_style()
        self.refresh_all_lists()

    def toggle_theme(self):
        self.dark = not self.dark
        self.cfg["dark"] = self.dark
        save_config(self.cfg)
        self.apply_style()

    def apply_style(self):
        bg, fg = ("#000000", "#ffffff") if self.dark else ("#ffffff", "#000000")
        dim = "rgba(255,255,255,0.55)" if self.dark else "rgba(0,0,0,0.55)"
        rule = "rgba(255,255,255,0.25)" if self.dark else "rgba(0,0,0,0.25)"
        s = self.font_size
        family = {"serif": "serif", "mono": "monospace"}.get(self.cfg.get("font"), "sans-serif")
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background: {bg}; color: {fg}; font-family: "{family}";
                                    font-size: {s}pt; font-weight: 300; }}
            QLabel#dim {{ color: {dim}; }}
            QLabel#clock {{ font-size: {s + 12}pt; }}
            QLabel#more {{ font-size: {s + 5}pt; padding: 0 6px; }}
            QLabel#newrow {{ font-size: {s + 1}pt; padding: 14px 22px; border-top: 1px solid {rule}; }}
            QFrame#sep {{ background: {rule}; }}
            QListWidget {{ background: {bg}; border: none; outline: none; }}
            QListWidget#feeds {{ border-right: 1px solid {rule}; padding: 10px 0; }}
            QListWidget#episodes {{ padding: 4px 0; }}
            QScrollBar:vertical {{ background: {bg}; width: 6px; }}
            QScrollBar:horizontal {{ background: {bg}; height: 0; }}
            QScrollBar::handle:vertical {{ background: {rule}; min-height: 24px; }}
            QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
            QScrollBar::add-page, QScrollBar::sub-page {{ background: {bg}; }}
            QMenu {{ background: {bg}; color: {fg}; border: 1px solid {rule}; padding: 4px 0; }}
            QMenu::item {{ padding: 6px 22px; }}
            QMenu::item:selected {{ background: {fg}; color: {bg}; }}
            QMenu::separator {{ height: 1px; background: {rule}; margin: 4px 0; }}
            QDialog QLineEdit, QComboBox, QSpinBox {{ background: {bg}; color: {fg}; border: 1px solid {rule}; padding: 6px; }}
            QComboBox QAbstractItemView {{ background: {bg}; color: {fg}; selection-background-color: {fg}; selection-color: {bg}; }}
            QPushButton {{ background: {bg}; color: {fg}; border: 1px solid {fg}; padding: 6px 18px; }}
            QPushButton:default {{ background: {fg}; color: {bg}; }}
            QStatusBar {{ color: {dim}; border-top: 1px solid {rule}; }}
            QToolTip {{ background: {bg}; color: {fg}; border: 1px solid {rule}; }}
        """)
        self.delegate.fg, self.delegate.bg = QtGui.QColor(fg), QtGui.QColor(bg)
        big = QtGui.QFont(family)
        big.setPointSize(s + 1)
        big.setWeight(QtGui.QFont.Light)
        small = QtGui.QFont(family)
        small.setPointSize(max(8, s - 2))
        small.setWeight(QtGui.QFont.Light)
        self.delegate.big, self.delegate.small = big, small
        self.feed_delegate.fg, self.feed_delegate.bg = QtGui.QColor(fg), QtGui.QColor(bg)
        self.feed_delegate.font = big
        self.feeds_list.doItemsLayout()
        self.line.fg = QtGui.QColor(fg)
        self.line.rule = QtGui.QColor(fg)
        self.line.rule.setAlphaF(0.25)
        self.left.setFixedWidth(max(240, s * 20))
        self.episodes_list.doItemsLayout()
        self.episodes_list.viewport().update()
        self.line.update()

    def closeEvent(self, event):
        self.save_position()
        self.cancel_download = True
        # A download or a fetch still in flight is given a moment to notice, so the process
        # does not end on Qt's "destroyed while thread is still running".
        deadline = QtCore.QElapsedTimer()
        deadline.start()
        while self.threads and deadline.elapsed() < 2000:
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 50)
        for thread, _worker in list(self.threads):
            thread.quit()
            thread.wait(500)
        super().closeEvent(event)


def main():
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Reader's Podcasts")
    window = Main()
    window.show()
    # A feed address given on the command line, so a browser or a file manager can hand one over.
    for argument in sys.argv[1:]:
        if argument.startswith(("http://", "https://", "feed://", "podcast://", "pcast://")):
            window.subscribe(argument)
            break
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
