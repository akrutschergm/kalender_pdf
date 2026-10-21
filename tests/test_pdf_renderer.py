"""PDF-Renderer schreibt eine gültige Datei und legt Spuren richtig."""

import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.lib.pagesizes import A3, landscape

from kalender_pdf.config import LayoutConfig
from kalender_pdf.events import CalendarEvent, EventKind, SourceStyle
from kalender_pdf.pdf_renderer import (
    _register_fonts,
    _resolve_font,
    assign_span_lanes,
    holiday_line_text,
    row_bottom_spans,
    is_bar_day,
    is_holiday_event,
    is_span_event,
    render_year_pdf,
)


def _event(**kwargs) -> CalendarEvent:
    defaults = dict(
        uid="x",
        summary="Test",
        source_name="S",
        style=SourceStyle(bar_color="#888888", bar_text_color="#000000"),
        start=date(2026, 1, 1),
        end=date(2026, 1, 2),
        all_day=True,
        kind=EventKind.ALL_DAY,
    )
    defaults.update(kwargs)
    return CalendarEvent(**defaults)


def test_render_minimal_pdf(tmp_path: Path):
    tz = ZoneInfo("Europe/Berlin")
    events = [
        _event(
            uid="1",
            summary="Neujahr",
            source_name="Feiertage",
            start=date(2026, 1, 1),
            end=date(2026, 1, 2),
            kind=EventKind.ALL_DAY,
            holiday_calendar=True,
            source_index=0,
            event_index=0,
        ),
        _event(
            uid="2",
            summary="Sommerferien",
            source_name="Feiertage",
            start=date(2026, 7, 1),
            end=date(2026, 7, 15),
            kind=EventKind.MULTI_DAY,
            holiday_calendar=True,
            source_index=0,
            event_index=1,
        ),
        _event(
            uid="3",
            summary="Gottesdienst",
            source_name="Gottesdienste",
            start=datetime(2026, 1, 1, 10, 30, tzinfo=tz),
            end=datetime(2026, 1, 1, 11, 30, tzinfo=tz),
            all_day=False,
            kind=EventKind.TIMED,
            source_index=1,
            event_index=0,
        ),
    ]
    out = tmp_path / "test.pdf"
    path = render_year_pdf(2026, events, out)
    assert path.is_file()
    assert path.stat().st_size > 1000
    assert path.read_bytes()[:4] == b"%PDF"


def test_page_size_a3_landscape(tmp_path: Path):
    out = tmp_path / "a3.pdf"
    render_year_pdf(2026, [], out, layout=LayoutConfig(page_size="A3", orientation="landscape"))
    expected_w, expected_h = landscape(A3)
    match = re.search(rb"MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", out.read_bytes())
    assert match is not None
    assert abs(float(match.group(1)) - expected_w) < 1
    assert abs(float(match.group(2)) - expected_h) < 1


def test_bold_and_oblique_are_not_regular():
    fonts = _register_fonts()
    regular = _resolve_font("Helvetica", fonts)
    bold = _resolve_font("Helvetica-Bold", fonts)
    oblique = _resolve_font("Helvetica-Oblique", fonts)
    assert bold != regular
    assert oblique != regular
    assert "Bold" in bold or "bold" in bold
    assert "Oblique" in oblique or "Italic" in oblique or "italic" in oblique


def test_holiday_line_and_span_classification():
    holiday = _event(summary="Neujahr", holiday_calendar=True, kind=EventKind.ALL_DAY)
    vacation = _event(
        summary="Sommerferien",
        holiday_calendar=True,
        start=date(2026, 7, 1),
        end=date(2026, 7, 15),
        kind=EventKind.MULTI_DAY,
    )
    assert is_holiday_event(holiday)
    assert not is_span_event(holiday)
    assert is_span_event(vacation)
    assert not is_holiday_event(vacation)
    assert holiday_line_text("Do", ["Neujahr"]) == "Do Neujahr"
    assert holiday_line_text("Do", ["Neujahr", "Zweiter Feiertag"]) == "Do Neujahr - Zweiter Feiertag"


def test_missing_days_have_no_bottom_line():
    # 2026 ist kein Schaltjahr: Februar endet am 28., April am 30.
    label, col = 10.0, 20.0
    feb = row_bottom_spans(2026, 30, 0.0, label, col)
    assert feb == [(0.0, label + col), (label + 2 * col, label + 12 * col)]

    april = row_bottom_spans(2026, 31, 0.0, label, col)
    april_x = label + 3 * col
    jan_x = label
    assert not any(x0 <= april_x < x1 for x0, x1 in april)
    assert any(x0 <= jan_x < x1 for x0, x1 in april)


def test_bar_day_on_start_and_month_boundary():
    vacation = _event(
        start=date(2026, 1, 30),
        end=date(2026, 2, 4),
        kind=EventKind.MULTI_DAY,
    )
    assert is_bar_day(vacation, date(2026, 1, 30))
    assert not is_bar_day(vacation, date(2026, 1, 31))
    assert is_bar_day(vacation, date(2026, 2, 1))
    assert not is_bar_day(vacation, date(2026, 2, 2))


def test_span_lanes_sort_by_start_then_later_end():
    early = _event(
        uid="early",
        summary="Früh",
        start=date(2026, 3, 1),
        end=date(2026, 3, 6),
        kind=EventKind.MULTI_DAY,
        source_index=0,
        event_index=0,
    )
    long = _event(
        uid="long",
        summary="Lang",
        start=date(2026, 3, 4),
        end=date(2026, 3, 20),
        kind=EventKind.MULTI_DAY,
        source_index=0,
        event_index=1,
    )
    short = _event(
        uid="short",
        summary="Kurz",
        start=date(2026, 3, 4),
        end=date(2026, 3, 8),
        kind=EventKind.MULTI_DAY,
        source_index=0,
        event_index=2,
    )
    lanes = assign_span_lanes([short, long, early])
    assert lanes[id(early)] == 0
    assert lanes[id(long)] == 1
    assert lanes[id(short)] == 2
