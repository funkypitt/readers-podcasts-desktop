# Reader's Podcasts — bureau

Un lecteur de podcasts en deux couleurs, tout en texte : les chaînes à gauche, les épisodes au
milieu, les notes de l'épisode à droite. Le jumeau de bureau de
[Reader's Podcasts pour Android](https://github.com/funkypitt/readers-podcasts). Ni compte ni
serveur : les abonnements voyagent en OPML, les réglages en JSON.

## Points-clés

- Un clic choisit un épisode, un double clic (ou Entrée) l'écoute ; clic droit pour le reste. Clic droit sur une chaîne : actualiser, régler, se désabonner.
- À gauche : épisodes, favoris, téléchargés, puis les chaînes, la dernière à avoir publié en tête, avec le nombre de non-écoutés.
- À droite : titre, date, durée, les chapitres quand les notes en donnent la liste (un clic y envoie le son), et les notes avec leurs liens.
- En bas : la position (un clic s'y déplace), −5 s / ▶ / +10 s, la vitesse. Sous ⋯ : chercher, actualiser, ajouter un flux, importer et exporter, couleurs, réglages.
- Une adresse YouTube (`@nom`, `/channel/…`, une liste de lecture) s'abonne comme un flux ; l'audio d'une vidéo est cherché par yt-dlp, s'il est installé.
- « Effacer une fois écouté » est inactif par défaut ; actif, il épargne les favoris, les épisodes mis par écrit sur le téléphone et les vidéos.
- Le lien avec le téléphone : `abonnements.opml` et `reglages.json` sont la synchronisation. Les identifiants de flux et d'épisode sont calculés de la même manière des deux côtés, si bien qu'une position prise sur le téléphone retombe sur le bon épisode.
- Les fichiers vivent dans `~/.local/share/readers-podcasts` (`feeds.json`, `feeds/<id>.json`, `audio/`), les réglages dans `~/.config/readers-podcasts/config.json`.
- Linux (.deb, PKGBUILD), et tout système où tournent Python 3 et PyQt5.

## Installer

- Debian, Ubuntu, Pop!_OS : ajouter le [dépôt apt](https://funkypitt.github.io/apt-repo/), puis `sudo apt install readers-podcasts`. Ou prendre le `.deb` de la [dernière version](https://github.com/funkypitt/readers-podcasts-desktop/releases/latest) : `sudo apt install ./readers-podcasts_*_all.deb`.
- Arch, Manjaro : `git clone https://github.com/funkypitt/readers-podcasts-desktop && cd readers-podcasts-desktop/packaging && makepkg -si`.
- À la main : `sudo apt install python3-pyqt5 python3-pyqt5.qtmultimedia libqt5multimedia5-plugins python3-requests gstreamer1.0-plugins-good`, puis `python3 readers_podcasts.py`.

`qtmultimedia` lit l'audio ; sans lui l'app démarre quand même et la barre du bas dit ce qui
manque. `gstreamer1.0-libav` lit les épisodes en m4a/aac.

## Construire

`packaging/build-deb.sh` construit le .deb. Un seul fichier Python, PyQt5 + requests.
`python3 tools/check-interop.py ../readers-podcasts` écrit les fichiers que les tests du dépôt
Android relisent, et relit ceux qu'ils laissent dans `app/build/interop/`.

Licence MIT.
