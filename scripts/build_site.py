#!/usr/bin/env python3
"""Build a dependency-free bilingual static CV site from JSON content."""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
ASSETS = ROOT / "assets"
DATA = ROOT / "data"
DIST = ROOT / "dist"

TARGET_NAME_VARIANTS = {"richul oh", "oh richul", "r oh", "oh r"}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def e(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def e_multiline(value: Any) -> str:
    return e(value).replace("\n", "<br>")


def normalize_name(raw: Any) -> str:
    return " ".join(str(raw or "").lower().replace(",", " ").split())


def timeline(items: list[dict[str, str]]) -> str:
    rows = []
    for item in items:
        detail = f'<p class="item-detail">{e(item.get("detail"))}</p>' if item.get("detail") else ""
        rows.append(
            f"""<li class="timeline-item">
              <span class="item-period">{e(item.get('period'))}</span>
              <h3 class="item-title">{e(item.get('title'))}</h3>
              <p class="item-organization">{e(item.get('organization'))}</p>
              {detail}
            </li>"""
        )
    return '<ol class="timeline">' + "".join(rows) + "</ol>"


def clean_list(items: list[dict[str, str]]) -> str:
    return '<ul class="clean-list">' + "".join(
        f'<li><strong>{e(item.get("title"))}</strong><span>{e(item.get("period"))}</span></li>' for item in items
    ) + "</ul>"


def author_markup(work: dict[str, Any], is_lead: bool) -> str:
    authors = []
    for contributor in work.get("contributors") or []:
        raw_name = str(contributor.get("name") or "").strip()
        escaped = e(raw_name)
        if normalize_name(raw_name) in TARGET_NAME_VARIANTS:
            star = '<span class="lead-star" aria-hidden="true">*</span>' if is_lead else ""
            escaped = f"<strong>{escaped}</strong>{star}"
        authors.append(escaped)
    return ", ".join(authors)


def is_lead_work(work: dict[str, Any], overrides: dict[str, Any]) -> bool:
    put_code = str(work.get("put_code") or "")
    override = overrides.get(put_code) or {}
    if "lead" in override:
        return bool(override["lead"])
    contributors = work.get("contributors") or []
    if not contributors:
        return False
    return normalize_name(contributors[0].get("name")) in TARGET_NAME_VARIANTS


def render_publication_item(work: dict[str, Any], is_lead: bool) -> str:
    title = e(work.get("title"))
    url = e(work.get("url"))
    title_markup = f'<a href="{url}" target="_blank" rel="noopener">{title}</a>' if url else title
    authors = author_markup(work, is_lead)
    author_line = f'<p class="publication-authors">{authors}</p>' if authors else ""
    journal = e(work.get("journal"))
    year = e((work.get("date") or {}).get("year"))
    venue = " · ".join(part for part in (journal, year) if part)
    venue_line = f'<p class="publication-venue"><em>{venue}</em></p>' if venue else ""
    ids = work.get("external_ids") or {}
    meta = []
    doi = ids.get("doi") or {}
    if doi.get("value"):
        doi_url = e(doi.get("url") or f'https://doi.org/{doi["value"]}')
        meta.append(f'<a class="badge" href="{doi_url}" target="_blank" rel="noopener">DOI</a>')
    pmid = ids.get("pmid") or {}
    if pmid.get("value"):
        pmid_url = e(pmid.get("url") or f'https://pubmed.ncbi.nlm.nih.gov/{pmid["value"]}')
        meta.append(f'<a class="badge" href="{pmid_url}" target="_blank" rel="noopener">PubMed</a>')
    return f"""<li class="publication-item">
      <div>
        <h3 class="publication-title">{title_markup}</h3>
        {author_line}
        {venue_line}
        <div class="publication-meta">{''.join(meta)}</div>
      </div>
    </li>"""


def publication_section(works: list[dict[str, Any]], overrides: dict[str, Any], labels: dict[str, str]) -> str:
    lead_items = []
    co_items = []
    for work in works:
        lead = is_lead_work(work, overrides)
        markup = render_publication_item(work, lead)
        (lead_items if lead else co_items).append(markup)

    lead_html = "".join(lead_items) or f'<li class="empty-state">—</li>'
    co_html = "".join(co_items) or f'<li class="empty-state">—</li>'

    return f"""<div class="pub-tabs">
      <button class="pub-tab is-active" type="button" data-pub-tab="lead" aria-pressed="true">{e(labels['publications_lead'])} ({len(lead_items)})</button>
      <button class="pub-tab" type="button" data-pub-tab="co" aria-pressed="false">{e(labels['publications_co'])} ({len(co_items)})</button>
    </div>
    <p class="lead-legend">{e(labels['lead_star_note'])}</p>
    <div class="pub-panel" data-pub-group="lead">
      <h3 class="pub-print-heading">{e(labels['publications_lead'])} ({len(lead_items)})</h3>
      <ul class="publication-list">{lead_html}</ul>
    </div>
    <div class="pub-panel" data-pub-group="co" hidden>
      <h3 class="pub-print-heading">{e(labels['publications_co'])} ({len(co_items)})</h3>
      <ul class="publication-list">{co_html}</ul>
    </div>"""


def project_list(items: list[dict[str, str]]) -> str:
    rows = []
    for item in items:
        detail = item.get("detail")
        detail_html = f'<p>{e(detail)}</p>' if detail else ""
        rows.append(
            f"""<li class="project-item">
              <span class="item-meta">{e(item.get('period'))} · {e(item.get('role'))}</span>
              <h3>{e(item.get('title'))}</h3>
              <p>{e(item.get('sponsor'))}</p>
              {detail_html}
            </li>"""
        )
    return '<ol class="project-list">' + "".join(rows) + "</ol>"


def award_list(items: list[dict[str, str]]) -> str:
    rows = []
    for item in items:
        detail = item.get("detail")
        detail_html = f'<p class="item-detail">{e_multiline(detail)}</p>' if detail else ""
        rows.append(
            f"""<li class="award-item">
              <span class="item-meta">{e(item.get('date'))}</span>
              <h3>{e(item.get('title'))}</h3>
              <p class="item-organization">{e(item.get('organization'))}</p>
              {detail_html}
            </li>"""
        )
    return '<ol class="award-list">' + "".join(rows) + "</ol>"


def presentation_list(items: list[dict[str, str]]) -> str:
    rows = []
    for item in items:
        dates = item.get("dates")
        dates_html = f'<p class="item-meta pres-dates">{e(dates)}</p>' if dates else ""
        rows.append(
            f"""<li class="presentation-item">
              <button class="disclosure-trigger" type="button" aria-expanded="false" data-disclosure>
                <span class="item-meta">{e(item.get('year'))} · {e(item.get('type'))}</span>
                <span class="item-venue-line">{e(item.get('venue'))}</span>
              </button>
              <div class="item-body" hidden>
                {dates_html}
                <p class="pres-title">{e(item.get('title'))}</p>
              </div>
            </li>"""
        )
    return '<ol class="presentation-list">' + "".join(rows) + "</ol>"


def build_page(profile: dict[str, Any], cv: dict[str, Any], orcid: dict[str, Any], overrides: dict[str, Any]) -> str:
    lang = cv["lang"]
    labels = cv["labels"]
    is_ko = lang == "ko"
    prefix = "" if is_ko else "../"
    language_href = "en/" if is_ko else "../"
    pdf_name = "richul-oh-cv-ko.pdf" if is_ko else "richul-oh-cv-en.pdf"
    works = orcid.get("works") or []
    address = profile["contact"]["address_ko" if is_ko else "address_en"]
    sync_date = str(orcid.get("last_synced_utc") or "").split("T")[0]
    email_links = "<br>".join(
        f'<a href="mailto:{e(email)}">{e(email)}</a>' for email in profile["contact"].get("emails", [])
    )
    research_label = "연구 분야" if is_ko else "Research interests"
    focus = " · ".join(e(item) for item in cv.get("focus", []))
    show_photo = profile.get("site", {}).get("show_photo", True)
    portrait = (
        f'<div class="portrait-wrap"><img class="portrait" src="{prefix}{e(profile["photo"])}" '
        f'alt="{e(cv["name"])}" width="434" height="530"></div>'
        if show_photo
        else ""
    )
    json_ld = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": cv["name"],
        "alternateName": cv["name_secondary"],
        "jobTitle": cv["role"],
        "affiliation": {"@type": "Hospital", "name": cv["affiliation"]},
        "identifier": profile["orcid_id"],
        "sameAs": [profile["links"]["orcid"], profile["links"]["google_scholar"]],
        "knowsAbout": cv.get("focus", []),
    }
    description = cv["bio"]
    page_title = f'{cv["name"]} — {cv["role"]}'
    publications_total = e(labels["publications_total"].replace("{count}", str(len(works))))
    publications_markup = publication_section(works, overrides, labels)

    base_url = str(profile.get("site", {}).get("base_url") or "").rstrip("/")
    canonical_path = "/" if is_ko else "/en/"
    canonical_url = f"{base_url}{canonical_path}" if base_url else ""
    canonical_tag = f'<link rel="canonical" href="{e(canonical_url)}">' if canonical_url else ""
    og_url_tag = f'<meta property="og:url" content="{e(canonical_url)}">' if canonical_url else ""
    hreflang_tags = ""
    if base_url:
        hreflang_tags = (
            f'<link rel="alternate" hreflang="ko" href="{e(base_url)}/">'
            f'<link rel="alternate" hreflang="en" href="{e(base_url)}/en/">'
            f'<link rel="alternate" hreflang="x-default" href="{e(base_url)}/">'
        )
    og_image = f"{base_url}/{e(profile['photo'])}" if base_url else f"{prefix}{e(profile['photo'])}"

    return f"""<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{e(description)}">
  <meta name="theme-color" content="{e(profile['site']['theme_color'])}">
  <meta property="og:type" content="profile">
  <meta property="og:title" content="{e(page_title)}">
  <meta property="og:description" content="{e(description)}">
  <meta property="og:image" content="{og_image}">
  {og_url_tag}
  {canonical_tag}
  {hreflang_tags}
  <title>{e(page_title)}</title>
  <link rel="stylesheet" href="{prefix}assets/site.css">
  <script type="application/ld+json">{json.dumps(json_ld, ensure_ascii=False).replace('</', '<\\/')}</script>
</head>
<body class="lang-{lang}">
  <a class="skip-link" href="#main">{e(labels['skip'])}</a>
  <header class="site-header">
    <div class="header-inner">
      <a class="brand" href="{prefix}">Richul Oh</a>
      <div class="nav-wrap">
        <nav class="main-nav" aria-label="Primary">
          <a href="#about">{e(labels['nav_about'])}</a>
          <a href="#experience">{e(labels['nav_experience'])}</a>
          <a href="#publications">{e(labels['nav_publications'])}</a>
          <a href="#research">{e(labels['nav_research'])}</a>
          <a href="#awards">{e(labels['nav_awards'])}</a>
        </nav>
        <div class="header-actions">
          <a class="header-link language-link" href="{language_href}" hreflang="{'en' if is_ko else 'ko'}">{e(labels['language'])}</a>
          <a class="header-link" href="{prefix}downloads/{pdf_name}" download>CV PDF</a>
        </div>
      </div>
    </div>
  </header>

  <main id="main" class="page-shell">
    <div class="academic-layout">
      <aside class="author-profile" aria-label="{e(labels['contact'])}">
        {portrait}
        <h1 id="hero-title">{e(cv['name'])}</h1>
        <p class="author-name-secondary">{e(cv['name_secondary'])}</p>
        <p class="author-role">{e(cv['role'])}</p>
        <p class="author-affiliation">{e(cv['affiliation'])}</p>
        <p class="author-tagline">{e(cv['tagline'])}</p>
        <dl class="author-contact">
          <div><dt>{e(labels['email'])}</dt><dd>{email_links}</dd></div>
          <div><dt>{e(labels['orcid'])}</dt><dd><a href="{e(profile['links']['orcid'])}" target="_blank" rel="me noopener">{e(profile['orcid_id'])}</a></dd></div>
          <div><dt>{e(labels['scholar'])}</dt><dd><a href="{e(profile['links']['google_scholar'])}" target="_blank" rel="noopener">Google Scholar</a></dd></div>
        </dl>
        <a class="cv-link" href="{prefix}downloads/{pdf_name}" download>{e(labels['download_pdf'])} ↓</a>
      </aside>

      <div class="academic-content">
        <section id="about" class="section intro-section">
          <h2>{e(labels['about'])}</h2>
          <p class="intro-bio">{e(cv['bio'])}</p>
          <p class="research-interests"><strong>{research_label}</strong><span>{focus}</span></p>
          <p class="address-line">{e(address)}</p>
        </section>

    <section id="experience" class="section">
      <div class="section-heading"><div><p class="section-kicker">Curriculum Vitae</p><h2>{e(labels['experience'])}</h2></div></div>
      <div class="career-grid">
        <div class="panel"><h3 class="card-title">{e(labels['experience'])}</h3>{timeline(cv.get('experience', []))}</div>
        <div>
          <div class="panel"><h3 class="card-title">{e(labels['education'])}</h3>{timeline(cv.get('education', []))}</div>
          <div class="panel" style="margin-top: 28px"><h3 class="card-title">{e(labels['licenses'])}</h3>{clean_list(cv.get('licenses', []))}</div>
        </div>
      </div>
    </section>

    <section id="publications" class="section">
      <div class="section-heading">
        <div><p class="section-kicker">ORCID · {e(profile['orcid_id'])}</p><h2>{e(labels['publications'])}</h2></div>
        <p>{publications_total} · {e(labels['publications_note'])}</p>
      </div>
      <div class="publication-head"><span class="sync-note">{e(labels['last_synced'])}: {e(sync_date)}</span></div>
      {publications_markup}
    </section>

    <section id="research" class="section">
      <div class="section-heading"><div><p class="section-kicker">Research</p><h2>{e(labels['research'])}</h2></div></div>
      <div class="panel"><h3 class="card-title">{e(labels['research'])}</h3>{project_list(cv.get('projects', []))}</div>
    </section>

    <section id="awards" class="section">
      <div class="section-heading"><div><p class="section-kicker">Recognition</p><h2>{e(labels['awards'])}</h2></div></div>
      <div class="panel"><h3 class="card-title">{e(labels['awards'])}</h3>{award_list(cv.get('awards', []))}</div>
      <div class="panel" style="margin-top: 36px"><h3 class="card-title">{e(labels['presentations'])}</h3>{presentation_list(cv.get('presentations', []))}</div>
    </section>
      </div>
    </div>
  </main>

  <footer class="site-footer">
    <div class="footer-inner"><p>© <span data-current-year></span> {e(cv['name'])}</p><p>{e(labels['last_synced'])}: {e(sync_date)}</p></div>
  </footer>
  <script src="{prefix}assets/site.js"></script>
</body>
</html>
"""


