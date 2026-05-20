# IPL Fantasy League Static Site

This folder is a fully static GitHub Pages site. It reads CSV files from `site/data/` and renders the fantasy tables in the browser.

## Update The Site Data

From the project root:

```bash
python3 -m src.main --season-year 2026 --output-dir outputs --inputs-dir inputs
python3 scripts/build_site.py
```

The first command refreshes the scoring outputs. The second command copies the needed CSVs into `site/data/` and writes `site/data/last_updated.txt`.

## Test Locally

```bash
cd site
python3 -m http.server 8000
```

Open:

```text
http://localhost:8000
```

## Publish On GitHub Pages

Push the project to GitHub. In the repository settings, go to:

```text
Settings > Pages > Deploy from branch > main > /site
```

If GitHub does not allow `/site` as the publishing folder, move the site contents to the repo root or use a `/docs` folder and select that folder in Pages settings.
