"""Konfiguration laden und validieren."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from kalender_pdf.events import SourceStyle


class ConfigError(Exception):
    """Ungültige oder unvollständige Konfiguration."""


@dataclass
class SourceConfig:
    name: str
    url: str | None = None
    path: str | None = None
    enabled: bool = True
    style: SourceStyle = field(default_factory=SourceStyle)

    def __post_init__(self) -> None:
        if not self.url and not self.path:
            raise ConfigError(f"Quelle '{self.name}': url oder path erforderlich")
        if self.url and self.path:
            raise ConfigError(f"Quelle '{self.name}': nur url ODER path angeben")


@dataclass
class LayoutConfig:
    """Seitenlayout. Standard: A2 Querformat – 12 Monatsspalten brauchen Breite."""

    page_size: str = "A2"
    orientation: str = "landscape"  # landscape | portrait
    margin_mm: float = 10.0
    day_label_width_mm: float = 8.0
    header_height_mm: float = 14.0
    title: str | None = None
    timezone: str = "Europe/Berlin"
    show_weekdays: bool = True
    weekday_locale: str = "de"
    grid_line_color: str = "#cccccc"
    header_bg_color: str = "#2c3e50"
    header_text_color: str = "#ffffff"
    weekend_bg_color: str = "#f5f5f5"
    empty_day_bg_color: str = "#eeeeee"
    title_font_size: float = 16.0
    month_font_size: float = 9.0
    day_font_size: float = 7.0
    max_events_per_cell: int = 6
    bar_height_pt: float = 8.0
    event_line_gap_pt: float = 1.0


@dataclass
class AppConfig:
    year: int
    output: str = "output/kalender.pdf"
    sources: list[SourceConfig] = field(default_factory=list)
    layout: LayoutConfig = field(default_factory=LayoutConfig)

    @property
    def output_path(self) -> Path:
        return Path(self.output)


def _require(data: dict[str, Any], key: str, ctx: str) -> Any:
    if key not in data:
        raise ConfigError(f"{ctx}: Pflichtfeld '{key}' fehlt")
    return data[key]


def _parse_style(raw: dict[str, Any] | None) -> SourceStyle:
    if not raw:
        return SourceStyle()
    known = {
        "font_name",
        "font_size",
        "color",
        "all_day_font_name",
        "all_day_font_size",
        "all_day_color",
        "bar_color",
        "bar_text_color",
        "bar_font_size",
        "show_time",
        "as_bar",
    }
    unknown = set(raw) - known
    if unknown:
        raise ConfigError(f"Unbekannte Style-Felder: {sorted(unknown)}")
    return SourceStyle(**raw)


def _parse_layout(raw: dict[str, Any] | None) -> LayoutConfig:
    if not raw:
        return LayoutConfig()
    orientation = raw.get("orientation", "landscape")
    if orientation not in {"landscape", "portrait"}:
        raise ConfigError("layout.orientation muss 'landscape' oder 'portrait' sein")
    known = {f.name for f in LayoutConfig.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    unknown = set(raw) - known
    if unknown:
        raise ConfigError(f"Unbekannte Layout-Felder: {sorted(unknown)}")
    return LayoutConfig(**raw)


def _parse_source(raw: dict[str, Any], index: int) -> SourceConfig:
    ctx = f"sources[{index}]"
    name = str(_require(raw, "name", ctx))
    style = _parse_style(raw.get("style"))
    return SourceConfig(
        name=name,
        url=raw.get("url"),
        path=raw.get("path"),
        enabled=bool(raw.get("enabled", True)),
        style=style,
    )


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigError(f"Konfigurationsdatei nicht gefunden: {config_path}")

    try:
        with config_path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML-Fehler in {config_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError("Konfiguration muss ein YAML-Objekt (Mapping) sein")

    year = int(_require(data, "year", "root"))
    sources_raw = _require(data, "sources", "root")
    if not isinstance(sources_raw, list) or not sources_raw:
        raise ConfigError("'sources' muss eine nicht-leere Liste sein")

    sources = [_parse_source(item, i) for i, item in enumerate(sources_raw)]
    enabled = [s for s in sources if s.enabled]
    if not enabled:
        raise ConfigError("Mindestens eine Quelle muss enabled: true haben")

    return AppConfig(
        year=year,
        output=str(data.get("output", "output/kalender.pdf")),
        sources=sources,
        layout=_parse_layout(data.get("layout")),
    )
