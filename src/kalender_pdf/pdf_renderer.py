"""A2-Jahreskalender mit ReportLab: Monate als Spalten, Tage 1–31 als Zeilen."""

from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A0, A1, A2, A3, A4, A5, A6, landscape, portrait
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from kalender_pdf.config import LayoutConfig
from kalender_pdf.events import CalendarEvent, EventKind

# Deutsche Monats- und Wochentagsnamen (ohne locale-Abhängigkeit)
MONTH_NAMES_DE = [
    "",
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
]
WEEKDAY_SHORT_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _color(value: str) -> Color:
    return HexColor(value)


def _register_fonts() -> dict[str, str]:
    """Versucht DejaVu für Umlaute; fällt auf Helvetica zurück."""
    mapping = {
        "Regular": "Helvetica",
        "Bold": "Helvetica-Bold",
        "Oblique": "Helvetica-Oblique",
        "Helvetica": "Helvetica",
        "Helvetica-Bold": "Helvetica-Bold",
        "Helvetica-Oblique": "Helvetica-Oblique",
        "Helvetica-BoldOblique": "Helvetica-BoldOblique",
    }
    candidates = [
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        ),
        (
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Oblique.ttf",
        ),
    ]
    for regular, bold, oblique in candidates:
        if Path(regular).is_file():
            pdfmetrics.registerFont(TTFont("DejaVu", regular))
            if Path(bold).is_file():
                pdfmetrics.registerFont(TTFont("DejaVu-Bold", bold))
            else:
                pdfmetrics.registerFont(TTFont("DejaVu-Bold", regular))
            if Path(oblique).is_file():
                pdfmetrics.registerFont(TTFont("DejaVu-Oblique", oblique))
            else:
                pdfmetrics.registerFont(TTFont("DejaVu-Oblique", regular))
            return {
                "Regular": "DejaVu",
                "Bold": "DejaVu-Bold",
                "Oblique": "DejaVu-Oblique",
                "Helvetica": "DejaVu",
                "Helvetica-Bold": "DejaVu-Bold",
                "Helvetica-Oblique": "DejaVu-Oblique",
            }
    return mapping


def _resolve_font(name: str, fonts: dict[str, str]) -> str:
    """Bekannte Namen umsetzen, unbekannte Standardschriften unverändert lassen.

    Ein unbekannter Name darf nicht auf Helvetica (Regular) zurückfallen, sonst
    gehen ``Helvetica-Bold`` und ``Helvetica-Oblique`` verloren.
    """
    return fonts.get(name, name)


_PAGE_SIZES = {
    "A0": A0,
    "A1": A1,
    "A2": A2,
    "A3": A3,
    "A4": A4,
    "A5": A5,
    "A6": A6,
}


def _page_size(layout: LayoutConfig) -> tuple[float, float]:
    key = layout.page_size.upper()
    base = _PAGE_SIZES.get(key)
    if base is None:
        known = ", ".join(sorted(_PAGE_SIZES))
        raise ValueError(f"Unbekannte page_size '{layout.page_size}'. Erlaubt: {known}")
    if layout.orientation == "portrait":
        return portrait(base)
    return landscape(base)


def _days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def row_bottom_spans(
    year: int,
    day: int,
    origin_x: float,
    day_label_w: float,
    col_w: float,
) -> list[tuple[float, float]]:
    """Unterkante von Tag `day`: Tageszahl und nur Monate, in denen der Tag existiert."""
    spans: list[tuple[float, float]] = []
    start = origin_x
    end = origin_x + day_label_w
    for month in range(1, 13):
        x = origin_x + day_label_w + (month - 1) * col_w
        if day <= _days_in_month(year, month):
            if x <= end + 0.01:
                end = x + col_w
            else:
                spans.append((start, end))
                start = x
                end = x + col_w
    spans.append((start, end))
    return spans


def is_span_event(event: CalendarEvent) -> bool:
    """Mehrtägiger Termin: Balken und senkrechter Strich, mit oder ohne Uhrzeit."""
    return event.last_inclusive_date > event.start_date


def is_holiday_event(event: CalendarEvent) -> bool:
    """Eintägiger Ganztagstermin eines als Feiertagskalender markierten Kalenders."""
    return (
        event.holiday_calendar
        and event.all_day
        and event.kind == EventKind.ALL_DAY
    )


