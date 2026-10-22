"""A2-Jahreskalender mit ReportLab: Monate als Spalten, Tage 1–31 als Zeilen."""

from __future__ import annotations

import calendar
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo
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


def bar_text_baseline(font_name: str, font_size: float, bottom: float, bar_h: float) -> float:
    """Grundlinie, sodass die Oberlänge in der Bar vertikal mittig steht.

    ``drawString`` setzt die Grundlinie, nicht die Unterkante der Schrift.
    Der freie Raum über den Großbuchstaben und unter der Grundlinie ist gleich.
    """
    face = pdfmetrics.getFont(font_name).face
    ascent = face.ascent * font_size / 1000.0
    return bottom + (bar_h - ascent) / 2.0


def bar_block_height(
    line_count: int,
    font_name: str,
    font_size: float,
    line_gap: float,
    min_height: float,
) -> float:
    """Höhe des Balkens. Eine Zeile bleibt bei ``min_height``.

    Weitere Zeilen weiten den Block auf die Zeilenhöhe auf, plus die Unterlänge
    der letzten Zeile, damit sie im Block bleibt.
    """
    if line_count <= 1:
        return min_height
    face = pdfmetrics.getFont(font_name).face
    descent = abs(face.descent) * font_size / 1000.0
    stack = line_count * font_size + (line_count - 1) * line_gap + descent
    return max(min_height, stack)


def format_generated_at(moment: datetime) -> str:
    """Erstellungszeile, z. B. ``Stand: 21.10.2026 12:52``."""
    return moment.strftime("Stand: %d.%m.%Y %H:%M")


def allocate_row_heights(needed: list[float], usable: float) -> list[float]:
    """Zeilenhöhen: knappe Zeilen wachsen, die übrigen schrumpfen anteilig.

    Reicht der Platz für diese Höhen nicht, werden alle Zeilen anteilig
    verkleinert, bis sie in ``usable`` passen.
    """
    count = len(needed)
    if count == 0 or usable <= 0:
        return [0.0] * count
    equal = usable / count
    heights = [equal] * count
    extra = 0.0
    others: list[int] = []
    for index, need in enumerate(needed):
        if need > equal:
            heights[index] = need
            extra += need - equal
        else:
            others.append(index)
    pool = equal * len(others)
    if extra > 0 and others and extra <= pool:
        factor = (pool - extra) / pool
        for index in others:
            heights[index] = equal * factor
        return heights
    total = sum(heights)
    if total > usable:
        scale = usable / total
        heights = [height * scale for height in heights]
    return heights


def _prefix_width(
    text: str,
    font_name: str,
    font_size: float,
    length: int,
    width_prefix: Callable[[int], float] | None,
) -> float:
    if width_prefix:
        return width_prefix(length)
    return pdfmetrics.stringWidth(text[:length], font_name, font_size)


def _split_line(
    text: str,
    font_name: str,
    font_size: float,
    max_width: float,
    width_prefix: Callable[[int], float] | None = None,
) -> tuple[str, str]:
    """Längster Präfix, der in die Breite passt. Bevorzugt eine Lücke zwischen Wörtern."""
    if _prefix_width(text, font_name, font_size, len(text), width_prefix) <= max_width:
        return text, ""
    low, high = 1, len(text)
    best = 0
    while low <= high:
        mid = (low + high) // 2
        if _prefix_width(text, font_name, font_size, mid, width_prefix) <= max_width:
            best = mid
            low = mid + 1
        else:
            high = mid - 1
    if best <= 0:
        return "", text
    chunk = text[:best]
    space = chunk.rfind(" ")
    if space > 0:
        return chunk[:space], text[space + 1 :]
    return chunk, text[best:]


