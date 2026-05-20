from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

from .models import MatchRecord


def _parse_match_date(raw_dates: object) -> date | None:
    if not raw_dates:
        return None
    first = raw_dates[0] if isinstance(raw_dates, list) else raw_dates
    try:
        return date.fromisoformat(str(first))
    except ValueError:
        return None


def _resolve_input_dir(input_dir: str | Path, warnings: list[str]) -> Path:
    root = Path(input_dir).expanduser()
    if root.exists():
        return root

    # Keep the default convenient when the JSON folder is beside the project
    # or still in Downloads after extracting the Cricsheet zip.
    if str(input_dir) in {"data/ipl_json", "ipl_json"}:
        candidates = [Path.cwd() / "ipl_json", Path.cwd().parent / "ipl_json", Path.home() / "Downloads" / "ipl_json"]
        for candidate in candidates:
            if candidate.exists():
                warnings.append(f"Input directory {input_dir} not found; using {candidate}.")
                return candidate

    return root


def load_matches(input_dir: str | Path, season_year: int, warnings: list[str]) -> list[MatchRecord]:
    """Load Cricsheet JSON files for a season, skipping malformed files."""
    root = _resolve_input_dir(input_dir, warnings)
    if not root.exists():
        warnings.append(f"Input directory does not exist: {root}")
        return []

    matches: list[MatchRecord] = []
    json_files = sorted(root.glob("*.json"))
    if not json_files:
        warnings.append(f"No JSON files found in input directory: {root}")
        return []

    available_years: Counter[str] = Counter()
    for path in json_files:
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"{path.name}: could not load JSON: {exc}")
            continue

        info = data.get("info", {})
        match_date = _parse_match_date(info.get("dates"))
        if match_date is None:
            warnings.append(f"{path.name}: missing or invalid info.dates")
            continue
        available_years[str(match_date.year)] += 1
        if match_date.year != season_year:
            continue

        teams = info.get("teams") or []
        if not isinstance(teams, list) or len(teams) < 2:
            warnings.append(f"{path.name}: missing or invalid info.teams")
            continue

        matches.append(MatchRecord(str(path), data, match_date, tuple(str(team) for team in teams)))

    if not matches:
        years = ", ".join(f"{year} ({count})" for year, count in sorted(available_years.items()))
        warnings.append(f"No matches found for season {season_year} in {root}. Available years: {years or 'none'}.")

    return sorted(matches, key=lambda match: (match.match_date, match.path))
