"""A2-Jahreskalender mit ReportLab: Monate als Spalten, Tage 1–31 als Zeilen."""

from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A2, landscape, portrait
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
    return fonts.get(name, fonts.get("Regular", name))


def _page_size(layout: LayoutConfig) -> tuple[float, float]:
    base = A2
    if layout.page_size.upper() != "A2":
        # Nur A2 wird offiziell unterstützt; andere Größen trotzdem übergeben
        base = A2
    if layout.orientation == "portrait":
        return portrait(base)
    return landscape(base)


@dataclass
class CellEvent:
    event: CalendarEvent
    is_bar_segment: bool
    bar_continues_prev: bool
    bar_continues_next: bool
    bar_span_days_in_month: int
    bar_day_index: int  # 0-basiert innerhalb des Monatssegments


def _days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _build_cell_map(
    events: list[CalendarEvent],
    year: int,
) -> dict[tuple[int, int], list[CellEvent]]:
    """Map (month, day) → darzustellende Einträge."""
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    cells: dict[tuple[int, int], list[CellEvent]] = defaultdict(list)

    for event in events:
        days = event.dates_in_range(year_start, year_end)
        if not days:
            continue

        use_bar = event.style.as_bar or event.kind == EventKind.MULTI_DAY
        if use_bar and event.all_day and len(days) >= 1:
            # Pro Monat ein Balken-Segment (Spalten sind monatsweise)
            by_month: dict[int, list[date]] = defaultdict(list)
            for d in days:
                by_month[d.month].append(d)
            for month, month_days in by_month.items():
                month_days.sort()
                for idx, d in enumerate(month_days):
                    cells[(month, d.day)].append(
                        CellEvent(
                            event=event,
                            is_bar_segment=True,
                            bar_continues_prev=idx > 0,
                            bar_continues_next=idx < len(month_days) - 1,
                            bar_span_days_in_month=len(month_days),
                            bar_day_index=idx,
                        )
                    )
        else:
            for d in days:
                cells[(d.month, d.day)].append(
                    CellEvent(
                        event=event,
                        is_bar_segment=False,
                        bar_continues_prev=False,
                        bar_continues_next=False,
                        bar_span_days_in_month=1,
                        bar_day_index=0,
                    )
                )

    # Sortierung: Bars zuerst, dann nach Startzeit / Titel
    def sort_key(ce: CellEvent) -> tuple:
        ev = ce.event
        start_key = ev.start.isoformat() if hasattr(ev.start, "isoformat") else str(ev.start)
        return (0 if ce.is_bar_segment else 1, start_key, ev.summary)

    for key in cells:
        cells[key].sort(key=sort_key)
    return cells


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


