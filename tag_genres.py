#!/usr/bin/env python3

import os
import sys
import time
import musicbrainzngs
import pylast
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen import File as MutagenFile
from collections import defaultdict

# ── Konfiguration ──────────────────────────────────────────────────────────────
BIBLIOTHEK    = os.path.expanduser("~/Musik/Bibliothek")
WHITELIST_TXT = os.path.expanduser("~/Musik/Bibliothek/genres_whitelist.txt")
INDEX_FILE    = os.path.expanduser("~/.genre_tagger_done.txt")
LASTFM_KEY    = ""  # Last.fm API-Key hier eintragen
MAX_GENRES    = 3
FUZZY_CUTOFF  = 0.82  # Ähnlichkeitsschwelle für Fuzzy-Matching (0.0–1.0)
SUPPORTED_EXT = (".flac", ".mp3", ".m4a", ".ogg", ".opus")
# ──────────────────────────────────────────────────────────────────────────────

if not LASTFM_KEY:
    print("Fehler: LASTFM_KEY ist nicht gesetzt. Bitte in tag_genres.py eintragen.")
    sys.exit(1)

musicbrainzngs.set_useragent("genre-tagger", "1.0", "deine@email.dev")
lastfm = pylast.LastFMNetwork(api_key=LASTFM_KEY)

# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

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

def fuzzy_match(genre, whitelist):
    """Gibt den besten Whitelist-Treffer zurück, wenn Ähnlichkeit >= FUZZY_CUTOFF."""
    from difflib import SequenceMatcher
    g = genre.strip().lower()
    best_score = 0
    best_match = None
    for wl_key, wl_val in whitelist.items():
        score = SequenceMatcher(None, g, wl_key).ratio()
        if score > best_score:
            best_score = score
            best_match = wl_val
    if best_score >= FUZZY_CUTOFF:
        return best_match, best_score
    return None, best_score

def filter_whitelist(genres, whitelist, dry=False):
    seen = set()
    result = []
    for g in genres:
        key = g.strip().lower()
        if key in whitelist and key not in seen:
            result.append(whitelist[key])
            seen.add(key)
        else:
            match, score = fuzzy_match(g, whitelist)
            if match and match.lower() not in seen:
                if dry:
                    print(f"    [fuzzy] '{g}' → '{match}' ({score:.0%})")
                result.append(match)
                seen.add(match.lower())
    return result

# ── Audio-Abstraktion ─────────────────────────────────────────────────────────

def read_tags(filepath):
    """Gibt (genres, artist, albumartist, album, mb_rgid) zurück."""
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".flac":
        audio = FLAC(filepath)
        return (
            audio.get("genre", []),
            (audio.get("artist", [""]))[0],
            (audio.get("albumartist", audio.get("artist", [""]))[0]),
            (audio.get("album", [""]))[0],
            (audio.get("musicbrainz_releasegroupid", [None]))[0],
        )
    elif ext == ".mp3":
        audio = MP3(filepath)
        tags = audio.tags
        def id3(key): return [str(v) for v in tags.getall(key)] if tags else []
        genres = id3("TCON")
        return (
            genres,
            str(tags.get("TPE1", "")),
            str(tags.get("TPE2", tags.get("TPE1", ""))),
            str(tags.get("TALB", "")),
            str(tags.get("TXXX:MusicBrainz Release Group Id", "")) or None,
        )
    elif ext == ".m4a":
        audio = MP4(filepath)
        t = audio.tags or {}
        return (
            t.get("\xa9gen", []),
            str(t.get("\xa9ART", [""])[0]),
            str(t.get("aART", t.get("\xa9ART", [""]))[0]),
            str(t.get("\xa9alb", [""])[0]),
            str(t.get("----:com.apple.iTunes:MusicBrainz Release Group Id", [b""])[0].decode("utf-8", errors="ignore")) or None,
        )
    else:  # ogg, opus
        audio = MutagenFile(filepath)
        if audio is None:
            return [], "", "", "", None
        return (
            audio.get("genre", []),
            (audio.get("artist", [""]))[0],
            (audio.get("albumartist", audio.get("artist", [""]))[0]),
            (audio.get("album", [""]))[0],
            (audio.get("musicbrainz_releasegroupid", [None]))[0],
        )

