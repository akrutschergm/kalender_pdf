"""Konfiguration: Feiertagskalender, entfernte Schalter."""

from pathlib import Path

import pytest

from kalender_pdf.config import ConfigError, load_config


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "kalender.yaml"
    path.write_text(body, encoding="utf-8")
    return path


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
