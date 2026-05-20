from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd

from .outputs import GAME_COLUMNS


def _load_overrides(inputs_dir: str | Path, warnings: list[str]) -> dict[str, str]:
    path = Path(inputs_dir) / "player_name_overrides.csv"
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        warnings.append(f"{path}: could not read player overrides: {exc}")
        return {}
    required = {"input_player_name", "cricsheet_player_name"}
    if not required.issubset(df.columns):
        warnings.append(f"{path}: expected columns input_player_name, cricsheet_player_name.")
        return {}
    return {
        str(row["input_player_name"]).strip(): str(row["cricsheet_player_name"]).strip()
        for _, row in df.dropna(subset=list(required)).iterrows()
        if str(row["input_player_name"]).strip()
    }


def load_owner_roster_lookup(
    inputs_dir: str | Path,
    warnings: list[str],
) -> dict[str, dict[str, list[tuple[str, str]]]]:
    """Return phase -> cricsheet player name -> [(owner, input player name)]."""
    root = Path(inputs_dir)
    overrides = _load_overrides(root, warnings)
    lookup: dict[str, dict[str, list[tuple[str, str]]]] = {
        "before": defaultdict(list),
        "after": defaultdict(list),
    }

    for phase, filename in [("before", "owners_before_trade.csv"), ("after", "owners_after_trade.csv")]:
        roster = _load_roster(root / filename, warnings)
        if roster is None:
            continue
        for _, row in roster.iterrows():
            owner = str(row["owner_name"]).strip()
            input_name = str(row["player_name"]).strip()
            if not owner or not input_name:
                continue
            cricsheet_name = overrides.get(input_name, input_name)
            lookup[phase][cricsheet_name].append((owner, input_name))

    return lookup


def _load_roster(path: Path, warnings: list[str]) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        warnings.append(f"{path}: could not read owner roster: {exc}")
        return None
    required = {"owner_name", "player_name"}
    if not required.issubset(df.columns):
        warnings.append(f"{path}: expected columns owner_name, player_name.")
        return None
    df["owner_name"] = df["owner_name"].astype(str).str.strip()
    df["player_name"] = df["player_name"].fillna("").astype(str).str.strip()
    return df[df["owner_name"] != ""]


def _filled_roster(roster: pd.DataFrame) -> pd.DataFrame:
    return roster[roster["player_name"] != ""].copy()


def _validate_roster_sizes(roster: pd.DataFrame, label: str, warnings: list[str]) -> None:
    filled = _filled_roster(roster)
    for owner, owner_rows in filled.groupby("owner_name"):
        count = len(owner_rows)
        if count != 15:
            warnings.append(f"{label}: {owner} has {count} filled players; expected exactly 15.")


def _validate_trade_limit(before: pd.DataFrame | None, after: pd.DataFrame | None, warnings: list[str]) -> None:
    if before is None or after is None:
        return

    before_filled = _filled_roster(before)
    after_filled = _filled_roster(after)
    if before_filled.empty or after_filled.empty:
        return

    owners = sorted(set(before["owner_name"]) | set(after["owner_name"]))
    for owner in owners:
        before_players = set(before_filled.loc[before_filled["owner_name"] == owner, "player_name"])
        after_players = set(after_filled.loc[after_filled["owner_name"] == owner, "player_name"])

        # Empty template rows should not warn before the rosters are filled.
        if not before_players and not after_players:
            continue

        dropped = before_players - after_players
        added = after_players - before_players
        if len(dropped) > 5 or len(added) > 5:
            warnings.append(
                f"Trade limit: {owner} changed {len(dropped)} outgoing and {len(added)} incoming players; maximum allowed is 5 each."
            )


def _sum_player_phase(player_df: pd.DataFrame, game_cols: list[str]) -> float:
    if player_df.empty:
        return 0.0
    return float(player_df[game_cols].sum(axis=1).sum())


def _apply_roster_phase(
    summary: dict[str, dict[str, float]],
    roster: pd.DataFrame,
    points_df: pd.DataFrame,
    overrides: dict[str, str],
    phase_key: str,
    game_cols: list[str],
    warnings: list[str],
) -> None:
    for _, row in roster.iterrows():
        owner = str(row["owner_name"]).strip()
        input_name = str(row["player_name"]).strip()
        if not input_name:
            continue
        cricsheet_name = overrides.get(input_name, input_name)
        matches = points_df[points_df["player_name"] == cricsheet_name]

        if matches.empty:
            warnings.append(f"Owner roster player not found: {input_name}")
            continue
        if len(matches["team_name"].unique()) > 1 and input_name not in overrides:
            warnings.append(
                f"Owner roster player is ambiguous and no override was supplied: {input_name}; including all matching teams."
            )

        summary[owner][phase_key] += _sum_player_phase(matches, game_cols)


def calculate_owner_summary(
    points_df: pd.DataFrame,
    inputs_dir: str | Path,
    warnings: list[str],
) -> pd.DataFrame | None:
    root = Path(inputs_dir)
    before = _load_roster(root / "owners_before_trade.csv", warnings)
    after = _load_roster(root / "owners_after_trade.csv", warnings)
    if before is None and after is None:
        return None

    overrides = _load_overrides(root, warnings)
    summary: dict[str, dict[str, float]] = defaultdict(lambda: {"phase1_points_G1_to_G7": 0.0, "phase2_points_G8_to_end": 0.0})

    for roster in [before, after]:
        if roster is not None:
            for owner in sorted(roster["owner_name"].dropna().unique()):
                if owner:
                    summary[str(owner)]

    if before is not None:
        _validate_roster_sizes(before, "owners_before_trade.csv", warnings)
    if after is not None:
        _validate_roster_sizes(after, "owners_after_trade.csv", warnings)
    _validate_trade_limit(before, after, warnings)

    if before is not None:
        _apply_roster_phase(summary, before, points_df, overrides, "phase1_points_G1_to_G7", GAME_COLUMNS[:7], warnings)
    if after is not None:
        _apply_roster_phase(summary, after, points_df, overrides, "phase2_points_G8_to_end", GAME_COLUMNS[7:], warnings)

    rows = []
    for owner, values in sorted(summary.items()):
        total = values["phase1_points_G1_to_G7"] + values["phase2_points_G8_to_end"]
        rows.append({"owner_name": owner, **values, "total_points": total})

    return pd.DataFrame(rows, columns=["owner_name", "phase1_points_G1_to_G7", "phase2_points_G8_to_end", "total_points"])
