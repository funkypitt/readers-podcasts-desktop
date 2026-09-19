#!/bin/bash
# Builds readers-podcasts_<version>_all.deb next to this script. Needs dpkg-deb and fakeroot.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"; SRC="$HERE/.."
VERSION=$(grep -oE '^VERSION = "[^"]+"' "$SRC/readers_podcasts.py" | cut -d'"' -f2)
ROOT="$HERE/deb-root"; rm -rf "$ROOT"
install -Dm755 "$SRC/readers_podcasts.py" "$ROOT/usr/lib/readers-podcasts/readers_podcasts.py"
install -Dm755 /dev/stdin "$ROOT/usr/bin/readers-podcasts" <<'SH'
#!/bin/sh
exec python3 /usr/lib/readers-podcasts/readers_podcasts.py "$@"
SH
install -Dm644 "$HERE/readers-podcasts.desktop" "$ROOT/usr/share/applications/readers-podcasts.desktop"
install -Dm644 "$HERE/readers-podcasts.svg" "$ROOT/usr/share/icons/hicolor/scalable/apps/readers-podcasts.svg"
install -Dm644 "$SRC/LICENSE" "$ROOT/usr/share/doc/readers-podcasts/copyright"
mkdir -p "$ROOT/DEBIAN"
cat > "$ROOT/DEBIAN/control" <<CTRL
Package: readers-podcasts
Version: $VERSION
Section: sound
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-pyqt5, python3-pyqt5.qtmultimedia, libqt5multimedia5-plugins, python3-requests, gstreamer1.0-plugins-good
Recommends: gstreamer1.0-libav, yt-dlp
Maintainer: funkypitt <pierregallaz@gmail.com>
Homepage: https://github.com/funkypitt/readers-podcasts-desktop
Description: Black-and-white, text-only podcast player
 Channels on the left, episodes in the middle, and what the selected episode
 is about on the right: its notes with their links alive and its chapters one
 click from the sound. OPML in and out, a settings file that carries where
 each episode was left, in step with the Reader's Podcasts Android app.
 YouTube channels are followed as feeds; their audio is fetched by yt-dlp
 when it is installed.
CTRL
fakeroot dpkg-deb --build "$ROOT" "$HERE/readers-podcasts_${VERSION}_all.deb"
rm -rf "$ROOT"
echo "built $HERE/readers-podcasts_${VERSION}_all.deb"
