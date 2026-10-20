# Kalender-PDF

Python-CLI, das mehrere iCalendar-Quellen zu einem **druckfertigen A2-Jahreskalender** zusammenführt.

- Ein Kalenderjahr pro A2-Seite
- Monate als Spalten, Tage 1–31 als Zeilen
- Nicht existente Tage (z. B. 31. Februar) bleiben leer
- Ganztägige und mehrtägige Termine (Ferien) als Balken; timed Events mit Uhrzeit
- Korrekte Behandlung exklusiver `DTEND`-Daten bei ganztägigen iCal-Events

## Orientierung

Standard ist **A2 Querformat (`landscape`)**: 12 Monatsspalten brauchen horizontale Breite; 31 Zeilen passen in die Höhe von A2 quer (594 × 420 mm). Portrait ist über die Konfiguration wählbar, liefert aber schmalere Monatsspalten.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Voraussetzungen: Python ≥ 3.10.

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

## PDF erzeugen

```bash
# mit Standard-Config
kalender-pdf

# oder
python -m kalender_pdf -c config/example.yaml

# Jahr / Ausgabe überschreiben
kalender-pdf -c config/example.yaml --year 2026 -o output/kalender-2026.pdf
```

Bei unerreichbarer oder ungültiger Quelle bricht das Tool mit einer klaren Fehlermeldung ab (kein stilles Überspringen).

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

```bash
pip install -e ".[dev]"
pytest
```

## Lizenz

MIT