def _fit_ellipsis(
    text: str,
    font_name: str,
    font_size: float,
    max_width: float,
    width_prefix: Callable[[int], float] | None = None,
) -> tuple[str, int]:
    """Sichtbarer Text mit Auslassung und wie viele Quellzeichen verbraucht sind."""
    ellipsis = "…"
    ellipsis_w = pdfmetrics.stringWidth(ellipsis, font_name, font_size)
    if _prefix_width(text, font_name, font_size, len(text), width_prefix) <= max_width:
        return text, len(text)
    if ellipsis_w > max_width:
        return "", 0
    low, high = 0, len(text)
    best = 0
    while low <= high:
        mid = (low + high) // 2
        body = text[:mid].rstrip()
        if _prefix_width(text, font_name, font_size, len(body), width_prefix) + ellipsis_w <= max_width:
            best = mid
            low = mid + 1
        else:
            high = mid - 1
    if best <= 0:
        return "", 0
    return text[:best].rstrip() + ellipsis, best


def wrap_tracked(
    text: str,
    font_name: str,
    font_size: float,
    max_width: float,
    max_lines: int,
    measure: Callable[[int, int], float] | None = None,
) -> list[tuple[int, int, bool]]:
    """Zeilen als ``(start, end, gekürzt)`` in ``text``. ``end`` ist exklusiv.

    ``measure(start, end)`` misst ``text[start:end]``, wenn Schrift und Größe
    innerhalb des Textes wechseln.
    """
    if not text or max_lines < 1 or max_width <= 1:
        return []
    lines: list[tuple[int, int, bool]] = []
    start = 0
    length = len(text)
    while start < length and len(lines) < max_lines:
        rest = text[start:]

        def width_prefix(length: int, origin: int = start) -> float:
            if measure:
                return measure(origin, origin + length)
            return pdfmetrics.stringWidth(text[origin : origin + length], font_name, font_size)

        if width_prefix(len(rest)) <= max_width:
            lines.append((start, length, False))
            break
        if len(lines) == max_lines - 1:
            _shown, consumed = _fit_ellipsis(rest, font_name, font_size, max_width, width_prefix)
            if consumed <= 0 and not _shown:
                break
            lines.append((start, start + consumed, True))
            break
        line, remainder = _split_line(rest, font_name, font_size, max_width, width_prefix)
        if not line:
            _shown, consumed = _fit_ellipsis(rest, font_name, font_size, max_width, width_prefix)
            if _shown:
                lines.append((start, start + consumed, True))
            break
        consumed = len(line)
        if remainder and rest[consumed : consumed + 1] == " ":
            consumed += 1
        lines.append((start, start + len(line), False))
        start += consumed
    return lines


def wrap_text_lines(
    text: str, font_name: str, font_size: float, max_width: float, max_lines: int
) -> list[str]:
    """Bricht ``text`` in höchstens ``max_lines`` Zeilen. Die letzte endet bei Bedarf mit …."""
    lines: list[str] = []
    for start, end, cut in wrap_tracked(text, font_name, font_size, max_width, max_lines):
        chunk = text[start:end]
        if cut:
            chunk = chunk.rstrip() + "…"
        if chunk:
            lines.append(chunk)
    return lines


def holiday_color_spans(
    events: list[CalendarEvent],
    fonts: list[str] | None = None,
) -> tuple[str, list[tuple[int, int, str, str, float]]]:
    """Zusammengesetzter Feiertagstext und Spannen ``(start, end, farbe, schrift, größe)``."""
    parts: list[str] = []
    spans: list[tuple[int, int, str, str, float]] = []
    cursor = 0
    for index, event in enumerate(events):
        font = fonts[index] if fonts else "Helvetica"
        size = event.style.resolve_font_size(all_day=True)
        if index:
            separator = " - "
            parts.append(separator)
            spans.append((cursor, cursor + len(separator), "#888888", font, size))
            cursor += len(separator)
        color = event.style.resolve_color(all_day=True)
        parts.append(event.summary)
        spans.append((cursor, cursor + len(event.summary), color, font, size))
        cursor += len(event.summary)
    return "".join(parts), spans


