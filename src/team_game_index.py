from __future__ import annotations

from collections import defaultdict

from .models import MatchRecord


def assign_team_game_numbers(matches: list[MatchRecord]) -> dict[tuple[str, str], int]:
    counters: dict[str, int] = defaultdict(int)
    assignments: dict[tuple[str, str], int] = {}
    for match in matches:
        for team in match.teams:
            counters[team] += 1
            assignments[(match.path, team)] = counters[team]
    return assignments


def validate_team_game_counts(matches: list[MatchRecord], warnings: list[str]) -> None:
    counters: dict[str, int] = defaultdict(int)
    for match in matches:
        for team in match.teams:
            counters[team] += 1

    for team, count in sorted(counters.items()):
        if count < 14:
            warnings.append(f"{team}: only {count} games found; expected at least 14 for a full IPL season.")
        if count > 17:
            warnings.append(f"{team}: {count} games found; expected no more than 17 including playoffs.")
