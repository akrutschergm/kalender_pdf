# Anforderungen: A2-Jahreskalender-PDF aus iCalendar

Stand: 2026-10-20

## Ziel

Ein ausführbares Python-Tool, das aus mehreren iCalendar-Quellen einen druckfertigen Jahreskalender als PDF im Format A2 erzeugt.

## Kalenderlayout

- Ein Kalenderjahr pro PDF-Seite im A2-Format.
- Die Monate stehen nebeneinander, die Tage 1 bis 31 untereinander.
- Tage, die es in einem Monat nicht gibt, bleiben leer.
- Das Layout soll für den Ausdruck gut lesbar sein und die verfügbare A2-Seitenfläche sinnvoll nutzen.

## iCalendar-Quellen und Darstellung

- Mehrere iCalendar-Quellen werden unterstützt.
- Die Quellen sind konfigurierbar (z. B. Datei mit Name, Dateipfad oder URL und Darstellungsregeln).
- Pro Quelle lassen sich Schriftstil, Schriftgröße und Farbe festlegen.
- Ganztagestermine erhalten eine eigene, konfigurierbare Darstellung (z. B. Feiertage).
- Mehrtägige Termine werden als Balken über die betroffenen Tage dargestellt (z. B. Ferien, Freizeiten).
- iCalendar-Datums- und Zeitzonenangaben korrekt auswerten.
- Ganztages- und mehrtägige Termine: exklusiven Endzeitpunkt (`DTEND`) im iCalendar-Sinne beachten (kein zusätzlicher Tag).

## Umsetzung

- Sprache: Python.
- iCalendar-Lesen/-Verarbeitung getrennt von der PDF-Erzeugung (Quellen und Layout unabhängig anpassbar).
- Geeignete Bibliotheken für iCal-Import und PDF (ReportLab als Kandidat für maßgeschneidertes Raster).
- Konfiguration für Kalenderjahr, A2-Ausrichtung, Quellen und Formatierung.
- Verständliche Fehlermeldungen, wenn eine Quelle nicht erreichbar oder ungültig ist.
- Kurzes README: Installation, Konfiguration, PDF-Erzeugung.

## Erwartetes Ergebnis

Ausführbares, übersichtlich strukturiertes Python-Projekt mit Beispielkonfiguration und einem Befehl zum Erzeugen des Jahreskalenders als A2-PDF.

## Kalender-Quellen (Beispielkonfiguration)

Weitere Quellen werden später hinzugefügt.

| Name | URL |
|------|-----|
| KAKI Gottesdienste | `https://vg-sh.church.tools/?q=churchcal/ical&security=yGGggm3rkhMKy9Dj3pyvETDe9iM5jDca&id=193` |
| KAKI Kinder- und Jugendarbeit | `https://vg-sh.church.tools/?q=churchcal/ical&security=mims1ENTX9aq6ayQuO0UgTzn8NBV1XbY&id=199` |
| KAKI sonstige Veranstaltungen | `https://vg-sh.church.tools/?q=churchcal/ical&security=rkKPocYsVSvjrNABbbplTSx8jxEspQmU&id=196` |
| VG Ferien und Feiertage | `https://vg-sh.church.tools/?q=churchcal/ical&security=gLf1lXx2sGcke8hCZPaPEWfaT3JwhfZn&id=34` |
| VG Veranstaltungen | `https://vg-sh.church.tools/?q=churchcal/ical&security=4oYZByr6ImioJp2vXf5IkadVYWEU3etp&id=263` |
