# IPL Fantasy League Static Site

This folder is a fully static GitHub Pages site. It reads CSV files from `docs/data/` and renders the fantasy tables in the browser.

The page shows:

- Leaderboard ranked by current total points
- Points by owner, with current players first and first-half-only players faded at the bottom
- Match dropdowns with owner totals and nested player-level point breakdowns
- Player breakdown for every player, split into batting, bowling, fielding, playing, and total points

## Update The Site Data

From the project root:

```bash
python3 -m src.main --season-year 2026 --output-dir outputs --inputs-dir inputs
python3 scripts/build_site.py
```

The first command refreshes the scoring outputs. The second command copies the needed CSVs into `docs/data/` and writes `docs/data/last_updated.txt`.

## Test Locally

```bash
cd docs
python3 -m http.server 8000
```

Open:

```text
http://localhost:8000
```

## Publish On GitHub Pages

Push the project to GitHub. In the repository settings, go to:

```text
Settings > Pages > Deploy from branch > main > /docs
```

If GitHub does not allow `/docs` as the publishing folder, move the site contents to the repo root and select root in Pages settings.
