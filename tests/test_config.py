"""Konfiguration: Feiertagskalender, entfernte Schalter."""

from pathlib import Path

import pytest

from kalender_pdf.config import ConfigError, load_config


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "kalender.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_file_url_is_relative_to_config(tmp_path: Path):
    path = _write(
        tmp_path,
        """
year: 2026
sources:
  - name: Feiertage
    url: file://feiertage_2027.ics
""",
    )
    source = load_config(path).sources[0]
    assert source.url is None
    assert Path(source.path) == tmp_path / "feiertage_2027.ics"

    absolute = _write(
        tmp_path,
        """
year: 2026
sources:
  - name: Feiertage
    url: file:///C:/kalender/feiertage.ics
""",
    )
    assert Path(load_config(absolute).sources[0].path) == Path("C:/kalender/feiertage.ics")


def test_holidays_flag(tmp_path: Path):
    path = _write(
        tmp_path,
        """
year: 2026
sources:
  - name: Ferien
    path: data/ferien.ics
    holidays: true
    style:
      color: "#888888"
""",
    )
    config = load_config(path)
    assert config.sources[0].holidays is True


def test_page_size_a3(tmp_path: Path):
    path = _write(
        tmp_path,
        """
year: 2026
layout:
  page_size: a3
sources:
  - name: Ferien
    path: data/ferien.ics
""",
    )
    config = load_config(path)
    assert config.layout.page_size == "A3"


def test_alternate_month_color_optional(tmp_path: Path):
    plain = _write(
        tmp_path,
        """
year: 2026
sources:
  - name: Ferien
    path: data/ferien.ics
""",
    )
    assert load_config(plain).layout.alternate_month_bg_color is None
    assert load_config(plain).layout.empty_day_bg_color is None
    assert load_config(plain).layout.day_font_size == 7.0
    assert load_config(plain).layout.weekday_font_size == 5.5
    tinted = tmp_path / "tinted.yaml"
    tinted.write_text(
        """
year: 2026
layout:
  alternate_month_bg_color: "#d9e6f2"
sources:
  - name: Ferien
    path: data/ferien.ics
""",
        encoding="utf-8",
    )
    assert load_config(tinted).layout.alternate_month_bg_color == "#d9e6f2"


def test_day_and_weekday_font_sizes(tmp_path: Path):
    path = _write(
        tmp_path,
        """
year: 2026
layout:
  day_font_size: 8
  weekday_font_size: 6
sources:
  - name: Ferien
    path: data/ferien.ics
""",
    )
    layout = load_config(path).layout
    assert layout.day_font_size == 8
    assert layout.weekday_font_size == 6


def test_wrap_text_and_max_lines(tmp_path: Path):
    path = _write(
        tmp_path,
        """
year: 2026
layout:
  max_event_lines: 4
sources:
  - name: Ferien
    path: data/ferien.ics
    wrap_text: false
""",
    )
    config = load_config(path)
    assert config.layout.max_event_lines == 4
    assert config.sources[0].wrap_text is False
    plain = _write(
        tmp_path,
        """
year: 2026
sources:
  - name: Ferien
    path: data/ferien.ics
""",
    )
    defaults = load_config(plain)
    assert defaults.layout.max_event_lines == 3
    assert defaults.sources[0].wrap_text is True


def test_unknown_page_size_rejected(tmp_path: Path):
    path = _write(
        tmp_path,
        """
year: 2026
layout:
  page_size: B3
sources:
  - name: Ferien
    path: data/ferien.ics
""",
    )
    with pytest.raises(ConfigError, match="page_size"):
        load_config(path)


def test_show_time_and_as_bar_rejected(tmp_path: Path):
    path = _write(
        tmp_path,
        """
year: 2026
sources:
  - name: Ferien
    path: data/ferien.ics
    style:
      show_time: false
      as_bar: true
""",
    )
    with pytest.raises(ConfigError, match="show_time"):
        load_config(path)
