"""PDF-Renderer schreibt eine gültige Datei und legt Spuren richtig."""

import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth

from kalender_pdf.config import LayoutConfig
from kalender_pdf.events import CalendarEvent, EventKind, SourceStyle
from kalender_pdf.pdf_renderer import (
    _register_fonts,
    _resolve_font,
    allocate_row_heights,
    assign_span_lanes,
    holiday_color_spans,
    paint_tracked_lines,
    wrap_text_lines,
    wrap_tracked,
    bar_block_height,
    bar_text_baseline,
    format_generated_at,
    holiday_line_text,
    row_bottom_spans,
    is_bar_day,
    is_holiday_event,
    is_span_event,
    YearCalendarRenderer,
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
    assert format_generated_at(datetime(2026, 10, 21, 12, 52)) == "Stand: 21.10.2026 12:52"


def test_allocate_expands_busy_row_and_shrinks_others():
    heights = allocate_row_heights([50, 10, 10], 90)
    assert heights[0] == 50
    assert heights[1] == 20
    assert heights[2] == 20
    assert sum(heights) == 90


def test_allocate_scales_when_content_exceeds_the_page():
    heights = allocate_row_heights([100, 10, 10], 90)
    assert sum(heights) == 90
    assert heights[0] == 100 * 90 / 160
    assert heights[1] == 30 * 90 / 160


def test_max_events_per_cell_hides_the_rest():
    events = [
        _event(uid=str(index), summary=f"Termin {index}", start=date(2026, 3, 4), end=date(2026, 3, 5))
        for index in range(4)
    ]
    renderer = YearCalendarRenderer(2026, LayoutConfig(max_events_per_cell=2, show_weekdays=False), events)
    renderer._col_w = 200
    renderer._stroke_w = 2
    renderer._stroke_edge = 1
    renderer._stroke_gap = 1
    plan = renderer._plan_cell(3, 4)
    shown = [line for line in plan.lines if line.layer == "text"]
    assert len(shown) == 2
    assert plan.hidden


def test_wrap_text_limits_lines():
    text = "alpha beta gamma delta epsilon zeta"
    lines = wrap_text_lines(text, "Helvetica", 10, 50, 2)
    assert len(lines) == 2
    assert lines[-1].endswith("…")
    assert len(wrap_text_lines(text, "Helvetica", 10, 50, 1)) == 1


def test_holiday_uses_source_font():
    event = _event(
        summary="Neujahr",
        holiday_calendar=True,
        style=SourceStyle(
            font_name="Oblique",
            font_size=11,
            all_day_font_name="Oblique",
            all_day_font_size=13,
            all_day_color="#888888",
        ),
    )
    renderer = YearCalendarRenderer(2026, LayoutConfig(), [event])
    renderer._col_w = 200
    renderer._stroke_w = 2
    renderer._stroke_edge = 1
    renderer._stroke_gap = 1
    plan = renderer._plan_cell(1, 1)
    holiday_lines = [line for line in plan.lines if line.layer == "holiday"]
    assert holiday_lines
    used = {run[2] for line in holiday_lines for run in line.runs}
    assert renderer._font("Oblique") in used
    assert {run[3] for line in holiday_lines for run in line.runs} == {13.0}

    plain = _event(
        summary="Karfreitag",
        holiday_calendar=True,
        style=SourceStyle(font_name="Oblique", font_size=9),
    )
    plain_renderer = YearCalendarRenderer(2026, LayoutConfig(), [plain])
    plain_renderer._col_w = 200
    plain_renderer._stroke_w = 2
    plain_renderer._stroke_edge = 1
    plain_renderer._stroke_gap = 1
    plain_plan = plain_renderer._plan_cell(1, 1)
    plain_lines = [line for line in plain_plan.lines if line.layer == "holiday"]
    assert {run[3] for line in plain_lines for run in line.runs} == {9.0}


def test_holiday_names_wrap_as_one_text():
    events = [
        _event(summary="Neujahrstag", holiday_calendar=True),
        _event(summary="Zweiter Feiertag", holiday_calendar=True, style=SourceStyle(all_day_color="#aa0000")),
    ]
    text, spans = holiday_color_spans(events)
    assert text == "Neujahrstag - Zweiter Feiertag"
    width = stringWidth("Neujahrstag - ", "Helvetica", 8) + 4
    parts = wrap_tracked(text, "Helvetica", 8, width, 3)
    lines = paint_tracked_lines(text, spans, parts)
    assert len(lines) >= 2
    flat = "".join(run[0] for line in lines for run in line)
    assert flat.startswith("Neujahrstag")
    assert "Zweiter" in flat


def test_bar_text_is_vertically_centered():
    bottom, bar_h, size = 0.0, 9.0, 7.0
    font_name = "Helvetica-Bold"
    baseline = bar_text_baseline(font_name, size, bottom, bar_h)
    ascent = pdfmetrics.getFont(font_name).face.ascent * size / 1000.0
    gap_below = baseline - bottom
    gap_above = (bottom + bar_h) - (baseline + ascent)
    assert abs(gap_below - gap_above) < 0.01
    assert baseline > (bar_h - size) / 2
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


def test_span_bar_wraps_and_grows():
    summary = "Sommerferien der Gemeinde mit einem sehr langen Namen"
    event = _event(
        summary=summary,
        start=date(2026, 7, 1),
        end=date(2026, 7, 15),
        kind=EventKind.MULTI_DAY,
        style=SourceStyle(font_size=10, bar_color="#888888", bar_text_color="#000000"),
    )
    layout = LayoutConfig(max_event_lines=3, show_weekdays=False, bar_height_pt=9, event_line_gap_pt=1)
    renderer = YearCalendarRenderer(2026, layout, [event])
    renderer._col_w = 70
    renderer._stroke_w = 4
    renderer._stroke_edge = 1
    renderer._stroke_gap = 1
    plan = renderer._plan_cell(7, 1)
    assert len(plan.bars) == 1
    bar = plan.bars[0]
    assert 2 <= len(bar.lines) <= layout.max_event_lines
    assert bar.lines[-1].endswith("…")
    assert bar.height == bar_block_height(len(bar.lines), renderer._font("Helvetica"), 10, 1, 9)
    assert bar.height > layout.bar_height_pt
    assert renderer._plan_cell(7, 2).bars == []

    single = _event(
        summary=summary,
        start=date(2026, 7, 1),
        end=date(2026, 7, 15),
        kind=EventKind.MULTI_DAY,
        wrap_text=False,
        style=SourceStyle(font_size=10, bar_color="#888888", bar_text_color="#000000"),
    )
    plain = YearCalendarRenderer(2026, layout, [single])
    plain._col_w = 70
    plain._stroke_w = 4
    plain._stroke_edge = 1
    plain._stroke_gap = 1
    short = plain._plan_cell(7, 1).bars[0]
    assert len(short.lines) == 1
    assert short.lines[0].endswith("…")
    assert short.height == layout.bar_height_pt


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
