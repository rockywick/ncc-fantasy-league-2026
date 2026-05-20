from __future__ import annotations

from pathlib import Path

import yaml

from .models import PlayerMatchStats


def load_scoring(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _range_points(value: float, ranges: list[dict]) -> float:
    for item in ranges or []:
        if float(item["min"]) <= value <= float(item["max"]):
            return float(item["points"])
    return 0


def _batting_milestone_points(runs: int, config: dict) -> float:
    bonuses = [
        (30, float(config.get("thirty_run_bonus", 0))),
        (50, float(config.get("fifty_run_bonus", 0))),
        (100, float(config.get("hundred_run_bonus", 0))),
    ]
    earned = [points for threshold, points in bonuses if runs >= threshold]
    if not earned:
        return 0
    if config.get("milestone_only_highest", True):
        return earned[-1]
    return sum(earned)


def _bowling_milestone_points(wickets: int, config: dict) -> float:
    bonuses = [
        (3, float(config.get("three_wicket_bonus", 0))),
        (4, float(config.get("four_wicket_bonus", 0))),
        (5, float(config.get("five_wicket_bonus", 0))),
    ]
    earned = [points for threshold, points in bonuses if wickets >= threshold]
    if not earned:
        return 0
    if config.get("milestone_only_highest", True):
        return earned[-1]
    return sum(earned)


def calculate_points(stats: PlayerMatchStats, scoring: dict) -> float:
    batting = scoring.get("batting", {})
    milestones = scoring.get("milestones", {})
    bowling = scoring.get("bowling", {})
    bowling_milestones = scoring.get("bowling_milestones", {})
    fielding = scoring.get("fielding", {})
    playing = scoring.get("playing", {})

    points = 0.0
    if stats.in_starting_xi:
        points += float(playing.get("in_starting_xi", 0))

    points += stats.runs * float(batting.get("run", 0))
    points += stats.fours * float(batting.get("four_bonus", 0))
    points += stats.sixes * float(batting.get("six_bonus", 0))
    if stats.dismissed and stats.runs == 0:
        points += float(batting.get("duck_penalty", 0))
    points += _batting_milestone_points(stats.runs, milestones)

    points += stats.bowler_wickets * float(bowling.get("wicket", 0))
    points += stats.lbw_bowled_wickets * float(bowling.get("lbw_bowled_bonus", 0))
    points += stats.maiden_overs * float(bowling.get("maiden_over", 0))
    points += _bowling_milestone_points(stats.bowler_wickets, bowling_milestones)

    points += stats.catches * float(fielding.get("catch", 0))
    if stats.catches >= 3:
        points += float(fielding.get("three_catch_bonus", 0))
    points += stats.stumpings * float(fielding.get("stumping", 0))
    points += stats.run_out_direct_hits * float(fielding.get("run_out_direct_hit", 0))
    points += stats.run_out_assists * float(fielding.get("run_out_thrower_or_catcher", 0))

    strike_rate = scoring.get("strike_rate", {})
    if strike_rate.get("enabled", False) and stats.balls_faced >= int(strike_rate.get("min_balls", 0)):
        rate = (stats.runs / stats.balls_faced) * 100 if stats.balls_faced else 0
        points += _range_points(rate, strike_rate.get("ranges", []))

    economy_rate = scoring.get("economy_rate", {})
    min_balls = int(float(economy_rate.get("min_overs", 0)) * 6)
    if economy_rate.get("enabled", False) and stats.legal_balls_bowled >= min_balls:
        overs = stats.legal_balls_bowled / 6
        economy = stats.bowler_runs_conceded / overs if overs else 0
        points += _range_points(economy, economy_rate.get("ranges", []))

    return points
