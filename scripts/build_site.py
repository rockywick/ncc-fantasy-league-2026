from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = ROOT / "outputs"
SITE_DATA_DIR = ROOT / "site" / "data"

FILES_TO_COPY = [
    ("player_points_by_team_game.csv", "player_points_by_team_game.csv"),
    ("owner_points_summary.csv", "owner_points_summary.csv"),
]


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

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updated_path = SITE_DATA_DIR / "last_updated.txt"
    updated_path.write_text(timestamp + "\n", encoding="utf-8")
    print(f"Wrote {updated_path.relative_to(ROOT)}")
    print("Site data is ready. Test with:")
    print("  cd site")
    print("  python3 -m http.server 8000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
