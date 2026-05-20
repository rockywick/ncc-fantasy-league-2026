from __future__ import annotations

from collections import defaultdict

from .models import MatchRecord, PlayerMatchStats

BOWLER_WICKET_KINDS = {
    "bowled",
    "caught",
    "caught and bowled",
    "lbw",
    "hit wicket",
    "stumped",
}
LBW_BOWLED_KINDS = {"bowled", "lbw"}


def _ensure(stats: dict[tuple[str, str], PlayerMatchStats], player: str, team: str) -> PlayerMatchStats:
    key = (player, team)
    if key not in stats:
        stats[key] = PlayerMatchStats(player_name=player, team_name=team)
    return stats[key]


def _opponent_team(teams: tuple[str, ...], batting_team: str) -> str:
    for team in teams:
        if team != batting_team:
            return team
    return "Unknown"


def _fielder_name(raw_fielder: object) -> str | None:
    if isinstance(raw_fielder, dict):
        return raw_fielder.get("name")
    if isinstance(raw_fielder, str):
        return raw_fielder
    return None


def _delivery_runs(delivery: dict) -> tuple[int, int]:
    runs = delivery.get("runs", {}) or {}
    extras = delivery.get("extras", {}) or {}
    batter_runs = int(runs.get("batter", 0))
    bowler_extras = int(extras.get("wides", 0)) + int(extras.get("noballs", 0))
    return batter_runs, batter_runs + bowler_extras


def _is_legal_ball(delivery: dict) -> bool:
    extras = delivery.get("extras", {}) or {}
    return "wides" not in extras and "noballs" not in extras


def parse_match(match: MatchRecord, warnings: list[str]) -> list[PlayerMatchStats]:
    info = match.data.get("info", {}) or {}
    stats: dict[tuple[str, str], PlayerMatchStats] = {}

    players = info.get("players")
    if isinstance(players, dict):
        for team, names in players.items():
            if len(names or []) != 11:
                warnings.append(
                    "Some Cricsheet info.players lists contain more or fewer than 11 players, commonly due to impact-player-era records; awarding playing points to all listed players."
                )
            for player in names or []:
                _ensure(stats, str(player), str(team)).in_starting_xi = True
    else:
        warnings.append(f"{match.path}: info.players missing; starting XI points cannot be awarded reliably.")

    innings = match.data.get("innings", [])
    if not isinstance(innings, list):
        warnings.append(f"{match.path}: innings is missing or not a list.")
        return list(stats.values())

    over_bowler_runs: dict[tuple[str, int, str], int] = defaultdict(int)
    over_legal_balls: dict[tuple[str, int, str], int] = defaultdict(int)

    for innings_item in innings:
        if not isinstance(innings_item, dict):
            warnings.append(f"{match.path}: unexpected innings item structure.")
            continue

        # Current Cricsheet JSON uses {"team": "...", "overs": [...]}; older variants may wrap this.
        innings_data = innings_item
        if "team" not in innings_data and len(innings_item) == 1:
            innings_data = next(iter(innings_item.values())) or {}
        if innings_data.get("super_over"):
            warnings.append(f"{match.path}: super over deliveries are included in fantasy scoring.")

        batting_team = str(innings_data.get("team", "Unknown"))
        bowling_team = _opponent_team(match.teams, batting_team)
        overs = innings_data.get("overs", [])
        if not isinstance(overs, list):
            warnings.append(f"{match.path}: overs missing for innings by {batting_team}.")
            continue

        for over in overs:
            over_number = int(over.get("over", 0)) if isinstance(over, dict) else 0
            deliveries = over.get("deliveries", []) if isinstance(over, dict) else []
            for delivery in deliveries:
                if not isinstance(delivery, dict):
                    warnings.append(f"{match.path}: unexpected delivery structure.")
                    continue

                batter = delivery.get("batter")
                bowler = delivery.get("bowler")
                if not batter or not bowler:
                    warnings.append(f"{match.path}: delivery missing batter or bowler.")
                    continue

                batter_stats = _ensure(stats, str(batter), batting_team)
                bowler_stats = _ensure(stats, str(bowler), bowling_team)

                batter_runs, bowler_runs = _delivery_runs(delivery)
                batter_stats.runs += batter_runs
                if batter_runs == 4:
                    batter_stats.fours += 1
                elif batter_runs == 6:
                    batter_stats.sixes += 1

                if _is_legal_ball(delivery):
                    batter_stats.balls_faced += 1
                    bowler_stats.legal_balls_bowled += 1
                    over_key = (bowling_team, over_number, str(bowler))
                    over_legal_balls[over_key] += 1

                bowler_stats.bowler_runs_conceded += bowler_runs
                over_bowler_runs[(bowling_team, over_number, str(bowler))] += bowler_runs

                for wicket in delivery.get("wickets", []) or []:
                    if not isinstance(wicket, dict):
                        continue
                    player_out = wicket.get("player_out")
                    kind = str(wicket.get("kind", "")).lower()
                    if player_out:
                        _ensure(stats, str(player_out), batting_team).dismissed = True

                    fielders = [_fielder_name(f) for f in wicket.get("fielders", []) or []]
                    fielders = [name for name in fielders if name]

                    if kind in BOWLER_WICKET_KINDS:
                        bowler_stats.bowler_wickets += 1
                        if kind in LBW_BOWLED_KINDS:
                            bowler_stats.lbw_bowled_wickets += 1

                    if kind == "caught":
                        for fielder in fielders:
                            _ensure(stats, fielder, bowling_team).catches += 1
                    elif kind == "caught and bowled":
                        bowler_stats.catches += 1
                    elif kind == "stumped":
                        for fielder in fielders:
                            _ensure(stats, fielder, bowling_team).stumpings += 1
                    elif kind == "run out":
                        if len(fielders) == 1:
                            _ensure(stats, fielders[0], bowling_team).run_out_direct_hits += 1
                        elif len(fielders) > 1:
                            for fielder in fielders:
                                _ensure(stats, fielder, bowling_team).run_out_assists += 1

    for key, legal_balls in over_legal_balls.items():
        if legal_balls == 6 and over_bowler_runs.get(key, 0) == 0:
            team, _over_number, bowler = key
            _ensure(stats, bowler, team).maiden_overs += 1

    return list(stats.values())
