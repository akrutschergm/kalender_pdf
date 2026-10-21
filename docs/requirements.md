# Anforderungen: A2-Jahreskalender-PDF aus iCalendar

Stand: 2026-10-21

## Ziel

Ein ausführbares Python-Tool, das aus mehreren iCalendar-Quellen einen druckfertigen Jahreskalender als PDF erzeugt. Standard ist A2 im Querformat.

## Kalenderlayout

- Ein Kalenderjahr pro PDF-Seite.
- `layout.page_size` wählt das Seitenformat: A0, A1, A2, A3, A4, A5 oder A6. Standard ist A2. Die Ausrichtung ist `landscape` oder `portrait`.
- Die Monate stehen nebeneinander, die Tage 1 bis 31 untereinander.
- Tage, die es in einem Monat nicht gibt (zum Beispiel der 30. Februar oder der 31. April), bleiben leer. Unter diesen Tagen wird kein unterer Rahmen gezeichnet; die Spalte endet mit dem letzten existierenden Tag.
- `empty_day_bg_color` ist optional. Ohne Angabe erhalten diese Tage keinen Hintergrund. Mit Angabe wird die Farbe gefüllt.
- `alternate_month_bg_color` ist optional. Gerade Monate (Februar, April, …) erhalten diese Hintergrundfarbe. Samstage und Sonntage behalten in allen Monaten `weekend_bg_color`.
- Ist `alternate_month_bg_color` gesetzt, entfallen die senkrechten Linien, auch an der Spalte mit den Tageszahlen. Es bleiben die waagerechten Trennlinien.
- Ohne diese Farbe bleibt der einheitliche Hintergrund mit senkrechtem Raster.
- Das Layout soll für den Ausdruck gut lesbar sein und die Seitenfläche sinnvoll nutzen.

## iCalendar-Quellen und Darstellung

- Mehrere iCalendar-Quellen werden unterstützt.
- Die Quellen sind konfigurierbar (z. B. Datei mit Name, Dateipfad oder URL und Darstellungsregeln).
- Pro Quelle lassen sich Schriftstil, Schriftgröße und Farbe festlegen. Der konfigurierte Stil wird verwendet, auch fett und kursiv.
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

- Ob ein Kalender Feiertage enthält, legt der Eintrag `holidays: true` auf der Quelle fest. Die Kennzeichnung gilt für den ganzen Kalender, nicht für einzelne Termine.
- In einem so markierten Kalender erscheinen eintägige Ganztagestermine in der Wochentagszeile. Sie werden nicht zusätzlich als Text in der Zelle wiederholt.
- Mehrtägige Ganztagestermine desselben Kalenders folgen der Darstellung für mehrtägige Termine (Balken und Strich), nicht der Wochentagszeile.
- Beispiel: `Do Neujahrstag`
- Mehrere Feiertage am selben Tag werden mit Bindestrich voneinander getrennt. Zwischen Wochentag und Feiertag steht kein Bindestrich.
- Beispiel bei zwei Einträgen: `Do Neujahrstag - Zweiter Feiertag`
- Die Reihenfolge ist die konfigurierte Reihenfolge der Kalender, und innerhalb eines Kalenders die Reihenfolge der Termine.
- Das Wochentagskürzel steht links und bleibt frei. Feiertagsnamen und übrige Termine beginnen rechts davon auf derselben Einzugslinie.
- Feiertage stehen in der ersten Zeile. Gibt es an dem Tag keinen Feiertag, nutzt der erste Termin diese Zeile neben dem Wochentag.

### Mehrtägige Termine

