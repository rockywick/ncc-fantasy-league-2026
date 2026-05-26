from __future__ import annotations

import csv
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = ROOT / "outputs"
INPUTS_DIR = ROOT / "inputs"
RECORDS_DIR = OUTPUTS_DIR / "records"
SITE_DATA_DIR = ROOT / "docs" / "data"

FILES_TO_COPY = [
    ("player_points_by_team_game.csv", "player_points_by_team_game.csv"),
    ("player_points_breakdown.csv", "player_points_breakdown.csv"),
    ("owner_points_summary.csv", "owner_points_summary.csv"),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_overrides() -> dict[str, str]:
    path = INPUTS_DIR / "player_name_overrides.csv"
    if not path.exists():
        return {}
    return {
        row["input_player_name"].strip(): row["cricsheet_player_name"].strip()
        for row in read_csv(path)
        if row.get("input_player_name") and row.get("cricsheet_player_name")
    }


def build_owner_player_points() -> None:
    point_rows = read_csv(OUTPUTS_DIR / "player_points_by_team_game.csv")
    before_rows = read_csv(INPUTS_DIR / "owners_before_trade.csv")
    after_rows = read_csv(INPUTS_DIR / "owners_after_trade.csv")
    overrides = load_overrides()

    by_player: dict[str, list[dict[str, str]]] = {}
    for row in point_rows:
        by_player.setdefault(row["player_name"], []).append(row)

    def phase_points(cricsheet_name: str, columns: list[str]) -> float:
        return sum(number(row.get(column)) for row in by_player.get(cricsheet_name, []) for column in columns)

    def roster(rows: list[dict[str, str]]) -> dict[str, list[tuple[str, str]]]:
        owners: dict[str, list[tuple[str, str]]] = {}
        for row in rows:
            owner = row.get("owner_name", "").strip()
            player = row.get("player_name", "").strip()
            if not owner or not player:
                continue
            owners.setdefault(owner, []).append((player, overrides.get(player, player)))
        return owners

    before = roster(before_rows)
    after = roster(after_rows)
    output: list[dict[str, object]] = []

    for owner in sorted(set(before) | set(after)):
        before_map = {cric: name for name, cric in before.get(owner, [])}
        after_map = {cric: name for name, cric in after.get(owner, [])}

        ordered_current = list(after_map)
        ordered_past = [cric for cric in before_map if cric not in after_map]
        for cric in ordered_current + ordered_past:
            phase1 = phase_points(cric, [f"G{i}" for i in range(1, 8)]) if cric in before_map else 0.0
            phase2 = phase_points(cric, [f"G{i}" for i in range(8, 18)]) if cric in after_map else 0.0
            output.append(
                {
                    "owner_name": owner,
                    "player_name": after_map.get(cric) or before_map.get(cric),
                    "cricsheet_player_name": cric,
                    "status": "current" if cric in after_map else "past",
                    "phase1_points_G1_to_G7": phase1,
                    "phase2_points_G8_to_end": phase2,
                    "total_points": phase1 + phase2,
                }
            )

    write_csv(
        SITE_DATA_DIR / "owner_player_points.csv",
        output,
        [
            "owner_name",
            "player_name",
            "cricsheet_player_name",
            "status",
            "phase1_points_G1_to_G7",
            "phase2_points_G8_to_end",
            "total_points",
        ],
    )


def build_player_breakdown() -> None:
    overrides = load_overrides()
    current_owners: dict[str, list[str]] = {}
    for row in read_csv(INPUTS_DIR / "owners_after_trade.csv"):
        owner = row.get("owner_name", "").strip()
        player = row.get("player_name", "").strip()
        if not owner or not player:
            continue
        cricsheet_name = overrides.get(player, player)
        current_owners.setdefault(cricsheet_name, []).append(owner)

    rows: list[dict[str, object]] = []
    for row in read_csv(OUTPUTS_DIR / "player_points_breakdown.csv"):
        owner_names = sorted(set(current_owners.get(row["player_name"], [])))
        rows.append({"owner_name": ", ".join(owner_names), **row})

    write_csv(
        SITE_DATA_DIR / "player_points_breakdown.csv",
        rows,
        [
            "player_name",
            "team_name",
            "owner_name",
            "batting_points",
            "bowling_points",
            "fielding_points",
            "playing_points",
            "total_points",
        ],
    )


def build_match_points() -> None:
    matches: list[dict[str, object]] = []
    detail_rows: list[dict[str, object]] = []

    for match_file in sorted(RECORDS_DIR.glob("*.csv")):
        if match_file.name.endswith("_points.csv"):
            continue
        rows = read_csv(match_file)
        if not rows:
            continue
        match_id = match_file.stem
        match_number = rows[0].get("match_number", "")
        match_date = rows[0].get("match_date", "")
        teams = sorted({row["team_name"] for row in rows if row.get("team_name")})
        label = f"Match {match_number}: {' vs '.join(teams)}"
        matches.append({"match_id": match_id, "match_number": match_number, "match_date": match_date, "match_label": label})

        points_file = RECORDS_DIR / f"{match_id}_points.csv"
        if not points_file.exists():
            continue
        for row in read_csv(points_file):
            detail_rows.append({"match_id": match_id, "match_label": label, "match_date": match_date, **row})

    matches.sort(key=lambda row: (number(row["match_number"]), str(row["match_id"])), reverse=True)
    detail_rows.sort(key=lambda row: (-number(row.get("match_id", "").split("_", 1)[0]), str(row.get("owner_name", ""))))

    write_csv(SITE_DATA_DIR / "matches.csv", matches, ["match_id", "match_number", "match_date", "match_label"])
    write_csv(
        SITE_DATA_DIR / "match_owner_player_points.csv",
        detail_rows,
        [
            "match_id",
            "match_label",
            "match_date",
            "owner_name",
            "player_name",
            "cricsheet_player_name",
            "team_name",
            "team_game_number",
            "phase",
            "points",
        ],
    )


def main() -> int:
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    missing: list[Path] = []
    for source_name, target_name in FILES_TO_COPY:
        source = OUTPUTS_DIR / source_name
        target = SITE_DATA_DIR / target_name
        if not source.exists():
            missing.append(source)
            continue
        shutil.copy2(source, target)
        print(f"Copied {source.relative_to(ROOT)} -> {target.relative_to(ROOT)}")

    if missing:
        print("Error: missing required output files.")
        for path in missing:
            print(f"  - {path.relative_to(ROOT)}")
        print("Run the scoring pipeline first:")
        print("  python3 -m src.main --season-year 2026 --output-dir outputs --inputs-dir inputs")
        return 1

    build_owner_player_points()
    print("Wrote docs/data/owner_player_points.csv")
    build_player_breakdown()
    print("Wrote docs/data/player_points_breakdown.csv")
    build_match_points()
    print("Wrote docs/data/matches.csv")
    print("Wrote docs/data/match_owner_player_points.csv")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updated_path = SITE_DATA_DIR / "last_updated.txt"
    updated_path.write_text(timestamp + "\n", encoding="utf-8")
    print(f"Wrote {updated_path.relative_to(ROOT)}")
    print("Site data is ready. Test with:")
    print("  cd docs")
    print("  python3 -m http.server 8000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
