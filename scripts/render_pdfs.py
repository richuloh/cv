#!/usr/bin/env python3
"""Render the bilingual CV pages to PDF with an installed Chromium browser."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def find_browser(explicit: str | None) -> Path:
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    if os.environ.get("CHROME_PATH"):
        candidates.append(os.environ["CHROME_PATH"])

    for command in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "msedge"):
        located = shutil.which(command)
        if located:
            candidates.append(located)

    candidates.extend(
        [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
    )
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return path
    raise FileNotFoundError("Chrome, Chromium, or Microsoft Edge was not found. Use --browser PATH.")


def render(browser: Path, source: Path, target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Missing built page: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="richul-cv-browser-") as user_data:
        temporary = target.with_suffix(".pdf.tmp")
        if temporary.exists():
            temporary.unlink()
        command = [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--allow-file-access-from-files",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=2500",
            "--no-pdf-header-footer",
            f"--user-data-dir={user_data}",
            f"--print-to-pdf={temporary.resolve()}",
            source.resolve().as_uri(),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=90)
        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(f"Browser PDF rendering failed ({completed.returncode}): {details}")
        if not temporary.exists() or temporary.stat().st_size < 5_000:
            details = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(f"Browser did not produce a valid PDF: {details}")
        with temporary.open("rb") as handle:
            if handle.read(4) != b"%PDF":
                raise RuntimeError(f"Invalid PDF signature: {temporary}")
        temporary.replace(target)
        print(f"Rendered {target.relative_to(ROOT)} ({target.stat().st_size:,} bytes)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", help="Path to Chrome, Chromium, or Microsoft Edge")
    args = parser.parse_args()
    browser = find_browser(args.browser)
    print(f"Using browser: {browser}")
    render(browser, DIST / "index.html", DIST / "downloads" / "richul-oh-cv-ko.pdf")
    render(browser, DIST / "en" / "index.html", DIST / "downloads" / "richul-oh-cv-en.pdf")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
