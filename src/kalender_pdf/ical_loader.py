"""iCalendar-Quellen laden, expandieren und normalisieren."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import httpx
import recurring_ical_events
from icalendar import Calendar
from icalendar import Event as ICalEvent

from kalender_pdf.config import SourceConfig
from kalender_pdf.events import CalendarEvent, classify_kind


class SourceError(Exception):
    """Quelle unerreichbar oder ungültig."""


def _default_tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception as exc:  # noqa: BLE001
        raise SourceError(f"Unbekannte Zeitzone: {name}") from exc


def fetch_ical_bytes(source: SourceConfig, *, timeout: float = 60.0) -> bytes:
    """Lädt iCal-Daten von URL oder Dateipfad."""
    if source.path:
        path = Path(source.path)
        if not path.is_file():
            raise SourceError(f"Quelle '{source.name}': Datei nicht gefunden: {path}")
        try:
            return path.read_bytes()
        except OSError as exc:
            raise SourceError(f"Quelle '{source.name}': Datei nicht lesbar: {exc}") from exc

    assert source.url is not None
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(source.url)
            response.raise_for_status()
            return response.content
    except httpx.HTTPStatusError as exc:
        raise SourceError(
            f"Quelle '{source.name}': HTTP {exc.response.status_code} von {source.url}"
        ) from exc
    except httpx.RequestError as exc:
        raise SourceError(
            f"Quelle '{source.name}': nicht erreichbar ({source.url}): {exc}"
        ) from exc


def parse_calendar(data: bytes, source_name: str) -> Calendar:
    try:
        cal = Calendar.from_ical(data)
    except Exception as exc:  # noqa: BLE001
        raise SourceError(f"Quelle '{source_name}': ungültiges iCalendar-Format: {exc}") from exc
    if not isinstance(cal, Calendar):
        raise SourceError(f"Quelle '{source_name}': Wurzel ist kein VCALENDAR")
    return cal


def _as_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value


def _normalize_dt(
    value: date | datetime,
    *,
    default_tz: ZoneInfo,
) -> date | datetime:
    if type(value) is date:
        return value
    assert isinstance(value, datetime)
    if value.tzinfo is None:
        return value.replace(tzinfo=default_tz)
    return value


def _extract_dt_pair(
    component: ICalEvent,
    default_tz: ZoneInfo,
) -> tuple[date | datetime, date | datetime, bool]:
    """Liefert (start, end, all_day).

    Bei ganztägigen Events ist ``end`` das iCal-exklusive DTEND-Datum
    (ein Feiertag am 1.1. hat DTEND=2.1.).
    """
    if "DTSTART" not in component:
        raise SourceError("VEVENT ohne DTSTART")

    dtstart_prop = component["DTSTART"]
    start_raw = dtstart_prop.dt
    value_param = str(dtstart_prop.params.get("VALUE", "")).upper()
    all_day = value_param == "DATE" or type(start_raw) is date

    if all_day:
        start: date | datetime = _as_date(start_raw)
    else:
        start = _normalize_dt(start_raw, default_tz=default_tz)

    if "DTEND" in component:
        end_raw = component["DTEND"].dt
        if all_day:
            end: date | datetime = _as_date(end_raw)
        else:
            end = _normalize_dt(end_raw, default_tz=default_tz)
    elif "DURATION" in component:
        duration = component["DURATION"].dt
        if all_day:
            end = _as_date(start) + duration
        else:
            assert isinstance(start, datetime)
            end = start + duration
    else:
        if all_day:
            end = _as_date(start) + timedelta(days=1)
        else:
            assert isinstance(start, datetime)
            end = start

    return start, end, all_day


def _summary(component: ICalEvent) -> str:
    raw = component.get("SUMMARY")
    if raw is None:
        return "(ohne Titel)"
    text = str(raw).strip()
    return text or "(ohne Titel)"


def _uid(component: ICalEvent, fallback: str) -> str:
    raw = component.get("UID")
    if raw is None:
        return fallback
    return str(raw)


def component_to_event(
    component: ICalEvent,
    source: SourceConfig,
    default_tz: ZoneInfo,
    *,
    occurrence_id: str = "",
) -> CalendarEvent:
    try:
        start, end, all_day = _extract_dt_pair(component, default_tz)
    except SourceError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise SourceError(f"Quelle '{source.name}': Event nicht lesbar: {exc}") from exc

    kind = classify_kind(start, end, all_day)
    uid = _uid(component, fallback=f"{source.name}:{occurrence_id}:{start}")
    if occurrence_id:
        uid = f"{uid}#{occurrence_id}"

    location = str(component["LOCATION"]) if component.get("LOCATION") else None
    description = str(component["DESCRIPTION"]) if component.get("DESCRIPTION") else None

    return CalendarEvent(
        uid=uid,
        summary=_summary(component),
        source_name=source.name,
        style=source.style,
        start=start,
        end=end,
        all_day=all_day,
        kind=kind,
        timezone=str(default_tz),
        location=location,
        description=description,
        holiday_calendar=source.holidays,
        wrap_text=source.wrap_text,
    )


def _overlapping_non_recurring(
    calendar: Calendar,
    source: SourceConfig,
    default_tz: ZoneInfo,
    year_start: date,
    year_end: date,
) -> list[CalendarEvent]:
    """Ganztägige Events, die vor dem Jahr starten und hineinreichen."""
    extra: list[CalendarEvent] = []
    for component in calendar.walk("VEVENT"):
        if component.get("RRULE") or component.get("RDATE"):
            continue
        try:
            start, end, all_day = _extract_dt_pair(component, default_tz)
        except Exception:  # noqa: BLE001
            continue
        if not all_day:
            continue
        start_d = _as_date(start)
        end_d = _as_date(end)  # exclusive
        last = end_d - timedelta(days=1)
        if start_d < year_start <= last:
            event = component_to_event(component, source, default_tz, occurrence_id="span")
            if event.dates_in_range(year_start, year_end):
                extra.append(event)
    return extra


def expand_source_events(
    source: SourceConfig,
    year: int,
    *,
    timezone_name: str = "Europe/Berlin",
    timeout: float = 60.0,
) -> list[CalendarEvent]:
    """Lädt eine Quelle und expandiert VEVENTs für das Kalenderjahr."""
    default_tz = _default_tz(timezone_name)
    data = fetch_ical_bytes(source, timeout=timeout)
    calendar = parse_calendar(data, source.name)

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    query_end = datetime(year + 1, 1, 1, tzinfo=default_tz)
    query_start = datetime(year, 1, 1, tzinfo=default_tz)

    try:
        occurrences: Iterable[ICalEvent] = recurring_ical_events.of(calendar).between(
            query_start, query_end
        )
    except Exception as exc:  # noqa: BLE001
        raise SourceError(
            f"Quelle '{source.name}': Wiederholungen konnten nicht expandiert werden: {exc}"
        ) from exc

    events: list[CalendarEvent] = []
    for index, component in enumerate(occurrences):
        if getattr(component, "name", None) != "VEVENT":
            continue
        event = component_to_event(
            component,
            source,
            default_tz,
            occurrence_id=str(index),
        )
        if event.dates_in_range(year_start, year_end):
            events.append(event)

    events.extend(
        _overlapping_non_recurring(calendar, source, default_tz, year_start, year_end)
    )

    seen: set[tuple[str, str]] = set()
    unique: list[CalendarEvent] = []
    for ev in events:
        key = (ev.uid.split("#")[0], ev.start.isoformat())
        if key in seen:
            continue
        seen.add(key)
        unique.append(ev)
    for index, ev in enumerate(unique):
        ev.event_index = index
    return unique


def load_all_sources(
    sources: list[SourceConfig],
    year: int,
    *,
    timezone_name: str = "Europe/Berlin",
    timeout: float = 60.0,
) -> list[CalendarEvent]:
    """Lädt alle aktivierten Quellen. Bei Fehler: klare Exception, Abbruch."""
    all_events: list[CalendarEvent] = []
    for source_index, source in enumerate(sources):
        if not source.enabled:
            continue
        print(f"  Lade: {source.name} …")
        events = expand_source_events(
            source,
            year,
            timezone_name=timezone_name,
            timeout=timeout,
        )
        for ev in events:
            ev.source_index = source_index
        print(f"    → {len(events)} Termin(e)")
        all_events.extend(events)
    return all_events
