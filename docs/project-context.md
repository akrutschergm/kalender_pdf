# Projektkontext: Kalender PDF mit Python

Stand: 2026-10-20

## Überblick

Python-CLI `kalender-pdf`, das konfigurierbare iCal-Quellen (ChurchTools) zu einem A2-Jahresraster (Querformat, Monate als Spalten, Tage 1–31 als Zeilen) rendert. iCal-Verarbeitung und PDF-Rendering sind getrennt.

## Repositories und Pfade

| Rolle | Pfad / URL |
|-------|------------|
| GitHub | https://github.com/akrutschergm/kalender_pdf |
| Lokaler Clone (bevorzugt) | `C:\Users\andre\dev\kalender_pdf` |
| Beispielkonfiguration | `config/example.yaml` |
| Beispiel-PDF | `output/kalender-2026.pdf` |

Project Notes und Agent-Context liegen im Cursor Project Store (nicht im Windows-Pfad). Code-Heimat ist das lokale Repo bzw. GitHub.

## Architektur (Ist)

- Paket unter `src/kalender_pdf/` (`config`, `ical_loader`, `events`, `pdf_renderer`, `cli`)
- Einstieg: Console-Script `kalender-pdf` → `kalender_pdf.cli:main`; Fallback `python -m kalender_pdf`
- Abhängigkeiten u. a.: `icalendar`, `recurring-ical-events`, `reportlab`, `PyYAML`, `httpx`, `tzdata`
- Layout: A2 landscape, 12 Monatsspalten

## Lokale Nutzung (Windows, empfohlen)

```powershell
cd C:\Users\andre\dev\kalender_pdf
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
kalender-pdf -c config/example.yaml
```

Wichtig: `Activate.ps1` allein installiert das Paket nicht — ohne `pip install -e .` fehlt `kalender-pdf.exe` in `.venv\Scripts`.

Fallback: `python -m kalender_pdf -c config/example.yaml`  
Bei blockiertem Activate: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` oder Aufruf über `.\.venv\Scripts\python.exe -m kalender_pdf ...`

Details: README (venv-Abschnitt; Draft-PR siehe unten).

## Entscheidungen und Erkenntnisse

- Cloud-Worker auf `agent_temp` konnte anfangs keinen Draft-PR öffnen und später nicht nach GitHub pushen (fehlende `gh`/Token-Credentials).
- Seed auf das echte Repo `akrutschergm/kalender_pdf` mit Cursor-GitHub-Anbindung hat funktioniert (`main`, u. a. Commit `a92af8d`).
- Privater/Self-hosted Worker war in diesem Project mehrfach nicht verbunden — lokal öffnen ≠ Worker gestartet. Direkte Arbeit auf dem Windows-Pfad nur mit laufendem Private Worker.
- Preference: wenn ein privater Worker verfügbar ist, lokal am Clone arbeiten; sonst über GitHub.

## Offene / begleitende Arbeit

- Draft-PR README venv-Setup: https://github.com/akrutschergm/kalender_pdf/pull/1
- Weitere iCal-Quellen später über Config ergänzen (kein Code-Zwang).

## Verwandte Dateien in diesem Store

- [Anforderungen](requirements.md) — Originalspezifikation