class YearCalendarRenderer:
    def __init__(self, year: int, layout: LayoutConfig, events: list[CalendarEvent]):
        self.year = year
        self.layout = layout
        self.events = events
        self.fonts = _register_fonts()
        self.cells = _build_cell_map(events, year)

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
        empty_bg = _color(layout.empty_day_bg_color)

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
                    c.setFillColor(empty_bg)
                    c.rect(x, row_bottom, col_w, row_h, fill=1, stroke=0)
                else:
                    d = date(self.year, month, day)
                    if d.weekday() >= 5:
                        c.setFillColor(weekend_bg)
                        c.rect(x, row_bottom, col_w, row_h, fill=1, stroke=0)
                    if layout.show_weekdays:
                        wd = WEEKDAY_SHORT_DE[d.weekday()]
                        c.setFillColor(_color("#888888"))
                        c.setFont(day_font, max(5.0, layout.day_font_size - 1.5))
                        c.drawString(x + 1.2 * mm, row_top - 3.2 * mm, wd)

                    self._draw_cell_events(
                        c,
                        month,
                        day,
                        x,
                        row_bottom,
                        col_w,
                        row_h,
                    )

                c.setStrokeColor(grid_line)
                c.setLineWidth(0.3)
                c.rect(x, row_bottom, col_w, row_h, fill=0, stroke=1)

            # Rahmen Tagesnummer
            c.setStrokeColor(grid_line)
            c.setLineWidth(0.3)
            c.rect(grid_left, row_bottom, day_label_w, row_h, fill=0, stroke=1)

        # Äußerer Rahmen Kopfzeile
        c.setStrokeColor(grid_line)
        c.setLineWidth(0.6)
        c.rect(
            grid_left,
            grid_bottom,
            grid_right - grid_left,
            grid_top - grid_bottom,
            fill=0,
            stroke=1,
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

    def _draw_cell_events(
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
        items = self.cells.get((month, day), [])
        if not items:
            return

        pad = 0.8 * mm
        # Platz unter Wochentag-Kürzel
        top_pad = 3.5 * mm if layout.show_weekdays else pad
        cursor_y = y + row_h - top_pad
        max_y_bottom = y + pad
        drawn = 0

        for ce in items:
            if drawn >= layout.max_events_per_cell:
                remaining = len(items) - drawn
                font = self._font("Helvetica-Oblique")
                size = 5.5
                c.setFont(font, size)
                c.setFillColor(_color("#666666"))
                msg = f"+{remaining} weitere"
                c.drawString(x + pad, max_y_bottom, msg)
                break

            if ce.is_bar_segment:
                bar_h = layout.bar_height_pt
                if cursor_y - bar_h < max_y_bottom:
                    break
                self._draw_bar_segment(c, ce, x, cursor_y - bar_h, col_w, bar_h, pad)
                cursor_y -= bar_h + layout.event_line_gap_pt
                drawn += 1
                continue

            ev = ce.event
            all_day = ev.all_day
            font_name = self._font(ev.style.resolve_font_name(all_day=all_day))
            font_size = ev.style.resolve_font_size(all_day=all_day)
            color = _color(ev.style.resolve_color(all_day=all_day))
            label = ev.label(self.layout.timezone)
            max_text_w = col_w - 2 * pad
            text = _truncate(label, font_name, font_size, max_text_w)
            if cursor_y - font_size < max_y_bottom:
                break
            c.setFont(font_name, font_size)
            c.setFillColor(color)
            c.drawString(x + pad, cursor_y - font_size, text)
            cursor_y -= font_size + layout.event_line_gap_pt
            drawn += 1

    def _draw_bar_segment(
        self,
        c: canvas.Canvas,
        ce: CellEvent,
        x: float,
        y: float,
        col_w: float,
        bar_h: float,
        pad: float,
    ) -> None:
        ev = ce.event
        bg = _color(ev.style.resolve_bar_color())
        fg = _color(ev.style.bar_text_color)
        font_name = self._font(ev.style.resolve_font_name(all_day=True))
        font_size = ev.style.resolve_font_size(all_day=True, bar=True)

        # Nahtlose Balken: wenig Padding an Fortsetzungsseiten
        left = x if ce.bar_continues_prev else x + pad * 0.5
        right = x + col_w if ce.bar_continues_next else x + col_w - pad * 0.5
        width = max(0.5, right - left)

        c.setFillColor(bg)
        c.roundRect(left, y, width, bar_h, 1.2, fill=1, stroke=0)

        # Text nur am ersten Tag des Monatssegments
        if ce.bar_day_index == 0:
            c.setFillColor(fg)
            c.setFont(font_name, font_size)
            text = _truncate(ev.summary, font_name, font_size, width - pad)
            c.drawString(left + pad * 0.6, y + (bar_h - font_size) / 2, text)


def render_year_pdf(
    year: int,
    events: list[CalendarEvent],
    output_path: str | Path,
    layout: LayoutConfig | None = None,
) -> Path:
    renderer = YearCalendarRenderer(year, layout or LayoutConfig(), events)
    return renderer.render(Path(output_path))
