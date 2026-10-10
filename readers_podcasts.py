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
import unicodedata
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha1
from urllib.parse import quote, quote_plus, urljoin, urlparse

import requests
from PyQt5 import QtCore, QtGui, QtWidgets

APP = "readers-podcasts"
VERSION = "1.4.1"
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

VIEW_CHANNELS = "channels"
VIEW_EPISODES = "episodes"
VIEW_FAVOURITES = "favourites"
VIEW_DOWNLOADED = "downloaded"
VIEWS = (VIEW_CHANNELS, VIEW_EPISODES, VIEW_FAVOURITES, VIEW_DOWNLOADED)

# ------------------------------------------------------------------------------------------
# Six languages, the English text as the key — the same wording as the phone
# ------------------------------------------------------------------------------------------

STRINGS = {
 "fr": {
  "write down": "mettre par écrit",
  "text": "texte",
  "notes": "notes",
  "translate": "traduire",
  "original": "original",
  "stop": "arrêter",
  "stopped": "arrêté",
  "writing down %d %%": "mise par écrit %d %%",
  "translating %d %%": "traduction %d %%",
  "fetching the model %d %%": "récupération du modèle %d %%",
  "nothing was heard in this episode": "rien n'a été entendu dans cet épisode",
  "the library refused the login": "la bibliothèque a refusé l'identification",
  "writing down needs a Whisper program (faster-whisper, whisper.cpp or whisper): none was found": "la mise par écrit demande un programme Whisper (faster-whisper, whisper.cpp ou whisper) : aucun n'a été trouvé",
  "translating needs Ollama, which is not running or has no model": "la traduction demande Ollama, qui ne tourne pas ou n'a aucun modèle",
  "the audio is fetched first; it is written down after": "le son est d'abord récupéré ; la mise par écrit suit",
  "let it work it out": "le laisser trouver",
  "last time": "la dernière fois",
  "the language spoken": "la langue parlée",
  "translate into": "traduire en",
  "written down": "mis par écrit",
  "translated": "traduit",
  "the writing down failed. %s": "la mise par écrit a échoué. %s",
  "the translation failed. %s": "la traduction a échoué. %s",
  "the transcripts could not be sent to the library. %s": "les transcriptions n'ont pas pu être envoyées à la bibliothèque. %s",
  "writing down": "mise par écrit",
  "ordinary": "ordinaire",
  "careful": "soignée",
  "several times slower": "plusieurs fois plus lente",
  "translation model": "modèle de traduction",
  "chosen by the app": "choisi par l'application",
  "With the WebDAV address of the library of Reader's Books, every transcript is sent to a « transcriptions » folder there, a small book per episode, to be read, highlighted and commented.": "Avec l'adresse WebDAV de la bibliothèque de Reader's Books, chaque transcription est envoyée dans un dossier « transcriptions » de cette bibliothèque, un petit livre par épisode, à lire, surligner et commenter.",
  "address of the library": "adresse de la bibliothèque",
  "username": "nom d'utilisateur",
  "password": "mot de passe",
  "import credentials…": "importer les identifiants…",
  "Reader's credentials": "Identifiants Reader's",
  "not a Reader's credentials file": "ce n'est pas un fichier d'identifiants Reader's",
  "this file names no drive": "ce fichier ne nomme aucun drive",
  "credentials imported": "identifiants importés",
  "load more episodes": "charger plus d'épisodes",
  "the feed only carries the latest fifteen": "le flux ne porte que les quinze derniers",
  "looking for the older ones…": "recherche des plus anciens…",
  "nothing older here": "rien de plus ancien",
  "%d older episodes added": "%d épisodes plus anciens ajoutés",
  "the older episodes could not be loaded: %s": "les épisodes plus anciens n'ont pas pu être chargés : %s",
  "this channel has no page to read": "cette chaîne n'a pas de page à lire",
  "yt-dlp brought nothing back": "yt-dlp n'a rien rapporté",
  "the words of this video are being fetched…": "les mots de cette vidéo arrivent…",
  "add a podcast": "ajouter un podcast",
  "a name, or a feed's address": "un nom, ou l'adresse d'un flux",
  "subscribe to this address": "s'abonner à cette adresse",
  "Type a few words of its name to look it up in the public directories, or paste the address of its feed.": "Tapez quelques mots de son nom pour le chercher dans les annuaires publics, ou collez l'adresse de son flux.",
  "searching the directories…": "recherche dans les annuaires…",
  "no podcast of that name in the directories": "aucun podcast de ce nom dans les annuaires",
  "the directories do not answer — is the computer online?": "les annuaires ne répondent pas — l'ordinateur est-il connecté ?",
  "%s did not answer: these come from the other one": "%s n'a pas répondu : ces résultats viennent de l'autre",
  "found in Apple Podcasts and fyyd": "trouvés dans Apple Podcasts et fyyd",
  "already followed": "déjà suivi",
  "episodes": "épisodes",
  "favourites": "favoris",
  "downloaded": "téléchargés",
  "YouTube needs yt-dlp, which is not installed": "YouTube demande yt-dlp, qui n'est pas installé",
  "no channel was found at that address": "aucune chaîne trouvée à cette adresse",
  "the audio is fetched first; it will play by itself": "l'audio est récupéré d'abord ; la lecture suivra",
  "listen": "écouter",
  "pause": "pause",
  "stop the download": "arrêter le téléchargement",
  "remove from this computer": "retirer de cet ordinateur",
  "download": "télécharger",
  "keep as a favourite": "garder en favori",
  "remove from favourites": "retirer des favoris",
  "chapters": "chapitres",
  "opens on": "s'ouvre sur",
  "keep as a favourite": "garder en favori",
  "no favourite yet.": "aucun favori pour l'instant.",
    "search": "recherche",
  "a channel, an episode": "une chaîne, un épisode",
  "to hear": "à écouter", "new": "nouveautés", "channels": "chaînes", "+ a feed": "+ un flux",
  "the address of a feed": "l'adresse d'un flux", "subscribe": "s'abonner", "unsubscribe": "se désabonner",
  "refresh": "actualiser", "refreshing…": "actualisation…", "reading the feed…": "lecture du flux…",
  "subscribed to %s": "abonné à %s", "that feed could not be read. %s": "ce flux n'a pas pu être lu. %s",
  "no connection": "pas de connexion",
  "no subscriptions yet. + a feed below finds a podcast by its name, or takes the address of its feed.":
      "aucun abonnement. « + un flux » ci-dessous trouve un podcast par son nom, ou prend l'adresse de son flux.",
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
  "every subscription in that file is already here": "tous les abonnements de ce fichier sont déjà ici",
  "reading the feeds: %d of %d": "lecture des flux : %d sur %d",
  "%d feeds added, %d could not be read": "%d flux ajoutés, %d n'ont pas pu être lus",
  "season %d": "saison %d",
  "other episodes": "autres épisodes",
  "%d episodes": "%d épisodes",
  "%d unheard": "%d à écouter",
  "settings": "réglages", "colours": "couleurs", "white on black": "blanc sur noir",
  "black on white": "noir sur blanc", "text size": "taille du texte", "font": "police",
  "refresh on opening": "actualiser à l'ouverture", "delete once heard": "effacer une fois écouté",
  "on": "actif", "off": "inactif", "today": "aujourd'hui", "yesterday": "hier",
  "speed": "vitesse", "play": "lire", "pause": "pause",
  "audio is missing: install python3-pyqt5.qtmultimedia": "audio manquant : installez python3-pyqt5.qtmultimedia",
  "nothing playing": "rien en écoute", "cancel": "annuler", "ok": "ok", "close": "fermer",
  "podcasts, kept on this computer.": "des podcasts, gardés sur cet ordinateur.",
  "%d s": "%d s", "%d min": "%d min", "%d h %02d": "%d h %02d",
  "sans-serif": "sans empattement", "serif": "avec empattement", "mono": "chasse fixe",
  "the download failed. %s": "le téléchargement a échoué. %s", "the refresh failed. %s": "l'actualisation a échoué. %s",
  "the import failed. %s": "l'import a échoué. %s", "last refresh failed: %s": "dernière actualisation échouée : %s",
 },
 "de": {
  "write down": "niederschreiben",
  "text": "Text",
  "notes": "Notizen",
  "translate": "übersetzen",
  "original": "Original",
  "stop": "anhalten",
  "stopped": "angehalten",
  "writing down %d %%": "Niederschrift %d %%",
  "translating %d %%": "Übersetzung %d %%",
  "fetching the model %d %%": "Modell wird geholt %d %%",
  "nothing was heard in this episode": "in dieser Folge war nichts zu hören",
  "the library refused the login": "die Bibliothek hat die Anmeldung abgelehnt",
  "writing down needs a Whisper program (faster-whisper, whisper.cpp or whisper): none was found": "das Niederschreiben braucht ein Whisper-Programm (faster-whisper, whisper.cpp oder whisper): keines wurde gefunden",
  "translating needs Ollama, which is not running or has no model": "das Übersetzen braucht Ollama, das nicht läuft oder kein Modell hat",
  "the audio is fetched first; it is written down after": "der Ton wird zuerst geholt; danach wird niedergeschrieben",
  "let it work it out": "selbst herausfinden lassen",
  "last time": "letztes Mal",
  "the language spoken": "die gesprochene Sprache",
  "translate into": "übersetzen in",
  "written down": "niedergeschrieben",
  "translated": "übersetzt",
  "the writing down failed. %s": "das Niederschreiben ist fehlgeschlagen. %s",
  "the translation failed. %s": "die Übersetzung ist fehlgeschlagen. %s",
  "the transcripts could not be sent to the library. %s": "die Transkripte konnten nicht an die Bibliothek gesendet werden. %s",
  "writing down": "Niederschrift",
  "ordinary": "gewöhnlich",
  "careful": "sorgfältig",
  "several times slower": "mehrfach langsamer",
  "translation model": "Übersetzungsmodell",
  "chosen by the app": "von der App gewählt",
  "With the WebDAV address of the library of Reader's Books, every transcript is sent to a « transcriptions » folder there, a small book per episode, to be read, highlighted and commented.": "Mit der WebDAV-Adresse der Bibliothek von Reader's Books wird jedes Transkript dort in einen Ordner « transcriptions » gesendet, ein kleines Buch pro Folge, zum Lesen, Markieren und Kommentieren.",
  "address of the library": "Adresse der Bibliothek",
  "username": "Benutzername",
  "password": "Passwort",
  "import credentials…": "Zugangsdaten importieren…",
  "Reader's credentials": "Reader's-Zugangsdaten",
  "not a Reader's credentials file": "keine Reader's-Zugangsdatendatei",
  "this file names no drive": "diese Datei nennt kein Drive",
  "credentials imported": "Zugangsdaten importiert",
  "load more episodes": "mehr Folgen laden",
  "the feed only carries the latest fifteen": "der Feed enthält nur die letzten fünfzehn",
  "looking for the older ones…": "ältere werden gesucht…",
  "nothing older here": "nichts Älteres mehr",
  "%d older episodes added": "%d ältere Folgen hinzugefügt",
  "the older episodes could not be loaded: %s": "die älteren Folgen konnten nicht geladen werden: %s",
  "this channel has no page to read": "dieser Kanal hat keine Seite zum Lesen",
  "yt-dlp brought nothing back": "yt-dlp hat nichts zurückgebracht",
  "the words of this video are being fetched…": "der Text zu diesem Video wird geholt…",
  "add a podcast": "Podcast hinzufügen",
  "a name, or a feed's address": "ein Name oder die Adresse eines Feeds",
  "subscribe to this address": "diese Adresse abonnieren",
  "Type a few words of its name to look it up in the public directories, or paste the address of its feed.": "Ein paar Wörter des Namens tippen, um in den öffentlichen Verzeichnissen zu suchen, oder die Adresse des Feeds einfügen.",
  "searching the directories…": "Suche in den Verzeichnissen…",
  "no podcast of that name in the directories": "kein Podcast dieses Namens in den Verzeichnissen",
  "the directories do not answer — is the computer online?": "die Verzeichnisse antworten nicht – ist der Computer online?",
  "%s did not answer: these come from the other one": "%s hat nicht geantwortet: diese kommen vom anderen",
  "found in Apple Podcasts and fyyd": "gefunden bei Apple Podcasts und fyyd",
  "already followed": "schon abonniert",
  "episodes": "Folgen",
  "favourites": "Favoriten",
  "downloaded": "heruntergeladen",
  "YouTube needs yt-dlp, which is not installed": "für YouTube wird yt-dlp gebraucht, das nicht installiert ist",
  "no channel was found at that address": "unter dieser Adresse wurde kein Kanal gefunden",
  "the audio is fetched first; it will play by itself": "der Ton wird zuerst geholt; er spielt dann von selbst",
  "listen": "anhören",
  "pause": "Pause",
  "stop the download": "Download abbrechen",
  "remove from this computer": "von diesem Rechner entfernen",
  "download": "herunterladen",
  "keep as a favourite": "als Favorit behalten",
  "remove from favourites": "aus den Favoriten entfernen",
  "chapters": "Kapitel",
  "opens on": "öffnet mit",
  "keep as a favourite": "als Favorit behalten",
  "no favourite yet.": "noch kein Favorit.",
    "search": "Suche",
  "a channel, an episode": "ein Kanal, eine Folge",
  "to hear": "zu hören", "new": "neu", "channels": "Kanäle", "+ a feed": "+ ein Feed",
  "the address of a feed": "die Adresse eines Feeds", "subscribe": "abonnieren", "unsubscribe": "abbestellen",
  "refresh": "aktualisieren", "refreshing…": "wird aktualisiert…", "reading the feed…": "Feed wird gelesen…",
  "subscribed to %s": "%s abonniert", "that feed could not be read. %s": "dieser Feed konnte nicht gelesen werden. %s",
  "no connection": "keine Verbindung",
  "no subscriptions yet. + a feed below finds a podcast by its name, or takes the address of its feed.":
      "noch keine Abos. „+ ein Feed“ unten findet einen Podcast über seinen Namen oder nimmt die Adresse seines Feeds.",
  "nothing on this computer yet.": "noch nichts auf diesem Rechner.",
  "nothing here yet.": "noch nichts hier.",
  "download": "herunterladen", "downloading %d %%": "wird geladen %d %%", "waiting": "wartet",
  "stop the download": "Download anhalten",
  "remove from this computer": "vom Rechner nehmen", "on this computer": "auf diesem Rechner",
  "heard": "gehört", "begun": "begonnen", "%s left": "noch %s",
  "mark as heard": "als gehört markieren", "mark as unheard": "als ungehört markieren",
  "copy the link": "Link kopieren", "open the channel": "zum Kanal",
  "automatic download": "automatisch laden",
  "import subscriptions": "Abos importieren", "export the subscriptions": "Abos exportieren",
  "import settings": "Einstellungen importieren", "export the settings": "Einstellungen exportieren",
  "subscriptions exported": "Abos exportiert", "no subscription in that file": "kein Abo in dieser Datei",
  "settings exported": "Einstellungen exportiert", "settings imported": "Einstellungen importiert",
  "that file could not be read": "diese Datei konnte nicht gelesen werden", "could not write the file": "Schreiben nicht möglich",
  "%d feeds added": "%d Feeds hinzugefügt",
  "every subscription in that file is already here": "alle Abos dieser Datei sind schon hier",
  "reading the feeds: %d of %d": "Feeds werden gelesen: %d von %d",
  "%d feeds added, %d could not be read": "%d Feeds hinzugefügt, %d konnten nicht gelesen werden",
  "season %d": "Staffel %d",
  "other episodes": "weitere Folgen",
  "%d episodes": "%d Folgen",
  "%d unheard": "%d ungehört",
  "settings": "Einstellungen", "colours": "Farben", "white on black": "weiss auf schwarz",
  "black on white": "schwarz auf weiss", "text size": "Textgrösse", "font": "Schrift",
  "refresh on opening": "beim Öffnen aktualisieren", "delete once heard": "nach dem Hören löschen",
  "on": "an", "off": "aus", "today": "heute", "yesterday": "gestern",
  "speed": "Tempo", "play": "abspielen", "pause": "Pause",
  "audio is missing: install python3-pyqt5.qtmultimedia": "Audio fehlt: python3-pyqt5.qtmultimedia installieren",
  "nothing playing": "nichts läuft", "cancel": "abbrechen", "ok": "ok", "close": "schliessen",
  "podcasts, kept on this computer.": "Podcasts, auf diesem Rechner behalten.",
  "%d s": "%d s", "%d min": "%d min", "%d h %02d": "%d h %02d",
  "sans-serif": "serifenlos", "serif": "mit Serifen", "mono": "feste Breite",
  "the download failed. %s": "der Download ist fehlgeschlagen. %s", "the refresh failed. %s": "die Aktualisierung ist fehlgeschlagen. %s",
  "the import failed. %s": "der Import ist fehlgeschlagen. %s", "last refresh failed: %s": "letzte Aktualisierung fehlgeschlagen: %s",
 },
 "es": {
  "write down": "poner por escrito",
  "text": "texto",
  "notes": "notas",
  "translate": "traducir",
  "original": "original",
  "stop": "detener",
  "stopped": "detenido",
  "writing down %d %%": "transcripción %d %%",
  "translating %d %%": "traducción %d %%",
  "fetching the model %d %%": "obteniendo el modelo %d %%",
  "nothing was heard in this episode": "no se oyó nada en este episodio",
  "the library refused the login": "la biblioteca rechazó el inicio de sesión",
  "writing down needs a Whisper program (faster-whisper, whisper.cpp or whisper): none was found": "poner por escrito necesita un programa Whisper (faster-whisper, whisper.cpp o whisper): no se encontró ninguno",
  "translating needs Ollama, which is not running or has no model": "traducir necesita Ollama, que no está en marcha o no tiene ningún modelo",
  "the audio is fetched first; it is written down after": "primero se obtiene el audio; después se pone por escrito",
  "let it work it out": "dejar que lo averigüe",
  "last time": "la última vez",
  "the language spoken": "el idioma hablado",
  "translate into": "traducir al",
  "written down": "puesto por escrito",
  "translated": "traducido",
  "the writing down failed. %s": "la transcripción falló. %s",
  "the translation failed. %s": "la traducción falló. %s",
  "the transcripts could not be sent to the library. %s": "las transcripciones no se pudieron enviar a la biblioteca. %s",
  "writing down": "transcripción",
  "ordinary": "normal",
  "careful": "cuidada",
  "several times slower": "varias veces más lenta",
  "translation model": "modelo de traducción",
  "chosen by the app": "elegido por la aplicación",
  "With the WebDAV address of the library of Reader's Books, every transcript is sent to a « transcriptions » folder there, a small book per episode, to be read, highlighted and commented.": "Con la dirección WebDAV de la biblioteca de Reader's Books, cada transcripción se envía a una carpeta « transcriptions » de esa biblioteca, un pequeño libro por episodio, para leer, resaltar y comentar.",
  "address of the library": "dirección de la biblioteca",
  "username": "nombre de usuario",
  "password": "contraseña",
  "import credentials…": "importar credenciales…",
  "Reader's credentials": "Credenciales Reader's",
  "not a Reader's credentials file": "no es un archivo de credenciales Reader's",
  "this file names no drive": "este archivo no nombra ningún drive",
  "credentials imported": "credenciales importadas",
  "load more episodes": "cargar más episodios",
  "the feed only carries the latest fifteen": "el canal solo trae los últimos quince",
  "looking for the older ones…": "buscando los más antiguos…",
  "nothing older here": "no hay nada más antiguo",
  "%d older episodes added": "%d episodios más antiguos añadidos",
  "the older episodes could not be loaded: %s": "no se pudieron cargar los episodios más antiguos: %s",
  "this channel has no page to read": "este canal no tiene página que leer",
  "yt-dlp brought nothing back": "yt-dlp no devolvió nada",
  "the words of this video are being fetched…": "se está buscando el texto de este vídeo…",
  "add a podcast": "añadir un podcast",
  "a name, or a feed's address": "un nombre o la dirección de una fuente",
  "subscribe to this address": "suscribirse a esta dirección",
  "Type a few words of its name to look it up in the public directories, or paste the address of its feed.": "Escriba unas palabras del nombre para buscarlo en los directorios públicos, o pegue la dirección de su fuente.",
  "searching the directories…": "buscando en los directorios…",
  "no podcast of that name in the directories": "ningún podcast con ese nombre en los directorios",
  "the directories do not answer — is the computer online?": "los directorios no responden: ¿está conectado el ordenador?",
  "%s did not answer: these come from the other one": "%s no respondió: estos vienen del otro",
  "found in Apple Podcasts and fyyd": "encontrados en Apple Podcasts y fyyd",
  "already followed": "ya suscrito",
  "episodes": "episodios",
  "favourites": "favoritos",
  "downloaded": "descargados",
  "YouTube needs yt-dlp, which is not installed": "YouTube necesita yt-dlp, que no está instalado",
  "no channel was found at that address": "no se encontró ningún canal en esa dirección",
  "the audio is fetched first; it will play by itself": "primero se obtiene el audio; sonará solo",
  "listen": "escuchar",
  "pause": "pausa",
  "stop the download": "detener la descarga",
  "remove from this computer": "quitar de este ordenador",
  "download": "descargar",
  "keep as a favourite": "guardar como favorito",
  "remove from favourites": "quitar de favoritos",
  "chapters": "capítulos",
  "opens on": "se abre en",
  "keep as a favourite": "guardar en favoritos",
  "no favourite yet.": "ningún favorito todavía.",
    "search": "búsqueda",
  "a channel, an episode": "un canal, un episodio",
  "to hear": "por escuchar", "new": "novedades", "channels": "canales", "+ a feed": "+ una fuente",
  "the address of a feed": "la dirección de una fuente", "subscribe": "suscribirse", "unsubscribe": "darse de baja",
  "refresh": "actualizar", "refreshing…": "actualizando…", "reading the feed…": "leyendo la fuente…",
  "subscribed to %s": "suscrito a %s", "that feed could not be read. %s": "no se pudo leer esa fuente. %s",
  "no connection": "sin conexión",
  "no subscriptions yet. + a feed below finds a podcast by its name, or takes the address of its feed.":
      "ninguna suscripción. «+ una fuente» abajo encuentra un podcast por su nombre o toma la dirección de su fuente.",
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
  "every subscription in that file is already here": "todas las suscripciones de ese archivo ya están aquí",
  "reading the feeds: %d of %d": "leyendo las fuentes: %d de %d",
  "%d feeds added, %d could not be read": "%d fuentes añadidas, %d no se pudieron leer",
  "season %d": "temporada %d",
  "other episodes": "otros episodios",
  "%d episodes": "%d episodios",
  "%d unheard": "%d sin escuchar",
  "settings": "ajustes", "colours": "colores", "white on black": "blanco sobre negro",
  "black on white": "negro sobre blanco", "text size": "tamaño del texto", "font": "tipografía",
  "refresh on opening": "actualizar al abrir", "delete once heard": "borrar una vez escuchado",
  "on": "activo", "off": "inactivo", "today": "hoy", "yesterday": "ayer",
  "speed": "velocidad", "play": "reproducir", "pause": "pausa",
  "audio is missing: install python3-pyqt5.qtmultimedia": "falta el audio: instale python3-pyqt5.qtmultimedia",
  "nothing playing": "nada en escucha", "cancel": "cancelar", "ok": "ok", "close": "cerrar",
  "podcasts, kept on this computer.": "podcasts, guardados en este ordenador.",
  "%d s": "%d s", "%d min": "%d min", "%d h %02d": "%d h %02d",
  "sans-serif": "sin serifa", "serif": "con serifa", "mono": "monoespaciada",
  "the download failed. %s": "la descarga falló. %s", "the refresh failed. %s": "la actualización falló. %s",
  "the import failed. %s": "la importación falló. %s", "last refresh failed: %s": "la última actualización falló: %s",
 },
 "pt": {
  "write down": "passar a escrito",
  "text": "texto",
  "notes": "notas",
  "translate": "traduzir",
  "original": "original",
  "stop": "parar",
  "stopped": "parado",
  "writing down %d %%": "transcrição %d %%",
  "translating %d %%": "tradução %d %%",
  "fetching the model %d %%": "a obter o modelo %d %%",
  "nothing was heard in this episode": "nada se ouviu neste episódio",
  "the library refused the login": "a biblioteca recusou o início de sessão",
  "writing down needs a Whisper program (faster-whisper, whisper.cpp or whisper): none was found": "passar a escrito precisa de um programa Whisper (faster-whisper, whisper.cpp ou whisper): nenhum foi encontrado",
  "translating needs Ollama, which is not running or has no model": "traduzir precisa do Ollama, que não está a correr ou não tem nenhum modelo",
  "the audio is fetched first; it is written down after": "primeiro obtém-se o áudio; depois passa-se a escrito",
  "let it work it out": "deixar descobrir",
  "last time": "da última vez",
  "the language spoken": "a língua falada",
  "translate into": "traduzir para",
  "written down": "passado a escrito",
  "translated": "traduzido",
  "the writing down failed. %s": "a transcrição falhou. %s",
  "the translation failed. %s": "a tradução falhou. %s",
  "the transcripts could not be sent to the library. %s": "as transcrições não puderam ser enviadas para a biblioteca. %s",
  "writing down": "transcrição",
  "ordinary": "normal",
  "careful": "cuidada",
  "several times slower": "várias vezes mais lenta",
  "translation model": "modelo de tradução",
  "chosen by the app": "escolhido pela aplicação",
  "With the WebDAV address of the library of Reader's Books, every transcript is sent to a « transcriptions » folder there, a small book per episode, to be read, highlighted and commented.": "Com o endereço WebDAV da biblioteca do Reader's Books, cada transcrição é enviada para uma pasta « transcriptions » dessa biblioteca, um pequeno livro por episódio, para ler, destacar e comentar.",
  "address of the library": "endereço da biblioteca",
  "username": "nome de utilizador",
  "password": "palavra-passe",
  "import credentials…": "importar credenciais…",
  "Reader's credentials": "Credenciais Reader's",
  "not a Reader's credentials file": "não é um ficheiro de credenciais Reader's",
  "this file names no drive": "este ficheiro não nomeia nenhuma drive",
  "credentials imported": "credenciais importadas",
  "load more episodes": "carregar mais episódios",
  "the feed only carries the latest fifteen": "o feed só traz os últimos quinze",
  "looking for the older ones…": "à procura dos mais antigos…",
  "nothing older here": "nada mais antigo",
  "%d older episodes added": "%d episódios mais antigos adicionados",
  "the older episodes could not be loaded: %s": "não foi possível carregar os episódios mais antigos: %s",
  "this channel has no page to read": "este canal não tem página para ler",
  "yt-dlp brought nothing back": "o yt-dlp não trouxe nada",
  "the words of this video are being fetched…": "o texto deste vídeo está a chegar…",
  "add a podcast": "adicionar um podcast",
  "a name, or a feed's address": "um nome ou o endereço de uma fonte",
  "subscribe to this address": "subscrever este endereço",
  "Type a few words of its name to look it up in the public directories, or paste the address of its feed.": "Escreva algumas palavras do nome para o procurar nos diretórios públicos, ou cole o endereço da sua fonte.",
  "searching the directories…": "a procurar nos diretórios…",
  "no podcast of that name in the directories": "nenhum podcast com esse nome nos diretórios",
  "the directories do not answer — is the computer online?": "os diretórios não respondem — o computador está ligado à rede?",
  "%s did not answer: these come from the other one": "%s não respondeu: estes vêm do outro",
  "found in Apple Podcasts and fyyd": "encontrados no Apple Podcasts e no fyyd",
  "already followed": "já subscrito",
  "episodes": "episódios",
  "favourites": "favoritos",
  "downloaded": "transferidos",
  "YouTube needs yt-dlp, which is not installed": "o YouTube precisa do yt-dlp, que não está instalado",
  "no channel was found at that address": "nenhum canal encontrado nesse endereço",
  "the audio is fetched first; it will play by itself": "o áudio é obtido primeiro; tocará sozinho",
  "listen": "ouvir",
  "pause": "pausa",
  "stop the download": "parar a transferência",
  "remove from this computer": "retirar deste computador",
  "download": "transferir",
  "keep as a favourite": "guardar como favorito",
  "remove from favourites": "retirar dos favoritos",
  "chapters": "capítulos",
  "opens on": "abre em",
  "keep as a favourite": "guardar nos favoritos",
  "no favourite yet.": "ainda nenhum favorito.",
    "search": "procura",
  "a channel, an episode": "um canal, um episódio",
  "to hear": "por ouvir", "new": "novidades", "channels": "canais", "+ a feed": "+ uma fonte",
  "the address of a feed": "o endereço de uma fonte", "subscribe": "subscrever", "unsubscribe": "anular a subscrição",
  "refresh": "atualizar", "refreshing…": "a atualizar…", "reading the feed…": "a ler a fonte…",
  "subscribed to %s": "subscrito: %s", "that feed could not be read. %s": "não foi possível ler essa fonte. %s",
  "no connection": "sem ligação",
  "no subscriptions yet. + a feed below finds a podcast by its name, or takes the address of its feed.":
      "nenhuma subscrição. «+ uma fonte» abaixo encontra um podcast pelo nome ou aceita o endereço da sua fonte.",
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
  "every subscription in that file is already here": "todas as subscrições desse ficheiro já estão aqui",
  "reading the feeds: %d of %d": "a ler as fontes: %d de %d",
  "%d feeds added, %d could not be read": "%d fontes adicionadas, %d não puderam ser lidas",
  "season %d": "temporada %d",
  "other episodes": "outros episódios",
  "%d episodes": "%d episódios",
  "%d unheard": "%d por ouvir",
  "settings": "definições", "colours": "cores", "white on black": "branco sobre preto",
  "black on white": "preto sobre branco", "text size": "tamanho do texto", "font": "tipo de letra",
  "refresh on opening": "atualizar ao abrir", "delete once heard": "apagar depois de ouvido",
  "on": "ativa", "off": "inativa", "today": "hoje", "yesterday": "ontem",
  "speed": "velocidade", "play": "reproduzir", "pause": "pausa",
  "audio is missing: install python3-pyqt5.qtmultimedia": "falta o áudio: instale python3-pyqt5.qtmultimedia",
  "nothing playing": "nada em audição", "cancel": "cancelar", "ok": "ok", "close": "fechar",
  "podcasts, kept on this computer.": "podcasts, guardados neste computador.",
  "%d s": "%d s", "%d min": "%d min", "%d h %02d": "%d h %02d",
  "sans-serif": "sem serifa", "serif": "com serifa", "mono": "monoespaçada",
  "the download failed. %s": "a transferência falhou. %s", "the refresh failed. %s": "a atualização falhou. %s",
  "the import failed. %s": "a importação falhou. %s", "last refresh failed: %s": "a última atualização falhou: %s",
 },
 "ru": {
  "write down": "записать текстом",
  "text": "текст",
  "notes": "заметки",
  "translate": "перевести",
  "original": "оригинал",
  "stop": "остановить",
  "stopped": "остановлено",
  "writing down %d %%": "расшифровка %d %%",
  "translating %d %%": "перевод %d %%",
  "fetching the model %d %%": "загрузка модели %d %%",
  "nothing was heard in this episode": "в этом выпуске ничего не расслышано",
  "the library refused the login": "библиотека отклонила вход",
  "writing down needs a Whisper program (faster-whisper, whisper.cpp or whisper): none was found": "для расшифровки нужна программа Whisper (faster-whisper, whisper.cpp или whisper): ни одна не найдена",
  "translating needs Ollama, which is not running or has no model": "для перевода нужен Ollama, а он не запущен или в нём нет модели",
  "the audio is fetched first; it is written down after": "сначала загружается звук; затем идёт расшифровка",
  "let it work it out": "пусть определит сам",
  "last time": "в прошлый раз",
  "the language spoken": "язык речи",
  "translate into": "перевести на",
  "written down": "расшифровано",
  "translated": "переведено",
  "the writing down failed. %s": "расшифровка не удалась. %s",
  "the translation failed. %s": "перевод не удался. %s",
  "the transcripts could not be sent to the library. %s": "расшифровки не удалось отправить в библиотеку. %s",
  "writing down": "расшифровка",
  "ordinary": "обычная",
  "careful": "тщательная",
  "several times slower": "в несколько раз медленнее",
  "translation model": "модель перевода",
  "chosen by the app": "выбирает приложение",
  "With the WebDAV address of the library of Reader's Books, every transcript is sent to a « transcriptions » folder there, a small book per episode, to be read, highlighted and commented.": "С адресом WebDAV библиотеки Reader's Books каждая расшифровка отправляется туда в папку « transcriptions », маленькая книга на выпуск: читать, выделять и комментировать.",
  "address of the library": "адрес библиотеки",
  "username": "имя пользователя",
  "password": "пароль",
  "import credentials…": "импортировать учётные данные…",
  "Reader's credentials": "Учётные данные Reader's",
  "not a Reader's credentials file": "это не файл учётных данных Reader's",
  "this file names no drive": "в этом файле не указан диск",
  "credentials imported": "учётные данные импортированы",
  "load more episodes": "загрузить ещё выпуски",
  "the feed only carries the latest fifteen": "лента содержит только последние пятнадцать",
  "looking for the older ones…": "ищем более старые…",
  "nothing older here": "старее ничего нет",
  "%d older episodes added": "добавлено более старых выпусков: %d",
  "the older episodes could not be loaded: %s": "не удалось загрузить более старые выпуски: %s",
  "this channel has no page to read": "у этого канала нет страницы для чтения",
  "yt-dlp brought nothing back": "yt-dlp ничего не вернул",
  "the words of this video are being fetched…": "текст к этому видео загружается…",
  "add a podcast": "добавить подкаст",
  "a name, or a feed's address": "название или адрес ленты",
  "subscribe to this address": "подписаться по этому адресу",
  "Type a few words of its name to look it up in the public directories, or paste the address of its feed.": "Введите несколько слов названия, чтобы найти подкаст в открытых каталогах, или вставьте адрес его ленты.",
  "searching the directories…": "поиск в каталогах…",
  "no podcast of that name in the directories": "в каталогах нет подкаста с таким названием",
  "the directories do not answer — is the computer online?": "каталоги не отвечают — есть ли подключение?",
  "%s did not answer: these come from the other one": "%s не ответил: это результаты другого",
  "found in Apple Podcasts and fyyd": "найдено в Apple Podcasts и fyyd",
  "already followed": "уже в подписках",
  "episodes": "выпуски",
  "favourites": "избранное",
  "downloaded": "загруженные",
  "YouTube needs yt-dlp, which is not installed": "для YouTube нужен yt-dlp, а он не установлен",
  "no channel was found at that address": "по этому адресу канал не найден",
  "the audio is fetched first; it will play by itself": "сначала загружается звук; потом заиграет сам",
  "listen": "слушать",
  "pause": "пауза",
  "stop the download": "остановить загрузку",
  "remove from this computer": "убрать с компьютера",
  "download": "скачать",
  "keep as a favourite": "в избранное",
  "remove from favourites": "убрать из избранного",
  "chapters": "главы",
  "opens on": "открывается на",
  "keep as a favourite": "в избранное",
  "no favourite yet.": "избранного пока нет.",
    "search": "поиск",
  "a channel, an episode": "канал, выпуск",
  "to hear": "послушать", "new": "новое", "channels": "каналы", "+ a feed": "+ лента",
  "the address of a feed": "адрес ленты", "subscribe": "подписаться", "unsubscribe": "отписаться",
  "refresh": "обновить", "refreshing…": "обновление…", "reading the feed…": "чтение ленты…",
  "subscribed to %s": "подписка на %s", "that feed could not be read. %s": "эту ленту не удалось прочитать. %s",
  "no connection": "нет связи",
  "no subscriptions yet. + a feed below finds a podcast by its name, or takes the address of its feed.":
      "подписок пока нет. «+ лента» внизу находит подкаст по названию или принимает адрес его ленты.",
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
  "%d feeds added": "добавлено лент: %d",
  "every subscription in that file is already here": "все подписки из этого файла уже здесь",
  "reading the feeds: %d of %d": "чтение лент: %d из %d",
  "%d feeds added, %d could not be read": "добавлено лент: %d, не удалось прочитать: %d",
  "season %d": "сезон %d",
  "other episodes": "другие выпуски",
  "%d episodes": "выпусков: %d",
  "%d unheard": "не прослушано: %d",
  "settings": "настройки", "colours": "цвета", "white on black": "белое на чёрном",
  "black on white": "чёрное на белом", "text size": "размер текста", "font": "шрифт",
  "refresh on opening": "обновлять при открытии", "delete once heard": "удалять после прослушивания",
  "on": "вкл", "off": "выкл", "today": "сегодня", "yesterday": "вчера",
  "speed": "скорость", "play": "воспроизвести", "pause": "пауза",
  "audio is missing: install python3-pyqt5.qtmultimedia": "нет аудио: установите python3-pyqt5.qtmultimedia",
  "nothing playing": "ничего не играет", "cancel": "отмена", "ok": "ок", "close": "закрыть",
  "podcasts, kept on this computer.": "подкасты, которые остаются на этом компьютере.",
  "%d s": "%d с", "%d min": "%d мин", "%d h %02d": "%d ч %02d",
  "sans-serif": "без засечек", "serif": "с засечками", "mono": "моноширинный",
  "the download failed. %s": "загрузка не удалась. %s", "the refresh failed. %s": "обновление не удалось. %s",
  "the import failed. %s": "импорт не удался. %s", "last refresh failed: %s": "последнее обновление не удалось: %s",
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
        return _("%d s", max(0, ms) // 1000)
    minutes = (ms + 30000) // 60000
    return _("%d h %02d", minutes // 60, minutes % 60) if minutes >= 60 else _("%d min", minutes)


_CHAPTER_HEAD = re.compile(r"^[\s\-–—*•>\[(]*(\d{1,2}:)?(\d{1,2}):(\d{2})[\s\-–—:•|)\]]*(.*)$")
_CHAPTER_TAIL = re.compile(r"^(.*?)[\s\-–—:•|(\[]+(\d{1,2}:)?(\d{1,2}):(\d{2})[\s)\]]*$")
_LINK = re.compile(r"(https?://[^\s<>\"')\]]+|www\.[^\s<>\"')\]]+)", re.I)


def parse_chapters(description, duration_ms=0):
    """The chapters a description carries, as the phone reads them (Chapters.kt): a list is only
    a list with two times or more, in order, none past the end — « il en parle à 12:30 » is prose."""
    found = []
    for raw in (description or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _CHAPTER_HEAD.match(line)
        if m and m.group(4).strip():
            h, mi, sec, title = m.group(1), m.group(2), m.group(3), m.group(4)
        else:
            m = _CHAPTER_TAIL.match(line)
            if not m:
                continue
            title, h, mi, sec = m.group(1), m.group(2), m.group(3), m.group(4)
        hours = int(h.rstrip(":")) if h else 0
        minutes, seconds = int(mi), int(sec)
        if seconds > 59 or (hours and minutes > 59):
            continue
        title = title.strip().strip("-–—:•|. ")
        if title:
            found.append(((hours * 3600 + minutes * 60 + seconds) * 1000, title))
    if len(found) < 2 or any(b[0] <= a[0] for a, b in zip(found, found[1:])):
        return []
    if duration_ms and found[-1][0] >= duration_ms:
        return []
    return found


_TIME = re.compile(r"(?<![\d:.])(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?![\d:])")


def times_in(text, duration_ms=0):
    """Every time written in a text (12:34, 1:02:03) as (start, end, ms) — as the phone reads them
    (Chapters.times): a time past the end of the episode is a clock time and is left alone."""
    found = []
    for m in _TIME.finditer(text or ""):
        seconds, minutes = int(m.group(3)), int(m.group(2))
        if seconds > 59 or (m.group(1) and minutes > 59):
            continue
        ms = ((int(m.group(1) or 0) * 3600) + minutes * 60 + seconds) * 1000
        if duration_ms and ms >= duration_ms:
            continue
        found.append((m.start(), m.end(), ms))
    return found


def _times_linked(text, duration_ms):
    out, last = [], 0
    for start, end, ms in times_in(text, duration_ms):
        out.append(html.escape(text[last:start]))
        out.append('<a href="chap:%d">%s</a>' % (ms, html.escape(text[start:end])))
        last = end
    out.append(html.escape(text[last:]))
    return "".join(out)


def linkify(text, duration_ms=0, times=False):
    """Plain text as HTML, its addresses made into links; the full stop that ends a sentence is
    not part of the address that ends it. With [times], every time written in it sends the sound
    there (a chap: link, as the chapter list uses)."""
    text = text or ""
    plain = (lambda t: _times_linked(t, duration_ms)) if times else html.escape
    out, last = [], 0
    for m in _LINK.finditer(text):
        url = m.group(0).rstrip(".,;:!?…")
        out.append(plain(text[last:m.start()]))
        href = url if url.lower().startswith("http") else "https://" + url
        out.append('<a href="%s">%s</a>' % (html.escape(href, quote=True), html.escape(url)))
        last = m.start() + len(url)
    out.append(plain(text[last:]))
    return "".join(out).replace("\n", "<br>")


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
    # Qt names the days and months in the interface's language, whatever the system's LC_TIME.
    loc = QtCore.QLocale("en_GB" if LANG == "en" else LANG)
    if days < 7:
        day = loc.dayName(then.isoweekday(), QtCore.QLocale.LongFormat)
        return day if LANG == "de" else day.lower()     # a German weekday is a noun
    return loc.toString(QtCore.QDate(then.year, then.month, then.day),
                        "d MMM" if then.year == now.year else "d MMM yyyy")


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
    """Returns (title, author, [episode dicts], serial). An item without playable media is not
    an episode; a YouTube entry points at its page, which is what yt-dlp would be handed.
    `serial` is the feed saying it is meant to be heard from its first episode on."""
    root = ET.fromstring(data)
    items = [n for n in root.iter() if _local(n.tag) in ("item", "entry")]
    # Atom repeats <title> and <author> inside every entry: only what lies outside one belongs
    # to the feed itself.
    within = {id(sub) for item in items for sub in item.iter()}
    title = author = ""
    serial = False
    for node in root.iter():
        if id(node) in within:
            continue
        tag = _local(node.tag)
        if tag == "title" and not title:
            title = (node.text or "").strip()
        elif tag in ("managingEditor", "name") and not author:
            author = (node.text or "").strip()
        elif tag == "type" and (node.text or "").strip().lower() == "serial":
            serial = True
    episodes = [e for e in (_build(fid, kind, item) for item in items) if e]
    return title, author, _unique(episodes), serial


def _number(raw):
    """A season or an episode number as feeds write it: `3`, ` 03 `, sometimes `3.0`."""
    try:
        return max(0, int(float((raw or "").strip())))
    except ValueError:
        return 0


def _unique(episodes):
    """Feeds do repeat a guid — two different talks under one id, in several of the Dharma Seed
    series. On the phone two rows with one id are a list that cannot be drawn at all; here they
    would simply be the same episode twice. The first one listed wins."""
    seen, out = set(), []
    for e in episodes:
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        out.append(e)
    return out


def _build(fid, kind, item):
    title = guid = media = mime = link = description = ""
    published = duration = 0
    size = 0
    season = number = 0
    season_name = ""
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
            # A YouTube entry's <media:content> is the Flash embed of fifteen years ago; its
            # page is what matters, and it comes from <link rel="alternate">.
            if "flash" not in (node.get("type") or "").lower():
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
        elif tag == "season" and not season:
            # <itunes:season> carries a number; <podcast:season> may give it a name as well.
            season = _number(text)
            season_name = (node.get("name") or "").strip()
        elif tag == "episode" and not number:
            number = _number(text)
        elif tag in ("description", "summary") and not description:
            description = strip_html(text)
    if kind == "YOUTUBE" and link:
        media = link
    elif not media and link and kind == "YOUTUBE":
        media = link
    if not media or not title:
        return None
    return {
        "id": episode_id(fid, guid or media or (title + str(published))),
        "title": title, "published": published or int(datetime.now().timestamp() * 1000),
        "mediaUrl": media, "mime": mime or "audio/*", "bytes": size, "durationMs": duration,
        "localPath": "", "positionMs": 0, "state": "NEW", "lastPlayed": 0, "starred": False,
        "description": description[:10000],
        "season": season, "seasonName": season_name, "number": number,
    }


# ---- seasons: the phone's Seasons.kt, rule for rule ----

def in_order(episodes, serial):
    """The episodes of one channel in the order it means them to be heard: a serial from its
    first episode on, anything else the latest first."""
    if serial:
        return sorted(episodes, key=lambda e: (e.get("number", 0) <= 0, e.get("number", 0), e["published"]))
    return sorted(episodes, key=lambda e: e["published"], reverse=True)


def shelves(episodes, serial):
    """The seasons of one channel, as [(season, name, [episodes])] — or [] when the feed numbers
    no season, or only one, in which case headings would say nothing.

    A serial is read from season 1 down; a show that merely numbers its years has the current
    season at the top. What carries no season (a trailer, an extra) comes last, as season 0."""
    groups = {}
    for e in episodes:
        groups.setdefault(e.get("season", 0), []).append(e)
    if len([s for s in groups if s > 0]) < 1 or len(groups) < 2:
        return []
    numbered = sorted((s for s in groups if s > 0), reverse=not serial)
    out = []
    for s in numbered + ([0] if 0 in groups else []):
        rows = in_order(groups[s], serial)
        name = next((e.get("seasonName") for e in rows if e.get("seasonName")), "")
        out.append((s, name, rows))
    return out


def season_label(season, name):
    if season <= 0:
        return _("other episodes")
    return _("season %d", season) + (" · " + name if name else "")


def open_season(found, episodes):
    """The season to show open when nothing was chosen: the one last listened to, or the first
    on the page."""
    heard = [e for e in episodes if e.get("lastPlayed", 0) > 0]
    if heard:
        return max(heard, key=lambda e: e["lastPlayed"]).get("season", 0)
    return found[0][0] if found else 0


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
    # What XML does not allow at all cannot be escaped, only left out.
    s = _NOT_XML.sub("", s)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))


_OUTLINE = re.compile(r"<outline\b([^>]*)>", re.I | re.S)
_ATTRIBUTE = re.compile(r"""([\w:.-]+)\s*=\s*("([^"]*)"|'([^']*)')""", re.S)
_NOT_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def _outlines(data):
    """Every <outline> of an OPML file as a dict of its attributes, names in lower case.

    Read as XML when the file is XML. A good many are not quite: a control character copied
    from a feed's title, an unescaped & in an address, a few bytes left over after </opml> by
    a program that wrote over a longer file. A strict reader refuses the whole file for any of
    these, so what it refuses is read tag by tag instead — the subscriptions are all there."""
    if isinstance(data, bytes):
        text = data.decode("utf-8-sig", "replace")
    else:
        text = data.lstrip("\ufeff")
    text = _NOT_XML.sub("", text)
    try:
        root = ET.fromstring(text.encode("utf-8"))
        return [{k.lower(): v for k, v in node.attrib.items()}
                for node in root.iter() if _local(node.tag).lower() == "outline"]
    except ET.ParseError:
        return [{m.group(1).lower(): html.unescape(m.group(3) if m.group(3) is not None else m.group(4))
                 for m in _ATTRIBUTE.finditer(tag.group(1))}
                for tag in _OUTLINE.finditer(text)]


def opml_parse(data):
    lines = []
    seen = set()
    for node in _outlines(data):
        url = (node.get("xmlurl") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        lines.append((url, (node.get("title") or node.get("text") or url).strip()))
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
                      "lastPlayed": e.get("lastPlayed", 0), "starred": bool(e.get("starred"))}
                     for e in episodes
                     if e.get("state", "NEW") != "NEW" or e.get("positionMs", 0) > 0 or e.get("starred")],
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

    def recent(self):
        """« Épisodes » — everything there is, the latest first, across all the channels."""
        return sorted(self.episodes, key=lambda e: e["published"], reverse=True)

    def favourites(self):
        """« Favoris » — the episodes given a star, the latest first."""
        return sorted([e for e in self.episodes if e.get("starred")],
                      key=lambda e: e["published"], reverse=True)

    def downloaded(self):
        """« Téléchargés » — what is on this machine, the latest first: what takes up room, and
        what can be heard with nothing in hand."""
        return sorted([e for e in self.episodes
                       if e.get("localPath") and os.path.exists(e["localPath"])],
                      key=lambda e: e["published"], reverse=True)

    def channels(self):
        """« Chaînes » — the one that published last at the top: alphabetical order says
        nothing, this order makes the first screen the news."""
        latest = {}
        for e in self.episodes:
            latest[e["feedId"]] = max(latest.get(e["feedId"], 0), e["published"])
        return sorted(self.feeds, key=lambda f: (-latest.get(f["id"], 0), (f.get("title") or "").lower()))

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
                transcript_forget(e["id"])
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
            # A serial is a catalogue and not the news: keeping its latest fifty would throw
            # away the very episodes one is meant to begin with.
            if (self.feed(fid) or {}).get("serial"):
                keep = max(keep, len(fresh))
            mine = {e["id"]: e for e in self.episodes if e["feedId"] == fid}
            merged = []
            for new in fresh:
                new = dict(new, feedId=fid)
                old = mine.get(new["id"])
                if old:
                    new.update({k: old[k] for k in ("localPath", "positionMs", "state", "lastPlayed", "starred")})
                    new.update({k: old[k] for k in ("transcript", "transcriptLanguage", "translation", "sent") if k in old})
                    if not new["durationMs"]:
                        new["durationMs"] = old["durationMs"]
                merged.append(new)
            fresh_ids = {e["id"] for e in merged}
            # A feed that lists only its last ten items must not delete what one is listening to.
            orphans = [e for e in mine.values()
                       if e["id"] not in fresh_ids and (e["localPath"] or e["state"] == "STARTED" or e.get("starred") or e.get("transcript"))]
            allofthem = sorted(merged + orphans, key=lambda e: e["published"], reverse=True)
            trimmed = _unique([e for i, e in enumerate(allofthem)
                               if i < keep or e["localPath"] or e["state"] == "STARTED" or e.get("starred") or e.get("transcript")])
            self.episodes = [e for e in self.episodes if e["feedId"] != fid] + trimmed
            self._save_episodes(fid)

    def add_older(self, fid, older):
        """Videos reached past the feed's fifteen: kept, and the channel's keepCount raised so
        that the next refresh does not trim them away again (the phone's addOlder)."""
        with self.lock:
            known = [e for e in self.episodes if e["feedId"] == fid]
            ids = {e["id"] for e in known}
            fresh = _unique([dict(e, feedId=fid) for e in older if e["id"] not in ids])
            if not fresh:
                return 0
            self.episodes += fresh
            feed = self.feed(fid)
            if feed:
                feed["keepCount"] = max(feed.get("keepCount", 50), len(known) + len(fresh) + 10)
                self._save_feeds()
            self._save_episodes(fid)
            return len(fresh)

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
            e.setdefault("starred", False)
            # A file deleted from outside must not leave a row claiming to be here.
            if e["localPath"] and not os.path.exists(e["localPath"]):
                e["localPath"] = ""
            out.append(e)
        # Written by a version that let a repeated guid through.
        return _unique(out)

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
# What was said, in writing. The phone carries its own Whisper and its own translator; a
# computer already has better ones, or can be given them. So this app uses what it finds — a
# Whisper program for the writing down, Ollama for the translation — the way it uses yt-dlp, and
# says what is missing when nothing is there. The transcripts are kept as on the phone: lines
# with their times, so that the reading follows the sound.
# ------------------------------------------------------------------------------------------

TRANSCRIPTS_DIR = os.path.join(DATA_DIR, "transcripts")
MODELS_DIR = os.path.join(DATA_DIR, "models")
SPEECH_LANGUAGES = ("fr", "en", "de", "es", "it", "pt", "ru", "nl")
TRANSLATE_LANGUAGES = ("fr", "en", "de", "es", "pt", "ru")
LANGUAGE_NAMES = {"fr": "français", "en": "English", "de": "Deutsch", "es": "español", "it": "italiano",
                  "pt": "português", "ru": "русский", "nl": "Nederlands"}
# Two qualities, the phone's: quick and decent, or clearly better and several times slower.
QUALITIES = {"normal": {"faster": "small", "openai": "small", "cpp": "ggml-small-q5_1.bin"},
             "high": {"faster": "large-v3-turbo", "openai": "turbo", "cpp": "ggml-large-v3-turbo-q5_0.bin"}}
WHISPER_CPP_MODELS = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/"


def transcript_path(eid, language=None):
    return os.path.join(TRANSCRIPTS_DIR, eid + (".%s" % language if language else "") + ".json")


def transcript_save(eid, language, lines, translation=False):
    os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
    with open(transcript_path(eid, language if translation else None), "w", encoding="utf-8") as fh:
        json.dump({"language": language, "lines": [{"a": int(a), "b": int(b), "t": t} for a, b, t in lines]}, fh, ensure_ascii=False)


def transcript_load(eid, language=None):
    """(language, [(start ms, end ms, text)]) or None."""
    try:
        with open(transcript_path(eid, language), encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("language", ""), [(int(o.get("a", 0)), int(o.get("b", 0)), o.get("t", "")) for o in data.get("lines", [])]
    except Exception:
        return None


def transcript_forget(eid):
    if os.path.isdir(TRANSCRIPTS_DIR):
        for name in os.listdir(TRANSCRIPTS_DIR):
            if name == eid + ".json" or name.startswith(eid + "."):
                try:
                    os.remove(os.path.join(TRANSCRIPTS_DIR, name))
                except OSError:
                    pass


def transcript_paragraphs(lines):
    """The lines gathered into paragraphs, a new one on a pause of over a second — the phone's
    rule. Each paragraph is the list of its lines."""
    out, last_end = [], -1
    for a, b, t in lines:
        if not t.strip():
            continue
        if not out or (last_end >= 0 and a - last_end > 1200):
            out.append([])
        out[-1].append((a, b, t.strip()))
        last_end = b
    return out


def transcript_text(lines):
    """What leaves the app: the paragraphs, a blank line between them."""
    return "\n\n".join(" ".join(t for _a, _b, t in p) for p in transcript_paragraphs(lines))


def _python_with(module):
    """A Python that has a module: this one, or one of the environments people keep such
    things in (conda, pipx). Found by looking for the module's folder, not by starting Pythons."""
    import glob
    import importlib.util
    try:
        if importlib.util.find_spec(module):
            return sys.executable
    except Exception:
        pass
    home = os.path.expanduser("~")
    for root in ("miniconda3/envs/*", "anaconda3/envs/*", "miniforge3/envs/*", "mambaforge/envs/*", ".conda/envs/*",
                 ".local/share/pipx/venvs/*", ".local/pipx/venvs/*", ".virtualenvs/*"):
        for env in sorted(glob.glob(os.path.join(home, root))):
            if glob.glob(os.path.join(env, "lib", "python*", "site-packages", module)) or \
                    os.path.isdir(os.path.join(env, "Lib", "site-packages", module)):
                for exe in ("bin/python", "bin/python3", "python.exe", "Scripts/python.exe"):
                    if os.path.exists(os.path.join(env, exe)):
                        return os.path.join(env, exe)
    return None


def find_whisper(cfg=None):
    """The program that writes speech down, as {"kind", "command"}: faster-whisper (a Python
    that has it), else whisper.cpp, else OpenAI's whisper. None when there is none."""
    import shutil
    given = (cfg or {}).get("whisper_python", "")
    if given and os.path.exists(given):
        return {"kind": "faster", "command": given}
    python = _python_with("faster_whisper")
    if python:
        return {"kind": "faster", "command": python}
    ffmpeg = shutil.which("ffmpeg")
    for name in ("whisper-cli", "whisper-cpp", "whisper.cpp"):
        if shutil.which(name) and ffmpeg:
            return {"kind": "cpp", "command": shutil.which(name)}
    if shutil.which("whisper"):
        return {"kind": "openai", "command": shutil.which("whisper")}
    return None


# Run by the Python that has faster-whisper: one JSON object per line — the length of the
# sound, each line as it is heard, the language at the end. The graphics card when there is
# one, the processor otherwise.
_FASTER_SCRIPT = r"""
import json, sys
from faster_whisper import WhisperModel
audio, name, language = sys.argv[1], sys.argv[2], sys.argv[3] or None
def run(device, kind):
    model = WhisperModel(name, device=device, compute_type=kind)
    segments, info = model.transcribe(audio, language=language, vad_filter=True)
    print(json.dumps({"d": info.duration}), flush=True)
    for s in segments:
        print(json.dumps({"a": s.start, "b": s.end, "t": s.text}), flush=True)
    print(json.dumps({"lang": info.language}), flush=True)
try:
    run("cuda", "float16")
except Exception as first:
    print(json.dumps({"again": str(first)[:200]}), flush=True)
    run("cpu", "int8")
"""


def parse_faster(rows):
    """What the script above printed, read back: (language, lines). `rows` are its lines; the
    ones heard before a second start (the card refused) are dropped."""
    language, lines = "", []
    for row in rows:
        try:
            o = json.loads(row)
        except ValueError:
            continue
        if not isinstance(o, dict):
            continue
        if "again" in o:
            lines = []
        elif "t" in o and str(o["t"]).strip():
            lines.append((int(float(o["a"]) * 1000), int(float(o["b"]) * 1000), str(o["t"]).strip()))
        elif "lang" in o:
            language = o["lang"] or ""
    return language, lines


def parse_whisper_cpp(data):
    """whisper.cpp's -oj file: (language, lines)."""
    lines = []
    for s in data.get("transcription") or []:
        text = (s.get("text") or "").strip()
        if text:
            lines.append((int(s["offsets"]["from"]), int(s["offsets"]["to"]), text))
    return (data.get("result") or {}).get("language", ""), lines


def parse_openai(data):
    """OpenAI whisper's --output_format json file: (language, lines)."""
    lines = [(int(float(s["start"]) * 1000), int(float(s["end"]) * 1000), s["text"].strip())
             for s in data.get("segments") or [] if (s.get("text") or "").strip()]
    return data.get("language", ""), lines


_STAMP = re.compile(r"\[(?:(\d+):)?(\d+):(\d+)[.,](\d+)\s*-->\s*(?:(\d+):)?(\d+):(\d+)[.,](\d+)\]")


def stamp_end_ms(text):
    """The end of a "[00:01.000 --> 00:05.500]" printed while a program works, for the progress."""
    m = _STAMP.search(text)
    if not m:
        return None
    h, mi, s, frac = m.group(5), m.group(6), m.group(7), m.group(8)
    return ((int(h or 0) * 60 + int(mi)) * 60 + int(s)) * 1000 + int(frac[:3].ljust(3, "0"))


def _fetch_model(name, on_progress, cancelled):
    """A whisper.cpp model, fetched once into the app's folder."""
    path = os.path.join(MODELS_DIR, name)
    if os.path.exists(path):
        return path
    os.makedirs(MODELS_DIR, exist_ok=True)
    with requests.get(WHISPER_CPP_MODELS + name, stream=True, timeout=(30, 60), headers={"User-Agent": AGENT}) as r:
        r.raise_for_status()
        total, got = int(r.headers.get("Content-Length") or 0), 0
        with open(path + ".part", "wb") as fh:
            for chunk in r.iter_content(1024 * 1024):
                if cancelled():
                    raise Told(_("stopped"))
                fh.write(chunk)
                got += len(chunk)
                if total:
                    on_progress(-int(got * 100 / total) - 1)        # below zero: the model, not the words
    os.replace(path + ".part", path)
    return path


def transcribe(engine, audio, quality, language, duration_ms, on_progress, cancelled):
    """Speech written down by the program found: (language, [(start, end, text)]). `language`
    is a two-letter code, or "" to let the program work it out. Blocking; `cancelled()` is
    asked along the way."""
    import shutil
    import subprocess
    import tempfile
    kind, command = engine["kind"], engine["command"]
    model = QUALITIES.get(quality, QUALITIES["normal"])[kind]
    work = tempfile.mkdtemp(prefix="readers-podcasts-")
    seen = {"length": duration_ms or 0}

    def progress(end_ms):
        if end_ms and seen["length"] > 0:
            on_progress(max(0, min(99, int(end_ms * 100 / seen["length"]))))

    def run(args, on_line):
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        tail = []
        try:
            for line in proc.stdout:
                if cancelled():
                    proc.terminate()
                    raise Told(_("stopped"))
                tail = (tail + [line.rstrip()])[-6:]
                on_line(line)
            if proc.wait() != 0:
                raise RuntimeError(" ".join(t for t in tail if t)[-300:] or "exit %d" % proc.returncode)
        finally:
            if proc.poll() is None:
                proc.kill()

    try:
        if kind == "faster":
            rows = []

            def heard(line):
                rows.append(line)
                try:
                    o = json.loads(line)
                except ValueError:
                    return
                if isinstance(o, dict) and "d" in o:
                    seen["length"] = int(float(o["d"]) * 1000)
                elif isinstance(o, dict) and "b" in o:
                    progress(int(float(o["b"]) * 1000))

            run([command, "-c", _FASTER_SCRIPT, audio, model, language or ""], heard)
            found, lines = parse_faster(rows)
        elif kind == "cpp":
            weights = _fetch_model(model, on_progress, cancelled)
            wav = os.path.join(work, "sound.wav")
            run([shutil.which("ffmpeg"), "-y", "-loglevel", "error", "-i", audio, "-ar", "16000", "-ac", "1", wav], lambda _l: None)
            run([command, "-m", weights, "-f", wav, "-l", language or "auto", "-oj", "-of", os.path.join(work, "out")],
                lambda line: progress(stamp_end_ms(line)))
            with open(os.path.join(work, "out.json"), encoding="utf-8") as fh:
                found, lines = parse_whisper_cpp(json.load(fh))
        else:
            args = [command, audio, "--model", model, "--output_format", "json", "--output_dir", work, "--verbose", "True"]
            if language:
                args += ["--language", language]
            run(args, lambda line: progress(stamp_end_ms(line)))
            name = os.path.splitext(os.path.basename(audio))[0] + ".json"
            with open(os.path.join(work, name), encoding="utf-8") as fh:
                found, lines = parse_openai(json.load(fh))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if not lines:
        raise Told(_("nothing was heard in this episode"))
    return (language or found or "")[:2], lines


# ---- translation: Ollama, in passages that stay tied to the sound ----

OLLAMA = "http://127.0.0.1:11434"
BLOCK_CHARS = 700
_PRIMERS = ["TRADUCTION EN FRANÇAIS :", "TRADUCTION EN FRANÇAIS:", "TRANSLATION INTO ENGLISH:", "ÜBERSETZUNG AUF DEUTSCH:", "TRADUCCIÓN AL ESPAÑOL:", "TRADUÇÃO PARA PORTUGUÊS:", "ПЕРЕВОД НА РУССКИЙ:"]
# The phone's own words (speech/translate/Translator.kt), so that both ask the same thing.
_ASK = {
    "en": "Translate the passage below into English. Give the English translation only: no comment, no note, no source text.\n\nPASSAGE:\n%s\n\nTRANSLATION INTO ENGLISH:",
    "fr": "Traduis en français le passage ci-dessous. Rends uniquement la traduction française : pas de commentaire, pas de note, pas le texte d'origine.\n\nPASSAGE :\n%s\n\nTRADUCTION EN FRANÇAIS :",
    "de": "Übersetze den folgenden Abschnitt auf Deutsch. Gib nur die deutsche Übersetzung: kein Kommentar, keine Anmerkung, nicht den Ausgangstext.\n\nABSCHNITT:\n%s\n\nÜBERSETZUNG AUF DEUTSCH:",
    "es": "Traduce al español el pasaje siguiente. Da solo la traducción española: sin comentario, sin nota, sin el texto de origen.\n\nPASAJE:\n%s\n\nTRADUCCIÓN AL ESPAÑOL:",
    "pt": "Traduz para português o trecho abaixo. Dá apenas a tradução portuguesa: sem comentário, sem nota, sem o texto de origem.\n\nTRECHO:\n%s\n\nTRADUÇÃO PARA PORTUGUÊS:",
    "ru": "Переведи следующий отрывок на русский язык. Дай только русский перевод: без комментариев, без примечаний, без исходного текста.\n\nОТРЫВОК:\n%s\n\nПЕРЕВОД НА РУССКИЙ:",
}
# The second attempt, for a passage the first one fumbled: the same, said harder.
_STRICT = {
    "en": "You are translating into English. Write the English of the passage below, sentence for sentence, and nothing else — no preamble, no explanation, not one word of the original.\n\nPASSAGE:\n%s\n\nTRANSLATION INTO ENGLISH:",
    "fr": "Tu traduis en français. Écris le français du passage ci-dessous, phrase après phrase, et rien d'autre — pas de préambule, pas d'explication, pas un mot de l'original.\n\nPASSAGE :\n%s\n\nTRADUCTION EN FRANÇAIS :",
    "de": "Du übersetzt auf Deutsch. Schreibe das Deutsche des folgenden Abschnitts, Satz für Satz, und sonst nichts — keine Vorrede, keine Erklärung, kein Wort des Originals.\n\nABSCHNITT:\n%s\n\nÜBERSETZUNG AUF DEUTSCH:",
    "es": "Estás traduciendo al español. Escribe el español del pasaje siguiente, frase por frase, y nada más: sin preámbulo, sin explicación, ni una palabra del original.\n\nPASAJE:\n%s\n\nTRADUCCIÓN AL ESPAÑOL:",
    "pt": "Estás a traduzir para português. Escreve o português do trecho abaixo, frase a frase, e nada mais: sem preâmbulo, sem explicação, nem uma palavra do original.\n\nTRECHO:\n%s\n\nTRADUÇÃO PARA PORTUGUÊS:",
    "ru": "Ты переводишь на русский язык. Напиши русский текст отрывка ниже, предложение за предложением, и больше ничего — без предисловий, без объяснений, ни слова из оригинала.\n\nОТРЫВОК:\n%s\n\nПЕРЕВОД НА РУССКИЙ:",
}


def ollama_models():
    """The models Ollama has, as [(name, size)] — [] when it is not running or not installed."""
    try:
        r = requests.get(OLLAMA + "/api/tags", timeout=2)
        r.raise_for_status()
        return [(m["name"], int(m.get("size") or 0)) for m in r.json().get("models") or []
                if "embed" not in m["name"] and not m["name"].startswith("bge")]
    except Exception:
        return []


def pick_model(models, wanted=""):
    """The model that translates: the one chosen if it is still there, else the phone's own
    family (Gemma 3), else whatever is there."""
    names = [n for n, _s in models]
    if wanted in names:
        return wanted
    for prefix in ("gemma3:4b", "gemma3", "gemma", "mistral-small", "qwen"):
        found = [n for n in names if n.startswith(prefix)]
        if found:
            return found[0]
    return names[0] if names else ""


def group_blocks(lines):
    """Consecutive lines gathered into passages of about 700 characters, each keeping the time
    it begins and ends at: translated line by line a sentence loses its neighbours, and a
    translation that drifts against the sound is worse than none."""
    out, start, end, text = [], -1, 0, ""
    for a, b, t in lines:
        piece = t.strip()
        if not piece:
            continue
        if start < 0:
            start = a
        text = (text + " " + piece) if text else piece
        end = b
        if len(text) >= BLOCK_CHARS:
            out.append((start, end, text))
            start, text = -1, ""
    if text:
        out.append((max(0, start), end, text))
    return out


def clean_answer(answer):
    """Models like to announce themselves, and some think aloud first."""
    s = re.sub(r"(?s)<think>.*?</think>", "", answer or "").strip()
    for p in _PRIMERS:
        if s.lower().startswith(p.lower()):
            s = s[len(p):].strip()
    if len(s) > 1 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1]
    return s.strip()


def acceptable(source, answer):
    """A translation, as far as its shape tells: not empty, not the passage handed back, not a
    length wildly out of proportion."""
    if not answer or answer.lower() == source.strip().lower():
        return False
    return 0.4 <= len(answer) / max(1, len(source)) <= 2.5


def translate(lines, target, model, on_progress, cancelled):
    """The lines translated passage by passage: [(start, end, text)]. A passage the model
    fumbles twice is kept as it was said. Blocking."""
    blocks = group_blocks(lines)
    out = []

    def once(text, table):
        r = requests.post(OLLAMA + "/api/generate", timeout=(10, 600), json={
            "model": model, "prompt": table.get(target, table["en"]) % text, "stream": False,
            "options": {"temperature": 0.2, "num_predict": 1200}})
        r.raise_for_status()
        answer = clean_answer(r.json().get("response", ""))
        return answer if acceptable(text, answer) else None

    try:
        for i, (a, b, text) in enumerate(blocks):
            if cancelled():
                raise Told(_("stopped"))
            on_progress(int(i * 100 / len(blocks)))
            out.append((a, b, once(text, _ASK) or once(text, _STRICT) or text))
    finally:
        try:        # the model leaves the memory it took: the next writing down may need the card
            requests.post(OLLAMA + "/api/generate", json={"model": model, "keep_alive": 0}, timeout=10)
        except Exception:
            pass
    return out


# ---- the transcripts, sent to the library of Reader's Books (the phone's Shelf.kt) ----

SHELF_FOLDER = "transcriptions"


def shelf_account(text):
    """The library of Reader's Books as a Reader's credentials file names it: (address, username,
    password). None when the text is not such a file; a blank address when it names no drive."""
    try:
        root = json.loads(text)
    except ValueError:
        return None
    if not isinstance(root, dict) or root.get("format") != "readers-credentials":
        return None

    def word(section, key):
        return section.get(key) if isinstance(section.get(key), str) else ""

    for name, key in (("readers-books", "url"), ("magazine-reader", "url"), ("readers-scanner", "server"),
                      ("readers-notes", "server"), ("readers-recorder", "server")):
        s = root.get(name)
        if isinstance(s, dict) and word(s, key).strip():
            return word(s, key).strip(), word(s, "username"), word(s, "password")
    return "", "", ""


def shelf_configured(cfg):
    return bool(cfg.get("shelf_url", "").strip() and cfg.get("shelf_username", "").strip() and cfg.get("shelf_password"))


def shelf_wanted(e):
    """What of an episode should be on the drive: "" nothing, "t" its transcript, "t+fr" its
    translation into French as well."""
    if not e.get("transcript"):
        return ""
    return "t+" + e["translation"] if e.get("translation") else "t"


def book_file_name(title):
    """A name the drive, the phone and a desktop all accept (Epub.fileName on the phone)."""
    base = re.sub(r'[\\/:*?"<>|\x00-\x1f\x7f]', " ", title)
    base = re.sub(r"\s+", " ", base).strip().rstrip(".")[:120].strip()
    return base or "untitled"


def epub_build(book_id, title, author, language, source, text):
    """What was said in an episode as a small book, the form Reader's Books reads: one chapter,
    the episode as title, the channel as author, a first line in small print saying where it
    comes from. The same book as the phone makes."""
    import io
    import zipfile

    def esc(s):
        s = "".join(c for c in s if c >= " " or c in "\n\t")
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    body = "<h1>%s</h1>\n" % esc(title)
    if source.strip():
        body += '<p class="author">%s</p>\n' % esc(source)
    body += "".join("<p>%s</p>\n" % esc(p).replace("\n", "<br/>") for p in paragraphs)
    lang = esc(language or "und")
    page = ('<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="%s" lang="%s">\n'
            '<head><meta charset="utf-8"/><title>%s</title></head>\n<body>\n%s</body>\n</html>\n') % (lang, lang, esc(title), body)
    nav = ('<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">\n'
           '<head><meta charset="utf-8"/><title>%s</title></head>\n<body><nav epub:type="toc"><ol><li><a href="text.xhtml">%s</a></li></ol></nav></body>\n</html>\n') % (esc(title), esc(title))
    opf = ('<?xml version="1.0" encoding="utf-8"?>\n<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">\n'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n<dc:identifier id="id">readers-podcasts:%s</dc:identifier>\n'
           '<dc:title>%s</dc:title>\n<dc:creator>%s</dc:creator>\n<dc:language>%s</dc:language>\n</metadata>\n<manifest>\n'
           '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>\n'
           '<item id="text" href="text.xhtml" media-type="application/xhtml+xml"/>\n</manifest>\n'
           '<spine><itemref idref="text"/></spine>\n</package>\n') % (esc(book_id), esc(title), esc(author), lang)
    container = ('<?xml version="1.0"?>\n<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
                 '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>\n</container>\n')
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        def put(name, data, method):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = method
            z.writestr(info, data)
        put("mimetype", "application/epub+zip", zipfile.ZIP_STORED)     # first, and stored as it is
        for name, data in (("META-INF/container.xml", container), ("OEBPS/content.opf", opf),
                           ("OEBPS/nav.xhtml", nav), ("OEBPS/text.xhtml", page)):
            put(name, data.encode("utf-8"), zipfile.ZIP_DEFLATED)
    return out.getvalue()


def shelf_send(cfg, episode, channel):
    """One episode's transcript, then its translation, put in the library — unless a book of
    that name is there already (the phone's, perhaps): a book once there is never written
    again, since a highlight made in Reader's Books is a place in that very text. Returns what
    is there now ("t", "t+fr"). Blocking."""
    session = requests.Session()
    session.auth = (cfg["shelf_username"].strip().encode("utf-8"), cfg["shelf_password"].encode("utf-8"))
    session.headers["User-Agent"] = AGENT
    channel = channel or "podcasts"
    base = cfg["shelf_url"].strip().rstrip("/") + "/" + quote(SHELF_FOLDER, safe="") + "/"
    place = base + quote(book_file_name(channel), safe="") + "/"
    name = book_file_name(episode["title"])
    when = QtCore.QLocale().toString(QtCore.QDateTime.fromMSecsSinceEpoch(episode["published"]).date(), "d MMMM yyyy") \
        if episode.get("published") else ""
    source = " · ".join(p for p in (channel, when) if p)
    made = []

    def check(r):
        if r.status_code in (401, 403):
            raise Told(_("the library refused the login"))
        if not 200 <= r.status_code < 300:
            raise IOError("HTTP %d" % r.status_code)

    def put(file_name, data):
        target = place + quote(file_name, safe="")
        there = session.head(target, timeout=(30, 60))
        if there.status_code == 200:
            return
        if there.status_code in (401, 403):
            check(there)
        if not made:
            for folder in (base, place):
                r = session.request("MKCOL", folder, timeout=(30, 60))
                if r.status_code not in (201, 405, 301):
                    check(r)
            made.append(True)
        check(session.put(target, data=data, headers={"Content-Type": "application/epub+zip"}, timeout=(30, 120)))

    sent = episode.get("sent", "")
    if not sent.startswith("t"):
        found = transcript_load(episode["id"])
        if not found:
            return sent
        put(name + ".epub", epub_build(episode["id"], episode["title"], channel, found[0], source, transcript_text(found[1])))
        sent = "t"
    target = episode.get("translation", "")
    if target and sent != "t+" + target:
        found = transcript_load(episode["id"], target)
        if not found:
            return sent
        put("%s · %s.epub" % (name, target),
            epub_build(episode["id"] + "." + target, "%s · %s" % (episode["title"], target), channel, target, source,
                       transcript_text(found[1])))
        sent = "t+" + target
    return sent


# ------------------------------------------------------------------------------------------
# The network, off the interface thread
# ------------------------------------------------------------------------------------------

def new_feed(fid, url, title, author, kind, serial):
    now = int(datetime.now().timestamp() * 1000)
    return {"id": fid, "url": url, "title": title, "author": author, "kind": kind, "addedAt": now,
            "lastFetch": now, "autoDownload": False, "keepCount": 50, "lastError": "",
            "serial": bool(serial)}


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



# ------------------------------------------------------------------------------------------
# Finding a podcast by its name — the phone's Catalogue.kt, rule for rule: Apple's directory
# and fyyd, both asked at once, either free to fail without the other's answer being lost.
# ------------------------------------------------------------------------------------------

CATALOGUE_APPLE = "Apple Podcasts"
CATALOGUE_FYYD = "fyyd"


def apple_search_url(term, country="", limit=30):
    """The store of the reader's country answers first with that country's podcasts."""
    url = "https://itunes.apple.com/search?media=podcast&entity=podcast&limit=%d&term=%s" % (
        limit, quote_plus(term))
    return url + ("&country=" + country.lower() if len(country or "") == 2 else "")


def fyyd_search_url(term, count=30):
    """`term=` rather than `title=`: the latter finds nothing as soon as there are two words."""
    return "https://api.fyyd.de/0.2/search/podcast?count=%d&term=%s" % (count, quote_plus(term))


def catalogue_author(raw):
    """Some feeds put their licence where the author goes; a line of that is no name."""
    s = " ".join((raw or "").split())
    return "" if len(s) > 80 or "://" in s else s


def parse_apple(data):
    found = []
    for o in (data or {}).get("results") or []:
        url = (o.get("feedUrl") or "").strip()
        title = (o.get("collectionName") or "").strip() or (o.get("trackName") or "").strip()
        if url and title:
            found.append({"title": title, "author": catalogue_author(o.get("artistName")),
                          "url": url, "episodes": int(o.get("trackCount") or 0)})
    return found


def parse_fyyd(data):
    found = []
    for o in (data or {}).get("data") or []:
        url = (o.get("xmlURL") or "").strip()
        title = (o.get("title") or "").strip()
        if url and title:
            found.append({"title": title, "author": catalogue_author(o.get("author")),
                          "url": url, "episodes": int(o.get("episode_count") or 0)})
    return found


def catalogue_key(url):
    """One feed however the directories spell it: scheme, `www.`, the host's case, a final
    slash. The path keeps its case — servers may tell /Feed from /feed."""
    s = re.sub(r"^[a-zA-Z]+://", "", (url or "").strip()).rstrip("/")
    host, slash, path = s.partition("/")
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host + slash + path


def _fold(text):
    return "".join(c for c in unicodedata.normalize("NFD", (text or "").lower())
                   if not unicodedata.combining(c))


def catalogue_merge(query, *lists):
    """Taken in turn from each directory, so neither buries the other; a feed both know appears
    once, with whatever either knew of it. Names holding the whole query first, then those
    holding all its words, then the rest — each group in the directories' order."""
    seen = {}
    for i in range(max((len(x) for x in lists), default=0)):
        for found in lists:
            if i >= len(found):
                continue
            f = found[i]
            k = catalogue_key(f["url"])
            had = seen.get(k)
            if had is None:
                seen[k] = dict(f)
            else:
                had["author"] = had["author"] or f["author"]
                had["episodes"] = max(had["episodes"], f["episodes"])
    q = _fold(query.strip())
    words = q.split()

    def rank(f):
        t = _fold(f["title"])
        if q and q in t:
            return 0
        if words and all(w in t for w in words):
            return 1
        return 2

    return sorted(seen.values(), key=rank)


def _get_json(url):
    r = requests.get(url, headers={"User-Agent": AGENT}, timeout=20)
    r.raise_for_status()
    return r.json()


def catalogue_search(term, country=""):
    """Both directories at once. Returns (found, the names of those that did not answer)."""
    def apple():
        try:
            return _get_json(apple_search_url(term, country))
        except Exception:
            if not country:
                raise
            return _get_json(apple_search_url(term))   # a country Apple does not know is a 400

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(apple)
        f = pool.submit(_get_json, fyyd_search_url(term))
        failed, lists = [], []
        for name, future, parse in ((CATALOGUE_APPLE, a, parse_apple), (CATALOGUE_FYYD, f, parse_fyyd)):
            try:
                lists.append(parse(future.result()))
            except Exception:
                failed.append(name)
                lists.append([])
    return catalogue_merge(term, *lists), failed


def clipboard_url(text):
    """An address worth offering, or "" — the clipboard usually holds something else entirely."""
    s = (text or "").strip()
    right = 8 <= len(s) <= 2000 and " " not in s and s.lower().startswith(
        ("http://", "https://", "feed://", "podcast://", "pcast://"))
    return s if right else ""


_ADDRESS = re.compile(r"^[^\s/]+\.[a-zA-Z]{2,}(/\S*)?$")


def looks_like_address(text):
    """An address rather than a name: a scheme, or a host with a dot and no spaces."""
    s = (text or "").strip()
    return bool(clipboard_url(s) or _ADDRESS.match(s))


def cut(text, limit=44):
    """A secondary line is read at a glance; past 44 characters it runs into the edge."""
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


_YT_ID = re.compile(r'(?:feeds/videos\.xml\?channel_id=|/channel/|"externalId":"|"channelId":")(UC[\w-]{20,})')


def looks_like_youtube(url):
    host = (urlparse(url).hostname or "").lower()
    return host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")


def youtube_feed(url):
    """The Atom feed of a channel from whatever address was pasted — the same one the phone
    arrives at (Youtube.kt), so the feed's id, which is computed from it, is the same on both."""
    if "/feeds/videos.xml" in url:
        return url
    m = re.search(r"/channel/(UC[\w-]{20,})", url, re.I)
    if m:
        return "https://www.youtube.com/feeds/videos.xml?channel_id=" + m.group(1)
    m = re.search(r"[?&]list=([\w-]+)", url)
    if m:
        return "https://www.youtube.com/feeds/videos.xml?playlist_id=" + m.group(1)
    # A @handle does not give the id away: the page states it, late, so it is read as it comes
    # and dropped the moment the id turns up rather than downloaded whole.
    # Without this cookie a reader in Europe is sent to the consent page, which names no channel.
    with requests.get(url, headers={"User-Agent": AGENT}, cookies={"SOCS": "CAI"}, stream=True, timeout=30) as r:
        r.raise_for_status()
        window = ""
        for chunk in r.iter_content(64 * 1024):
            window += chunk.decode("utf-8", "ignore")
            found = _YT_ID.search(window)
            if found:
                return "https://www.youtube.com/feeds/videos.xml?channel_id=" + found.group(1)
            window = window[-512:]
    return None


def auto_deletable(episode):
    """What may be thrown away on its own once heard — the phone's rule (Model.kt): not a
    favourite, not something written down, and not a video, which has no file to fetch again."""
    return not episode.get("starred") and not episode.get("transcript") and not is_youtube_episode(episode)


def is_youtube_episode(episode):
    return looks_like_youtube(episode.get("mediaUrl", ""))


def ytdlp_path():
    import shutil
    return shutil.which("yt-dlp")


class Told(RuntimeError):
    """An error already worded for the user, in the interface's language: shown as it is."""


def download_with_ytdlp(episode, on_progress, cancelled):
    """A YouTube entry is a page, not a file: yt-dlp finds the audio track and brings that down
    alone. It is the system's own yt-dlp, kept current by whoever keeps the system."""
    import subprocess
    exe = ytdlp_path()
    if not exe:
        raise Told(_("YouTube needs yt-dlp, which is not installed"))
    os.makedirs(AUDIO_DIR, exist_ok=True)
    stem = os.path.join(AUDIO_DIR, episode["id"])
    for name in os.listdir(AUDIO_DIR):
        if name.startswith(episode["id"] + "."):
            os.remove(os.path.join(AUDIO_DIR, name))
    proc = subprocess.Popen(
        [exe, "-f", "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio", "-o", stem + ".%(ext)s",
         "--no-playlist", "--no-mtime", "--newline", "--retries", "3", episode["mediaUrl"]],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    tail = []
    for line in proc.stdout:
        if cancelled():
            proc.kill()
            return None
        m = re.search(r"\[download\]\s+([\d.]+)%", line)
        if m:
            on_progress(min(100, int(float(m.group(1)))))
        elif line.strip():
            tail = (tail + [line.strip()])[-3:]
    if proc.wait() != 0:
        raise RuntimeError(" ".join(tail)[:300] or "yt-dlp")
    for name in os.listdir(AUDIO_DIR):
        if name.startswith(episode["id"] + ".") and not name.endswith(".part"):
            return os.path.join(AUDIO_DIR, name)
    raise RuntimeError(" ".join(tail)[:300] or "yt-dlp")


def resolve_address(url):
    """What an address pasted or imported stands for: a feed and its kind. A YouTube address
    becomes the channel's Atom feed, which is what the phone stores too (same id on both)."""
    if looks_like_youtube(url):
        return youtube_feed(url), "YOUTUBE"
    return url, "RSS"


def youtube_page_of(feed_url):
    """The page that lists a channel's videos, from the address of its feed (Extractor.kt)."""
    m = re.search(r"channel_id=([\w-]+)", feed_url)
    if m:
        return "https://www.youtube.com/channel/%s/videos" % m.group(1)
    m = re.search(r"playlist_id=([\w-]+)", feed_url)
    if m:
        return "https://www.youtube.com/playlist?list=%s" % m.group(1)
    return None


def ytdlp_json(args):
    """One `yt-dlp -J` run, its JSON; the last lines of its complaint otherwise."""
    import subprocess
    exe = ytdlp_path()
    if not exe:
        raise Told(_("YouTube needs yt-dlp, which is not installed"))
    proc = subprocess.run([exe, "-J", "--no-warnings"] + args, capture_output=True, text=True, timeout=180)
    text = (proc.stdout or "").strip()
    if not text:
        tail = " ".join((proc.stderr or "").strip().splitlines()[-3:])
        raise RuntimeError(tail[:300] or _("yt-dlp brought nothing back"))
    return json.loads(text)


def ytdlp_list_channel(feed_url, start, count):
    """The videos of a channel, [start, start+count) in the order of its page, newest first —
    the feed only ever carries fifteen. A flat listing: titles and lengths, no dates (yt-dlp's
    approximate ones came back identical for every video, which is worse than none)."""
    page = youtube_page_of(feed_url)
    if not page:
        raise Told(_("this channel has no page to read"))
    data = ytdlp_json(["--flat-playlist", "--playlist-start", str(start),
                       "--playlist-end", str(start + count - 1), page])
    out = []
    for o in data.get("entries") or []:
        if o and o.get("id"):
            out.append((o["id"], o.get("title") or o["id"], int((o.get("duration") or 0) * 1000)))
    return out


def ytdlp_describe(url):
    """The words under one video and its publication date (0 when unknown): what a flat
    listing leaves out, fetched when such a video is opened. Nothing is downloaded."""
    o = ytdlp_json(["--skip-download", "--no-playlist", url])
    day = o.get("upload_date") or ""
    try:
        published = int(datetime.strptime(day, "%Y%m%d").timestamp() * 1000)
    except ValueError:
        published = 0
    return (o.get("description") or "", published)


def older_episode(fid, video_id, title, duration_ms):
    """The same shape the feed gives a video (Atom id yt:video:ID), or it would arrive twice.
    No date: the row shows the length instead of a date that lies."""
    return {
        "id": episode_id(fid, "yt:video:" + video_id), "title": title, "published": 0,
        "mediaUrl": "https://www.youtube.com/watch?v=" + video_id, "mime": "audio/*", "bytes": 0,
        "durationMs": duration_ms, "localPath": "", "positionMs": 0, "state": "NEW", "lastPlayed": 0,
        "starred": False, "description": "",
    }


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
    if is_youtube_episode(episode):
        return download_with_ytdlp(episode, on_progress, cancelled)
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

DEFAULTS = {"dark": True, "font": "sans", "font_size": 12, "view": VIEW_CHANNELS,
            "default_view": VIEW_CHANNELS, "auto_refresh": True, "delete_when_played": False,
            "speed": 1.0}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    """Readable by this account only where the system knows what that means: it may hold the
    password of the library."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        fd = os.open(CONFIG_FILE + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
        os.replace(CONFIG_FILE + ".tmp", CONFIG_FILE)
    except OSError:
        pass


def settings_for_backup(cfg):
    """The keys the phone writes, so one file serves both."""
    return {"theme": "DARK" if cfg.get("dark", True) else "LIGHT",
            "default_view": cfg.get("default_view", VIEW_CHANNELS),
            "font": {"sans": "SANS", "serif": "SERIF", "mono": "MONO"}.get(cfg.get("font", "sans"), "SANS"),
            "auto_refresh": bool(cfg.get("auto_refresh", True)),
            "delete_when_played": bool(cfg.get("delete_when_played", False)),
            "speed": float(cfg.get("speed", 1.0))}


def settings_from_backup(cfg, settings):
    if "theme" in settings:
        cfg["dark"] = settings["theme"] != "LIGHT"
    if "font" in settings:
        cfg["font"] = {"SANS": "sans", "SERIF": "serif", "MONO": "mono"}.get(settings["font"], "sans")
    for key in ("auto_refresh", "delete_when_played"):
        if key in settings:
            cfg[key] = bool(settings[key])
    # The 0.1 names are mapped rather than dropped, so a file written then still opens something.
    view = {"queue": VIEW_CHANNELS, "new": VIEW_EPISODES}.get(settings.get("default_view"),
                                                              settings.get("default_view"))
    if view in VIEWS:
        cfg["default_view"] = view
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
        key = index.data(QtCore.Qt.UserRole)
        two = key is not None and not str(key).startswith("season:")
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


class AddDialog(QtWidgets.QDialog):
    """Adding a podcast. One field takes either an address — the clipboard's is offered,
    selected, so the first key replaces it — subscribed to as before, or a few words of a name,
    looked up in the public directories as one types. A podcast found goes down the same road as
    a pasted address; one already followed says so, and opens instead."""

    def __init__(self, main, initial=""):
        super().__init__(main)
        self.main = main
        self.generation = 0          # a newer search makes an older answer stale
        self.setWindowTitle(_("add a podcast"))
        self.resize(max(520, main.font_size * 44), max(420, main.font_size * 38))
        box = QtWidgets.QVBoxLayout(self)
        box.setContentsMargins(18, 18, 18, 12)
        box.setSpacing(10)
        self.field = QtWidgets.QLineEdit(initial)
        self.field.setPlaceholderText(_("a name, or a feed's address"))
        self.field.selectAll()
        box.addWidget(self.field)
        self.list = QtWidgets.QListWidget()
        self.list.setObjectName("found")
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.list.setWordWrap(True)
        self.list.itemClicked.connect(self.chosen)
        box.addWidget(self.list, 1)
        self.status = QtWidgets.QLabel()
        self.status.setObjectName("dim")
        self.status.setWordWrap(True)
        box.addWidget(self.status)
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(600)
        self.timer.timeout.connect(self.search)
        self.field.textChanged.connect(self.changed)
        self.field.returnPressed.connect(self.entered)
        self.changed()

    def _row(self, title, secondary, action):
        dim = self.main.colors.get("dim", "#8c8c8c")
        label = QtWidgets.QLabel("<div>%s</div><div style='color:%s; font-size:%dpt'>%s</div>" % (
            html.escape(title), dim, max(8, self.main.font_size - 2), html.escape(secondary)))
        label.setWordWrap(True)
        label.setContentsMargins(4, 8, 4, 8)
        label.setMinimumHeight(44)
        label.setCursor(QtCore.Qt.PointingHandCursor)
        label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        item = QtWidgets.QListWidgetItem()
        item.setData(QtCore.Qt.UserRole, action)
        self.list.addItem(item)
        self.list.setItemWidget(item, label)
        item.setSizeHint(QtCore.QSize(0, max(44, label.heightForWidth(self.list.viewport().width() - 8))))

    def changed(self, *_args):
        self.generation += 1
        self.timer.stop()
        self.list.clear()
        text = self.field.text().strip()
        if looks_like_address(text):
            self._row(_("subscribe to this address"), cut(text), ("subscribe", text))
            self.status.setText("")
        elif len(text) < 2:
            self.status.setText(_("Type a few words of its name to look it up in the public directories, or paste the address of its feed."))
        else:
            self.status.setText(_("searching the directories…"))
            self.timer.start()

    def entered(self):
        text = self.field.text().strip()
        if looks_like_address(text):
            self.act(("subscribe", text))
        elif len(text) >= 2:
            self.timer.stop()
            self.search()

    def search(self):
        text = self.field.text().strip()
        if len(text) < 2 or looks_like_address(text):
            return
        self.generation += 1
        mine = self.generation
        country = (QtCore.QLocale().name().split("_") + [""])[1]
        self.status.setText(_("searching the directories…"))

        def done(result, error):
            if mine != self.generation:
                return
            found, failed = result if result else ([], [CATALOGUE_APPLE, CATALOGUE_FYYD])
            self.show_found(found, failed)

        self.main.run(lambda _progress: catalogue_search(text, country), done)

    def show_found(self, found, failed):
        self.list.clear()
        followed = {catalogue_key(f["url"]): f["id"] for f in self.main.store.feeds}
        for f in found:
            who = f["author"] or (urlparse(f["url"]).hostname or "")
            fid = followed.get(catalogue_key(f["url"]))
            if fid:
                self._row(f["title"], cut(_("already followed") + " · " + who), ("open", fid))
            else:
                self._row(f["title"], cut(who), ("subscribe", f["url"]))
        if not found:
            self.status.setText(_("the directories do not answer — is the computer online?") if len(failed) >= 2
                                else _("no podcast of that name in the directories"))
        elif failed:
            self.status.setText(_("%s did not answer: these come from the other one", failed[0]))
        else:
            self.status.setText(_("found in Apple Podcasts and fyyd"))

    def chosen(self, item):
        action = item.data(QtCore.Qt.UserRole)
        if action:
            self.act(action)

    def act(self, action):
        kind, value = action
        self.accept()
        if kind == "open":
            self.main.open_feed(value)
        else:
            self.main.subscribe(value)


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
        for key, label in (("sans", _("sans-serif")), ("serif", _("serif")), ("mono", _("mono"))):
            self.font.addItem(label, key)
        self.font.setCurrentIndex(max(0, self.font.findData(cfg.get("font", "sans"))))
        form.addRow(_("font"), self.font)
        self.size = QtWidgets.QSpinBox()
        self.size.setRange(9, 24)
        self.size.setValue(int(cfg.get("font_size", 12)))
        form.addRow(_("text size"), self.size)
        self.opens = QtWidgets.QComboBox()
        for key, label in ((VIEW_EPISODES, _("episodes")), (VIEW_FAVOURITES, _("favourites")),
                           (VIEW_DOWNLOADED, _("downloaded"))):
            self.opens.addItem(label, key)
        self.opens.setCurrentIndex(max(0, self.opens.findData(cfg.get("default_view", VIEW_CHANNELS))))
        form.addRow(_("opens on"), self.opens)
        self.auto = QtWidgets.QCheckBox()
        self.auto.setChecked(bool(cfg.get("auto_refresh", True)))
        form.addRow(_("refresh on opening"), self.auto)
        self.delete_played = QtWidgets.QCheckBox()
        self.delete_played.setChecked(bool(cfg.get("delete_when_played", False)))
        form.addRow(_("delete once heard"), self.delete_played)
        # What was said: how carefully it is written down, and which of Ollama's models translates.
        self.quality = QtWidgets.QComboBox()
        self.quality.addItem(_("ordinary"), "normal")
        self.quality.addItem(_("careful") + " — " + _("several times slower"), "high")
        self.quality.setCurrentIndex(max(0, self.quality.findData(cfg.get("speech_quality", "normal"))))
        form.addRow(_("writing down"), self.quality)
        self.model = QtWidgets.QComboBox()
        self.model.addItem(_("chosen by the app"), "")
        for name, _size in ollama_models():
            self.model.addItem(name, name)
        self.model.setCurrentIndex(max(0, self.model.findData(cfg.get("translate_model", ""))))
        form.addRow(_("translation model"), self.model)
        # The library of Reader's Books, where the transcripts go.
        hint = QtWidgets.QLabel(_("With the WebDAV address of the library of Reader's Books, every transcript is sent to a « transcriptions » folder there, a small book per episode, to be read, highlighted and commented."))
        hint.setObjectName("dim")
        hint.setWordWrap(True)
        form.addRow(hint)
        self.shelf_url, self.shelf_user, self.shelf_password = QtWidgets.QLineEdit(), QtWidgets.QLineEdit(), QtWidgets.QLineEdit()
        self.shelf_url.setText(cfg.get("shelf_url", ""))
        self.shelf_user.setText(cfg.get("shelf_username", ""))
        self.shelf_password.setText(cfg.get("shelf_password", ""))
        self.shelf_password.setEchoMode(QtWidgets.QLineEdit.Password)
        self.shelf_url.setMinimumWidth(self.shelf_url.fontMetrics().averageCharWidth() * 44)
        form.addRow(_("address of the library"), self.shelf_url)
        form.addRow(_("username"), self.shelf_user)
        form.addRow(_("password"), self.shelf_password)
        self.said = QtWidgets.QLabel("")
        self.said.setObjectName("dim")
        fetch = QtWidgets.QPushButton(_("import credentials…"))
        fetch.setAutoDefault(False)
        fetch.clicked.connect(self.import_credentials)
        form.addRow(fetch, self.said)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        # No Qt translator is loaded: without these the buttons say OK / Cancel in every language.
        buttons.button(QtWidgets.QDialogButtonBox.Ok).setText(_("ok"))
        buttons.button(QtWidgets.QDialogButtonBox.Cancel).setText(_("cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        # A sentence that wraps asks for its height only once its width is known: without this
        # the form gives it two lines and cuts the rest.
        self.adjustSize()
        margins = form.contentsMargins()
        hint.setMinimumHeight(hint.heightForWidth(max(200, self.width() - margins.left() - margins.right())))

    def values(self):
        return {"dark": self.colours.currentData(), "font": self.font.currentData(),
                "font_size": self.size.value(), "auto_refresh": self.auto.isChecked(),
                "delete_when_played": self.delete_played.isChecked(),
                "default_view": self.opens.currentData(),
                "speech_quality": self.quality.currentData(), "translate_model": self.model.currentData(),
                "shelf_url": self.shelf_url.text().strip(), "shelf_username": self.shelf_user.text().strip(),
                "shelf_password": self.shelf_password.text()}

    def import_credentials(self):
        """The library's account from a Reader's credentials file: Reader's Books' own section,
        else the drive and login of an app that keeps its files on the same kind of drive."""
        path, _sel = QtWidgets.QFileDialog.getOpenFileName(self, _("import credentials…"), os.path.expanduser("~"),
                                                           "%s (*.json);;* (*)" % _("Reader's credentials"))
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                found = shelf_account(fh.read())
        except OSError:
            found = None
        if found is None:
            self.said.setText(_("not a Reader's credentials file"))
        elif not found[0]:
            self.said.setText(_("this file names no drive"))
        else:
            self.shelf_url.setText(found[0])
            self.shelf_user.setText(found[1])
            self.shelf_password.setText(found[2])
            self.said.setText(_("credentials imported"))


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
        self.view = self.cfg.get("view") or self.cfg.get("default_view", VIEW_EPISODES)
        if self.view == VIEW_CHANNELS:
            self.view = VIEW_EPISODES
        self.threads = []            # kept referenced: a QThread garbage-collected mid-job dies
        self.downloading = None      # id of the episode coming down
        self.download_queue = []
        self.speech = None           # what is being written down or translated: {"id", "kind", "percent"}
        self.speech_queue = []       # (episode id, "write" | "translate", language) still to do
        self.cancel_speech = False
        self.after_fetch = {}        # episode id -> what to do once its audio is here
        self.show_text = False       # the pane on the right shows what was said, not the notes
        self.show_translation = True
        self.text_line = -1          # the line of the text the sound is at
        self.shelving = False
        self.download_percent = 0
        self.cancel_download = False
        self.busy = ""               # a line at the top while something is happening
        self.open_seasons = {}       # channel id -> the seasons shown open, for this sitting

        self.setWindowTitle("Reader's Podcasts")
        self.resize(1000, 680)
        self._build()
        self._player()
        self.apply_style()
        self.refresh_all_lists()
        if self.cfg.get("auto_refresh", True) and self.store.feeds:
            QtCore.QTimer.singleShot(200, self.refresh_feeds)
        QtCore.QTimer.singleShot(1500, self.send_to_library)       # what could not be sent the last time

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

        self.filter_text = ""
        self.find = QtWidgets.QLineEdit()
        self.find.setObjectName("find")
        self.find.setPlaceholderText(_("a channel, an episode"))
        self.find.setVisible(False)
        self.find.textChanged.connect(self.on_filter)
        # Escape puts the field away and shows the whole list again.
        QtWidgets.QShortcut(QtGui.QKeySequence("Escape"), self.find, activated=self.close_search)
        right_box.addWidget(self.find)

        self.episodes_list = QtWidgets.QListWidget()
        self.episodes_list.setObjectName("episodes")
        self.episodes_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.delegate = EpisodeDelegate(self)
        self.episodes_list.setItemDelegate(self.delegate)
        self.episodes_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.episodes_list.customContextMenuRequested.connect(self.episode_menu)
        self.episodes_list.itemActivated.connect(self.play_selected)
        self.episodes_list.itemClicked.connect(self.on_episode_clicked)
        self.episodes_list.itemDoubleClicked.connect(self.play_selected)
        # What the selected episode is about, beside the list: one reads before one listens, and a
        # window has the room the telephone had to find by opening another screen.
        self.details = QtWidgets.QTextBrowser()
        self.details.setObjectName("details")
        self.details.setOpenLinks(False)
        self.details.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.details.anchorClicked.connect(self.on_detail_link)
        self.details.setMinimumWidth(320)
        # The selection, not the current item: at a click the current item changes first, and the
        # pane then described the episode chosen the click before.
        self.episodes_list.itemSelectionChanged.connect(self.refresh_details)
        split = QtWidgets.QHBoxLayout()
        split.setContentsMargins(0, 0, 0, 0)
        split.setSpacing(0)
        split.addWidget(self.episodes_list, 3)
        split.addWidget(self.details, 2)
        right_box.addLayout(split, 1)
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
        self.refresh_details()

    def refresh_details(self):
        """The pane on the right: the title in full, when and how long, what can be done, the
        chapters if the notes list any, and the notes themselves with their links alive."""
        e = self.selected_episode()
        if not e:
            self.details.setHtml("")
            return
        colors = getattr(self, "colors", {"fg": "#ffffff", "dim": "#8c8c8c"})
        fg, dim = colors["fg"], colors["dim"]
        feed = self.store.feed(e["feedId"]) or {}
        duration = e.get("durationMs", 0)
        meta = " · ".join(p for p in (feed.get("title", ""), relative_date(e.get("published", 0)),
                                       spoken(duration) if duration else "") if p)
        playing = self.current and self.current["id"] == e["id"]
        here = bool(e.get("localPath"))
        busy = e["id"] == self.downloading or e["id"] in self.download_queue
        actions = [("act:play", _("pause") if playing and self.is_playing() else _("listen")),
                   ("act:stopdl", _("stop the download")) if busy else
                   ("act:remove", _("remove from this computer")) if here else ("act:download", _("download")),
                   ("act:star", _("remove from favourites") if e.get("starred") else _("keep as a favourite"))]
        working = bool(self.speech and self.speech["id"] == e["id"])
        if working:
            actions.append(("act:stopspeech", self.speech_label() + " · " + _("stop")))
        elif not e.get("transcript"):
            actions.append(("act:write", _("write down")))
        else:
            actions.append(("act:text", _("notes") if self.show_text else _("text")))
            if e.get("translation") and self.show_text:
                actions.append(("act:which", _("original") if self.show_translation else LANGUAGE_NAMES.get(e["translation"], e["translation"])))
            if not e.get("translation"):
                actions.append(("act:translate", _("translate")))
        link = 'style="color:%s;"' % fg
        parts = ['<div style="font-size:%dpt; margin-bottom:4px;">%s%s</div>'
                 % (self.font_size + 4, "★ " if e.get("starred") else "", html.escape(e["title"])),
                 '<div style="color:%s; margin-bottom:14px;">%s</div>' % (dim, html.escape(meta)),
                 '<div style="margin-bottom:14px;">%s</div>' % " &nbsp;·&nbsp; ".join(
                     '<a href="%s" %s>%s</a>' % (href, link, html.escape(label)) for href, label in actions)]
        said = self.said(e) if self.show_text else None
        if said:
            # What was said, each line a way to the sound; the line the sound is at stands out.
            now = self.line_at(e, said)
            self.text_line = now
            plain = 'style="color:%s; text-decoration:none;"' % fg
            here_style = 'style="color:%s; text-decoration:underline; font-weight:600;"' % fg
            rows, i = [], 0
            for paragraph in transcript_paragraphs(said):
                bits = []
                for a, _b, t in paragraph:
                    bits.append('<a name="l%d" href="t:%d" %s>%s</a>' % (i, a, here_style if i == now else plain, html.escape(t)))
                    i += 1
                rows.append('<p style="line-height:150%%; margin:0 0 12px 0;">%s</p>' % " ".join(bits))
            at = self.details.verticalScrollBar().value() if getattr(self, "_detail_id", None) == e["id"] + "/text" else 0
            self._detail_id = e["id"] + "/text"
            self.details.setHtml("".join(parts + rows))
            self.details.verticalScrollBar().setValue(at)
            return
        chapters = parse_chapters(e.get("description", ""), duration)
        if chapters:
            parts.append('<div style="color:%s; margin-bottom:4px;">%s</div>' % (dim, html.escape(_("chapters"))))
            parts.append("".join('<div><a href="chap:%d" %s>%s</a> &nbsp;%s</div>'
                                 % (ms, link, clock(ms), html.escape(title)) for ms, title in chapters))
            parts.append('<br>')
        notes = linkify(e.get("description", ""), duration, times=True).replace("<a href=", "<a %s href=" % link)
        if not e.get("description") and is_youtube_episode(e) and ytdlp_path():
            notes = '<span style="color:%s;">%s</span>' % (dim, html.escape(_("the words of this video are being fetched…")))
            self.describe_later(e)
        parts.append('<div style="line-height:140%%;">%s</div>' % notes)
        at = self.details.verticalScrollBar().value() if getattr(self, "_detail_id", None) == e["id"] else 0
        self._detail_id = e["id"]
        self.details.setHtml("".join(parts))
        self.details.verticalScrollBar().setValue(at)

    def is_playing(self):
        return bool(self.player) and self.player.state() == QtMultimedia.QMediaPlayer.PlayingState

    # ---- what was said: written down, translated, read against the sound ----

    def said(self, e):
        """The lines to show for an episode: its translation when there is one and it is asked
        for, else what was said. None when nothing was written down."""
        if not e.get("transcript"):
            return None
        if e.get("translation") and self.show_translation:
            found = transcript_load(e["id"], e["translation"])
            if found:
                return found[1]
        found = transcript_load(e["id"])
        return found[1] if found else None

    def line_at(self, e, lines):
        """The line the sound is at, counted among the lines that are shown; -1 when this
        episode is not the one playing."""
        if not (self.current and self.current["id"] == e["id"] and self.player):
            return -1
        position, found, i = self.player.position(), -1, 0
        for a, _b, t in lines:
            if not t.strip():
                continue
            if a <= position:
                found = i
            i += 1
        return found

    def follow_text(self):
        """While the text is on the page and its episode plays, the line being said stands out
        and stays in sight."""
        e = self.selected_episode()
        if not (self.show_text and e and self.current and self.current["id"] == e["id"]):
            return
        lines = self.said(e)
        if not lines:
            return
        now = self.line_at(e, lines)
        if now != self.text_line and now >= 0:
            self.refresh_details()
            self.details.scrollToAnchor("l%d" % max(0, now - 1))

    def speech_label(self):
        job = self.speech or {}
        percent = job.get("percent", 0)
        if percent < 0:
            return _("fetching the model %d %%", -percent - 1)
        return _("translating %d %%", percent) if job.get("kind") == "translate" else _("writing down %d %%", percent)

    def choose_language(self, title, codes, first=None, auto=False):
        """A short menu under the pointer: the language last used for this channel first, then
        the others. Returns a code, "" for « let it work it out », None when nothing was chosen."""
        menu = QtWidgets.QMenu(self)
        head = menu.addAction(title)
        head.setEnabled(False)
        menu.addSeparator()
        chosen = []
        if first in codes:
            menu.addAction("%s  ·  %s" % (LANGUAGE_NAMES.get(first, first), _("last time")), lambda: chosen.append(first))
        if auto:
            menu.addAction(_("let it work it out"), lambda: chosen.append(""))
        for code in codes:
            if code != first:
                menu.addAction(LANGUAGE_NAMES.get(code, code), lambda code=code: chosen.append(code))
        menu.exec_(QtGui.QCursor.pos())
        return chosen[0] if chosen else None

    def last_language(self, fid):
        """The language this channel was last written down in: a suggestion, never a choice
        made on the listener's behalf."""
        done = [e for e in self.store.episodes_of(fid) if e.get("transcript") and e.get("transcriptLanguage")]
        return done[0]["transcriptLanguage"] if done else None

    def ask_write(self, e):
        if not find_whisper(self.cfg):
            self.say(_("writing down needs a Whisper program (faster-whisper, whisper.cpp or whisper): none was found"))
            return
        language = self.choose_language(_("the language spoken"), SPEECH_LANGUAGES, self.last_language(e["feedId"]), auto=True)
        if language is not None:
            self.queue_speech(e, "write", language)

    def ask_translate(self, e):
        if not ollama_models():
            self.say(_("translating needs Ollama, which is not running or has no model"))
            return
        source = e.get("transcriptLanguage", "")
        # The language of this computer first: it is the likeliest wish.
        codes = sorted((c for c in TRANSLATE_LANGUAGES if c != source), key=lambda c: c != LANG)
        target = self.choose_language(_("translate into"), codes)
        if target:
            self.queue_speech(e, "translate", target)

    def queue_speech(self, e, kind, language):
        eid = e["id"]
        if kind == "write" and not (e.get("localPath") and os.path.exists(e["localPath"])):
            # Nothing can be heard that is not here: the audio is fetched first, the rest follows.
            self.after_fetch[eid] = lambda: self.queue_speech(self.store.episode(eid), kind, language)
            self.queue_download(e, quiet=True)
            self.say(_("the audio is fetched first; it is written down after"))
            self.refresh_all_lists()
            return
        self.speech_queue.append((eid, kind, language))
        self.next_speech()
        self.refresh_all_lists()

    def stop_speech(self, e):
        self.speech_queue = [q for q in self.speech_queue if q[0] != e["id"]]
        self.after_fetch.pop(e["id"], None)
        if self.speech and self.speech["id"] == e["id"]:
            self.cancel_speech = True
        self.refresh_all_lists()

    def next_speech(self):
        if self.speech or not self.speech_queue:
            return
        eid, kind, language = self.speech_queue.pop(0)
        e = self.store.episode(eid)
        if not e:
            return self.next_speech()
        self.speech = {"id": eid, "kind": kind, "percent": 0}
        self.cancel_speech = False
        cfg = dict(self.cfg)

        def job(progress):
            if kind == "write":
                return transcribe(find_whisper(cfg), e["localPath"], cfg.get("speech_quality", "normal"), language,
                                  e.get("durationMs", 0), progress, lambda: self.cancel_speech)
            source = transcript_load(eid)
            model = pick_model(ollama_models(), cfg.get("translate_model", ""))
            if not source or not model:
                raise Told(_("translating needs Ollama, which is not running or has no model"))
            return language, translate(source[1], language, model, progress, lambda: self.cancel_speech)

        def done(result, error):
            self.speech = None
            if error:
                if not self.cancel_speech:
                    self.say(str(error) if isinstance(error, Told) else
                             _("the translation failed. %s", str(error)[:160]) if kind == "translate" else
                             _("the writing down failed. %s", str(error)[:160]))
                    print("speech failed:", error, file=sys.stderr)
            else:
                heard, lines = result
                if kind == "write":
                    transcript_save(eid, heard, lines)
                    self.store.update_episode(eid, transcript=True, transcriptLanguage=heard)
                    self.say(_("written down"))
                else:
                    transcript_save(eid, heard, lines, translation=True)
                    self.store.update_episode(eid, translation=heard)
                    self.say(_("translated"))
                if self.selected_id() == eid:
                    self.show_text = True
                self.send_to_library()
            self.refresh_all_lists()
            self.next_speech()

        def progress(percent):
            if self.speech:
                self.speech["percent"] = percent
            self.refresh_episodes_list()
            if self.selected_id() == eid:
                self.refresh_details()

        self.run(job, done, progress)

    def send_to_library(self):
        """Every transcript that is not yet in the library of Reader's Books, in the background;
        what cannot be sent now is sent at the next start or the next transcript."""
        if self.shelving or not shelf_configured(self.cfg):
            return
        waiting = [dict(e) for e in self.store.episodes if e.get("transcript") and e.get("sent", "") != shelf_wanted(e)]
        if not waiting:
            return
        self.shelving = True
        cfg = dict(self.cfg)
        channels = {f["id"]: f.get("title", "") for f in self.store.feeds}

        def job(_progress):
            out, failure = [], ""
            for e in waiting:
                try:
                    out.append((e["id"], shelf_send(cfg, e, channels.get(e["feedId"], ""))))
                except Told as exc:
                    failure = str(exc)
                    break
                except Exception as exc:
                    failure = str(exc)[:160]
            return out, failure

        def done(result, error):
            self.shelving = False
            sent, failure = result if result else ([], str(error)[:160] if error else "")
            for eid, state in sent:
                if self.store.episode(eid):
                    self.store.update_episode(eid, sent=state)
            if failure:
                self.say(_("the transcripts could not be sent to the library. %s", failure))

        self.run(job, done)

    def describe_later(self, e):
        """A video reached by « load more » comes with a title and a length only: its words —
        and the times in them — and its date are asked for once, when it is opened."""
        asked = self.__dict__.setdefault("_described", set())
        if e["id"] in asked:
            return
        asked.add(e["id"])
        eid, url = e["id"], e["mediaUrl"]

        def done(result, error):
            if error or not result:
                return
            description, published = result
            fields = {"description": description[:10000]}
            current = self.store.episode(eid) or {}
            if not current.get("published") and published:
                fields["published"] = published
            self.store.update_episode(eid, **fields)
            self.refresh_episodes_list()
            if self.selected_id() == eid:
                self.refresh_details()

        self.run(lambda _progress: ytdlp_describe(url), done)

    def on_detail_link(self, url):
        target = url.toString()
        e = self.selected_episode()
        if target.startswith("http"):
            QtGui.QDesktopServices.openUrl(url)
        elif not e:
            return
        elif target == "act:play":
            self.play(e)
        elif target == "act:download":
            self.queue_download(e)
        elif target == "act:stopdl":
            self.stop_download(e)
        elif target == "act:remove":
            self.remove_file(e)
        elif target == "act:star":
            self.star(e, not e.get("starred"))
        elif target == "act:write":
            self.ask_write(e)
        elif target == "act:translate":
            self.ask_translate(e)
        elif target == "act:stopspeech":
            self.stop_speech(e)
        elif target == "act:text":
            self.show_text = not self.show_text
        elif target == "act:which":
            self.show_translation = not self.show_translation
        elif target.startswith(("chap:", "t:")):
            ms = int(target.split(":", 1)[1])
            if self.current and self.current["id"] == e["id"] and self.player:
                self.player.setPosition(ms)
                if not self.is_playing():
                    self.player.play()
            else:
                self.store.update_episode(e["id"], positionMs=ms)
                self.play(self.store.episode(e["id"]))
        self.refresh_details()

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

        # No "channels" row here: on a window the channels are the column itself, always in
        # sight. The setting that names it simply opens on the episodes.
        row(_("episodes"), VIEW_EPISODES, len(self.store.recent()))
        row(_("favourites"), VIEW_FAVOURITES, len(self.store.favourites()))
        row(_("downloaded"), VIEW_DOWNLOADED, len(self.store.downloaded()))
        if self.store.feeds:
            rule = QtWidgets.QListWidgetItem("")
            rule.setData(QtCore.Qt.UserRole, FeedDelegate.RULE)
            rule.setFlags(QtCore.Qt.NoItemFlags)
            self.feeds_list.addItem(rule)
        for f in self.store.channels():
            row(f.get("title") or f["url"], f["id"], self.store.unplayed(f["id"]),
                _("last refresh failed: %s", f["lastError"]) if f.get("lastError") else None)
        self.feeds_list.blockSignals(False)

    def current_episodes(self):
        if self.store.feed(self.view):
            episodes = self.store.episodes_of(self.view)
        elif self.view == VIEW_FAVOURITES:
            episodes = self.store.favourites()
        elif self.view == VIEW_DOWNLOADED:
            episodes = self.store.downloaded()
        else:
            episodes = self.store.recent()
        needle = self.filter_text.strip().lower()
        if needle:
            episodes = [e for e in episodes if needle in e["title"].lower()]
        return episodes

    def refresh_episodes_list(self):
        keep = self.selected_id()
        # Rebuilt in silence: emptied and filled again, the list would announce "nothing chosen"
        # and then the same episode, and the pane on the right would blink and lose its place.
        self.episodes_list.blockSignals(True)
        try:
            self._fill_episodes_list(keep)
        finally:
            self.episodes_list.blockSignals(False)
        if self.selected_id() != keep:
            self.refresh_details()

    def _fill_episodes_list(self, keep):
        self.episodes_list.clear()
        feed = self.store.feed(self.view)
        self.head_label.setText(self.busy or (feed.get("title") if feed else
                                              (_("favourites") if self.view == VIEW_FAVOURITES
                                               else _("downloaded") if self.view == VIEW_DOWNLOADED
                                               else _("episodes"))))
        episodes = self.current_episodes()
        if not episodes:
            hint = (_("no subscriptions yet. + a feed below finds a podcast by its name, or takes the address of its feed.") if not self.store.feeds
                    else _("no favourite yet.") if self.view == VIEW_FAVOURITES
                    else _("nothing on this computer yet.") if self.view == VIEW_DOWNLOADED
                    else _("nothing here yet."))
            item = QtWidgets.QListWidgetItem(hint)
            item.setFlags(QtCore.Qt.NoItemFlags)
            self.episodes_list.addItem(item)
            self.add_older_row(feed)
            return
        mixed = feed is None

        def row(e):
            item = QtWidgets.QListWidgetItem(e["title"])
            item.setData(QtCore.Qt.UserRole, e["id"])
            item.setData(QtCore.Qt.UserRole + 1, self.status_of(e, mixed))
            self.episodes_list.addItem(item)
            if e["id"] == keep:
                item.setSelected(True)

        # A channel cut into seasons shows them as headings, one open at a time unless more
        # are asked for; a search runs through all of them, so it is shown flat.
        found = shelves(episodes, feed.get("serial")) if feed and not self.filter_text.strip() else []
        if found:
            opened = self.open_seasons.setdefault(feed["id"], {open_season(found, episodes)})
            for season, name, rows in found:
                is_open = season in opened
                item = QtWidgets.QListWidgetItem(("▾ " if is_open else "▸ ") + season_label(season, name))
                item.setData(QtCore.Qt.UserRole, "season:%d" % season)
                unheard = len([e for e in rows if e.get("state") != "PLAYED"])
                item.setData(QtCore.Qt.UserRole + 1, " · ".join(
                    [_("%d episodes", len(rows))] + ([_("%d unheard", unheard)] if 0 < unheard < len(rows) else [])))
                self.episodes_list.addItem(item)
                if keep == "season:%d" % season:
                    item.setSelected(True)
                if is_open:
                    for e in rows:
                        row(e)
        else:
            for e in (in_order(episodes, True) if feed and feed.get("serial") and not self.filter_text.strip() else episodes):
                row(e)
        self.add_older_row(feed)

    def add_older_row(self, feed):
        """A YouTube feed only ever carries the latest fifteen: the last row of such a channel
        walks its page for more, twenty-five at a time."""
        if feed and looks_like_youtube(feed.get("url", "")) and not self.busy:
            item = QtWidgets.QListWidgetItem(_("load more episodes"))
            item.setData(QtCore.Qt.UserRole, "older:" + feed["id"])
            item.setData(QtCore.Qt.UserRole + 1, _("the feed only carries the latest fifteen"))
            self.episodes_list.addItem(item)

    def load_older(self, feed):
        known = len(self.store.episodes_of(feed["id"]))
        self.set_busy(_("looking for the older ones…"))

        def job(_progress):
            listed = ytdlp_list_channel(feed["url"], known + 1, 25)
            # The feed names a video by its Atom id; an address already known is the surer
            # way to spot a repeat should that ever differ.
            seen = {e["mediaUrl"] for e in self.store.episodes_of(feed["id"])}
            return [older_episode(feed["id"], vid, title, ms) for vid, title, ms in listed
                    if "https://www.youtube.com/watch?v=" + vid not in seen]

        def done(result, error):
            self.set_busy("")
            if error:
                self.say(str(error) if isinstance(error, Told)
                         else _("the older episodes could not be loaded: %s", str(error)[:120]))
                return
            n = self.store.add_older(feed["id"], result)
            self.refresh_all_lists()
            self.say(_("%d older episodes added", n) if n else _("nothing older here"))

        self.run(job, done)

    def on_episode_clicked(self, item):
        target = item.data(QtCore.Qt.UserRole) or ""
        if isinstance(target, str) and target.startswith("season:") and self.store.feed(self.view):
            opened = self.open_seasons.setdefault(self.view, set())
            opened ^= {int(target[7:])}
            self.refresh_episodes_list()
        elif isinstance(target, str) and target.startswith("older:"):
            feed = self.store.feed(target[6:])
            if feed:
                self.load_older(feed)

    def status_of(self, e, with_feed):
        """The one line under a title: the channel when the list mixes them, when it came out,
        and the single thing worth knowing right now."""
        playing = self.current and self.current["id"] == e["id"]
        position = self.player.position() if (playing and self.player) else e.get("positionMs", 0)
        duration = e.get("durationMs", 0)
        if playing and self.player and self.player.duration() > 0:
            duration = self.player.duration()
        if self.speech and self.speech["id"] == e["id"]:
            state = self.speech_label()
        elif any(q[0] == e["id"] for q in self.speech_queue) or e["id"] in self.after_fetch:
            state = _("waiting")
        elif self.downloading == e["id"]:
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
        star = "★" if e.get("starred") else ""
        return " · ".join(p for p in (star, channel, relative_date(e.get("published", 0)), state or length) if p)

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
        menu.addAction(_("search"), self.open_search)
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
        menu.addAction(_("remove from favourites") if e.get("starred") else _("keep as a favourite"),
                       lambda: self.star(e, not e.get("starred")))
        heard = e.get("state") == "PLAYED"
        menu.addAction(_("mark as unheard") if heard else _("mark as heard"),
                       lambda: self.mark_played(e, not heard))
        menu.addSeparator()
        menu.addAction(_("copy the link"), lambda: QtWidgets.QApplication.clipboard().setText(e["mediaUrl"]))
        feed = self.store.feed(e["feedId"])
        if feed and self.view != feed["id"]:
            menu.addAction(_("open the channel"), lambda: self.open_feed(feed["id"]))
        menu.exec_(self.episodes_list.viewport().mapToGlobal(point))

    def close_search(self):
        self.find.clear()
        self.find.setVisible(False)
        self.filter_text = ""
        self.refresh_episodes_list()

    def open_search(self):
        """A field above the list, filtering what is already here — no one else's directory is
        asked anything, which is also why it works with the connection off."""
        self.find.setVisible(True)
        self.find.setFocus()
        self.find.selectAll()

    def on_filter(self, text):
        self.filter_text = text
        self.refresh_episodes_list()

    def open_feed(self, fid):
        self.view = fid
        self.cfg["view"] = fid
        save_config(self.cfg)
        self.refresh_all_lists()

    # ---- subscriptions ----

    def add_feed(self):
        AddDialog(self, clipboard_url(QtWidgets.QApplication.clipboard().text())).exec_()

    def subscribe(self, raw):
        url = normalise(raw)
        if self.store.feed(feed_id(url)):
            self.open_feed(feed_id(url))
            return
        self.set_busy(_("reading the feed…"))

        def job(_progress):
            address, kind = resolve_address(url)
            if not address:
                raise Told(_("no channel was found at that address"))
            fid = feed_id(address)
            title, author, episodes, serial = fetch_feed(address, fid, kind)
            return fid, address, title, author, episodes, kind, serial

        def done(result, error):
            self.set_busy("")
            if error:
                self.say(str(error) if isinstance(error, Told)
                         else _("that feed could not be read. %s", str(error)[:80]))
                return
            fid, url_, title, author, episodes, kind, serial = result
            if self.store.feed(fid):
                self.open_feed(fid)
                return
            self.store.add_feed(new_feed(fid, url_, title or url_, author, kind, serial))
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
            self.view = VIEW_EPISODES
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
                    kind = "YOUTUBE" if looks_like_youtube(f["url"]) else f.get("kind", "RSS")
                    out.append((f["id"], fetch_feed(f["url"], f["id"], kind), None))
                except Exception as exc:
                    out.append((f["id"], None, str(exc)[:120]))
            return out

        def done(result, error):
            self.set_busy("")
            if error:
                self.say(_("the refresh failed. %s", str(error)[:120]))
                return
            for fid, parsed, failure in result:
                if failure:
                    self.store.update_feed(fid, lastError=failure)
                    continue
                title, author, episodes, serial = parsed
                self.store.update_feed(fid, serial=serial)
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
                self.say(str(error) if isinstance(error, Told)
                         else _("the download failed. %s", str(error)[:120]))
                print("download failed:", error, file=sys.stderr)
            elif path:
                self.store.update_episode(eid, localPath=path, bytes=os.path.getsize(path))
            then = self.after_fetch.pop(eid, None)
            if then and path:
                then()
            self.refresh_all_lists()
            if path and getattr(self, "play_when_fetched", None) == eid:
                self.play_when_fetched = None
                self.play(self.store.episode(eid))
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

    def star(self, episode, starred):
        self.store.update_episode(episode["id"], starred=bool(starred))
        self.refresh_all_lists()

    def mark_played(self, episode, played):
        if played and self.current and self.current["id"] == episode["id"]:
            self.stop()
        self.store.update_episode(episode["id"], state="PLAYED" if played else "NEW", positionMs=0)
        if played and self.cfg.get("delete_when_played", False) and auto_deletable(episode):
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
        if not lines:
            self.say(_("no subscription in that file"))
            return
        fresh = [(url, title) for url, title in lines if not self.store.feed(feed_id(url))]
        if not fresh:
            self.say(_("every subscription in that file is already here"))
            return
        self.bring_in(fresh)

    def bring_in(self, lines, then=None):
        """Subscriptions named in a file, fetched four at a time and added as each one answers:
        a hundred and forty feeds read one after the other, and kept back until the last had
        answered, was minutes of a window that showed nothing and lost everything if closed.
        `lines` are (address, title); `then` runs once they are all in."""
        total = len(lines)
        self.set_busy(_("reading the feeds: %d of %d", 0, total))

        def one(line):
            url, given = line
            try:
                # A YouTube channel in the file (the phone writes its Atom feed; Podcast
                # Addict may write its page) is read as a channel, not as a podcast feed.
                address, kind = resolve_address(normalise(url))
                if not address:
                    return False
                fid = feed_id(address)
                if self.store.feed(fid):
                    return True
                title, author, episodes, serial = fetch_feed(address, fid, kind)
                self.store.add_feed(new_feed(fid, address, title or given or address, author, kind, serial))
                self.store.merge(fid, episodes)
                return True
            except Exception:
                return False

        def job(progress):
            added = seen = 0
            with ThreadPoolExecutor(max_workers=4) as pool:
                for ok in pool.map(one, lines):
                    seen += 1
                    added += 1 if ok else 0
                    progress(seen)
            return added

        def progress(seen):
            self.busy = _("reading the feeds: %d of %d", seen, total)
            self.refresh_all_lists()

        def done(added, error):
            self.set_busy("")
            if then:
                then()
            self.refresh_all_lists()
            if error:
                self.say(_("the import failed. %s", str(error)[:120]))
            elif added == total:
                self.say(_("%d feeds added", added))
            else:
                self.say(_("%d feeds added, %d could not be read", added, total - added))

        self.run(job, done, progress)

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
        fresh = [(url, title) for url, title, _f in missing if not self.store.feed(feed_id(url))]
        if fresh:
            # Positions and per-channel settings again once the episodes they name are here.
            self.bring_in(fresh, lambda: (self.apply_feed_settings(missing), self.apply_states(states)))

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
                # The star is not a matter of when: a file that carries one puts it on.
                if s.get("starred") and not e.get("starred"):
                    self.store.update_episode(e["id"], starred=True)
                continue
            self.store.update_episode(e["id"], positionMs=int(s.get("positionMs", 0)),
                                      state=s.get("state", "NEW"), lastPlayed=int(s.get("lastPlayed", 0)),
                                      starred=bool(s.get("starred")))

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
        if item and str(item.data(QtCore.Qt.UserRole) or "").startswith("older:"):
            return
        if e:
            self.play(e)

    def play(self, episode):
        if not self.player:
            self.say(_("audio is missing: install python3-pyqt5.qtmultimedia"))
            return
        if self.current and self.current["id"] == episode["id"]:
            self.toggle()
            return
        if is_youtube_episode(episode) and not episode.get("localPath"):
            # A page, not a file: nothing can play until yt-dlp has been through it. Asking for
            # it to play fetches it, and the sound follows by itself — one asked to listen.
            self.play_when_fetched = episode["id"]
            self.queue_download(episode)
            self.say(_("the audio is fetched first; it will play by itself"))
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
        self.follow_text()

    def on_media_status(self, status):
        if not self.player or status != QtMultimedia.QMediaPlayer.EndOfMedia or not self.current:
            return
        # An episode heard through: marked, put back to its beginning, and its file let go if
        # that is the setting. A phone or a desk that fills up with what was already heard is
        # something one stops trusting.
        eid = self.current["id"]
        self.store.update_episode(eid, state="PLAYED", positionMs=0)
        if self.cfg.get("delete_when_played", False) and auto_deletable(self.store.episode(eid) or {}):
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
        self.send_to_library()

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
        self.colors = {"bg": bg, "fg": fg, "dim": "#8c8c8c" if self.dark else "#737373"}
        family = {"serif": "serif", "mono": "monospace"}.get(self.cfg.get("font"), SANS_FAMILY)
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
            QTextBrowser#details {{ border: none; border-left: 1px solid {rule}; padding: 16px 20px; }}
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
        self.cancel_speech = True
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


SANS_FAMILY = "sans-serif"   # "Roboto" once the bundled font is loaded (load_bundled_fonts)


def bundled_fonts_dir():
    """Where the fonts shipped with the app lie: next to the script (packaging/fonts in the
    source tree, fonts/ once installed) or inside a PyInstaller bundle."""
    here = os.path.dirname(os.path.abspath(__file__))
    for d in (os.path.join(getattr(sys, "_MEIPASS", ""), "fonts"), os.path.join(here, "fonts"), os.path.join(here, "packaging", "fonts")):
        if d and os.path.isdir(d):
            return d
    return None


def load_bundled_fonts():
    """Roboto Light and Regular travel with the app, so that every computer draws the same
    text instead of whatever sans-serif the system picks."""
    global SANS_FAMILY
    d = bundled_fonts_dir()
    if not d:
        return 0
    n = 0
    for name in sorted(os.listdir(d)):
        if name.lower().endswith((".ttf", ".otf")) and QtGui.QFontDatabase.addApplicationFont(os.path.join(d, name)) >= 0:
            n += 1
    if n:
        SANS_FAMILY = "Roboto"
    return n


def main():
    # Sizes in the layout are pixels and text sizes are points: without this, a scaled screen
    # (125 %, 150 %, 200 %) grows the text and not the boxes around it.
    if hasattr(QtCore.Qt, "HighDpiScaleFactorRoundingPolicy"):
        QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    load_bundled_fonts()
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
