# genre-tagger
Taggt Audiodateien automatisch mit Genres aus MusicBrainz und Last.fm, gefiltert nach einer eigenen Whitelist. Erstellt mithilfe von Anthropic Claude.

## Hintergrund
Viele Musik-Player und Streaming-Server wie Navidrome ermöglichen das Filtern und Browsen nach Genres, aber nur, wenn die Dateien sauber getaggt sind. Tools wie [MusicBrainz Picard](https://github.com/metabrainz/picard) schreiben Genres oft als einzelnen Tag mit Trennzeichen (`GENRE=Rock, Metal`), anstatt als separate Vorbis Comments (dies ließe sich in Picard zwar umstellen, allerdings funktionierte das bei mir nicht zuverlässig). Außerdem sind die verfügbaren Genres auf MusicBrainz häufig lückenhaft oder zu spezifisch, bei Last.fm herrscht in der Regel großes Chaos.

Dieses Skript löst beides: Es holt Genres aus MusicBrainz und Last.fm, filtert sie gegen eine eigene Whitelist und schreibt sie als separate Tags in die Dateien.

## Funktionen
- Genres werden pro **Album** vergeben (nicht pro Track) für Konsistenz
- Quellen: **MusicBrainz** zuerst, dann **Last.fm** als Fallback – erst Album, dann Artist
- filtert Genres anhand einer selbst definierten **Whitelist**
- **Fuzzy-Matching** – ähnliche Genres werden automatisch auf den passenden Whitelist-Eintrag normalisiert (z.B. `Post Punk` → `Post-Punk`)
- schreibt jedes Genre als **separaten Tag** (Vorbis Comment, ID3, etc.)
- **überschreibt keine** vorhandenen gültigen Genres – ergänzt nur bis zum konfigurierten Maximum
- führt einen **Index** bereits verarbeiteter Alben, um diese beim nächsten Durchlauf zu überspringen
- `--force`-Flag, um alle Alben unabhängig vom Index neu zu verarbeiten
- `--dry-run`-Flag, um Änderungen nur anzuzeigen ohne Dateien zu verändern
- `--per-track`-Flag, um Genres pro Track statt pro Album zu vergeben

## Unterstützte Formate
FLAC, MP3 (ID3v2.4), M4A, Ogg, Opus

> **Hinweis:** Bei MP3 mit ID3v2.3 funktionieren Multi-Tags nicht zuverlässig. Es wird empfohlen, ID3v2.4 zu verwenden.

## Voraussetzungen
```zsh
sudo pacman -S python-musicbrainzngs python-pylast python-mutagen
```
Zudem wird (für das Fallback) ein kostenloser [Last.fm-API-Key](https://www.last.fm/api/account/create) benötigt.

## Einrichtung
1. Repo klonen und Abhängigkeiten installieren
2. `genres_whitelist.txt` in den Musikbibliothek-Ordner legen (oder den Pfad im Skript anpassen)
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
MAX_GENRES    = 3   # Maximale Anzahl Genres pro Album
FUZZY_CUTOFF  = 0.82  # Ähnlichkeitsschwelle für Fuzzy-Matching (0.0–1.0)
```

## Verwendung
```zsh
# Normaler Durchlauf – bereits verarbeitete Alben werden übersprungen
python tag_genres.py

# Alle Alben neu verarbeiten (Index wird ignoriert)
python tag_genres.py --force

# Nur anzeigen was geändert würde, ohne Dateien zu verändern
python tag_genres.py --dry-run

# Genres pro Track statt pro Album vergeben
python tag_genres.py --per-track

# Flags lassen sich kombinieren
python tag_genres.py --dry-run --per-track
python tag_genres.py --force --dry-run
```

## Whitelist
`genres_whitelist.txt` enthält ein Genre pro Zeile. Nur Genres die in dieser Liste stehen (Groß-/Kleinschreibung egal) werden in die Dateien geschrieben. Die Datei kann jederzeit erweitert oder angepasst werden.

Beispiel:
```
Alternative Metal
Dark Wave
Gothic Rock
Industrial
Symphonic Metal
...
```

## Fuzzy-Matching
Wenn ein gefundenes Genre nicht exakt in der Whitelist steht, versucht das Skript automatisch den ähnlichsten Whitelist-Eintrag zu finden. Die Ähnlichkeitsschwelle lässt sich über `FUZZY_CUTOFF` einstellen – höhere Werte bedeuten strengeres Matching.

Beispiele:
- `Post Punk` → `Post-Punk`
- `Hip Hop` → `Hip-Hop`
- `death metal` → `Death Metal`

Im `--dry-run`-Modus werden alle Fuzzy-Matches mit Ähnlichkeitswert angezeigt.

## Funktionsweise
1. alle Audiodateien werden nach MusicBrainz-Release-Group-ID gruppiert (Fallback: Ordnerpfad, wenn keine ID vorhanden)
2. pro Album werden vorhandene gültige Genres geprüft – wenn `MAX_GENRES` erreicht, wird das Album übersprungen
3. fehlende Genres werden von MusicBrainz, dann Last.fm (Album, dann Artist) geholt
4. nur Whitelist-konforme Genres werden ergänzt (inkl. Fuzzy-Matching), maximal bis `MAX_GENRES`
5. alle Tracks des Albums erhalten dieselben Genres
6. das Album wird in den Index eingetragen und beim nächsten Durchlauf übersprungen

## Index
Verarbeitete Alben werden in `~/.genre_tagger_done.txt` gespeichert (eine Release-Group-ID oder ein Ordnerpfad pro Zeile). Die Datei löschen oder `--force` nutzen, um alles neu zu verarbeiten.

## Limitationen
- die Qualität der Genres hängt von MusicBrainz- und Last.fm-Daten ab – bei weniger bekannten Künstlern kann das Ergebnis lückenhaft sein
- MusicBrainz und Last.fm haben Rate-Limits – bei sehr großen Bibliotheken kann das Skript entsprechend lange laufen
- Alben ohne MusicBrainz-Release-Group-ID werden nach Ordnerpfad gruppiert, was bei ungewöhnlichen Ordnerstrukturen zu falschen Gruppierungen führen kann
- MP3-Unterstützung setzt ID3v2.4 voraus

## Geplante Funktionen
- **Logging** – Änderungen werden zusätzlich in eine Logdatei geschrieben
- **interaktiver Modus** – bei Genres, die nicht in der Whitelist stehen, wird nachgefragt, ob sie hinzugefügt werden sollen

## Lizenz
[MIT-Lizenz](https://github.com/svetixoxo/flac-genre-tagger/blob/main/LICENSE)
