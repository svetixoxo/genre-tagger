# flac-genre-tagger

Taggt FLAC-Dateien automatisch mit Genres aus MusicBrainz und Last.fm, gefiltert nach einer eigenen Whitelist. Erstellt mithilfe von Anthropic Claude.

## Funktionen

- Genres werden pro **Album** vergeben (nicht pro Track) für Konsistenz
- Quellen: **MusicBrainz** zuerst, dann **Last.fm Album**, dann **Last.fm Artist** als Fallback
- Filtert Genres anhand einer selbst definierten **Whitelist**
- Schreibt jedes Genre als **separaten Vorbis Comment** (z.B. `GENRE=Rock`, `GENRE=Metal`)
- **Überschreibt keine** vorhandenen gültigen Genres — ergänzt nur bis zum konfigurierten Maximum
- Führt einen **Index** bereits verarbeiteter Alben, um diese beim nächsten Durchlauf zu überspringen
- `--force` Flag um alle Alben unabhängig vom Index neu zu verarbeiten

## Voraussetzungen

```zsh
sudo pacman -S python-musicbrainzngs python-pylast python-mutagen
```

Zudem wird (für das Fallback) ein kostenloser [Last.fm-API-Key](https://www.last.fm/api/account/create) benötigt.

## Einrichtung

1. Repo klonen und Abhängigkeiten installieren
2. `genres_whitelist.txt` in den Musikbibliothek-Ordner legen (oder den Pfad im Script anpassen)
3. Last.fm-API-Key direkt in `tag_genres.py` eintragen:

```python
LASTFM_KEY = "dein_api_key"
```

## Konfiguration

Am Anfang von `tag_genres.py` diese Variablen an das eigene Setup anpassen:

```python
BIBLIOTHEK    = os.path.expanduser("~/Musik/Bibliothek")  # Pfad zur Musikbibliothek
WHITELIST_TXT = os.path.expanduser("~/Musik/Bibliothek/genres_whitelist.txt")
INDEX_FILE    = os.path.expanduser("~/.genre_tagger_done.txt")
MAX_GENRES    = 5  # Maximale Anzahl Genres pro Album
```

## Verwendung

```zsh
# Normaler Durchlauf — bereits verarbeitete Alben werden übersprungen
python tag_genres.py

# Alle Alben neu verarbeiten (Index wird ignoriert)
python tag_genres.py --force
```

## Whitelist

`genres_whitelist.txt` enthält ein Genre pro Zeile. Nur Genres die in dieser Liste stehen (Groß-/Kleinschreibung egal) werden in die Dateien geschrieben. Die Datei kann jederzeit erweitert oder angepasst werden.

Beispiel:
```
Rock
Metal
Metalcore
Post-Hardcore
Doom Metal
...
```

## Funktionsweise

1. alle FLAC-Dateien werden nach MusicBrainz-Release-Group-ID gruppiert (Fallback: Ordnerpfad, wenn keine ID vorhanden)
2. pro Album werden vorhandene gültige Genres geprüft — wenn `MAX_GENRES` erreicht, wird das Album übersprungen
3. fehlende Genres werden von MusicBrainz, dann Last.fm (Album, dann Artist) geholt
4. nur Whitelist-konforme Genres werden ergänzt, maximal bis `MAX_GENRES`
5. alle Tracks des Albums erhalten dieselben Genres
6. das Album wird in den Index eingetragen und beim nächsten Durchlauf übersprungen

## Index

Verarbeitete Alben werden in `~/.genre_tagger_done.txt` gespeichert (eine Release-Group-ID oder ein Ordnerpfad pro Zeile). Die Datei löschen oder `--force` nutzen, um alles neu zu verarbeiten.

## Lizenz
[MIT-Lizenz](https://github.com/svetixoxo/flac-genre-tagger/blob/main/LICENSE)
