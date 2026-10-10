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
- Une chaîne YouTube n'annonce que ses quinze dernières vidéos : « charger plus d'épisodes », en bas de sa liste, en lit vingt-cinq de plus à chaque fois (par yt-dlp) ; une vidéo ainsi trouvée reçoit sa date et ses notes quand on l'ouvre. Les chaînes YouTube d'un fichier OPML (celui du téléphone ou d'une autre application) entrent comme des chaînes.
- « Effacer une fois écouté » est inactif par défaut ; actif, il épargne les favoris, les épisodes mis par écrit sur le téléphone et les vidéos.
- Les saisons : une chaîne découpée en saisons les montre en titres qu'on ouvre et referme d'un clic. Une série (un flux qui se dit « serial ») se lit de la saison 1 vers la dernière, du premier épisode au dernier, et elle est gardée entière ; une émission qui numérote simplement ses années montre la saison en cours en haut.
- L'import d'abonnements lit quatre flux à la fois, les ajoute à mesure et dit combien n'ont pas répondu ; un fichier OPML abîmé (caractère interdit, fin de fichier en trop) est lu quand même.
- Mettre par écrit et traduire : l'application se sert de ce que l'ordinateur a déjà, comme elle le fait de yt-dlp. Pour la mise par écrit, un programme Whisper — faster-whisper (`pip install faster-whisper`, trouvé aussi dans un environnement conda ou pipx), sinon whisper.cpp (`whisper-cli`, avec ffmpeg ; son modèle est alors récupéré une fois), sinon le `whisper` d'OpenAI. On dit la langue parlée (la dernière de la chaîne est proposée, ou on le laisse trouver), en qualité ordinaire ou soignée (réglages). Pour la traduction, Ollama : le modèle est choisi par l'application (Gemma 3 d'abord, comme sur le téléphone) ou dans les réglages ; le texte est traduit par passages d'une quarantaine de secondes, qui restent accrochés au son, et le modèle quitte la mémoire une fois la traduction faite. Sans ces programmes, l'application dit ce qui manque.
- Les paragraphes suivent la parole, sans étiquette de locuteur : un nouveau paragraphe quand la voix change (une question, puis sa réponse), après une longue pause, après une pause plus courte qui suit la fin d'une phrase, et, quand une seule voix parle longtemps, à la fin d'une phrase une fois le paragraphe devenu long. Les voix sont distinguées par pyannote quand l'ordinateur l'a (cherché dans le même environnement que faster-whisper ; il lui faut ffmpeg, et son modèle déjà présent ou un jeton Hugging Face dans `HF_TOKEN`) ; une ligne qui contient la fin d'une question et le début de la réponse est coupée à l'endroit où la voix change. Sans pyannote, ou case décochée dans les réglages, les pauses décident seules. La traduction garde les paragraphes de l'original.
- Le texte se lit contre le son, dans la colonne de droite (« texte ») : la ligne en train d'être dite est soulignée et reste en vue, un clic sur une ligne y envoie le son ; « original » et le nom de la langue passent de l'un à l'autre quand il y a une traduction.
- Les transcriptions vont dans Reader's Books : avec l'adresse WebDAV de sa bibliothèque dans les réglages (ou le fichier d'identifiants), chaque transcription part dans un dossier `transcriptions` de cette bibliothèque, un petit livre par épisode, un dossier par chaîne, et une traduction en fait un second. Un livre déjà là (celui du téléphone, par exemple) n'est jamais réécrit.
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