def write_genres(filepath, genres, dry=False):
    if dry:
        return
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".flac":
        audio = FLAC(filepath)
        audio["genre"] = genres
        audio.save()
    elif ext == ".mp3":
        from mutagen.id3 import ID3, TCON
        audio = MP3(filepath)
        if audio.tags is None:
            audio.add_tags()
        audio.tags["TCON"] = TCON(encoding=3, text=genres)
        audio.save(v2_version=4)
    elif ext == ".m4a":
        audio = MP4(filepath)
        if audio.tags is None:
            audio.add_tags()
        audio.tags["\xa9gen"] = genres
        audio.save()
    else:  # ogg, opus
        audio = MutagenFile(filepath)
        if audio is None:
            return
        audio["genre"] = genres
        audio.save()

# ── API-Abfragen ──────────────────────────────────────────────────────────────

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

def get_lastfm_track_genres(artist, title):
    try:
        t = lastfm.get_track(artist, title)
        tags = t.get_top_tags(limit=10)
        return [t.item.name for t in tags]
    except Exception:
        return []

def resolve_genres(release_group_id, artist, album, whitelist, dry=False, title=None, per_track=False):
    genres = []

    if release_group_id:
        mb = get_mb_genres(release_group_id)
        genres += filter_whitelist(mb, whitelist, dry)
        time.sleep(0.3)

    if per_track and title and len(genres) < MAX_GENRES:
        lfm_track = get_lastfm_track_genres(artist, title)
        for g in filter_whitelist(lfm_track, whitelist, dry):
            if g.lower() not in {x.lower() for x in genres}:
                genres.append(g)
        time.sleep(0.3)
    elif not per_track and artist and album and len(genres) < MAX_GENRES:
        lfm_album = get_lastfm_album_genres(artist, album)
        for g in filter_whitelist(lfm_album, whitelist, dry):
            if g.lower() not in {x.lower() for x in genres}:
                genres.append(g)
        time.sleep(0.3)

    if len(genres) < MAX_GENRES and artist:
        lfm_artist = get_lastfm_artist_genres(artist)
        for g in filter_whitelist(lfm_artist, whitelist, dry):
            if g.lower() not in {x.lower() for x in genres}:
                genres.append(g)
        time.sleep(0.3)

    return genres[:MAX_GENRES]

# ── Verarbeitung ──────────────────────────────────────────────────────────────

def group_files(all_files):
    albums = defaultdict(list)
    for filepath in all_files:
        try:
            genres, artist, albumartist, album, mb_rgid = read_tags(filepath)
            key = mb_rgid if mb_rgid else os.path.dirname(filepath)
        except Exception:
            key = os.path.dirname(filepath)
        albums[key].append(filepath)
    return albums

def process_album(files, whitelist, dry=False):
    genres, artist, albumartist, album, mb_rgid = read_tags(files[0])
    print(f"  Album: {albumartist or artist} – {album}")

    existing = []
    for f in files:
        g, *_ = read_tags(f)
        for genre in filter_whitelist(g, whitelist):
            if genre.lower() not in {x.lower() for x in existing}:
                existing.append(genre)

    if len(existing) >= MAX_GENRES:
        print(f"  → Bereits {len(existing)} Genres vorhanden, übersprungen")
        return 0

    new_genres = resolve_genres(mb_rgid, albumartist or artist, album, whitelist, dry)

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

    action = "[dry-run] würde setzen" if dry else "→ Genres"
    print(f"  {action}: {final} ({len(files)} Tracks)")

    for filepath in files:
        write_genres(filepath, final, dry)

    return 0 if dry else len(files)

