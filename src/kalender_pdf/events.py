"""Gemeinsames Event-Modell unabhängig von iCal und PDF."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo


class EventKind(str, Enum):
    TIMED = "timed"
    ALL_DAY = "all_day"
    MULTI_DAY = "multi_day"


@dataclass(frozen=True)
class SourceStyle:
    """Darstellung eines Kalender-Quellen-Eintrags."""

    font_name: str = "Helvetica"
    font_size: float = 6.0
    color: str = "#1a1a1a"
    all_day_font_name: str | None = None
    all_day_font_size: float | None = None
    all_day_color: str | None = None
    bar_color: str | None = None
    bar_text_color: str = "#ffffff"
    bar_font_size: float | None = None

    def resolve_font_name(self, *, all_day: bool) -> str:
        if all_day and self.all_day_font_name:
            return self.all_day_font_name
        return self.font_name

    def resolve_font_size(self, *, all_day: bool, bar: bool = False) -> float:
        if bar and self.bar_font_size is not None:
            return self.bar_font_size
        if all_day and self.all_day_font_size is not None:
            return self.all_day_font_size
        return self.font_size

    def resolve_color(self, *, all_day: bool) -> str:
        if all_day and self.all_day_color:
            return self.all_day_color
        return self.color

    def resolve_bar_color(self) -> str:
        return self.bar_color or self.all_day_color or self.color


@dataclass
class CalendarEvent:
    """Normalisiertes Kalenderereignis für die PDF-Darstellung."""

    uid: str
    summary: str
    source_name: str
    style: SourceStyle
    start: date | datetime
    end: date | datetime
    all_day: bool
    kind: EventKind
    timezone: str | None = None
    location: str | None = None
    description: str | None = None
    meta: dict = field(default_factory=dict)
    holiday_calendar: bool = False
    wrap_text: bool = True
    source_index: int = 0
    event_index: int = 0

    @property
    def start_date(self) -> date:
        if isinstance(self.start, datetime):
            return self.start.date()
        return self.start

    @property
    def end_date_exclusive(self) -> date:
        """Exklusives Enddatum (iCal-Semantik für ganztägige Events)."""
        if isinstance(self.end, datetime):
            # Timed: Ende am selben Tag zählt noch; nächster Tag nur bei Mitternacht
            if self.end.time() == time(0, 0):
                return self.end.date()
            return self.end.date() + timedelta(days=1)
        return self.end

    @property
    def last_inclusive_date(self) -> date:
        return self.end_date_exclusive - timedelta(days=1)

    def dates_in_range(self, year_start: date, year_end: date) -> list[date]:
        """Inklusive Kalendertage, die das Event im angegebenen Jahresbereich berührt."""
        first = max(self.start_date, year_start)
        last = min(self.last_inclusive_date, year_end)
        if last < first:
            return []
        days: list[date] = []
        current = first
        while current <= last:
            days.append(current)
            current += timedelta(days=1)
        return days

    def display_time(self, tz_name: str | None = None) -> str | None:
        if self.all_day or not isinstance(self.start, datetime):
            return None
        dt = self.start
        if dt.tzinfo is None:
            return dt.strftime("%H:%M")
        target = ZoneInfo(tz_name) if tz_name else dt.tzinfo
        return dt.astimezone(target).strftime("%H:%M")

    def label(self, tz_name: str | None = None) -> str:
        time_prefix = self.display_time(tz_name)
        if time_prefix:
            return f"{time_prefix} {self.summary}"
        return self.summary


def classify_kind(start: date | datetime, end: date | datetime, all_day: bool) -> EventKind:
    if not all_day:
        return EventKind.TIMED
    start_d = start.date() if isinstance(start, datetime) else start
    if isinstance(end, datetime):
        end_excl = end.date() if end.time() == time(0, 0) else end.date() + timedelta(days=1)
    else:
        end_excl = end
    span = (end_excl - start_d).days
    if span > 1:
        return EventKind.MULTI_DAY
    return EventKind.ALL_DAY