def main() -> int:
    required = [CONTENT / "profile.json", CONTENT / "cv.ko.json", CONTENT / "cv.en.json", DATA / "orcid.json"]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required files: {', '.join(missing)}")

    profile = load_json(CONTENT / "profile.json")
    orcid = load_json(DATA / "orcid.json")
    if profile["orcid_id"] != orcid["orcid_id"]:
        raise ValueError("The ORCID ID in content/profile.json does not match data/orcid.json")
    if not orcid.get("works"):
        raise ValueError("ORCID snapshot contains no works; refusing to build an empty publications page")

    overrides_path = CONTENT / "publication_overrides.json"
    overrides = load_json(overrides_path) if overrides_path.exists() else {}

    resolved_dist = DIST.resolve()
    if resolved_dist.parent != ROOT.resolve() or resolved_dist.name != "dist":
        raise RuntimeError(f"Unsafe output directory: {resolved_dist}")
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    shutil.copytree(ASSETS, DIST / "assets")
    shutil.copytree(DATA, DIST / "data")
    (DIST / "downloads").mkdir()
    (DIST / "en").mkdir()

    ko = load_json(CONTENT / "cv.ko.json")
    en = load_json(CONTENT / "cv.en.json")
    (DIST / "index.html").write_text(build_page(profile, ko, orcid, overrides), encoding="utf-8")
    (DIST / "en" / "index.html").write_text(build_page(profile, en, orcid, overrides), encoding="utf-8")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")

    base_url = str(profile.get("site", {}).get("base_url") or "").rstrip("/")
    robots_lines = ["User-agent: *", "Allow: /"]
    if base_url:
        robots_lines.append(f"Sitemap: {base_url}/sitemap.xml")
        lastmod = str(orcid.get("last_synced_utc") or "").split("T")[0]
        sitemap_urls = [f"{base_url}/", f"{base_url}/en/"]
        sitemap_entries = "".join(
            f"  <url><loc>{html.escape(url)}</loc><lastmod>{lastmod}</lastmod></url>\n" for url in sitemap_urls
        )
        sitemap = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{sitemap_entries}"
            "</urlset>\n"
        )
        (DIST / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (DIST / "robots.txt").write_text("\n".join(robots_lines) + "\n", encoding="utf-8")
    print(f"Built Korean and English pages in {DIST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