def paint_tracked_lines(
    text: str,
    spans: list[tuple[int, int, str, str, float]],
    parts: list[tuple[int, int, bool]],
) -> list[list[tuple[str, str, str, float]]]:
    """Gefärbte Zeilen. Jeder Lauf ist ``(text, farbe, schrift, größe)``."""
    painted: list[list[tuple[str, str, str, float]]] = []
    for start, end, cut in parts:
        visible_end = end
        if cut:
            visible_end = start + len(text[start:end].rstrip())
        runs: list[tuple[str, str, str, float]] = []
        for span_start, span_end, color, font, size in spans:
            left = max(span_start, start)
            right = min(span_end, visible_end)
            if left >= right:
                continue
            piece = text[left:right]
            if runs and runs[-1][1] == color and runs[-1][2] == font and runs[-1][3] == size:
                runs[-1] = (runs[-1][0] + piece, color, font, size)
            else:
                runs.append((piece, color, font, size))
        if cut and runs:
            runs.append(("…", runs[-1][1], runs[-1][2], runs[-1][3]))
        elif cut:
            runs.append(("…", "#888888", "Helvetica", spans[-1][4] if spans else 6.0))
        if runs:
            painted.append(runs)
    return painted


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


_TOP_INSET = 0.25 * mm
_BOTTOM_PAD = 0.35 * mm
_AFTER_HOLIDAY = 0.45 * mm


@dataclass
class _PlannedLine:
    baseline_from_top: float
    font: str
    size: float
    x: float
    runs: list[tuple[str, ...]]
    layer: str


@dataclass
class _PlannedBar:
    event: CalendarEvent
    lane: int
    top_from_top: float
    height: float
    lines: list[str] = field(default_factory=list)


