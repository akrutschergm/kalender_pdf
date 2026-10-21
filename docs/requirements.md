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
- `day_font_size` setzt die Schriftgröße der Tageszahlen, `weekday_font_size` die der Wochentagskürzel in der Zelle. Die Kürzel stehen links und sind in der Zeile vertikal zentriert, wie die Tageszahlen. Feiertagsnamen nutzen `all_day_font_size` ihrer Quelle, sonst `font_size`.
- In der Zeile der Legende steht rechtsbündig Datum und Uhrzeit der Erstellung, zum Beispiel `Stand: 21.10.2026 12:52`. Die Zeit folgt `layout.timezone`.
- Das Layout soll für den Ausdruck gut lesbar sein und die Seitenfläche sinnvoll nutzen.

## iCalendar-Quellen und Darstellung

- Mehrere iCalendar-Quellen werden unterstützt.
- Die Quellen sind konfigurierbar (z. B. Datei mit Name, Dateipfad oder URL und Darstellungsregeln).
- Eine lokale Datei kann als `url: file://feiertage_2027.ics` angegeben werden. Der Pfad gilt relativ zum Ordner der Konfigurationsdatei. Absolute `file:///`-Pfade bleiben absolut.
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
- In einem so markierten Kalender erscheinen eintägige Ganztagestermine als erste Zeile der Tageszelle. Sie werden nicht zusätzlich als weiterer Text in der Zelle wiederholt.
- Diese Tage erhalten denselben Hintergrund wie Wochenenden, `layout.weekend_bg_color`.
- Mehrtägige Ganztagestermine desselben Kalenders folgen der Darstellung für mehrtägige Termine (Balken und Strich), nicht der ersten Zeile.
- Beispiel: `Neujahrstag`
- Mehrere Feiertage am selben Tag werden mit Bindestrich voneinander getrennt.
- Beispiel bei zwei Einträgen: `Neujahrstag - Zweiter Feiertag`
- Die Reihenfolge ist die konfigurierte Reihenfolge der Kalender, und innerhalb eines Kalenders die Reihenfolge der Termine.
- Das Wochentagskürzel steht links, vertikal in der Zeile zentriert, und bleibt frei. Feiertagsnamen und übrige Termine beginnen rechts davon auf derselben Einzugslinie.
- Feiertage sind die erste Inhaltszeile und stehen nicht in derselben Zeile wie das Wochentagskürzel. Gibt es an dem Tag keinen Feiertag, beginnt der erste Termin oben in der Zelle.
- Die Feiertagsnamen eines Tages sind ein gemeinsamer Text. Er wird wie ein Termin umbrochen oder auf eine Zeile gekürzt.
- Lange Termintexte werden standardmäßig mehrzeilig dargestellt, höchstens `layout.max_event_lines` Zeilen (Standard 3). Die letzte Zeile endet mit Auslassung, wenn der Text nicht vollständig passt. Pro Quelle schaltet `wrap_text: false` auf eine einzelne Zeile.
- Reicht die Höhe einer Tageszeile für die Termine nicht, wird diese Zeile so weit gedehnt wie nötig. Die übrigen Tageszeilen werden anteilig verkleinert.
- Passt diese Aufteilung nicht auf die Seite, werden alle Tageszeilen anteilig verkleinert, bis sie auf das Blatt passen.
- `layout.max_events_per_cell` begrenzt, wie viele Balken und Texttermine in einer Zelle gezeichnet werden (Standard 6). Feiertage in der ersten Zeile zählen nicht mit. Weitere Termine werden weggelassen.
- Termine, die wegen dieser Grenze oder wegen zu geringer Zeilenhöhe nicht in die Zelle passen, werden durch `...` in der rechten unteren Ecke angezeigt. Das Zeichen liegt über Terminen, Balken und Strichen.

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
