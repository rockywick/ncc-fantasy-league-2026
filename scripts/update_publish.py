from __future__ import annotations

import argparse
import json
import ssl
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ZIP_PATH = DATA_DIR / "ipl_json.zip"
JSON_DIR = DATA_DIR / "ipl_json"
EXTRACT_DIR = DATA_DIR / "_ipl_json_extract"
DOWNLOAD_URL = "https://cricsheet.org/downloads/ipl_json.zip"


def run(command: list[str]) -> None:
    print("$ " + " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def download_zip() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {DOWNLOAD_URL}")
    request = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request) as response, ZIP_PATH.open("wb") as target:
            shutil.copyfileobj(response, target)
    except urllib.error.URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        print("Python could not verify the SSL certificate. Retrying download without certificate verification.")
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(request, context=context) as response, ZIP_PATH.open("wb") as target:
            shutil.copyfileobj(response, target)

    if not zipfile.is_zipfile(ZIP_PATH):
        preview = ZIP_PATH.read_text(encoding="utf-8", errors="ignore")[:200].replace("\n", " ")
        raise RuntimeError(
            "Downloaded file is not a zip. Cricsheet likely returned a browser challenge page. "
            f"Preview: {preview!r}. Download the zip in your browser from "
            "https://cricsheet.org/downloads/ipl_json.zip, save it as data/ipl_json.zip, then run "
            "python3 scripts/update_publish.py --skip-download"
        )
    print(f"Saved {ZIP_PATH.relative_to(ROOT)}")


def refresh_json_files() -> None:
    if JSON_DIR.exists():
        print(f"Removing old {JSON_DIR.relative_to(ROOT)}")
        shutil.rmtree(JSON_DIR)

    if EXTRACT_DIR.exists():
        shutil.rmtree(EXTRACT_DIR)
    EXTRACT_DIR.mkdir(parents=True)

    print("Extracting IPL JSON zip")
    with zipfile.ZipFile(ZIP_PATH) as archive:
        archive.extractall(EXTRACT_DIR)

    downloaded_json_files = sorted(EXTRACT_DIR.rglob("*.json"))
    if not downloaded_json_files:
        raise RuntimeError("No JSON files found in downloaded zip.")

    JSON_DIR.mkdir(parents=True)

    copied = 0
    skipped = 0
    for path in downloaded_json_files:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        event = data.get("info", {}).get("event", {})
        if event.get("name") != "Indian Premier League":
            skipped += 1
            continue
        shutil.copy2(path, JSON_DIR / path.name)
        copied += 1

    if copied == 0:
        raise RuntimeError("No Indian Premier League JSON files found in downloaded zip.")

    shutil.rmtree(EXTRACT_DIR)
    print(f"Copied {copied} IPL JSON files into {JSON_DIR.relative_to(ROOT)}")
    if skipped:
        print(f"Skipped {skipped} non-IPL JSON files")


def commit_and_push(message: str, push: bool) -> None:
    paths = ["README.md", "docs", "scripts", "src", "config", "inputs", "requirements.txt"]
    run(["git", "add", *paths])

    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if diff.returncode == 0:
        print("No staged changes to commit.")
    else:
        run(["git", "commit", "-m", message])

    if push:
        run(["git", "push"])
    else:
        print("Skipping git push because --no-push was supplied.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download latest Cricsheet IPL data, rebuild outputs/site, and push.")
    parser.add_argument("--season-year", type=int, default=2026)
    parser.add_argument("--commit-message", default="Update IPL fantasy points")
    parser.add_argument("--skip-download", action="store_true", help="Use existing data/ipl_json.zip instead of downloading.")
    parser.add_argument("--no-push", action="store_true", help="Commit locally but do not push to GitHub.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.skip_download:
            if not zipfile.is_zipfile(ZIP_PATH):
                raise RuntimeError(f"{ZIP_PATH.relative_to(ROOT)} is missing or is not a valid zip file.")
            print(f"Using existing {ZIP_PATH.relative_to(ROOT)}")
        else:
            download_zip()
        refresh_json_files()
        run(["python3", "-m", "src.main", "--season-year", str(args.season_year), "--output-dir", "outputs", "--inputs-dir", "inputs"])
        run(["python3", "scripts/build_site.py"])
        commit_and_push(args.commit_message, push=not args.no_push)
    except Exception as exc:
        print(f"Update failed: {exc}", file=sys.stderr)
        return 1

    print("Update complete.")
    print("GitHub Pages should refresh after GitHub finishes deploying the pushed docs/ folder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
