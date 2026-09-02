#!/usr/bin/env python3
"""Run lightweight integrity checks on the generated website and PDFs."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        key = "src" if tag in {"img", "script"} else "href" if tag in {"a", "link"} else ""
        if key and attributes.get(key):
            self.links.append(str(attributes[key]))


def check_html(path: Path, expected_lang: str) -> None:
    text = path.read_text(encoding="utf-8")
    required = [f'<html lang="{expected_lang}">', "0000-0003-3221-5121", "data-pub-group"]
    for marker in required:
        if marker not in text:
            raise AssertionError(f"Missing {marker!r} in {path}")

    collector = LinkCollector()
    collector.feed(text)
    missing: list[str] = []
    for raw in collector.links:
        split = urlsplit(raw)
        if split.scheme or split.netloc or raw.startswith(("#", "mailto:", "tel:")):
            continue
        local = unquote(split.path)
        target = (path.parent / local).resolve() if local else path.resolve()
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            missing.append(raw)
    if missing:
        raise AssertionError(f"Broken local links in {path}: {missing}")


def check_pdf(path: Path) -> int:
    data = path.read_bytes()
    if len(data) < 5_000 or not data.startswith(b"%PDF"):
        raise AssertionError(f"Invalid PDF: {path}")
    pages = len(re.findall(rb"/Type\s*/Page(?!s)\b", data))
    if pages < 1:
        raise AssertionError(f"Could not find PDF pages in {path}")
    return pages


def main() -> int:
    check_html(DIST / "index.html", "ko")
    check_html(DIST / "en" / "index.html", "en")
    ko_pages = check_pdf(DIST / "downloads" / "richul-oh-cv-ko.pdf")
    en_pages = check_pdf(DIST / "downloads" / "richul-oh-cv-en.pdf")
    print(f"Output checks passed: Korean PDF {ko_pages} pages, English PDF {en_pages} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
