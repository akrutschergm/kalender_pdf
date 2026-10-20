"""PDF-Renderer schreibt eine gültige Datei."""

from datetime import date
from pathlib import Path

from kalender_pdf.events import CalendarEvent, EventKind, SourceStyle
from kalender_pdf.pdf_renderer import render_year_pdf


def test_render_minimal_pdf(tmp_path: Path):
    events = [
        CalendarEvent(
            uid="1",
            summary="Neujahr",
            source_name="Feiertage",
            style=SourceStyle(as_bar=True, bar_color="#9b59b6"),
            start=date(2026, 1, 1),
            end=date(2026, 1, 2),
            all_day=True,
            kind=EventKind.ALL_DAY,
        ),
        CalendarEvent(
            uid="2",
            summary="Sommerferien",
            source_name="Feiertage",
            style=SourceStyle(as_bar=True, bar_color="#9b59b6"),
            start=date(2026, 7, 1),
            end=date(2026, 7, 15),
            all_day=True,
            kind=EventKind.MULTI_DAY,
        ),
    ]
    out = tmp_path / "test.pdf"
    path = render_year_pdf(2026, events, out)
    assert path.is_file()
    assert path.stat().st_size > 1000
    assert path.read_bytes()[:4] == b"%PDF"