@dataclass
class _CellPlan:
    lines: list[_PlannedLine]
    bars: list[_PlannedBar]
    weekday_baseline: float | None
    weekday_label: str
    content_left: float
    needed: float
    hidden: bool


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

        # Legende der Quellen, rechts daneben der Erstellungszeitpunkt.
        legend_y = page_h - margin - layout.title_font_size - 4 * mm
        legend_font = self._font("Helvetica")
        legend_size = 6.5
        stamp = format_generated_at(datetime.now(ZoneInfo(layout.timezone)))
        stamp_w = pdfmetrics.stringWidth(stamp, legend_font, legend_size)
        legend_gap = 4 * mm
        legend_width = max(0.0, page_w - 2 * margin - stamp_w - legend_gap)
        self._draw_legend(c, margin, legend_y, legend_width)
        c.setFillColor(_color("#333333"))
        c.setFont(legend_font, legend_size)
        c.drawRightString(page_w - margin, legend_y, stamp)

        grid_top = legend_y - 4 * mm
        grid_bottom = margin
        grid_left = margin
        grid_right = page_w - margin

        usable_w = grid_right - grid_left - day_label_w
        usable_h = grid_top - grid_bottom - header_h
        col_w = usable_w / 12
        ref_row_h = usable_h / 31
        lane_count = max(self.lanes.values(), default=-1) + 1
        stroke_w, stroke_edge, stroke_gap = self._lane_metrics(ref_row_h, col_w, lane_count)
        self._col_w = col_w
        self._stroke_w = stroke_w
        self._stroke_edge = stroke_edge
        self._stroke_gap = stroke_gap
        row_heights = self._allocated_row_heights(usable_h)
        if row_heights:
            row_heights[-1] += usable_h - sum(row_heights)
        row_tops: list[float] = []
        row_bottoms: list[float] = []
        y_cursor = grid_top - header_h
        for height in row_heights:
            row_tops.append(y_cursor)
            y_cursor -= height
            row_bottoms.append(y_cursor)

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
            row_h = row_heights[day - 1]
            row_bottom = row_bottoms[day - 1]

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
                    if d.weekday() >= 5 or (month, day) in self.holidays:
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
                y = row_bottoms[day - 1]
                for x0, x1 in row_bottom_spans(self.year, day, grid_left, day_label_w, col_w):
                    c.line(x0, y, x1, y)
        else:
            c.setLineWidth(0.6)
            c.line(grid_left, grid_top, grid_right, grid_top)
            c.line(grid_left, grid_bottom, grid_left, grid_top)
            c.line(grid_right, grid_bottom, grid_right, grid_top)
            y_bottom = row_bottoms[30]
            for x0, x1 in row_bottom_spans(self.year, 31, grid_left, day_label_w, col_w):
                c.line(x0, y_bottom, x1, y_bottom)

        # Striche und Texte über dem Raster, damit der Strich die Tagesgrenze überdeckt.
        for day in range(1, 32):
            row_h = row_heights[day - 1]
            row_bottom = row_bottoms[day - 1]
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

    def _bar_text_width(self, lane: int, content_left: float, pad: float) -> float:
        """Innenbreite des Balkens, abzüglich des Textabstands links und rechts."""
        stroke_left = self._lane_x(self._col_w, lane, self._stroke_w, self._stroke_edge, self._stroke_gap)
        width = max(1.0, stroke_left + self._stroke_w - content_left)
        inset = min(pad, width * 0.15)
        return max(1.0, width - 2 * inset)

    def _allocated_row_heights(self, usable_h: float) -> list[float]:
        floor = max(self.layout.day_font_size, self.layout.weekday_font_size) + 0.6 * mm
        needed: list[float] = []
        for day in range(1, 32):
            cell_need = floor
            for month in range(1, 13):
                if day > _days_in_month(self.year, month):
                    continue
                cell_need = max(cell_need, self._plan_cell(month, day).needed)
            needed.append(cell_need)
        return allocate_row_heights(needed, usable_h)

    def _active_on(self, month: int, day: int) -> list[tuple[CalendarEvent, int, bool]]:
        current = date(self.year, month, day)
        active: list[tuple[CalendarEvent, int, bool]] = []
        for event in self.spans:
            if event.start_date <= current <= event.last_inclusive_date:
                active.append((event, self.lanes[id(event)], is_bar_day(event, current)))
        active.sort(key=lambda item: item[1])
        return active

    def _plan_cell(self, month: int, day: int) -> _CellPlan:
        layout = self.layout
        pad = 0.55 * mm
        line_gap = layout.event_line_gap_pt
        active = self._active_on(month, day)
        holiday_events = self.holidays.get((month, day), [])
        show_weekday = layout.show_weekdays
        line_size = layout.weekday_font_size
        line_font = self._font("Helvetica")
        content_left = self._event_indent(show_weekday, line_font, line_size, pad)
        full_lanes = [lane for _event, lane, bar in active if not bar]
        all_lanes = [lane for _event, lane, _bar in active]
        holiday_width = (
            self._content_right(self._col_w, full_lanes, self._stroke_w, self._stroke_edge, self._stroke_gap, pad)
            - content_left
        )
        text_width = (
            self._content_right(self._col_w, all_lanes, self._stroke_w, self._stroke_edge, self._stroke_gap, pad)
            - content_left
        )

        lines: list[_PlannedLine] = []
        bars: list[_PlannedBar] = []
        hidden = False
        current = date(self.year, month, day)
        weekday_label = WEEKDAY_SHORT_DE[current.weekday()] if show_weekday else ""
        cursor = _TOP_INSET

        if holiday_events:
            if holiday_width <= 1:
                hidden = True
            else:
                wrap = all(event.wrap_text for event in holiday_events)
                max_lines = layout.max_event_lines if wrap else 1
                holiday_fonts = [
                    self._font(event.style.resolve_font_name(all_day=True)) for event in holiday_events
                ]
                text, spans = holiday_color_spans(holiday_events, holiday_fonts)

                def measure(start: int, end: int) -> float:
                    total = 0.0
                    for span_start, span_end, _color, font, size in spans:
                        left, right = max(span_start, start), min(span_end, end)
                        if left < right:
                            total += pdfmetrics.stringWidth(text[left:right], font, size)
                    return total

                parts = wrap_tracked(
                    text,
                    holiday_fonts[0],
                    holiday_events[0].style.resolve_font_size(all_day=True),
                    holiday_width,
                    max_lines,
                    measure,
                )
                for runs in paint_tracked_lines(text, spans, parts):
                    size = max(run[3] for run in runs)
                    lines.append(
                        _PlannedLine(cursor + size, runs[0][2], size, content_left, runs, "holiday")
                    )
                    cursor += size + line_gap
                if any(line.layer == "holiday" for line in lines):
                    cursor = cursor - line_gap + _AFTER_HOLIDAY
                else:
                    hidden = True

        slots = layout.max_events_per_cell
        for event, lane, is_bar in active:
            if not is_bar:
                continue
            if slots <= 0:
                hidden = True
                break
            font_name = self._font(event.style.resolve_font_name(all_day=event.all_day))
            font_size = event.style.resolve_font_size(all_day=event.all_day, bar=True)
            max_lines = layout.max_event_lines if event.wrap_text else 1
            label = event.label(layout.timezone)
            wrapped = wrap_text_lines(
                label,
                font_name,
                font_size,
                self._bar_text_width(lane, content_left, pad),
                max_lines,
            )
            if label and not wrapped:
                hidden = True
            height = bar_block_height(
                len(wrapped) if wrapped else 1,
                font_name,
                font_size,
                line_gap,
                layout.bar_height_pt,
            )
            bars.append(_PlannedBar(event, lane, cursor, height, wrapped))
            cursor += height + line_gap
            slots -= 1

        texts = self.texts.get((month, day), [])
        if len(texts) > slots:
            hidden = True
            texts = texts[: max(0, slots)]
        if texts and text_width <= 1:
            hidden = True
        if text_width > 1:
            for event in texts:
                max_lines = layout.max_event_lines if event.wrap_text else 1
                font_name = self._font(event.style.resolve_font_name(all_day=event.all_day))
                font_size = event.style.resolve_font_size(all_day=event.all_day)
                wrapped = wrap_text_lines(
                    event.label(layout.timezone),
                    font_name,
                    font_size,
                    text_width,
                    max_lines,
                )
                if not wrapped:
                    hidden = True
                    continue
                color = event.style.resolve_color(all_day=event.all_day)
                for index, line in enumerate(wrapped):
                    baseline = cursor + font_size + index * (font_size + line_gap)
                    lines.append(
                        _PlannedLine(baseline, font_name, font_size, content_left, [(line, color)], "text")
                    )
                count = len(wrapped)
                cursor += count * font_size + max(0, count - 1) * line_gap + line_gap

        return _CellPlan(
            lines,
            bars,
            None,
            weekday_label,
            content_left,
            cursor + _BOTTOM_PAD,
            hidden,
        )

    def _line_fits(self, baseline_from_top: float, row_h: float) -> bool:
        return baseline_from_top <= row_h - _BOTTOM_PAD + 0.05

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
        plan = self._plan_cell(month, day)
        top = y + row_h
        pad = 0.55 * mm
        cell_right = x + col_w
        stroke_w, edge, gap = self._stroke_w, self._stroke_edge, self._stroke_gap
        active = self._active_on(month, day)
        bar_by_event = {id(bar.event): bar for bar in plan.bars}
        overflow = plan.hidden

        for event, lane, is_bar in active:
            sx = self._lane_x(cell_right, lane, stroke_w, edge, gap)
            if not is_bar:
                top_y = top
            else:
                planned = bar_by_event.get(id(event))
                if planned is None:
                    top_y = top
                else:
                    bar_top = top - planned.top_from_top
                    fits = planned.top_from_top + planned.height <= row_h - _BOTTOM_PAD + 0.05
                    if fits:
                        top_y = bar_top - planned.height + 0.6
                    else:
                        overflow = True
                        top_y = min(bar_top, top)
            height = top_y - y
            if height <= 0.2 or sx < x or sx + stroke_w > cell_right:
                continue
            c.setFillColor(_color(event.style.resolve_bar_color()))
            c.rect(sx, y, stroke_w, height, fill=1, stroke=0)

        for line in plan.lines:
            if line.layer != "holiday":
                continue
            if not self._line_fits(line.baseline_from_top, row_h):
                overflow = True
                continue
            self._draw_runs(c, x + line.x, top - line.baseline_from_top, line)

        for bar in plan.bars:
            if bar.top_from_top + bar.height > row_h - _BOTTOM_PAD + 0.05:
                continue
            stroke_left = self._lane_x(cell_right, bar.lane, stroke_w, edge, gap)
            left = x + plan.content_left
            width = max(1.0, stroke_left + stroke_w - left)
            bottom = top - bar.top_from_top - bar.height
            self._draw_horizontal_bar(c, bar.event, left, bottom, width, bar.height, pad, bar.lines)

        for line in plan.lines:
            if line.layer != "text":
                continue
            if not self._line_fits(line.baseline_from_top, row_h):
                overflow = True
                continue
            self._draw_runs(c, x + line.x, top - line.baseline_from_top, line)

        if plan.weekday_label:
            size = self.layout.weekday_font_size
            c.setFont(self._font("Helvetica"), size)
            c.setFillColor(_color("#888888"))
            c.drawString(x + pad, y + (row_h - size) / 2, plan.weekday_label)

        if overflow:
            self._draw_overflow_mark(c, x, y, col_w, row_h)

    def _draw_runs(self, c: canvas.Canvas, x: float, baseline: float, line: _PlannedLine) -> None:
        cursor = x
        for run in line.runs:
            text, color = run[0], run[1]
            font = run[2] if len(run) > 2 else line.font
            size = run[3] if len(run) > 3 else line.size
            c.setFont(font, size)
            c.setFillColor(_color(color))
            c.drawString(cursor, baseline, text)
            cursor += pdfmetrics.stringWidth(text, font, size)

    def _draw_overflow_mark(
        self,
        c: canvas.Canvas,
        x: float,
        y: float,
        col_w: float,
        row_h: float,
    ) -> None:
        """`...` rechts unten, über Strichen und Balken, mit deckendem Hintergrund."""
        font = self._font("Helvetica-Bold")
        size = 6.0
        mark = "..."
        pad = 0.35 * mm
        width = pdfmetrics.stringWidth(mark, font, size)
        left = x + col_w - pad - width
        baseline = y + 0.3 * mm
        if baseline + size > y + row_h:
            baseline = y + max(0.2, row_h - size - 0.2)
        c.setFillColor(_color("#ffffff"))
        c.rect(left - 0.8, baseline - 1.2, width + 1.6, size + 1.6, fill=1, stroke=0)
        c.setFillColor(_color("#222222"))
        c.setFont(font, size)
        c.drawString(left, baseline, mark)

    def _draw_horizontal_bar(
        self,
        c: canvas.Canvas,
        event: CalendarEvent,
        left: float,
        bottom: float,
        width: float,
        bar_h: float,
        pad: float,
        lines: list[str],
    ) -> None:
        bg = _color(event.style.resolve_bar_color())
        fg = _color(event.style.bar_text_color)
        font_name = self._font(event.style.resolve_font_name(all_day=event.all_day))
        font_size = event.style.resolve_font_size(all_day=event.all_day, bar=True)
        c.setFillColor(bg)
        c.rect(left, bottom, width, bar_h, fill=1, stroke=0)
        if not lines:
            return
        inset = min(pad, width * 0.15)
        c.setFillColor(fg)
        c.setFont(font_name, font_size)
        if len(lines) == 1:
            c.drawString(left + inset, bar_text_baseline(font_name, font_size, bottom, bar_h), lines[0])
            return
        face = pdfmetrics.getFont(font_name).face
        descent = abs(face.descent) * font_size / 1000.0
        line_gap = self.layout.event_line_gap_pt
        stack = len(lines) * font_size + (len(lines) - 1) * line_gap + descent
        top_pad = max(0.0, (bar_h - stack) / 2)
        for index, line in enumerate(lines):
            baseline = bottom + bar_h - top_pad - font_size - index * (font_size + line_gap)
            c.drawString(left + inset, baseline, line)


def render_year_pdf(
    year: int,
    events: list[CalendarEvent],
    output_path: str | Path,
    layout: LayoutConfig | None = None,
) -> Path:
    renderer = YearCalendarRenderer(year, layout or LayoutConfig(), events)
    return renderer.render(Path(output_path))