- Balken und Strich gelten für jeden Termin, der mehr als einen Kalendertag umfasst, ganztägig oder mit Uhrzeit. Beides sieht gleich aus.
- Liegt eine Startuhrzeit vor, erscheint sie im Balken. Die Enduhrzeit wird nicht angezeigt.
- Der Konfigurationseintrag `as_bar` entfällt.
- Leere Fortsetzungsbalken an Folgetagen entfallen.
- Am ersten Tag des Termins und zusätzlich am Ersten jedes weiteren betroffenen Monats: waagerechter Balken mit dem Termintext.
- Vom waagerechten Balken an läuft ein senkrechter Strich durch die Zelle dieses Tages weiter bis zum letzten Tag des Termins. An den Folgetagen füllt der Strich die ganze Tageszeile. Die Breite beträgt etwa ein Sechzehntel der Zeilenhöhe.
- Monate sind Spalten. Der Strich läuft innerhalb einer Monatsspalte von Tag zu Tag. Am Ersten eines Folgemonats steht erneut der waagerechte Balken mit Text; der Strich setzt darunter in dieser Spalte fort.
- Striche stehen am rechten Zellenrand, mit etwas Abstand zum Rand. Mehrere gleichzeitige mehrtägige Termine stehen mit Abstand nebeneinander.
- Überlagerte mehrtägige Termine werden nach früherem Anfangsdatum sortiert, bei gleichem Anfang nach späterem Endedatum. Der erste in dieser Reihenfolge steht rechts, weitere Striche schließen nach links an.
- Termine der betroffenen Tage enden vor den Strichen, damit kein Strich sie kreuzt. Der waagerechte Balken endet links von bereits laufenden Strichen anderer Termine; der eigene Strich setzt an seinem rechten Ende an.

## Umsetzung

- Sprache: Python.
- iCalendar-Lesen/-Verarbeitung getrennt von der PDF-Erzeugung (Quellen und Layout unabhängig anpassbar).
- Geeignete Bibliotheken für iCal-Import und PDF (ReportLab als Kandidat für maßgeschneidertes Raster).
- Konfiguration für Kalenderjahr, Seitenformat (A0–A6), Ausrichtung, Quellen und Formatierung.
- Verständliche Fehlermeldungen, wenn eine Quelle nicht erreichbar oder ungültig ist.
- Kurzes README: Installation, Konfiguration, PDF-Erzeugung.

## Erwartetes Ergebnis

Ausführbares, übersichtlich strukturiertes Python-Projekt mit Beispielkonfiguration und einem Befehl zum Erzeugen des Jahreskalenders als PDF.

## Kalender-Quellen (Beispielkonfiguration)

Die Liste entspricht `config/example.yaml`.

| Name | URL |
|------|-----|
| KAKI Gottesdienste | `https://vg-sh.church.tools/?q=churchcal/ical&security=yGGggm3rkhMKy9Dj3pyvETDe9iM5jDca&id=193` |
| KAKI Kinder- und Jugendarbeit | `https://vg-sh.church.tools/?q=churchcal/ical&security=mims1ENTX9aq6ayQuO0UgTzn8NBV1XbY&id=199` |
| KAKI sonstige Veranstaltungen | `https://vg-sh.church.tools/?q=churchcal/ical&security=rkKPocYsVSvjrNABbbplTSx8jxEspQmU&id=196` |
| KAKI Vorstand | `https://vg-sh.church.tools/?q=churchcal/ical&security=YqWxP8WtvIvt9q7FwoxyCitMFEO6xyVE&id=205` |
| KAKI Chor 82 (in der Beispielkonfiguration deaktiviert) | `https://vg-sh.church.tools/?q=churchcal/ical&security=kB2eIKpvg1UQmaqTLlDmPpKymvVVW980&id=321` |
| VG Ferien und Feiertage | `https://vg-sh.church.tools/?q=churchcal/ical&security=gLf1lXx2sGcke8hCZPaPEWfaT3JwhfZn&id=34` |
| VG Veranstaltungen | `https://vg-sh.church.tools/?q=churchcal/ical&security=4oYZByr6ImioJp2vXf5IkadVYWEU3etp&id=263` |
| EC Veranstaltungen | `https://vg-sh.church.tools/?q=churchcal/ical&security=mQRqqvEMJnGCZijcYpkCDqTBhCvPyucP&id=308` |
