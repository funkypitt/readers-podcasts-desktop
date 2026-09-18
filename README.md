# Reader's Podcasts — bureau

Le jumeau de bureau de l'app Android, dans la même langue visuelle : deux couleurs, du texte,
la sélection en inversé. Un seul fichier Python, PyQt5 + requests, comme Reader's Notes desktop.

État : **0.1.0**.

## Installation

    sudo apt install python3-pyqt5 python3-pyqt5.qtmultimedia python3-requests
    python3 readers_podcasts.py

`python3-pyqt5.qtmultimedia` est la seule dépendance qui sorte de l'ordinaire : c'est elle qui
lit l'audio. Sans elle l'app démarre quand même — on peut s'abonner, actualiser, télécharger —
et la barre du bas dit ce qui manque au lieu de rester muette.

## Ce qu'il fait

- la colonne de gauche : **à écouter**, **nouveautés**, puis les chaînes, avec le nombre de
  non-écoutés ; un clic droit sur une chaîne pour l'actualiser, la régler ou s'en désabonner ;
- la liste de droite : les épisodes, titre sur deux lignes et une ligne qui dit d'où il vient,
  quand il est sorti et où il en est ; clic droit pour télécharger, retirer, marquer écouté ;
- la barre du bas : la position, un filet qu'on clique pour se déplacer, −5 s / ▶ / +10 s, la vitesse ;
- **⋯** en haut à droite : actualiser, ajouter un flux, importer/exporter les abonnements (OPML)
  et les réglages (JSON), les couleurs, les réglages.

Les fichiers vivent dans `~/.local/share/readers-podcasts` (`feeds.json`, `feeds/<id>.json`,
`audio/`) et les réglages dans `~/.config/readers-podcasts/config.json`.

## Le lien avec le téléphone

Il n'y a pas de serveur : `abonnements.opml` et `reglages.json` *sont* la synchronisation. Les
identifiants d'épisode sont calculés des deux côtés de la même manière, si bien qu'une position
prise sur le téléphone retombe sur le bon épisode ici.

    python3 tools/check-interop.py ../readers-podcasts

écrit les fichiers que les tests du dépôt Android relisent, et relit ceux qu'ils laissent dans
`app/build/interop/`. À lancer après `./gradlew :app:testPriveDebugUnitTest` côté téléphone.
