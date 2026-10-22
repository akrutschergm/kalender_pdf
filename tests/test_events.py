"""Tests für Event-Modell und exklusive DTEND-Semantik."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from kalender_pdf.events import CalendarEvent, EventKind, SourceStyle, classify_kind
from kalender_pdf.pdf_renderer import is_span_event


def _event(**kwargs) -> CalendarEvent:
    defaults = dict(
        uid="x",
        summary="Test",
        source_name="S",
        style=SourceStyle(),
        start=date(2026, 1, 1),
        end=date(2026, 1, 2),
        all_day=True,
        kind=EventKind.ALL_DAY,
    )
    defaults.update(kwargs)
    return CalendarEvent(**defaults)


def test_single_all_day_exclusive_end():
    """Feiertag 1.1. mit DTEND=2.1. → nur ein Tag."""
    ev = _event(start=date(2026, 1, 1), end=date(2026, 1, 2))
    assert ev.last_inclusive_date == date(2026, 1, 1)
    assert ev.dates_in_range(date(2026, 1, 1), date(2026, 12, 31)) == [date(2026, 1, 1)]


def test_multi_day_vacation_exclusive_end():
    """Ferien 1.7.–14.7. mit DTEND=15.7. → 14 Tage, kein 15.7."""
    ev = _event(
        start=date(2026, 7, 1),
        end=date(2026, 7, 15),
        kind=EventKind.MULTI_DAY,
    )
    days = ev.dates_in_range(date(2026, 1, 1), date(2026, 12, 31))
    assert days[0] == date(2026, 7, 1)
    assert days[-1] == date(2026, 7, 14)
    assert len(days) == 14
    assert date(2026, 7, 15) not in days


def test_classify_multi_day():
    assert classify_kind(date(2026, 7, 1), date(2026, 7, 15), True) == EventKind.MULTI_DAY
    assert classify_kind(date(2026, 1, 1), date(2026, 1, 2), True) == EventKind.ALL_DAY


def test_timed_label():
    tz = ZoneInfo("Europe/Berlin")
    ev = _event(
        start=datetime(2026, 3, 1, 10, 30, tzinfo=tz),
        end=datetime(2026, 3, 1, 11, 30, tzinfo=tz),
        all_day=False,
        kind=EventKind.TIMED,
        summary="Gottesdienst",
    )
    assert ev.label("Europe/Berlin") == "10:30 Gottesdienst"


def test_timed_multi_day_is_span_with_start_time():
    tz = ZoneInfo("Europe/Berlin")
    start = datetime(2026, 5, 1, 18, 0, tzinfo=tz)
    end = datetime(2026, 5, 3, 12, 0, tzinfo=tz)
    assert classify_kind(start, end, False) == EventKind.TIMED
    ev = _event(
        start=start,
        end=end,
        all_day=False,
        kind=EventKind.TIMED,
        summary="Freizeit",
    )
    assert is_span_event(ev)
    assert ev.label("Europe/Berlin") == "18:00 Freizeit"


def test_same_day_timed_is_not_span():
    tz = ZoneInfo("Europe/Berlin")
    ev = _event(
        start=datetime(2026, 5, 1, 10, 0, tzinfo=tz),
        end=datetime(2026, 5, 1, 12, 0, tzinfo=tz),
        all_day=False,
        kind=EventKind.TIMED,
    )
    assert not is_span_event(ev)
