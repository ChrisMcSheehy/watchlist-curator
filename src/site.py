"""Static site generator: newsletters/*.md -> styled HTML + search index + RSS.

Zero build step: the daily/weekly runs call build() and commit the output.
GitHub Pages serves docs/ raw (.nojekyll).
"""
import html
import json
import pathlib
import re
from datetime import date, datetime, timezone

import markdown
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
NEWSLETTERS = DOCS / "newsletters"
BASE_URL = "https://chrismcsheehy.github.io/watchlist-curator"

FRONT_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
H2_RE = re.compile(r"^## +(.+?)\s*$", re.MULTILINE)


def parse_issue(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    m = FRONT_RE.match(text)
    meta = yaml.safe_load(m.group(1)) if m else {}
    body = text[m.end():] if m else text
    slug = pathlib.Path(path).stem
    kind = "weekly" if slug.endswith("-weekly") else "daily"
    iso = slug.removesuffix("-weekly")
    summary = meta.get("summary") or _first_paragraph(body)
    return {
        "slug": slug,
        "kind": kind,
        "date": iso,
        "title": str(meta.get("title") or slug),
        "summary": str(summary),
        "tags": [str(t) for t in (meta.get("tags") or [])],
        "breaking": "## Breaking News" in body,
        "minutes": max(1, round(len(body.split()) / 230)),
        "headings": H2_RE.findall(body),
        "body": body.strip(),
    }


def _first_paragraph(body):
    for block in body.split("\n\n"):
        block = " ".join(block.split())
        if block and not block.startswith(("#", "-", "---", "*")):
            return block[:180] + ("..." if len(block) > 180 else "")
    return ""


def _display_date(iso):
    return date.fromisoformat(iso).strftime("%d %b %Y")


def _page(title, content, depth=0, extra_head=""):
    p = "../" * depth
    return f"""<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="preconnect" href="https://api.fontshare.com">
<link href="https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700,900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{p}assets/style.css">
<link rel="alternate" type="application/rss+xml" title="Watchlist Curator" href="{p}feed.xml">
<script>
try {{ document.documentElement.dataset.theme = localStorage.getItem("theme") || "light"; }} catch (e) {{}}
</script>
{extra_head}
</head>
<body>
<header class="site-head">
  <a class="brand" href="{p}index.html">Watchlist<span class="brand-accent">.</span></a>
  <nav class="head-nav">
    <a href="{p}feed.xml" class="head-link">RSS</a>
    <button id="theme-toggle" class="toggle" type="button" aria-label="Switch theme">
      <span class="toggle-light">Light</span><span class="toggle-dark">Dark</span>
    </button>
  </nav>
</header>
{content}
<footer class="site-foot">
  <span>Curated daily by the watchlist pipeline.</span>
  <a href="https://github.com/ChrisMcSheehy/watchlist-curator">Source</a>
</footer>
<script src="{p}assets/app.js"></script>
</body>
</html>"""


def _issue_card(it):
    badges = f'<span class="badge badge-{it["kind"]}">{it["kind"]}</span>'
    if it["breaking"]:
        badges += '<span class="badge badge-breaking">Breaking news</span>'
    tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in it["tags"])
    return f"""<article class="issue" data-slug="{it["slug"]}">
  <div class="issue-meta">
    <span class="mono">{_display_date(it["date"])}</span>
    {badges}
    <span class="mono dim">{it["minutes"]} min read</span>
  </div>
  <h2 class="issue-title"><a href="newsletters/{it["slug"]}.html">{html.escape(it["title"])}</a></h2>
  <p class="issue-summary">{html.escape(it["summary"])}</p>
  <div class="issue-tags">{tags}</div>
</article>"""


def _index_html(issues):
    all_tags = sorted({t for it in issues for t in it["tags"]})
    pills = "".join(
        f'<button class="pill" data-tag="{html.escape(t)}" type="button">{html.escape(t)}</button>'
        for t in all_tags
    )
    cards = "\n".join(_issue_card(it) for it in issues)
    content = f"""<main class="wrap">
  <section class="hero">
    <h1>The daily brief on<br>local LLMs, Snowflake <span class="amp">and</span> dbt.</h1>
    <p class="hero-sub">Curated videos, headlines and repos. Published every morning, digested every Sunday.</p>
  </section>
  <section class="controls">
    <input id="search" class="search" type="search" placeholder="Search issues, topics, headlines..." autocomplete="off">
    <div class="pills">{pills}</div>
  </section>
  <section id="issues" class="issues">
    {cards}
  </section>
  <p id="no-results" class="no-results" hidden>Nothing matches that search.</p>
</main>"""
    return _page("Watchlist Curator", content)