def is_bar_day(event: CalendarEvent, day: date) -> bool:
    """Waagerechter Balken am ersten Tag und am Ersten jedes weiteren Monats."""
    if day < event.start_date or day > event.last_inclusive_date:
        return False
    if day == event.start_date:
        return True
    return day.day == 1


def holiday_line_text(weekday: str, names: list[str]) -> str:
    """Wochentagszeile: ``Do Neujahrstag - Zweiter Feiertag``."""
    if not names:
        return weekday
    return f"{weekday} {' - '.join(names)}"


def _ranges_overlap(a: CalendarEvent, b: CalendarEvent) -> bool:
    return a.start_date <= b.last_inclusive_date and b.start_date <= a.last_inclusive_date


def assign_span_lanes(events: list[CalendarEvent]) -> dict[int, int]:
    """Stabile Spur pro Mehrtagestermin.

    Früherer Anfang steht rechts, bei gleichem Anfang der später endende Termin.
    Eine Spur bleibt über die ganze Spanne gleich, damit der Strich gerade durchläuft.
    Überlappende Termine bekommen die nächste Spur links daneben.
    """
    spans = [event for event in events if is_span_event(event)]
    spans.sort(
        key=lambda event: (
            event.start_date,
            -event.last_inclusive_date.toordinal(),
            event.source_index,
            event.event_index,
            event.summary,
        )
    )
    placed: list[tuple[CalendarEvent, int]] = []
    lanes: dict[int, int] = {}
    for event in spans:
        used = [lane for other, lane in placed if _ranges_overlap(event, other)]
        lane = max(used) + 1 if used else 0
        placed.append((event, lane))
        lanes[id(event)] = lane
    return lanes


def _index_events(
    events: list[CalendarEvent],
    year: int,
) -> tuple[
    dict[tuple[int, int], list[CalendarEvent]],
    dict[tuple[int, int], list[CalendarEvent]],
    list[CalendarEvent],
]:
    """Text-Termine, Feiertage und Mehrtages-Termine für das Jahr."""
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    texts: dict[tuple[int, int], list[CalendarEvent]] = defaultdict(list)
    holidays: dict[tuple[int, int], list[CalendarEvent]] = defaultdict(list)
    spans: list[CalendarEvent] = []

    for event in events:
        days = event.dates_in_range(year_start, year_end)
        if not days:
            continue
        if is_span_event(event):
            spans.append(event)
            continue
        for day in days:
            key = (day.month, day.day)
            if is_holiday_event(event):
                holidays[key].append(event)
            else:
                texts[key].append(event)

    def text_key(event: CalendarEvent) -> tuple:
        start_key = event.start.isoformat() if hasattr(event.start, "isoformat") else str(event.start)
        return (start_key, event.summary, event.source_index, event.event_index)

    for key in texts:
        texts[key].sort(key=text_key)
    for key in holidays:
        holidays[key].sort(key=lambda event: (event.source_index, event.event_index, event.summary))
    return texts, holidays, spans


def _truncate(text: str, font_name: str, font_size: float, max_width: float) -> str:
    if pdfmetrics.stringWidth(text, font_name, font_size) <= max_width:
        return text
    ellipsis = "…"
    if pdfmetrics.stringWidth(ellipsis, font_name, font_size) > max_width:
        return ""
    low, high = 0, len(text)
    best = ""
    while low <= high:
        mid = (low + high) // 2
        candidate = text[:mid].rstrip() + ellipsis
        if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
            best = candidate
            low = mid + 1
        else:
            high = mid - 1
    return best


def _fit_segments(
    segments: list[tuple[str, Color]],
    font_name: str,
    font_size: float,
    max_width: float,
) -> list[tuple[str, Color]]:
    """Kürzt die Wochentagszeile am Ende, wenn sie nicht in die Zelle passt."""
    total = sum(pdfmetrics.stringWidth(text, font_name, font_size) for text, _color in segments)
    if total <= max_width:
        return segments
    fitted: list[tuple[str, Color]] = []
    used = 0.0
    ellipsis_w = pdfmetrics.stringWidth("…", font_name, font_size)
    for text, color in segments:
        width = pdfmetrics.stringWidth(text, font_name, font_size)
        if used + width <= max_width:
            fitted.append((text, color))
            used += width
            continue
        remaining = max_width - used
        if remaining <= ellipsis_w:
            break
        fitted.append((_truncate(text, font_name, font_size, remaining), color))
        break
    return fitted


