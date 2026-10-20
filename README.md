# Kalender-PDF

Python-CLI, das mehrere iCalendar-Quellen zu einem **druckfertigen A2-Jahreskalender** zusammenführt.

- Ein Kalenderjahr pro A2-Seite
- Monate als Spalten, Tage 1–31 als Zeilen
- Nicht existente Tage (z. B. 31. Februar) bleiben leer
- Ganztägige und mehrtägige Termine (Ferien) als Balken; timed Events mit Uhrzeit
- Korrekte Behandlung exklusiver `DTEND`-Daten bei ganztägigen iCal-Events

Docs: [Anforderungen](docs/requirements.md) · [Projektkontext](docs/project-context.md)

## Orientierung

Standard ist **A2 Querformat (`landscape`)**: 12 Monatsspalten brauchen horizontale Breite; 31 Zeilen passen in die Höhe von A2 quer (594 × 420 mm). Portrait ist über die Konfiguration wählbar, liefert aber schmalere Monatsspalten.

## Einrichtung (neues System)

Voraussetzung: Python ≥ 3.10.

Empfohlen ist eine **lokale virtuelle Umgebung** (`.venv`). Das Verzeichnis ist in `.gitignore` und gehört nicht ins Repo.

### 1. Virtuelle Umgebung anlegen

```bash
python -m venv .venv
```

(Unter Linux/macOS ggf. `python3` statt `python`.)

### 2. Aktivieren

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\Activate.ps1
```

Falls die Ausführung von Skripten blockiert wird:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Danach `Activate.ps1` erneut ausführen.

**Linux / macOS (bash/zsh):**

```bash
source .venv/bin/activate
```

### 3. Paket installieren (erforderlich)

Nur Aktivieren reicht nicht — ohne Installation gibt es keinen Befehl `kalender-pdf`. Im aktivierten venv:

```bash
python -m pip install -U pip   # optional
python -m pip install -e .
```

`-e .` installiert das Projekt editierbar und legt das Console-Skript `kalender-pdf` an.

### 4. Ersten Lauf testen

```bash
kalender-pdf -c config/example.yaml
```

Falls `kalender-pdf` nicht gefunden wird (z. B. ohne Console-Skript-Pfad):

```bash
python -m kalender_pdf -c config/example.yaml
```

### Alternative ohne venv

```bash
python -m pip install -e .
kalender-pdf -c config/example.yaml
```

## Tägliche Nutzung

Im Projektverzeichnis venv aktivieren, dann ausführen:

```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate

kalender-pdf -c config/example.yaml
```

Jahr oder Ausgabepfad überschreiben:

```bash
kalender-pdf -c config/example.yaml --year 2026 -o output/kalender-2026.pdf
```

Fallback ohne Console-Skript: `python -m kalender_pdf -c config/example.yaml`.

Bei unerreichbarer oder ungültiger Quelle bricht das Tool mit einer klaren Fehlermeldung ab (kein stilles Überspringen).

## Konfiguration

Beispiel: [`config/example.yaml`](config/example.yaml)

Wichtige Felder:

| Feld | Bedeutung |
|------|-----------|
| `year` | Kalenderjahr |
| `output` | Ziel-PDF |
| `layout.orientation` | `landscape` (empfohlen) oder `portrait` |
| `layout.timezone` | Anzeige-Zeitzone (Standard `Europe/Berlin`) |
| `sources[]` | Name, `url` oder `path`, `style` (Farbe, Schrift, `as_bar`, …) |

Weitere Quellen nur in der YAML ergänzen — kein Code nötig.

## Architektur

```
src/kalender_pdf/
  config.py       # YAML laden / validieren
  ical_loader.py  # Abruf, Parsing, RRULE-Expansion
  events.py       # gemeinsames Event-Modell
  pdf_renderer.py # A2-Raster mit ReportLab
  cli.py          # Einstieg
```

iCal-Verarbeitung und PDF-Rendering sind getrennt, damit Quellen und Layout unabhängig weiterentwickelt werden können.

## Beispielquellen (ChurchTools)

Die Datei `config/example.yaml` enthält:

1. KAKI Gottesdienste  
2. KAKI Kinder- und Jugendarbeit  
3. KAKI sonstige Veranstaltungen  
4. VG Ferien und Feiertage (Balken-Stil)  
5. VG Veranstaltungen  

## Tests

Im aktivierten venv:

```bash
python -m pip install -e ".[dev]"
pytest
```

## Lizenz

MIT
