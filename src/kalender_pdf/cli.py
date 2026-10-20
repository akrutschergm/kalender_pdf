"""Kommandozeile: kalender-pdf / python -m kalender_pdf."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kalender_pdf import __version__
from kalender_pdf.config import ConfigError, load_config
from kalender_pdf.ical_loader import SourceError, load_all_sources
from kalender_pdf.pdf_renderer import render_year_pdf


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kalender-pdf",
        description=(
            "Mehrere iCalendar-Quellen zu einem druckfertigen "
            "A2-Jahreskalender-PDF zusammenführen."
        ),
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config/example.yaml",
        help="Pfad zur YAML-Konfiguration (Standard: config/example.yaml)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Ausgabe-PDF (überschreibt config.output)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Kalenderjahr (überschreibt config.year)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="HTTP-Timeout pro Quelle in Sekunden (Standard: 60)",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Konfigurationsfehler: {exc}", file=sys.stderr)
        return 2

    if args.year is not None:
        config.year = args.year
    output = Path(args.output) if args.output else config.output_path

    enabled = [s for s in config.sources if s.enabled]
    print(f"Jahr {config.year} · {len(enabled)} Quelle(n) · A2 {config.layout.orientation}")

    try:
        events = load_all_sources(
            config.sources,
            config.year,
            timezone_name=config.layout.timezone,
            timeout=args.timeout,
        )
    except SourceError as exc:
        print(f"Quellenfehler: {exc}", file=sys.stderr)
        print(
            "Hinweis: Prüfen Sie URL/Pfad und Netzwerk. "
            "Lokale .ics-Dateien können über 'path:' statt 'url:' konfiguriert werden.",
            file=sys.stderr,
        )
        return 1

    print(f"{len(events)} Termin(e) geladen.")
    try:
        path = render_year_pdf(
            config.year,
            events,
            output,
            layout=config.layout,
        )
    except OSError as exc:
        print(f"PDF konnte nicht geschrieben werden: {exc}", file=sys.stderr)
        return 1

    print(f"PDF geschrieben: {path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
