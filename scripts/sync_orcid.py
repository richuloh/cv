#!/usr/bin/env python3
"""Download the public ORCID record and keep a compact, site-friendly snapshot."""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "content" / "profile.json"
OUTPUT_PATH = ROOT / "data" / "orcid.json"
API_ROOT = "https://pub.orcid.org/v3.0"


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def nested_value(value: Any, *keys: str, default: str = "") -> str:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    if current is None:
        return default
    return str(current).strip()


def validate_orcid(orcid_id: str) -> None:
    compact = orcid_id.replace("-", "").upper()
    if not re.fullmatch(r"\d{15}[\dX]", compact):
        raise ValueError(f"Invalid ORCID format: {orcid_id}")

    total = 0
    for digit in compact[:15]:
        total = (total + int(digit)) * 2
    result = (12 - (total % 11)) % 11
    expected = "X" if result == 10 else str(result)
    if compact[-1] != expected:
        raise ValueError(f"Invalid ORCID checksum: {orcid_id}")


def fetch_json(url: str, user_agent: str, attempts: int = 3) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.orcid+json",
            "User-Agent": user_agent,
        },
    )
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            if attempt == attempts - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Unable to fetch {url}")


def date_parts(item: dict[str, Any]) -> dict[str, str]:
    raw = item.get("publication-date") or {}
    return {
        "year": nested_value(raw, "year", "value"),
        "month": nested_value(raw, "month", "value"),
        "day": nested_value(raw, "day", "value"),
    }


def external_ids(item: dict[str, Any]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    raw_ids = (item.get("external-ids") or {}).get("external-id") or []
    for raw in raw_ids:
        id_type = str(raw.get("external-id-type") or "").lower().strip()
        value = str(raw.get("external-id-value") or "").strip()
        if not id_type or not value:
            continue
        if id_type == "doi":
            value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.I).lower()
        url = nested_value(raw, "external-id-url", "value")
        result[id_type] = {"value": value, "url": url}
    return result


def contributors(item: dict[str, Any]) -> list[dict[str, str]]:
    result = []
    raw_contributors = (item.get("contributors") or {}).get("contributor") or []
    for raw in raw_contributors:
        name = nested_value(raw, "credit-name", "value")
        if not name:
            continue
        attributes = raw.get("contributor-attributes") or {}
        result.append(
            {
                "name": name,
                "role": str(attributes.get("contributor-role") or ""),
                "sequence": str(attributes.get("contributor-sequence") or ""),
            }
        )
    return result


def normalize_work(summary: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    source = detail or summary
    ids = external_ids(source) or external_ids(summary)
    doi = ids.get("doi", {})
    url = doi.get("url") or nested_value(source, "url", "value")
    if doi.get("value") and not url:
        url = f"https://doi.org/{doi['value']}"

    title = nested_value(source, "title", "title", "value")
    if not title:
        title = nested_value(summary, "title", "title", "value")

    source_name = nested_value(source, "source", "source-name", "value")
    return {
        "put_code": source.get("put-code") or summary.get("put-code"),
        "title": title,
        "journal": nested_value(source, "journal-title", "value")
        or nested_value(summary, "journal-title", "value"),
        "type": str(source.get("type") or summary.get("type") or ""),
        "date": date_parts(source if source.get("publication-date") else summary),
        "contributors": contributors(source),
        "external_ids": ids,
        "url": url,
        "source": source_name,
    }


def affiliation_date(item: dict[str, Any], key: str) -> str:
    raw = item.get(key) or {}
    year = nested_value(raw, "year", "value")
    month = nested_value(raw, "month", "value")
    day = nested_value(raw, "day", "value")
    return "-".join(part for part in (year, month, day) if part)


def normalize_affiliations(record: dict[str, Any], section: str, summary_key: str) -> list[dict[str, str]]:
    activities = record.get("activities-summary") or {}
    groups = (activities.get(section) or {}).get("affiliation-group") or []
    result: list[dict[str, str]] = []
    for group in groups:
        for wrapper in group.get("summaries") or []:
            item = wrapper.get(summary_key) or {}
            organization = item.get("organization") or {}
            result.append(
                {
                    "organization": str(organization.get("name") or ""),
                    "role": str(item.get("role-title") or item.get("role") or ""),
                    "department": str(item.get("department-name") or item.get("department") or ""),
                    "start": affiliation_date(item, "start-date"),
                    "end": affiliation_date(item, "end-date"),
                }
            )
    return result


def timestamp_from_millis(raw: Any) -> str:
    try:
        millis = int((raw or {}).get("value"))
    except (TypeError, ValueError, AttributeError):
        return ""
    return datetime.fromtimestamp(millis / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    profile = read_json(PROFILE_PATH)
    orcid_id = profile["orcid_id"]
    validate_orcid(orcid_id)

    public_email = profile.get("contact", {}).get("emails", ["cv@example.org"])[0]
    user_agent = f"richul-oh-cv/1.0 (mailto:{public_email})"
    record_url = f"{API_ROOT}/{orcid_id}/record"
    print(f"Fetching ORCID record {orcid_id} ...")
    record = fetch_json(record_url, user_agent)

    groups = ((record.get("activities-summary") or {}).get("works") or {}).get("group") or []
    summaries = [group.get("work-summary", [])[0] for group in groups if group.get("work-summary")]

    def fetch_detail(summary: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        put_code = summary.get("put-code")
        if not put_code:
            return summary, {}
        detail_url = f"{API_ROOT}/{orcid_id}/work/{put_code}"
        try:
            return summary, fetch_json(detail_url, user_agent)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            print(f"Warning: using summary for work {put_code}: {error}", file=sys.stderr)
            return summary, {}

    normalized: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(fetch_detail, summary) for summary in summaries]
        for future in as_completed(futures):
            summary, detail = future.result()
            normalized.append(normalize_work(summary, detail))

    def sort_key(work: dict[str, Any]) -> tuple[str, str, str, str]:
        date = work["date"]
        return (date.get("year", ""), date.get("month", ""), date.get("day", ""), work["title"])

    normalized.sort(key=sort_key, reverse=True)
    person = record.get("person") or {}
    name = person.get("name") or {}
    result = {
        "orcid_id": orcid_id,
        "orcid_url": f"https://orcid.org/{orcid_id}",
        "api_record_url": record_url,
        "name": {
            "given": nested_value(name, "given-names", "value"),
            "family": nested_value(name, "family-name", "value"),
            "credit": nested_value(name, "credit-name", "value"),
        },
        "last_synced_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "record_last_modified_utc": timestamp_from_millis(record.get("history", {}).get("last-modified-date")),
        "works": normalized,
        "affiliations": {
            "employment": normalize_affiliations(record, "employments", "employment-summary"),
            "education": normalize_affiliations(record, "educations", "education-summary"),
            "qualification": normalize_affiliations(record, "qualifications", "qualification-summary"),
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT_PATH)
    print(f"Saved {len(normalized)} public works to {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