def process_track(filepath, whitelist, dry=False):
    genres, artist, albumartist, album, mb_rgid = read_tags(filepath)
    title = ""
    try:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".flac":
            title = FLAC(filepath).get("title", [""])[0]
        elif ext == ".mp3":
            audio = MP3(filepath)
            title = str(audio.tags.get("TIT2", "")) if audio.tags else ""
        elif ext == ".m4a":
            audio = MP4(filepath)
            title = str((audio.tags or {}).get("\xa9nam", [""])[0])
        else:
            audio = MutagenFile(filepath)
            title = audio.get("title", [""])[0] if audio else ""
    except Exception:
        pass

    existing = filter_whitelist(genres, whitelist)

    if len(existing) >= MAX_GENRES:
        return 0

    new_genres = resolve_genres(mb_rgid, albumartist or artist, album, whitelist, dry,
                                title=title, per_track=True)

    final = list(existing)
    for g in new_genres:
        if g.lower() not in {x.lower() for x in final} and len(final) < MAX_GENRES:
            final.append(g)

    if not final or set(g.lower() for g in final) == set(g.lower() for g in existing):
        return 0

    action = "[dry-run] würde setzen" if dry else "→ Genres"
    print(f"  {action}: {final}")

    write_genres(filepath, final, dry)
    return 0 if dry else 1

# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main():
    force     = "--force"     in sys.argv
    dry       = "--dry-run"   in sys.argv
    per_track = "--per-track" in sys.argv

    if dry:
        print("⚠️  dry-run Modus – keine Dateien werden verändert\n")

    whitelist = load_whitelist(WHITELIST_TXT)
    print(f"Whitelist geladen: {len(whitelist)} Genres")

    index = load_index(INDEX_FILE)
    if force:
        print("--force: Index wird ignoriert, alle Alben werden verarbeitet\n")
    else:
        print(f"Index geladen: {len(index)} bereits verarbeitete Einträge\n")

    all_files = []
    for root, _, files in os.walk(BIBLIOTHEK):
        for f in files:
            if f.lower().endswith(SUPPORTED_EXT):
                all_files.append(os.path.join(root, f))

    print(f"{len(all_files)} Audiodateien gefunden\n")

    changed = 0
    skipped = 0

    if per_track:
        for i, filepath in enumerate(all_files, 1):
            print(f"[{i}/{len(all_files)}] {os.path.basename(filepath)}")
            if not force and filepath in index:
                print("  → Bereits im Index, übersprungen")
                skipped += 1
                continue
            try:
                n = process_track(filepath, whitelist, dry)
                changed += n
                if not dry:
                    save_to_index(INDEX_FILE, filepath)
                else:
                    skipped += 1
            except Exception as e:
                print(f"  Fehler: {e}")
    else:
        albums = group_files(all_files)
        print(f"{len(albums)} Alben gefunden\n")

        for i, (key, files) in enumerate(albums.items(), 1):
            print(f"[{i}/{len(albums)}]")
            if not force and key in index:
                try:
                    _, artist, albumartist, album, _ = read_tags(files[0])
                    print(f"  Album: {albumartist or artist} – {album}")
                except Exception:
                    pass
                print("  → Bereits im Index, übersprungen")
                skipped += 1
                continue
            try:
                n = process_album(files, whitelist, dry)
                changed += n
                if not dry:
                    save_to_index(INDEX_FILE, key)
                else:
                    skipped += 1
            except Exception as e:
                print(f"  Fehler: {e}")

    print(f"\nFertig! Geändert: {changed}, Übersprungen: {skipped}")
    if dry:
        print("(dry-run – keine Dateien wurden verändert)")
    else:
        print(f"Index gespeichert unter: {INDEX_FILE}")

if __name__ == "__main__":
    main()