class YearCalendarRenderer:
    def __init__(self, year: int, layout: LayoutConfig, events: list[CalendarEvent]):
        self.year = year
        self.layout = layout
        self.events = events
        self.fonts = _register_fonts()
        self.texts, self.holidays, self.spans = _index_events(events, year)
        self.lanes = assign_span_lanes(self.spans)

    def render(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        page_w, page_h = _page_size(self.layout)
        c = canvas.Canvas(str(output_path), pagesize=(page_w, page_h))
        self._draw_page(c, page_w, page_h)
        c.save()
        return output_path

    def _font(self, name: str) -> str:
        return _resolve_font(name, self.fonts)

    def _draw_page(self, c: canvas.Canvas, page_w: float, page_h: float) -> None:
        layout = self.layout
        margin = layout.margin_mm * mm
        day_label_w = layout.day_label_width_mm * mm
        header_h = layout.header_height_mm * mm

        title = layout.title or f"Jahreskalender {self.year}"
        title_font = self._font("Helvetica-Bold")
        c.setFont(title_font, layout.title_font_size)
        c.setFillColor(_color("#1a1a1a"))
        c.drawString(margin, page_h - margin - layout.title_font_size, title)

        # Legende der Quellen (kompakt)
        legend_y = page_h - margin - layout.title_font_size - 4 * mm
        self._draw_legend(c, margin, legend_y, page_w - 2 * margin)

        grid_top = legend_y - 4 * mm
        grid_bottom = margin
        grid_left = margin
        grid_right = page_w - margin

        usable_w = grid_right - grid_left - day_label_w
        usable_h = grid_top - grid_bottom - header_h
        col_w = usable_w / 12
        row_h = usable_h / 31

        # Monatsköpfe
        header_bg = _color(layout.header_bg_color)
        header_fg = _color(layout.header_text_color)
        month_font = self._font("Helvetica-Bold")
        for month in range(1, 13):
            x = grid_left + day_label_w + (month - 1) * col_w
            y = grid_top - header_h
            c.setFillColor(header_bg)
            c.rect(x, y, col_w, header_h, fill=1, stroke=0)
            c.setFillColor(header_fg)
            c.setFont(month_font, layout.month_font_size)
            label = MONTH_NAMES_DE[month]
            text_w = pdfmetrics.stringWidth(label, month_font, layout.month_font_size)
            c.drawString(
                x + (col_w - text_w) / 2,
                y + (header_h - layout.month_font_size) / 2,
                label,
            )

        # Leere Ecke oben links
        c.setFillColor(header_bg)
        c.rect(grid_left, grid_top - header_h, day_label_w, header_h, fill=1, stroke=0)

        # Tageszeilen
        day_font = self._font("Helvetica")
        grid_line = _color(layout.grid_line_color)
        weekend_bg = _color(layout.weekend_bg_color)
        empty_raw = (layout.empty_day_bg_color or "").strip()
        empty_bg = _color(empty_raw) if empty_raw else None
        alternate = (layout.alternate_month_bg_color or "").strip()
        alternating = bool(alternate)
        alternate_bg = _color(alternate) if alternating else None

        for day in range(1, 32):
            row_top = grid_top - header_h - (day - 1) * row_h
            row_bottom = row_top - row_h

            # Tagesnummer
            c.setFillColor(_color("#f0f0f0"))
            c.rect(grid_left, row_bottom, day_label_w, row_h, fill=1, stroke=0)
            c.setFillColor(_color("#333333"))
            c.setFont(day_font, layout.day_font_size)
            day_label = str(day)
            tw = pdfmetrics.stringWidth(day_label, day_font, layout.day_font_size)
            c.drawString(
                grid_left + (day_label_w - tw) / 2,
                row_bottom + (row_h - layout.day_font_size) / 2,
                day_label,
            )

            for month in range(1, 13):
                x = grid_left + day_label_w + (month - 1) * col_w
                dim = _days_in_month(self.year, month)
                exists = day <= dim

                if not exists:
                    if empty_bg is not None:
                        c.setFillColor(empty_bg)
                        c.rect(x, row_bottom, col_w, row_h, fill=1, stroke=0)
                else:
                    d = date(self.year, month, day)
                    if alternating and month % 2 == 0 and alternate_bg is not None:
                        c.setFillColor(alternate_bg)
                        c.rect(x, row_bottom, col_w, row_h, fill=1, stroke=0)
                    if d.weekday() >= 5:
                        c.setFillColor(weekend_bg)
                        c.rect(x, row_bottom, col_w, row_h, fill=1, stroke=0)

                if not alternating and exists:
                    c.setStrokeColor(grid_line)
                    c.setLineWidth(0.3)
                    c.rect(x, row_bottom, col_w, row_h, fill=0, stroke=1)

            if not alternating:
                c.setStrokeColor(grid_line)
                c.setLineWidth(0.3)
                c.rect(grid_left, row_bottom, day_label_w, row_h, fill=0, stroke=1)

        c.setStrokeColor(grid_line)
        if alternating:
            # Nur waagerechte Trennung. Senkrechte Linien entfallen, auch an der Tageszahl.
            # Unter nicht existierenden Tagen (30.02., 31.04.) fehlt die Linie.
            c.setLineWidth(0.3)
            c.line(grid_left, grid_top - header_h, grid_right, grid_top - header_h)
            for day in range(1, 32):
                y = grid_top - header_h - day * row_h
                for x0, x1 in row_bottom_spans(self.year, day, grid_left, day_label_w, col_w):
                    c.line(x0, y, x1, y)
        else:
            c.setLineWidth(0.6)
            c.line(grid_left, grid_top, grid_right, grid_top)
            c.line(grid_left, grid_bottom, grid_left, grid_top)
            c.line(grid_right, grid_bottom, grid_right, grid_top)
            y_bottom = grid_top - header_h - 31 * row_h
            for x0, x1 in row_bottom_spans(self.year, 31, grid_left, day_label_w, col_w):
                c.line(x0, y_bottom, x1, y_bottom)

        # Striche und Texte über dem Raster, damit der Strich die Tagesgrenze überdeckt.
        for day in range(1, 32):
            row_top = grid_top - header_h - (day - 1) * row_h
            row_bottom = row_top - row_h
            for month in range(1, 13):
                if day > _days_in_month(self.year, month):
                    continue
                x = grid_left + day_label_w + (month - 1) * col_w
                self._draw_cell_contents(
                    c,
                    month,
                    day,
                    x,
                    row_bottom,
                    col_w,
                    row_h,
                )

    def _draw_legend(
        self, c: canvas.Canvas, x: float, y: float, max_width: float
    ) -> None:
        # Einzigartige Quellen aus Events
        seen: dict[str, str] = {}
        for ev in self.events:
            if ev.source_name not in seen:
                seen[ev.source_name] = ev.style.resolve_color(all_day=False)

        font = self._font("Helvetica")
        size = 6.5
        c.setFont(font, size)
        cursor_x = x
        for name, color in seen.items():
            swatch = 2.5 * mm
            if cursor_x + swatch + 2 * mm + pdfmetrics.stringWidth(name, font, size) > x + max_width:
                break
            c.setFillColor(_color(color))
            c.rect(cursor_x, y - 0.5 * mm, swatch, swatch, fill=1, stroke=0)
            cursor_x += swatch + 1 * mm
            c.setFillColor(_color("#333333"))
            c.drawString(cursor_x, y, name)
            cursor_x += pdfmetrics.stringWidth(name, font, size) + 4 * mm

    def _event_indent(self, show_weekdays: bool, font: str, size: float, pad: float) -> float:
        """Einzug, damit „Mo“ frei bleibt und Feiertage wie Termine darunter stehen."""
        if not show_weekdays:
            return pad
        label_w = max(pdfmetrics.stringWidth(name, font, size) for name in WEEKDAY_SHORT_DE)
        gap = pdfmetrics.stringWidth(" ", font, size)
        return pad + label_w + gap

    def _lane_metrics(
        self, row_h: float, col_w: float, lane_count: int
    ) -> tuple[float, float, float]:
        """Strichbreite ≈ 1/16 Zeilenhöhe, etwas Abstand zum Rand und zwischen den Spuren."""
        stroke_w = row_h / 16
        edge = 0.55 * mm
        gap = 0.4 * mm
        if lane_count <= 0:
            return stroke_w, edge, gap
        block = edge + lane_count * stroke_w + max(0, lane_count - 1) * gap
        limit = col_w * 0.62
        if block > limit and block > 0:
            scale = limit / block
            stroke_w *= scale
            edge *= scale
            gap *= scale
        return stroke_w, edge, gap

    def _lane_x(
        self, cell_right: float, lane: int, stroke_w: float, edge: float, gap: float
    ) -> float:
        """Linke Kante des Strichs. Spur 0 liegt am rechten Zellenrand."""
        return cell_right - edge - (lane + 1) * stroke_w - lane * gap

    def _content_right(
        self,
        cell_right: float,
        lanes: list[int],
        stroke_w: float,
        edge: float,
        gap: float,
        pad: float,
    ) -> float:
        if not lanes:
            return cell_right - pad
        max_lane = max(lanes)
        return self._lane_x(cell_right, max_lane, stroke_w, edge, gap) - pad

    def _draw_cell_contents(
        self,
        c: canvas.Canvas,
        month: int,
        day: int,
        x: float,
        y: float,
        col_w: float,
        row_h: float,
    ) -> None:
        layout = self.layout
        current = date(self.year, month, day)
        pad = 0.55 * mm
        bottom_limit = y + 0.35 * mm
        top = y + row_h
        cell_right = x + col_w

        active: list[tuple[CalendarEvent, int, bool]] = []
        for event in self.spans:
            if event.start_date <= current <= event.last_inclusive_date:
                active.append((event, self.lanes[id(event)], is_bar_day(event, current)))
        active.sort(key=lambda item: item[1])

        lane_count = max(self.lanes.values(), default=-1) + 1
        stroke_w, edge, gap = self._lane_metrics(row_h, col_w, lane_count)

        holiday_events = self.holidays.get((month, day), [])
        show_weekday = layout.show_weekdays
        line_size = max(5.0, layout.day_font_size - 1.5)
        line_font = self._font("Helvetica")
        content_left = x + self._event_indent(show_weekday, line_font, line_size, pad)

        top_inset = 0.25 * mm
        first_baseline = top - top_inset - line_size
        # Ohne Feiertag teilen sich Wochentag und erster Termin die oberste Zeile.
        cursor = first_baseline - 0.45 * mm if holiday_events else top - top_inset

        bar_h = layout.bar_height_pt
        bars: list[tuple[CalendarEvent, int, float, float, float]] = []
        stroke_top: dict[int, float] = {}
        for event, lane, bar in active:
            if not bar:
                stroke_top[id(event)] = top
                continue
            if cursor - bar_h < bottom_limit:
                # Kein Platz für den Balken: Strich nur im Rest der Zelle, nicht durch die Zeile darüber.
                stroke_top[id(event)] = cursor
                continue
            stroke_left = self._lane_x(cell_right, lane, stroke_w, edge, gap)
            left = content_left
            width = max(1.0, stroke_left + stroke_w - left)
            bottom = cursor - bar_h
            bars.append((event, lane, left, bottom, width))
            stroke_top[id(event)] = bottom + 0.6
            cursor -= bar_h + layout.event_line_gap_pt

        for event, lane, _bar in active:
            sx = self._lane_x(cell_right, lane, stroke_w, edge, gap)
            top_y = stroke_top.get(id(event), top)
            height = top_y - y
            if height <= 0.2 or sx < x or sx + stroke_w > cell_right:
                continue
            c.setFillColor(_color(event.style.resolve_bar_color()))
            c.rect(sx, y, stroke_w, height, fill=1, stroke=0)

        full_height_lanes = [
            lane
            for event, lane, _bar in active
            if stroke_top.get(id(event), top) >= top - 0.2
        ]
        if show_weekday or holiday_events:
            weekday = WEEKDAY_SHORT_DE[current.weekday()]
            if show_weekday:
                c.setFont(line_font, line_size)
                c.setFillColor(_color("#888888"))
                c.drawString(x + pad, first_baseline, weekday)
            if holiday_events:
                holiday_right = self._content_right(
                    cell_right, full_height_lanes, stroke_w, edge, gap, pad
                )
                self._draw_holiday_names(
                    c,
                    content_left,
                    first_baseline,
                    holiday_right - content_left,
                    holiday_events,
                    line_font,
                    line_size,
                )

        for event, _lane, left, bottom, width in bars:
            self._draw_horizontal_bar(c, event, left, bottom, width, bar_h, pad)

        text_lanes = [lane for _event, lane, _bar in active]
        text_right = self._content_right(cell_right, text_lanes, stroke_w, edge, gap, pad)
        max_text_w = text_right - content_left
        self._draw_text_events(
            c,
            self.texts.get((month, day), []),
            content_left,
            cursor,
            bottom_limit,
            max_text_w,
        )

    def _draw_holiday_names(
        self,
        c: canvas.Canvas,
        x: float,
        baseline: float,
        max_width: float,
        holidays: list[CalendarEvent],
        font: str,
        size: float,
    ) -> None:
        if max_width <= 1 or not holidays:
            return
        gray = _color("#888888")
        segments: list[tuple[str, Color]] = []
        for index, event in enumerate(holidays):
            if index:
                segments.append((" - ", gray))
            segments.append((event.summary, _color(event.style.resolve_color(all_day=True))))
        fitted = _fit_segments(segments, font, size, max_width)
        cursor = x
        c.setFont(font, size)
        for text, color in fitted:
            c.setFillColor(color)
            c.drawString(cursor, baseline, text)
            cursor += pdfmetrics.stringWidth(text, font, size)

    def _draw_horizontal_bar(
        self,
        c: canvas.Canvas,
        event: CalendarEvent,
        left: float,
        bottom: float,
        width: float,
        bar_h: float,
        pad: float,
    ) -> None:
        bg = _color(event.style.resolve_bar_color())
        fg = _color(event.style.bar_text_color)
        font_name = self._font(event.style.resolve_font_name(all_day=event.all_day))
        font_size = event.style.resolve_font_size(all_day=event.all_day, bar=True)
        c.setFillColor(bg)
        c.rect(left, bottom, width, bar_h, fill=1, stroke=0)
        inset = min(pad, width * 0.15)
        text = _truncate(
            event.label(self.layout.timezone),
            font_name,
            font_size,
            max(1.0, width - 2 * inset),
        )
        if not text:
            return
        c.setFillColor(fg)
        c.setFont(font_name, font_size)
        c.drawString(left + inset, bottom + (bar_h - font_size) / 2, text)

    def _draw_text_events(
        self,
        c: canvas.Canvas,
        items: list[CalendarEvent],
        left: float,
        cursor_top: float,
        bottom_limit: float,
        max_width: float,
    ) -> None:
        if not items or max_width <= 1:
            return
        layout = self.layout
        cursor = cursor_top
        drawn = 0
        for event in items:
            if drawn >= layout.max_events_per_cell:
                self._draw_more(c, left, bottom_limit, len(items) - drawn)
                return
            all_day = event.all_day
            font_name = self._font(event.style.resolve_font_name(all_day=all_day))
            font_size = event.style.resolve_font_size(all_day=all_day)
            if cursor - font_size < bottom_limit:
                self._draw_more(c, left, bottom_limit, len(items) - drawn)
                return
            label = event.label(layout.timezone)
            text = _truncate(label, font_name, font_size, max_width)
            c.setFont(font_name, font_size)
            c.setFillColor(_color(event.style.resolve_color(all_day=all_day)))
            c.drawString(left, cursor - font_size, text)
            cursor -= font_size + layout.event_line_gap_pt
            drawn += 1

    def _draw_more(self, c: canvas.Canvas, left: float, baseline: float, remaining: int) -> None:
        if remaining <= 0:
            return
        font = self._font("Helvetica-Oblique")
        size = 5.5
        c.setFont(font, size)
        c.setFillColor(_color("#666666"))
        c.drawString(left, baseline, f"+{remaining} weitere")


def render_year_pdf(
    year: int,
    events: list[CalendarEvent],
    output_path: str | Path,
    layout: LayoutConfig | None = None,
) -> Path:
    renderer = YearCalendarRenderer(year, layout or LayoutConfig(), events)
    return renderer.render(Path(output_path))
