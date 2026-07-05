import pathlib
import time
from datetime import datetime, timedelta, timezone

import feedparser
import requests
import yaml

from . import llm

CONFIG = pathlib.Path(__file__).resolve().parent.parent / "config"


def recent_entries(parsed, hours):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    out = []
    for e in parsed.entries:
        t = e.get("published_parsed") or e.get("updated_parsed")
        if t and datetime.fromtimestamp(time.mktime(t), timezone.utc) >= since:
            out.append({
                "title": e.get("title", ""),
                "link": e.get("link", ""),
                "summary": e.get("summary", "")[:500],
            })
    return out


def fetch_feeds(hours=24):
    urls = yaml.safe_load((CONFIG / "feeds.yaml").read_text())["feeds"]
    items = []
    for url in urls:
        try:
            items += recent_entries(feedparser.parse(url), hours)
        except Exception:
            pass  # a dead feed never blocks the newsletter
    return items


def research(hours=24):
    span = "24 hours" if hours <= 24 else f"{hours // 24} days"
    topics = yaml.safe_load((CONFIG / "interests.yaml").read_text())["topics"]
    return llm.complete(
        "research",
        f"What notable news happened in the last {span} in these areas: "
        + "; ".join(topics)
        + "? Report only genuinely notable items. Include a source URL for every claim. "
        "Flag anything that qualifies as major breaking news (model launches/retirements, "
        "major product releases, acquisitions).",
    )


def github_trending(days=7, per_keyword=5):
    keywords = yaml.safe_load((CONFIG / "interests.yaml").read_text())["github_keywords"]
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    repos = {}
    for kw in keywords:
        r = requests.get(
            "https://api.github.com/search/repositories",
            params={"q": f"{kw} created:>{since}", "sort": "stars",
                    "order": "desc", "per_page": per_keyword},
            headers={"Accept": "application/vnd.github+json"},
            timeout=30,
        )
        if r.ok:
            for it in r.json().get("items", []):
                repos[it["full_name"]] = {
                    "name": it["full_name"],
                    "url": it["html_url"],
                    "stars": it["stargazers_count"],
                    "description": it.get("description") or "",
                }
    return list(repos.values())
