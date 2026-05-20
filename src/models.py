from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class MatchRecord:
    path: str
    data: dict
    match_date: date
    teams: tuple[str, ...]


@dataclass
class PlayerMatchStats:
    player_name: str
    team_name: str
    in_starting_xi: bool = False
    runs: int = 0
    balls_faced: int = 0
    fours: int = 0
    sixes: int = 0
    dismissed: bool = False
    bowler_wickets: int = 0
    lbw_bowled_wickets: int = 0
    legal_balls_bowled: int = 0
    bowler_runs_conceded: int = 0
    maiden_overs: int = 0
    catches: int = 0
    stumpings: int = 0
    run_out_direct_hits: int = 0
    run_out_assists: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlayerMatchPoints:
    player_name: str
    team_name: str
    match_date: date
    game_number: int
    points: float
