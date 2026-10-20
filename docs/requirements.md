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
- iCalendar-Datums- und Zeitzonenangaben korrekt auswerten.
- Ganztages- und mehrtägige Termine: exklusiven Endzeitpunkt (`DTEND`) im iCalendar-Sinne beachten (kein zusätzlicher Tag).

### Uhrzeit

- Termine mit Uhrzeit zeigen diese immer an.
- Ganztagestermine haben keine Uhrzeit.
- Der Konfigurationseintrag `show_time` entfällt.

### Ganztagestermine

- Ganztagestermine werden nicht als Kasten dargestellt, sondern als Text ohne Uhrzeit.
- Schriftstil, Schriftgröße und Farbe bleiben pro Quelle konfigurierbar.

### Feiertage

- Ob ein Kalender Feiertage enthält, legt ein Konfigurationseintrag auf Kalenderebene fest. Die Kennzeichnung gilt für den ganzen Kalender, nicht für einzelne Termine.
- In einem so markierten Kalender erscheinen eintägige Ganztagestermine in der Wochentagszeile. Sie werden nicht zusätzlich als Text in der Zelle wiederholt.
- Mehrtägige Ganztagestermine desselben Kalenders folgen der Darstellung für mehrtägige Termine (Balken und Strich), nicht der Wochentagszeile.
- Zwischen Wochentag und Feiertag steht ein Bindestrich als Abstand.
- Beispiel: `Do - Neujahrstag`
- Mehrere Feiertage am selben Tag werden mit Bindestrich aneinandergereiht.
- Beispiel bei zwei Einträgen: `Do - Neujahrstag - Zweiter Feiertag`
- Die Reihenfolge ist die konfigurierte Reihenfolge der Kalender, und innerhalb eines Kalenders die Reihenfolge der Termine.

### Mehrtägige Termine

- Balken und Strich gelten nur für ganztägige Termine, die mehr als einen Tag umfassen. Termine mit Uhrzeit, die über Mitternacht reichen, bleiben normale Termine mit Uhrzeit.
- Der Konfigurationseintrag `as_bar` entfällt.
- Leere Fortsetzungsbalken an Folgetagen entfallen.
- Am ersten Tag des Termins und zusätzlich am Ersten jedes weiteren betroffenen Monats: waagerechter Balken mit dem Termintext.
- Vom waagerechten Balken an läuft ein senkrechter Strich durch die Zelle dieses Tages weiter bis zum letzten Tag des Termins. An den Folgetagen füllt der Strich die ganze Tageszeile. Die Breite beträgt etwa ein Viertel der Zeilenhöhe.
- Monate sind Spalten. Der Strich läuft innerhalb einer Monatsspalte von Tag zu Tag. Am Ersten eines Folgemonats steht erneut der waagerechte Balken mit Text; der Strich setzt darunter in dieser Spalte fort.
- Striche stehen am linken Zellenrand, mit etwas Abstand zum Rand. Mehrere gleichzeitige mehrtägige Termine stehen mit Abstand nebeneinander.
- Überlagerte mehrtägige Termine werden nach früherem Anfangsdatum sortiert, bei gleichem Anfang nach späterem Endedatum. Der erste in dieser Reihenfolge steht links.
- Termine der betroffenen Tage rücken so weit ein, dass kein Strich sie kreuzt. Der waagerechte Balken beginnt rechts neben bereits laufenden Strichen anderer Termine.

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
