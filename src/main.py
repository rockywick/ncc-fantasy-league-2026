from __future__ import annotations

import argparse
from pathlib import Path

from .cricsheet_loader import load_matches
from .fantasy_points import calculate_points, load_scoring
from .models import PlayerMatchPoints
from .outputs import build_player_name_reference, build_player_points_table, match_number, write_dataframe, write_match_records, write_warnings
from .owner_points import calculate_owner_summary
from .scorecard_parser import parse_match
from .team_game_index import assign_team_game_numbers, validate_team_game_counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calculate IPL fantasy points from Cricsheet JSON data.")
    parser.add_argument("--season-year", type=int, required=True, help="Season year, e.g. 2026.")
    parser.add_argument("--input-dir", default="data/ipl_json", help="Directory containing Cricsheet JSON files.")
    parser.add_argument("--output-dir", default="outputs", help="Directory where outputs are written.")
    parser.add_argument("--inputs-dir", default="inputs", help="Directory containing optional owner roster CSVs.")
    parser.add_argument("--scoring-config", default="config/scoring.yaml", help="Path to scoring YAML config.")
    return parser.parse_args()


def run(args: argparse.Namespace) -> int:
    warnings: list[str] = []
    scoring = load_scoring(args.scoring_config)
    matches = load_matches(args.input_dir, args.season_year, warnings)
    game_numbers = assign_team_game_numbers(matches)
    validate_team_game_counts(matches, warnings)

    all_points: list[PlayerMatchPoints] = []
    match_player_rows: dict[str, list[dict[str, object]]] = {}
    for match in matches:
        try:
            stats_rows = parse_match(match, warnings)
        except Exception as exc:
            warnings.append(f"{match.path}: unexpected parse failure: {exc}")
            continue

        for stats in stats_rows:
            game_number = game_numbers.get((match.path, stats.team_name))
            if game_number is None:
                warnings.append(f"{match.path}: could not assign game number for {stats.player_name} ({stats.team_name}).")
                continue
            points = calculate_points(stats, scoring)
            all_points.append(
                PlayerMatchPoints(
                    player_name=stats.player_name,
                    team_name=stats.team_name,
                    match_date=match.match_date,
                    game_number=game_number,
                    points=points,
                )
            )
            match_player_rows.setdefault(match.path, []).append(
                {
                    "match_number": match_number(match),
                    "match_date": match.match_date.isoformat(),
                    "team_name": stats.team_name,
                    "team_game_number": game_number,
                    "player_name": stats.player_name,
                    "points": points,
                }
            )

    output_dir = Path(args.output_dir)
    points_df = build_player_points_table(all_points, warnings)
    write_dataframe(points_df, output_dir, "player_points_by_team_game")
    write_dataframe(build_player_name_reference(points_df), output_dir, "cricsheet_player_names")
    write_match_records(match_player_rows, matches, args.inputs_dir, output_dir, warnings)

    owner_df = calculate_owner_summary(points_df, args.inputs_dir, warnings)
    if owner_df is not None:
        write_dataframe(owner_df, output_dir, "owner_points_summary")

    warnings.append(
        "Skipped Dream11 rules not available from Cricsheet-only data, such as official announced substitutes not represented in info.players and any platform-specific adjustments outside ball-by-ball data."
    )
    write_warnings(warnings, output_dir)

    print(f"Wrote {output_dir / 'player_points_by_team_game.csv'}")
    print(f"Wrote {output_dir / 'player_points_by_team_game.xlsx'}")
    print(f"Wrote {output_dir / 'cricsheet_player_names.csv'}")
    print(f"Wrote {output_dir / 'cricsheet_player_names.xlsx'}")
    print(f"Wrote per-match records in {output_dir / 'records'}")
    if owner_df is not None:
        print(f"Wrote {output_dir / 'owner_points_summary.csv'}")
        print(f"Wrote {output_dir / 'owner_points_summary.xlsx'}")
    print(f"Wrote {output_dir / 'warnings.txt'}")
    return 0


def main() -> None:
    raise SystemExit(run(parse_args()))


if __name__ == "__main__":
    main()
