"""iCal-Parsing und exclusive Enddaten."""

from datetime import date
from pathlib import Path

from kalender_pdf.config import SourceConfig
from kalender_pdf.events import EventKind, SourceStyle
from kalender_pdf.ical_loader import expand_source_events, parse_calendar

FIXTURE = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
UID:holiday-1
DTSTART;VALUE=DATE:20260101
DTEND;VALUE=DATE:20260102
SUMMARY:Neujahr
END:VEVENT
BEGIN:VEVENT
UID:vacation-1
DTSTART;VALUE=DATE:20260701
DTEND;VALUE=DATE:20260715
SUMMARY:Sommerferien
END:VEVENT
BEGIN:VEVENT
UID:service-1
DTSTART:20260301T100000
DTEND:20260301T110000
SUMMARY:Gottesdienst
END:VEVENT
END:VCALENDAR
"""


def test_parse_and_expand(tmp_path: Path):
    ics = tmp_path / "test.ics"
    ics.write_bytes(FIXTURE)
    source = SourceConfig(
        name="Test",
        path=str(ics),
        style=SourceStyle(as_bar=True, show_time=True),
    )
    events = expand_source_events(source, 2026, timezone_name="Europe/Berlin")
    by_uid = {e.uid.split("#")[0]: e for e in events}

    holiday = by_uid["holiday-1"]
    assert holiday.all_day
    assert holiday.kind == EventKind.ALL_DAY
    assert holiday.dates_in_range(date(2026, 1, 1), date(2026, 12, 31)) == [date(2026, 1, 1)]

    vacation = by_uid["vacation-1"]
    assert vacation.kind == EventKind.MULTI_DAY
    days = vacation.dates_in_range(date(2026, 1, 1), date(2026, 12, 31))
    assert len(days) == 14
    assert days[-1] == date(2026, 7, 14)

    service = by_uid["service-1"]
    assert not service.all_day
    assert "Gottesdienst" in service.label("Europe/Berlin")


def test_invalid_ical_raises():
    import pytest

    from kalender_pdf.ical_loader import SourceError, parse_calendar

    with pytest.raises(SourceError):
        parse_calendar(b"NOT ICAL", "Bad")