def _toc_html(headings):
    if not headings:
        return ""
    items = "".join(
        f'<li><a href="#{_slugify(h)}">{html.escape(h)}</a></li>' for h in headings
    )
    return f"""<aside class="toc" id="toc">
  <div class="toc-label">On this page</div>
  <ul>{items}</ul>
</aside>"""


def _slugify(text):
    # mirror python-markdown's toc slugify: lowercase, spaces to hyphens
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s]+", "-", text).strip("-")


def _issue_html(it, prev_it, next_it):
    body_html = markdown.markdown(it["body"], extensions=["extra", "toc"])
    nav = ""
    if prev_it:
        nav += f'<a class="pager-link" href="{prev_it["slug"]}.html"><span class="mono dim">Older</span><span>{html.escape(prev_it["title"])}</span></a>'
    else:
        nav += "<span></span>"
    if next_it:
        nav += f'<a class="pager-link pager-next" href="{next_it["slug"]}.html"><span class="mono dim">Newer</span><span>{html.escape(next_it["title"])}</span></a>'
    badges = f'<span class="badge badge-{it["kind"]}">{it["kind"]}</span>'
    if it["breaking"]:
        badges += '<span class="badge badge-breaking">Breaking news</span>'
    content = f"""<main class="wrap article-wrap">
  <div class="article-grid">
    <article class="prose">
      <p class="crumbs"><a href="../index.html">All issues</a></p>
      <div class="issue-meta">
        <span class="mono">{_display_date(it["date"])}</span>
        {badges}
        <span class="mono dim">{it["minutes"]} min read</span>
      </div>
      <h1>{html.escape(it["title"])}</h1>
      {body_html}
      <nav class="pager">{nav}</nav>
    </article>
    {_toc_html(it["headings"])}
  </div>
</main>"""
    return _page(it["title"], content, depth=1)


def _feed_xml(issues):
    entries = []
    for it in issues[:20]:
        url = f"{BASE_URL}/newsletters/{it['slug']}.html"
        pub = datetime.combine(
            date.fromisoformat(it["date"]), datetime.min.time(), timezone.utc
        ).strftime("%a, %d %b %Y 06:00:00 GMT")
        entries.append(
            f"<item><title>{html.escape(it['title'])}</title>"
            f"<link>{url}</link><guid>{url}</guid>"
            f"<pubDate>{pub}</pubDate>"
            f"<description>{html.escape(it['summary'])}</description></item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        "<title>Watchlist Curator</title>"
        f"<link>{BASE_URL}/</link>"
        "<description>Daily brief on local LLMs, Snowflake and dbt.</description>"
        + "".join(entries)
        + "</channel></rss>"
    )


def build(docs=DOCS):
    news = docs / "newsletters"
    issues = sorted(
        (parse_issue(p) for p in news.glob("*.md")),
        key=lambda it: it["slug"],
        reverse=True,
    )
    (docs / "index.html").write_text(_index_html(issues), encoding="utf-8")
    for i, it in enumerate(issues):
        prev_it = issues[i + 1] if i + 1 < len(issues) else None  # older
        next_it = issues[i - 1] if i > 0 else None  # newer
        (news / f"{it['slug']}.html").write_text(
            _issue_html(it, prev_it, next_it), encoding="utf-8"
        )
    (docs / "search.json").write_text(
        json.dumps([{k: it[k] for k in
                     ("slug", "title", "date", "kind", "tags", "summary", "headings")}
                    for it in issues]),
        encoding="utf-8",
    )
    (docs / "feed.xml").write_text(_feed_xml(issues), encoding="utf-8")
    (docs / ".nojekyll").touch()
    return len(issues)


if __name__ == "__main__":
    print(f"built site with {build()} issues")
