# IPL Fantasy Points from Cricsheet JSON

This project calculates Dream11-style IPL fantasy points from Cricsheet ball-by-ball JSON files.

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Download the IPL JSON zip from Cricsheet, extract it, and place the `.json` match files here:

```text
data/ipl_json/
```

No paid APIs are used. The project only reads local Cricsheet JSON files.

## Quick Update

When new IPL matches are available:

Run the one-command updater:

```bash
python3 scripts/update_publish.py
```

It will:

- download the latest IPL JSON zip from Cricsheet
- replace `data/ipl_json/` with the downloaded match JSON files
- run the scoring pipeline
- rebuild the static website data in `docs/data/`
- commit the updated site/source files
- push to GitHub so GitHub Pages can redeploy

After pushing, wait 1-5 minutes and open:

```text
https://rockywick.github.io/ncc-fantasy-league-2026/
```

If the old page is still visible, hard refresh with `Cmd + Shift + R` or check the repo's **Actions** tab to confirm the Pages deployment finished.

Use this if you want to do the steps manually:

1. Download the latest IPL JSON zip from Cricsheet:

```text
https://cricsheet.org/matches/
```

2. Extract the zip.
3. Put the extracted IPL JSON files in:

```text
data/ipl_json/
```

The folder should contain the match `.json` files directly. If macOS creates a folder like `ipl_json 2`, rename it to `ipl_json` so the path is exactly `data/ipl_json/`.

4. From the project folder, run the scoring pipeline:

```bash
python3 -m src.main --season-year 2026 --output-dir outputs --inputs-dir inputs
```

This refreshes:

```text
outputs/player_points_by_team_game.csv
outputs/owner_points_summary.csv
outputs/records/
outputs/warnings.txt
```

Use the same command every time you update the Cricsheet files. Change `--season-year 2026` only when running a different IPL season.

5. Refresh the static website data:

```bash
python3 scripts/build_site.py
```

6. Commit and push the updated website files:

```bash
git add .
git commit -m "Update IPL fantasy points"
git push
```

GitHub Pages redeploys from the pushed `docs/` folder.

## Run

```bash
python3 -m src.main --season-year 2026 --output-dir outputs --inputs-dir inputs
```

Optional arguments:

```bash
python3 -m src.main \
  --season-year 2026 \
  --input-dir data/ipl_json \
  --output-dir outputs \
  --inputs-dir inputs \
  --scoring-config config/scoring.yaml
```

## Outputs

Main output:

```text
outputs/player_points_by_team_game.csv
outputs/player_points_by_team_game.xlsx
```

Columns:

```text
player_name, team_name, G1, G2, ..., G17, total_points
```

Each row is a unique `player_name` and `team_name` combination. `G1` is that team's first match of the season, `G2` is that team's second match, and so on. Missing games are written as `0`.

Owner summary output, when roster files exist:

```text
outputs/owner_points_summary.csv
outputs/owner_points_summary.xlsx
```

Per-match records are written to:

```text
outputs/records/
```

For each match, two CSV files are created:

```text
outputs/records/1_Sunrisers_Hyderabad_Royal_Challengers_Bengaluru.csv
outputs/records/1_Sunrisers_Hyderabad_Royal_Challengers_Bengaluru_points.csv
```

The first file contains every player from that match and their fantasy points. The `_points.csv` file contains owner-level player rows for that match, for example `owner_name, player_name, points`. It uses the before-trade roster for team games `G1-G7` and the after-trade roster from `G8` onward.

Warnings are written to:

```text
outputs/warnings.txt
```

For owner roster cleanup, the run also writes the exact Cricsheet names found in the output:

```text
outputs/cricsheet_player_names.csv
outputs/cricsheet_player_names.xlsx
```

## Owner Roster Inputs

Before-trade roster:

```text
inputs/owners_before_trade.csv
```

After-trade roster:

```text
inputs/owners_after_trade.csv
```

Both files use:

```csv
owner_name,player_name
nishant,V Kohli
nishant,JJ Bumrah
```

Trade logic:

- `phase1_points_G1_to_G7` uses `owners_before_trade.csv`.
- `phase2_points_G8_to_end` uses `owners_after_trade.csv`.
- If a player name matches multiple team rows, all matching rows are included and a warning is written unless an override exists.
- Each owner should have exactly 15 filled player rows in each roster file.
- After the trade, each owner may have at most 5 outgoing and 5 incoming players compared with the before-trade roster.

## Name Overrides

Use this file to map your manual roster names to Cricsheet names:

```text
inputs/player_name_overrides.csv
```

Format:

```csv
input_player_name,cricsheet_player_name
Jasprit Bumrah,JJ Bumrah
```

Cricsheet often uses abbreviated player names such as `V Kohli` or `JJ Bumrah`. Run the main command once, then use `outputs/cricsheet_player_names.csv` to fill this mapping for any names in your owner files that do not match exactly.

## Scoring Config

Fantasy rules live in:

```text
config/scoring.yaml
```

Change point values there without editing code.

Example:

```yaml
batting:
  run: 1
  four_bonus: 1

strike_rate:
  enabled: true
  min_balls: 10
  ranges:
    - {min: 170, max: 9999, points: 6}
```

The code reads this YAML file every time it runs, so edits apply the next time you run the update command.

Implemented from Cricsheet data:

- Batting runs, fours, sixes, ducks, 30/50/100 milestones
- Bowler wickets, lbw/bowled bonus, maiden overs, 3/4/5 wicket milestones
- Catches, 3-catch bonus, stumpings, direct and assisted run outs
- Starting XI points from `info.players`
- Strike-rate and economy-rate bonuses/penalties

Recent IPL Cricsheet files may list 12 or 13 players for a team because of impact-player-era records. The project awards the configured playing points to every player listed in `info.players` and writes a warning when the count is not 11.

Cricsheet-only limitations are logged in `outputs/warnings.txt` when relevant.

## Static Website

The `docs/` folder contains a plain HTML/CSS/JavaScript dashboard that can be hosted on GitHub Pages.

Refresh it with:

```bash
python3 -m src.main --season-year 2026 --output-dir outputs --inputs-dir inputs
python3 scripts/build_site.py
git add .
git commit -m "Update IPL fantasy points"
git push
```

Only files committed and pushed to GitHub are visible on GitHub Pages. Running the scripts locally is not enough by itself.

Test locally with:

```bash
cd docs
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

See `docs/README.md` for GitHub Pages publishing notes.
