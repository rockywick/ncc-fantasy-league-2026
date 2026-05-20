from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re

import pandas as pd

from .models import MatchRecord, PlayerMatchPoints

GAME_COLUMNS = [f"G{i}" for i in range(1, 18)]


def build_player_points_table(points: list[PlayerMatchPoints], warnings: list[str]) -> pd.DataFrame:
    rows: dict[tuple[str, str], dict[str, object]] = {}
    duplicate_teams: dict[str, set[str]] = defaultdict(set)

    for item in points:
        key = (item.player_name, item.team_name)
        duplicate_teams[item.player_name].add(item.team_name)
        if key not in rows:
            rows[key] = {"player_name": item.player_name, "team_name": item.team_name, **{col: 0.0 for col in GAME_COLUMNS}}
        if 1 <= item.game_number <= 17:
            rows[key][f"G{item.game_number}"] = float(rows[key][f"G{item.game_number}"]) + item.points
        else:
            warnings.append(
                f"{item.player_name} ({item.team_name}): game number {item.game_number} outside G1-G17; points omitted."
            )

    for player, teams in sorted(duplicate_teams.items()):
        if len(teams) > 1:
            warnings.append(f"Duplicate player name across teams: {player} appears for {', '.join(sorted(teams))}.")

    df = pd.DataFrame(rows.values())
    if df.empty:
        columns = ["player_name", "team_name", *GAME_COLUMNS, "total_points"]
        return pd.DataFrame(columns=columns)

    for col in GAME_COLUMNS:
        df[col] = df[col].fillna(0)
    df["total_points"] = df[GAME_COLUMNS].sum(axis=1)
    return df[["player_name", "team_name", *GAME_COLUMNS, "total_points"]].sort_values(
        ["team_name", "player_name"], kind="stable"
    )


def build_player_name_reference(points_df: pd.DataFrame) -> pd.DataFrame:
    if points_df.empty:
        return pd.DataFrame(columns=["player_name", "team_name"])
    return points_df[["player_name", "team_name"]].drop_duplicates().sort_values(["player_name", "team_name"], kind="stable")


def write_dataframe(df: pd.DataFrame, output_dir: str | Path, stem: str) -> None:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    df.to_csv(root / f"{stem}.csv", index=False)
    df.to_excel(root / f"{stem}.xlsx", index=False)


def _safe_filename_part(value: object) -> str:
    text = str(value).strip()
    text = re.sub(r"[^A-Za-z0-9]+", "_", text)
    return text.strip("_") or "unknown"


def match_number(match: MatchRecord) -> str:
    event = match.data.get("info", {}).get("event", {}) or {}
    number = event.get("match_number")
    if number is not None:
        return str(number)
    stage = event.get("stage") or event.get("name") or Path(match.path).stem
    return _safe_filename_part(stage)


def match_record_stem(match: MatchRecord) -> str:
    team1 = _safe_filename_part(match.teams[0] if len(match.teams) > 0 else "team1")
    team2 = _safe_filename_part(match.teams[1] if len(match.teams) > 1 else "team2")
    return f"{_safe_filename_part(match_number(match))}_{team1}_{team2}"


def write_match_records(
    match_player_rows: dict[str, list[dict[str, object]]],
    matches: list[MatchRecord],
    inputs_dir: str | Path,
    output_dir: str | Path,
    warnings: list[str],
) -> None:
    from .owner_points import load_owner_roster_lookup

    records_dir = Path(output_dir) / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    for old_file in records_dir.glob("*.csv"):
        old_file.unlink()

    owner_lookup = load_owner_roster_lookup(inputs_dir, warnings)
    for match in matches:
        stem = match_record_stem(match)
        rows = match_player_rows.get(match.path, [])
        player_df = pd.DataFrame(
            rows,
            columns=[
                "match_number",
                "match_date",
                "team_name",
                "team_game_number",
                "player_name",
                "points",
            ],
        ).sort_values(["team_name", "player_name"], kind="stable")
        player_df.to_csv(records_dir / f"{stem}.csv", index=False)

        owner_rows: list[dict[str, object]] = []
        for row in rows:
            phase = "before" if int(row["team_game_number"]) <= 7 else "after"
            cricsheet_player = str(row["player_name"])
            for owner_name, input_player_name in owner_lookup.get(phase, {}).get(cricsheet_player, []):
                owner_rows.append(
                    {
                        "owner_name": owner_name,
                        "player_name": input_player_name,
                        "cricsheet_player_name": cricsheet_player,
                        "team_name": row["team_name"],
                        "team_game_number": row["team_game_number"],
                        "phase": phase,
                        "points": row["points"],
                    }
                )

        owner_df = pd.DataFrame(
            owner_rows,
            columns=[
                "owner_name",
                "player_name",
                "cricsheet_player_name",
                "team_name",
                "team_game_number",
                "phase",
                "points",
            ],
        ).sort_values(["owner_name", "player_name", "team_name"], kind="stable")
        owner_df.to_csv(records_dir / f"{stem}_points.csv", index=False)


def write_warnings(warnings: list[str], output_dir: str | Path) -> None:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    text = "\n".join(dict.fromkeys(warnings))
    (root / "warnings.txt").write_text(text + ("\n" if text else ""), encoding="utf-8")
