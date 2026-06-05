#!/usr/bin/env python3

import os
import sys
import time
import musicbrainzngs
import pylast
from mutagen.flac import FLAC
from collections import defaultdict

# ── Konfiguration ──────────────────────────────────────────────────────────────
BIBLIOTHEK    = os.path.expanduser("~/Musik/Bibliothek")
WHITELIST_TXT = os.path.expanduser("~/Musik/Bibliothek/genres_whitelist.txt")
INDEX_FILE    = os.path.expanduser("~/.genre_tagger_done.txt")
LASTFM_KEY    = os.environ.get("LASTFM_KEY", "")
MAX_GENRES    = 5
# ──────────────────────────────────────────────────────────────────────────────

if not LASTFM_KEY:
    print("Fehler: LASTFM_KEY-Umgebungsvariable nicht gesetzt.")
    sys.exit(1)

musicbrainzngs.set_useragent("genre-tagger", "1.0", "deine@email.dev")
lastfm = pylast.LastFMNetwork(api_key=LASTFM_KEY)

def load_whitelist(path):
    with open(path, "r") as f:
        return {line.strip().lower(): line.strip() for line in f if line.strip()}

def load_index(path):
    if not os.path.exists(path):
        return set()
    with open(path, "r") as f:
        return {line.strip() for line in f if line.strip()}

def save_to_index(path, key):
    with open(path, "a") as f:
        f.write(key + "\n")

def filter_whitelist(genres, whitelist):
    seen = set()
    result = []
    for g in genres:
        key = g.strip().lower()
        if key in whitelist and key not in seen:
            result.append(whitelist[key])
            seen.add(key)
    return result

def get_mb_genres(release_group_id):
    try:
        result = musicbrainzngs.get_release_group_by_id(
            release_group_id, includes=["tags"]
        )
        tags = result["release-group"].get("tag-list", [])
        tags.sort(key=lambda t: int(t.get("count", 0)), reverse=True)
        return [t["name"] for t in tags]
    except Exception as e:
        print(f"  MB Fehler: {e}")
        return []

def get_lastfm_album_genres(artist, album):
    try:
        a = lastfm.get_album(artist, album)
        tags = a.get_top_tags(limit=10)
        return [t.item.name for t in tags]
    except Exception:
        return []

def get_lastfm_artist_genres(artist):
    try:
        a = lastfm.get_artist(artist)
        tags = a.get_top_tags(limit=10)
        return [t.item.name for t in tags]
    except Exception as e:
        print(f"  LastFM Artist Fehler: {e}")
        return []

def resolve_album_genres(release_group_id, artist, album, whitelist):
    genres = []

    if release_group_id:
        mb = get_mb_genres(release_group_id)
        genres += filter_whitelist(mb, whitelist)
        time.sleep(0.3)

    if len(genres) < MAX_GENRES and artist and album:
        lfm_album = get_lastfm_album_genres(artist, album)
        for g in filter_whitelist(lfm_album, whitelist):
            if g.lower() not in {x.lower() for x in genres}:
                genres.append(g)
        time.sleep(0.3)

    if len(genres) < MAX_GENRES and artist:
        lfm_artist = get_lastfm_artist_genres(artist)
        for g in filter_whitelist(lfm_artist, whitelist):
            if g.lower() not in {x.lower() for x in genres}:
                genres.append(g)
        time.sleep(0.3)

    return genres[:MAX_GENRES]

def group_by_album(flac_files):
    albums = defaultdict(list)
    for filepath in flac_files:
        try:
            audio = FLAC(filepath)
            key = audio.get("musicbrainz_releasegroupid", [None])[0]
            if not key:
                key = os.path.dirname(filepath)
        except Exception:
            key = os.path.dirname(filepath)
        albums[key].append(filepath)
    return albums

def process_album(files, whitelist):
    first = FLAC(files[0])
    release_group_id = first.get("musicbrainz_releasegroupid", [None])[0]
    artist = first.get("albumartist", first.get("artist", [""]))[0]
    album  = first.get("album", [""])[0]

    print(f"  Album: {artist} – {album}")

    existing = []
    for f in files:
        audio = FLAC(f)
        for g in filter_whitelist(audio.get("genre", []), whitelist):
            if g.lower() not in {x.lower() for x in existing}:
                existing.append(g)

    if len(existing) >= MAX_GENRES:
        print(f"  → Bereits {len(existing)} Genres vorhanden, übersprungen")
        return 0

    new_genres = resolve_album_genres(release_group_id, artist, album, whitelist)

    final = list(existing)
    for g in new_genres:
        if g.lower() not in {x.lower() for x in final} and len(final) < MAX_GENRES:
            final.append(g)

    if not final:
        print(f"  → Keine Genres gefunden")
        return 0

    if set(g.lower() for g in final) == set(g.lower() for g in existing):
        print(f"  → Keine neuen Genres, übersprungen")
        return 0

    for filepath in files:
        audio = FLAC(filepath)
        audio["genre"] = final
        audio.save()

    print(f"  → Genres: {final} ({len(files)} Tracks)")
    return len(files)

def main():
    force = "--force" in sys.argv

    whitelist = load_whitelist(WHITELIST_TXT)
    print(f"Whitelist geladen: {len(whitelist)} Genres")

    index = load_index(INDEX_FILE)
    if force:
        print("--force: Index wird ignoriert, alle Alben werden verarbeitet\n")
    else:
        print(f"Index geladen: {len(index)} bereits verarbeitete Alben\n")

    flac_files = []
    for root, _, files in os.walk(BIBLIOTHEK):
        for f in files:
            if f.lower().endswith(".flac"):
                flac_files.append(os.path.join(root, f))

    print(f"{len(flac_files)} FLAC-Dateien gefunden\n")

    albums = group_by_album(flac_files)
    print(f"{len(albums)} Alben gefunden\n")

    changed_tracks = 0
    skipped_albums = 0

    for i, (key, files) in enumerate(albums.items(), 1):
        print(f"[{i}/{len(albums)}]")

        if not force and key in index:
            artist = ""
            album  = ""
            try:
                first = FLAC(files[0])
                artist = first.get("albumartist", first.get("artist", [""]))[0]
                album  = first.get("album", [""])[0]
            except Exception:
                pass
            print(f"  Album: {artist} – {album}")
            print(f"  → Bereits im Index, übersprungen")
            skipped_albums += 1
            continue

        try:
            n = process_album(files, whitelist)
            if n:
                changed_tracks += n
            else:
                skipped_albums += 1
            # Auch bei 0 Änderungen in Index schreiben (Album wurde geprüft)
            save_to_index(INDEX_FILE, key)
        except Exception as e:
            print(f"  Fehler: {e}")

    print(f"\nFertig! Geänderte Tracks: {changed_tracks}, Übersprungene Alben: {skipped_albums}")
    print(f"Index gespeichert unter: {INDEX_FILE}")

if __name__ == "__main__":
    main()
