# flac-genre-tagger
Taggt FLAC-Dateien automatisch mit Genres aus MusicBrainz und Last.fm, gefiltert nach einer eigenen Whitelist. Erstellt mithilfe von Anthropic Claude.

## Hintergrund
Viele Musik-Player und Streaming-Server wie Navidrome ermöglichen das Filtern und Browsen nach Genres — aber nur wenn die Dateien sauber getaggt sind. Tools wie MusicBrainz Picard schreiben Genres oft als einzelnen Tag mit Trennzeichen (`GENRE=Rock, Metal`), anstatt als separate Vorbis Comments. Außerdem sind die verfügbaren Genres auf MusicBrainz häufig lückenhaft oder zu spezifisch.

Dieses Script löst beides: Es holt Genres aus MusicBrainz und Last.fm, filtert sie gegen eine eigene Whitelist und schreibt sie als separate Tags in die Dateien.

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
4. Mailadresse für MusicBrainz-Abfragen angeben:
```python
musicbrainzngs.set_useragent("genre-tagger", "1.0", "deine@email.dev")
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

## Track-weises Tagging
Standardmäßig werden Genres pro Album vergeben. Wer stattdessen jeden Track einzeln taggen möchte, muss folgende Änderungen vornehmen:

1. `group_by_album()` entfernen — stattdessen direkt über alle Dateien iterieren
2. `process_album()` zu `process_track()` umbenennen — `artist` und `album` aus dem jeweiligen Track lesen statt vom ersten Track des Albums
3. In `resolve_album_genres()` die Last.fm-Abfrage von `get_album()` auf `get_track()` umstellen

## Index
Verarbeitete Alben werden in `~/.genre_tagger_done.txt` gespeichert (eine Release-Group-ID oder ein Ordnerpfad pro Zeile). Die Datei löschen oder `--force` nutzen, um alles neu zu verarbeiten.

## Limitationen
- nur FLAC wird unterstützt — kein MP3, Opus etc.
- die Qualität der Genres hängt von MusicBrainz- und Last.fm-Daten ab — bei weniger bekannten Künstlern kann das Ergebnis lückenhaft sein
- MusicBrainz und Last.fm haben Rate Limits — bei sehr großen Bibliotheken kann das Script entsprechend lange laufen
- Alben ohne MusicBrainz-Release-Group-ID werden nach Ordnerpfad gruppiert, was bei ungewöhnlichen Ordnerstrukturen zu falschen Gruppierungen führen kann

## Lizenz
[MIT-Lizenz](https://github.com/svetixoxo/flac-genre-tagger/blob/main/LICENSE)
