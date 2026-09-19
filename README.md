# Reader's Podcasts — bureau

Le jumeau de bureau de [Reader's Podcasts pour Android](https://github.com/funkypitt/readers-podcasts),
dans la même langue visuelle : deux couleurs, du texte, la sélection en inversé. Un seul fichier
Python, PyQt5 + requests.

**1.0.0** — Linux (.deb, PKGBUILD), et tout système où tournent Python 3 et PyQt5.

## Installer

**Debian, Ubuntu, Pop!_OS** — le paquet amène ses dépendances :

    sudo apt install ./readers-podcasts_1.0.0_all.deb

**Arch, Manjaro** :

    cd packaging && makepkg -si

**À la main** :

    sudo apt install python3-pyqt5 python3-pyqt5.qtmultimedia libqt5multimedia5-plugins python3-requests gstreamer1.0-plugins-good
    python3 readers_podcasts.py

`qtmultimedia` est ce qui lit l'audio ; sans lui l'app démarre quand même — on s'abonne, on
actualise, on télécharge — et la barre du bas dit ce qui manque au lieu de rester muette.
`gstreamer1.0-libav` lit les épisodes en m4a/aac, et **yt-dlp**, s'il est installé, va chercher
l'audio des chaînes YouTube.

## Ce qu'il fait

Trois colonnes, parce qu'une fenêtre a la place que le téléphone doit trouver en ouvrant un écran :

- **à gauche** : épisodes, favoris, téléchargés, puis les chaînes — celle qui a publié en dernier
  en tête, avec le nombre de non-écoutés ; clic droit pour actualiser, régler ou se désabonner ;
- **au milieu** : les épisodes ; un clic choisit, un double clic (ou Entrée) écoute — ouvrir n'est
  pas écouter ; clic droit pour le reste ;
- **à droite** : ce dont parle l'épisode choisi — le titre en entier, la date et la durée, ses
  **chapitres** quand les notes en donnent la liste (un clic y envoie le son), et les notes
  elles-mêmes avec leurs **liens vivants** ;
- **en bas** : la position, un filet qu'on clique pour se déplacer, −5 s / ▶ / +10 s, la vitesse ;
- **⋯** : chercher, actualiser, ajouter un flux, importer/exporter les abonnements (OPML) et les
  réglages (JSON), les couleurs, les réglages.

Une adresse YouTube (`@nom`, `/channel/…`, une liste de lecture) s'abonne comme un flux. Une vidéo
n'a pas de fichier à diffuser : ▶ va la chercher par yt-dlp, puis la joue.

« Effacer une fois écouté » est **inactif par défaut**, et même actif il épargne les favoris, ce
qui a été mis par écrit sur le téléphone, et les vidéos — qui n'ont pas de fichier à reprendre.

Les fichiers vivent dans `~/.local/share/readers-podcasts` (`feeds.json`, `feeds/<id>.json`,
`audio/`) et les réglages dans `~/.config/readers-podcasts/config.json`.

## Le lien avec le téléphone

Il n'y a pas de serveur : `abonnements.opml` et `reglages.json` *sont* la synchronisation. Les
identifiants de flux et d'épisode sont calculés des deux côtés de la même manière — y compris
pour une chaîne YouTube, résolue vers la même adresse de flux — si bien qu'une position prise sur
le téléphone retombe sur le bon épisode ici.

    python3 tools/check-interop.py ../readers-podcasts

écrit les fichiers que les tests du dépôt Android relisent, et relit ceux qu'ils laissent dans
`app/build/interop/`.

Licence MIT.
