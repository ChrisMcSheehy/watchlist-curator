# Watchlist Curator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Daily/weekly GitHub Actions jobs that curate YouTube playlists (2-3 videos/day, ≤1 hr) and publish a newsletter (headlines, breaking news, video dissections, repo watchlist) to GitHub Pages.

**Architecture:** Plain Python fetches raw material (YouTube uploads + captions, RSS, Perplexity deep research via OpenRouter, GitHub search); one curation LLM call returns structured JSON (playlist picks + newsletter markdown); the script mutates playlists and commits `docs/newsletters/YYYY-MM-DD.md`. No database — the repo is the state. All LLM calls route through OpenRouter with model IDs in `config/models.yaml`.

**Tech Stack:** Python 3.12, requests, pyyaml, feedparser, google-api-python-client, google-auth-oauthlib, youtube-transcript-api, GitHub Actions, GitHub Pages (Jekyll from `/docs`).

**Spec:** `docs/superpowers/specs/2026-07-05-watchlist-curator-design.md`

**Testing convention (from spec):** assert-based checks in `tests/test_core.py`, run with `python tests/test_core.py` — no pytest, no fixtures. Network/API glue is verified with `python -m src.daily --dry-run` (read-only; skips playlist writes and file writes), not unit tests.

---

### Task 1: Scaffold — configs, requirements, Pages setup, spec amendment

**Files:**
- Create: `requirements.txt`, `.gitignore`, `config/models.yaml`, `config/interests.yaml`, `config/feeds.yaml`, `docs/_config.yml`, `docs/newsletters/.gitkeep`
- Modify: `docs/superpowers/specs/2026-07-05-watchlist-curator-design.md` (replace `site/` with `docs/newsletters/` — classic Pages only serves `/` or `/docs`)

- [ ] **Step 1: Create `requirements.txt`**

```
requests
pyyaml
feedparser
google-api-python-client
google-auth
google-auth-oauthlib
youtube-transcript-api
```

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
*.pyc
.env
client_secret.json
token.json
```

- [ ] **Step 3: Create `config/models.yaml`**

```yaml
# OpenRouter model IDs. Swap freely as cheaper/better models appear.
research: perplexity/sonar-deep-research
curation: anthropic/claude-sonnet-5
```

- [ ] **Step 4: Create `config/interests.yaml`**

```yaml
topics:
  - Local / open-weight large language models (llama.cpp, Ollama, vLLM, quantization, new model releases)
  - Snowflake (new features, performance, cost optimisation)
  - dbt (releases, modelling patterns, testing, performance)
  - LLM development (agents, APIs, evals, prompting, major provider news)
github_keywords:
  - local llm
  - llm agent
  - dbt
  - snowflake
```

- [ ] **Step 5: Create `config/feeds.yaml`** (URLs are best-guess starters; user tunes over time)

```yaml
feeds:
  - https://hnrss.org/newest?q=LLM&points=50
  - https://hnrss.org/newest?q=dbt&points=30
  - https://hnrss.org/newest?q=Snowflake&points=30
  - https://www.reddit.com/r/LocalLLaMA/top/.rss?t=day
  - https://simonwillison.net/atom/everything/
  - https://www.snowflake.com/feed/
```

- [ ] **Step 6: Create `docs/_config.yml`** (Pages will serve `/docs`; keep specs/plans out of the rendered site)

```yaml
title: Watchlist Curator
exclude:
  - superpowers
```

- [ ] **Step 7: Create empty `docs/newsletters/.gitkeep`**

- [ ] **Step 8: Amend spec** — in the spec file, change the repo-layout line `site/  # newsletters as dated markdown, served by GitHub Pages` to `docs/newsletters/  # dated markdown, served by GitHub Pages (classic Pages serves /docs)`, and change step 9 of the daily run from `site/newsletters/` to `docs/newsletters/`. Same in the Weekly run section.

- [ ] **Step 9: Install deps and commit**

Run: `pip install -r requirements.txt`
Expected: all packages install without error.

```bash
git add requirements.txt .gitignore config docs
git commit -m "chore: scaffold configs, requirements, Pages setup"
```

---

### Task 2: Pure date/duration helpers in `src/youtube.py` (TDD)

**Files:**
- Create: `src/__init__.py` (empty), `src/youtube.py` (helpers only; API functions come in Task 4)
- Test: `tests/test_core.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_core.py`:

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from datetime import date
from src.youtube import week_start, playlist_name, playlist_date, parse_duration


def test_week_helpers():
    # 2026-07-05 is a Sunday; week runs Sunday..Saturday
    assert week_start(date(2026, 7, 5)) == date(2026, 7, 5)
    assert week_start(date(2026, 7, 8)) == date(2026, 7, 5)   # Wednesday
    assert week_start(date(2026, 7, 11)) == date(2026, 7, 5)  # Saturday
    assert playlist_name(date(2026, 7, 8)) == "05-07-2026"
    assert playlist_date("05-07-2026") == date(2026, 7, 5)
    assert playlist_date("My Mixtape") is None


def test_parse_duration():
    assert parse_duration("PT1H2M30S") == 62.5
    assert parse_duration("PT15M") == 15
    assert parse_duration("PT45S") == 0.75
    assert parse_duration("") == 0
    assert parse_duration(None) == 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
```

- [ ] **Step 2: Run to verify failure**

Run: `python tests/test_core.py`
Expected: `ModuleNotFoundError: No module named 'src.youtube'` (or ImportError).

- [ ] **Step 3: Implement helpers**

Create empty `src/__init__.py`. Create `src/youtube.py`:

```python
import re
from datetime import date, timedelta

PLAYLIST_NAME_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{4})$")


def week_start(d=None):
    """Sunday that starts the week containing d."""
    d = d or date.today()
    return d - timedelta(days=(d.weekday() + 1) % 7)


def playlist_name(d=None):
    return week_start(d).strftime("%d-%m-%Y")


def playlist_date(name):
    m = PLAYLIST_NAME_RE.match(name or "")
    if not m:
        return None
    try:
        return date(int(m[3]), int(m[2]), int(m[1]))
    except ValueError:
        return None


def parse_duration(iso):
    """ISO8601 video duration ('PT1H2M30S') -> minutes as float."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 60 + mi + s / 60
```

- [ ] **Step 4: Run tests**

Run: `python tests/test_core.py`
Expected: `ok test_parse_duration` / `ok test_week_helpers`.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: week/playlist/duration helpers"
```

---

### Task 3: OpenRouter client `src/llm.py` (TDD for config lookup)

**Files:**
- Create: `src/llm.py`
- Test: `tests/test_core.py` (append)

- [ ] **Step 1: Append failing test to `tests/test_core.py`** (before the `__main__` block)

```python
def test_model_for():
    from src.llm import model_for
    assert model_for("research") == "perplexity/sonar-deep-research"
    assert "/" in model_for("curation")
```

- [ ] **Step 2: Run to verify failure**

Run: `python tests/test_core.py`
Expected: `ModuleNotFoundError: No module named 'src.llm'`.

- [ ] **Step 3: Implement `src/llm.py`**

```python
import os
import pathlib

import requests
import yaml

CONFIG = pathlib.Path(__file__).resolve().parent.parent / "config" / "models.yaml"
URL = "https://openrouter.ai/api/v1/chat/completions"


def model_for(role):
    return yaml.safe_load(CONFIG.read_text())[role]


def complete(role, prompt, system=None, timeout=1800):
    """One OpenRouter chat completion. role is a key in models.yaml."""
    messages = ([{"role": "system", "content": system}] if system else [])
    messages.append({"role": "user", "content": prompt})
    r = requests.post(
        URL,
        timeout=timeout,
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
        json={"model": model_for(role), "messages": messages},
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
```

(Timeout is 30 min because sonar-deep-research runs are slow.)

- [ ] **Step 4: Run tests**

Run: `python tests/test_core.py`
Expected: all `ok` lines including `ok test_model_for`.

- [ ] **Step 5: Commit**

```bash
git add src/llm.py tests/test_core.py
git commit -m "feat: OpenRouter client with models.yaml roles"
```

---

### Task 4: YouTube API functions in `src/youtube.py`

**Files:**
- Modify: `src/youtube.py` (append)

No unit tests — network glue, verified via `--dry-run` in Task 7 and live in Task 11.

- [ ] **Step 1: Append to `src/youtube.py`**

```python
import os
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def get_service():
    creds = Credentials(
        None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("youtube", "v3", credentials=creds)


def recent_videos(yt, channel_ids, hours=24):
    """New uploads from the given channels within the window, with durations in minutes."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    out = []
    for cid in channel_ids:
        ch = yt.channels().list(part="contentDetails", id=cid).execute()
        if not ch.get("items"):
            continue
        uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        items = yt.playlistItems().list(
            part="contentDetails,snippet", playlistId=uploads, maxResults=10
        ).execute()
        for it in items.get("items", []):
            pub = datetime.fromisoformat(
                it["contentDetails"]["videoPublishedAt"].replace("Z", "+00:00")
            )
            if pub >= since:
                out.append({
                    "id": it["contentDetails"]["videoId"],
                    "title": it["snippet"]["title"],
                    "channel": it["snippet"]["channelTitle"],
                    "description": it["snippet"]["description"][:500],
                })
    if out:
        # ponytail: single videos.list call caps at 50 ids; fine for daily volume
        vids = yt.videos().list(
            part="contentDetails", id=",".join(v["id"] for v in out[:50])
        ).execute()
        durations = {v["id"]: parse_duration(v["contentDetails"]["duration"])
                     for v in vids.get("items", [])}
        for v in out:
            v["minutes"] = durations.get(v["id"], 0)
    return out


def captions(video_id, max_chars=12000):
    """Auto-caption text, empty string if unavailable."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        fetched = YouTubeTranscriptApi().fetch(video_id)
        return " ".join(s.text for s in fetched)[:max_chars]
    except Exception:
        return ""


def _my_playlists(yt):
    return yt.playlists().list(part="id,snippet", mine=True, maxResults=50).execute().get("items", [])


def get_or_create_playlist(yt, name):
    for pl in _my_playlists(yt):
        if pl["snippet"]["title"] == name:
            return pl["id"]
    body = {
        "snippet": {"title": name, "description": "Created by watchlist curator"},
        "status": {"privacyStatus": "private"},
    }
    return yt.playlists().insert(part="snippet,status", body=body).execute()["id"]


def add_video(yt, playlist_id, video_id):
    yt.playlistItems().insert(part="snippet", body={"snippet": {
        "playlistId": playlist_id,
        "resourceId": {"kind": "youtube#video", "videoId": video_id},
    }}).execute()


def delete_old_playlists(yt, days=30):
    cutoff = date.today() - timedelta(days=days)
    for pl in _my_playlists(yt):
        d = playlist_date(pl["snippet"]["title"])
        if d and d < cutoff:
            yt.playlists().delete(id=pl["id"]).execute()
```

Note: only playlists matching the `DD-MM-YYYY` name pattern are ever deleted — the user's own playlists are safe.

- [ ] **Step 2: Sanity-check imports and rerun tests**

Run: `python -c "import src.youtube" && python tests/test_core.py`
Expected: no import errors, all `ok` lines.

- [ ] **Step 3: Commit**

```bash
git add src/youtube.py
git commit -m "feat: YouTube API functions (uploads, captions, playlist CRUD)"
```

---

### Task 5: `src/sources.py` — RSS, deep research, GitHub trending (TDD for feed filtering)

**Files:**
- Create: `src/sources.py`
- Test: `tests/test_core.py` (append)

- [ ] **Step 1: Append failing test**

```python
def test_recent_entries():
    import time
    from types import SimpleNamespace
    from src.sources import recent_entries
    now = time.gmtime()
    old = time.gmtime(time.time() - 90 * 3600)
    parsed = SimpleNamespace(entries=[
        {"title": "fresh", "link": "http://a", "summary": "x", "published_parsed": now},
        {"title": "stale", "link": "http://b", "summary": "y", "published_parsed": old},
        {"title": "undated", "link": "http://c", "summary": "z"},
    ])
    got = recent_entries(parsed, hours=24)
    assert [e["title"] for e in got] == ["fresh"]
```

- [ ] **Step 2: Run to verify failure**

Run: `python tests/test_core.py`
Expected: `ModuleNotFoundError: No module named 'src.sources'`.

- [ ] **Step 3: Implement `src/sources.py`**

```python
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
```

- [ ] **Step 4: Run tests**

Run: `python tests/test_core.py`
Expected: all `ok` lines including `ok test_recent_entries`.

- [ ] **Step 5: Commit**

```bash
git add src/sources.py tests/test_core.py
git commit -m "feat: RSS, deep-research, and GitHub trending sources"
```

---

### Task 6: `src/curate.py` — curation call, JSON parsing, dedupe (TDD)

**Files:**
- Create: `src/curate.py`
- Test: `tests/test_core.py` (append)

- [ ] **Step 1: Append failing tests**

```python
def test_parse_llm_json():
    from src.curate import parse_llm_json
    fenced = 'Here you go:\n```json\n{"a": [1, 2]}\n```'
    assert parse_llm_json(fenced) == {"a": [1, 2]}
    assert parse_llm_json('{"b": 1}') == {"b": 1}


def test_seen_video_ids(tmp_dir="tests/_tmp_newsletters"):
    import shutil
    from src.curate import seen_video_ids
    p = pathlib.Path(tmp_dir)
    shutil.rmtree(p, ignore_errors=True)
    p.mkdir(parents=True)
    (p / "2026-07-04.md").write_text(
        "watch [this](https://www.youtube.com/watch?v=abcdefghijk) "
        "and [that](https://youtu.be/AAAAAAAAAAA)", encoding="utf-8")
    assert seen_video_ids(p) == {"abcdefghijk", "AAAAAAAAAAA"}
    shutil.rmtree(p)
```

- [ ] **Step 2: Run to verify failure**

Run: `python tests/test_core.py`
Expected: `ModuleNotFoundError: No module named 'src.curate'`.

- [ ] **Step 3: Implement `src/curate.py`**

```python
import json
import pathlib
import re

import yaml

from . import llm

ROOT = pathlib.Path(__file__).resolve().parent.parent
NEWSLETTERS = ROOT / "docs" / "newsletters"
VIDEO_ID_RE = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})")


def interests_text():
    return (ROOT / "config" / "interests.yaml").read_text()


def parse_llm_json(text):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"no JSON object in LLM output: {text[:200]}")
    return json.loads(m.group(0))


def seen_video_ids(folder=NEWSLETTERS):
    ids = set()
    for f in pathlib.Path(folder).glob("*.md"):
        ids |= set(VIDEO_ID_RE.findall(f.read_text(encoding="utf-8")))
    return ids


SYSTEM = (
    "You are a personal news curator producing a daily briefing for a data/AI "
    "engineer. You are precise, skeptical of hype, and always cite sources as "
    "markdown links. Respond with a single JSON object and nothing else."
)


def curate_daily(videos, feed_items, research_text, repos, today):
    prompt = f"""My interests (with weighting context):
{interests_text()}

Today is {today.isoformat()}.

CANDIDATE VIDEOS (new uploads from my curated channels; 'transcript' is auto-captions, may be empty):
{json.dumps(videos, indent=1)}

ALREADY-RECOMMENDED VIDEO IDS (never pick these again):
{json.dumps(sorted(seen_video_ids()))}

RSS ITEMS (last 24h):
{json.dumps(feed_items, indent=1)}

DEEP RESEARCH REPORT (last 24h):
{research_text}

NEW GITHUB REPOS (created recently, by stars):
{json.dumps(repos, indent=1)}

Return JSON with exactly these keys:
- "playlist_videos": the 2-3 best videos for me to WATCH today. Hard constraint:
  total minutes <= 60. Each: {{"id", "title", "minutes", "why"}} ('why' = one sentence).
  Fewer or zero picks is fine on a thin day — never pad with mediocre videos.
- "newsletter_markdown": a newspaper-style daily briefing in markdown (5-10 min read).
  Sections, in order, omitting any that are empty:
  1. "## Breaking News" — ONLY if the material contains a genuinely major event
     (model launch/retirement, major product release, acquisition). Include 2-3
     practical "how to make the most of it" tips.
  2. "## Headlines" — the day's notable items as short paragraphs, each with a
     markdown citation link to its source.
  3. "## Today's Watchlist" — the playlist_videos with youtube links
     (https://www.youtube.com/watch?v=ID) and the one-line 'why'.
  4. "## Worth a Skim" — dissect the candidate videos that did NOT make the
     playlist using their transcripts: 2-4 bullet key takeaways each, with links.
     Skip videos that are off-topic entirely.
  5. "## Repo Watchlist" — the most interesting new repos, one line each on why
     it's cool, with links.
Every factual claim needs a linked source. Do not invent items not present in the material above."""
    return parse_llm_json(llm.complete("curation", prompt, system=SYSTEM))
```

- [ ] **Step 4: Run tests**

Run: `python tests/test_core.py`
Expected: all `ok` lines including the two new tests.

- [ ] **Step 5: Commit**

```bash
git add src/curate.py tests/test_core.py
git commit -m "feat: curation prompt, JSON parsing, video dedupe"
```

---

### Task 7: Daily entrypoint `src/daily.py` with `--dry-run`

**Files:**
- Create: `src/daily.py`
- Test: `tests/test_core.py` (append test for the index writer)

- [ ] **Step 1: Append failing test**

```python
def test_write_index(tmp_dir="tests/_tmp_docs"):
    import shutil
    from src.daily import write_index
    root = pathlib.Path(tmp_dir)
    shutil.rmtree(root, ignore_errors=True)
    (root / "newsletters").mkdir(parents=True)
    (root / "newsletters" / "2026-07-05.md").write_text("x", encoding="utf-8")
    (root / "newsletters" / "2026-07-04.md").write_text("x", encoding="utf-8")
    write_index(root)
    idx = (root / "index.md").read_text(encoding="utf-8")
    assert idx.index("2026-07-05.html") < idx.index("2026-07-04.html")  # newest first
    shutil.rmtree(root)
```

- [ ] **Step 2: Run to verify failure**

Run: `python tests/test_core.py`
Expected: `ModuleNotFoundError: No module named 'src.daily'`.

- [ ] **Step 3: Implement `src/daily.py`**

```python
import argparse
import pathlib
import yaml
from datetime import date

from . import curate, sources, youtube

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def channel_ids():
    data = yaml.safe_load((ROOT / "config" / "channels.yaml").read_text())
    return [c["id"] for c in data["channels"]]


def write_index(docs=DOCS):
    files = sorted((docs / "newsletters").glob("*.md"), reverse=True)
    lines = ["---", "title: Watchlist Curator", "---", "", "# Newsletters", ""]
    lines += [f"- [{f.stem}](newsletters/{f.stem}.html)" for f in files]
    (docs / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_newsletter(today, markdown, kind="Daily"):
    suffix = "" if kind == "Daily" else "-weekly"
    path = DOCS / "newsletters" / f"{today.isoformat()}{suffix}.md"
    front = f"---\ntitle: {kind} Watchlist — {today.isoformat()}\n---\n\n"
    path.write_text(front + markdown + "\n", encoding="utf-8")
    write_index()
    return path


def main(dry_run=False):
    today = date.today()
    yt = youtube.get_service()

    videos = youtube.recent_videos(yt, channel_ids())
    for v in videos:
        v["transcript"] = youtube.captions(v["id"])
    feed_items = sources.fetch_feeds()
    research_text = sources.research()
    repos = sources.github_trending()

    result = curate.curate_daily(videos, feed_items, research_text, repos, today)

    if dry_run:
        print(result["newsletter_markdown"])
        print("\nPLAYLIST PICKS:", [v["id"] for v in result["playlist_videos"]])
        return

    try:
        pl = youtube.get_or_create_playlist(yt, youtube.playlist_name(today))
        for v in result["playlist_videos"]:
            youtube.add_video(yt, pl, v["id"])
        youtube.delete_old_playlists(yt)
    except Exception as e:
        # newsletter still publishes if playlist ops fail (spec: error handling)
        print(f"WARNING: playlist update failed: {e}")

    path = write_newsletter(today, result["newsletter_markdown"])
    print(f"wrote {path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="print newsletter, mutate nothing")
    main(dry_run=p.parse_args().dry_run)
```

- [ ] **Step 4: Run tests**

Run: `python tests/test_core.py`
Expected: all `ok` lines including `ok test_write_index`.

- [ ] **Step 5: Commit**

```bash
git add src/daily.py tests/test_core.py
git commit -m "feat: daily entrypoint with dry-run"
```

---

### Task 8: Weekly entrypoint `src/weekly.py`

**Files:**
- Create: `src/weekly.py`

- [ ] **Step 1: Implement `src/weekly.py`**

```python
import argparse
from datetime import date, timedelta

from . import llm, youtube
from .daily import DOCS, write_newsletter


def past_week_dailies(today):
    texts = []
    for i in range(1, 8):
        f = DOCS / "newsletters" / f"{(today - timedelta(days=i)).isoformat()}.md"
        if f.exists():
            texts.append(f.read_text(encoding="utf-8"))
    return texts


def main(dry_run=False):
    today = date.today()

    dailies = past_week_dailies(today)
    digest = llm.complete(
        "curation",
        "Synthesize these daily briefings into one weekly digest (20-30 min read). "
        "Markdown. Sections: '## The Week in Brief' (narrative summary), "
        "'## Breaking News Recap' (only if any daily had breaking news), "
        "'## Best of the Watchlist' (standout videos of the week with links), "
        "'## Repo Roundup'. Keep every citation link from the dailies that you reference. "
        "Do not invent anything not present in the dailies.\n\n---\n\n"
        + "\n\n=====\n\n".join(dailies),
        system="You are a personal news curator writing a weekly digest. Respond with markdown only.",
    ) if dailies else "No daily briefings were published this week."

    if dry_run:
        print(digest)
        return

    try:
        yt = youtube.get_service()
        youtube.get_or_create_playlist(yt, youtube.playlist_name(today))
        youtube.delete_old_playlists(yt)
    except Exception as e:
        print(f"WARNING: playlist ops failed: {e}")

    path = write_newsletter(today, digest, kind="Weekly")
    print(f"wrote {path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    main(dry_run=p.parse_args().dry_run)
```

- [ ] **Step 2: Sanity-check imports and rerun tests**

Run: `python -c "import src.weekly" && python tests/test_core.py`
Expected: no import errors, all `ok` lines.

- [ ] **Step 3: Commit**

```bash
git add src/weekly.py
git commit -m "feat: weekly digest entrypoint"
```

---

### Task 9: One-time setup scripts

**Files:**
- Create: `scripts/setup_auth.py`, `scripts/curate_channels.py`

- [ ] **Step 1: Create `scripts/setup_auth.py`**

```python
"""One-time: exchange client_secret.json for a refresh token.

1. In Google Cloud console: create project, enable 'YouTube Data API v3',
   create OAuth client (Desktop app), download as client_secret.json here.
2. Run: python scripts/setup_auth.py
3. Complete the browser consent; copy the printed refresh token into
   GitHub secrets as GOOGLE_REFRESH_TOKEN (plus GOOGLE_CLIENT_ID/SECRET
   from the client_secret.json).
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube"]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
print("\nGOOGLE_REFRESH_TOKEN:", creds.refresh_token)
```

- [ ] **Step 2: Create `scripts/curate_channels.py`**

```python
"""One-time: pull all subscriptions, LLM-classify against interests,
write config/channels.yaml. Re-run any time; hand-edit the output freely.

Needs env vars: OPENROUTER_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
GOOGLE_REFRESH_TOKEN.
"""
import json
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from src import curate, llm, youtube  # noqa: E402

yt = youtube.get_service()
subs, token = [], None
while True:
    resp = yt.subscriptions().list(
        part="snippet", mine=True, maxResults=50, pageToken=token
    ).execute()
    subs += [{
        "id": s["snippet"]["resourceId"]["channelId"],
        "title": s["snippet"]["title"],
        "description": s["snippet"]["description"][:200],
    } for s in resp.get("items", [])]
    token = resp.get("nextPageToken")
    if not token:
        break
print(f"{len(subs)} subscriptions found")

result = curate.parse_llm_json(llm.complete(
    "curation",
    f"""My interests:
{curate.interests_text()}

My YouTube subscriptions:
{json.dumps(subs, indent=1)}

Return JSON: {{"channels": [{{"id", "title"}}]}} — ONLY the channels likely to
publish videos relevant to my interests. Be selective; lifestyle/entertainment
channels are out even if I subscribe to them.""",
    system="Respond with a single JSON object and nothing else.",
))

out = pathlib.Path("config/channels.yaml")
out.write_text(
    "# Generated by scripts/curate_channels.py — hand-edit freely.\n"
    + yaml.safe_dump({"channels": result["channels"]}, allow_unicode=True),
    encoding="utf-8",
)
print(f"wrote {out} with {len(result['channels'])} channels")
```

- [ ] **Step 3: Commit**

```bash
git add scripts
git commit -m "feat: one-time auth and channel-curation scripts"
```

---

### Task 10: GitHub Actions workflows

**Files:**
- Create: `.github/workflows/daily.yml`, `.github/workflows/weekly.yml`

- [ ] **Step 1: Create `.github/workflows/daily.yml`**

Cron is UTC: 05:30 UTC ≈ 6:30am BST. Weekly runs first on Sundays (05:00).

```yaml
name: daily
on:
  schedule:
    - cron: "30 5 * * *"
  workflow_dispatch: {}
permissions:
  contents: write
jobs:
  daily:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python -m src.daily
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
          GOOGLE_CLIENT_ID: ${{ secrets.GOOGLE_CLIENT_ID }}
          GOOGLE_CLIENT_SECRET: ${{ secrets.GOOGLE_CLIENT_SECRET }}
          GOOGLE_REFRESH_TOKEN: ${{ secrets.GOOGLE_REFRESH_TOKEN }}
      - run: |
          git config user.name "watchlist-curator"
          git config user.email "actions@users.noreply.github.com"
          git add docs
          git diff --cached --quiet || git commit -m "newsletter: $(date -u +%F)"
          git push
```

- [ ] **Step 2: Create `.github/workflows/weekly.yml`**

```yaml
name: weekly
on:
  schedule:
    - cron: "0 5 * * 0"
  workflow_dispatch: {}
permissions:
  contents: write
jobs:
  weekly:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python -m src.weekly
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
          GOOGLE_CLIENT_ID: ${{ secrets.GOOGLE_CLIENT_ID }}
          GOOGLE_CLIENT_SECRET: ${{ secrets.GOOGLE_CLIENT_SECRET }}
          GOOGLE_REFRESH_TOKEN: ${{ secrets.GOOGLE_REFRESH_TOKEN }}
      - run: |
          git config user.name "watchlist-curator"
          git config user.email "actions@users.noreply.github.com"
          git add docs
          git diff --cached --quiet || git commit -m "weekly digest: $(date -u +%F)"
          git push
```

- [ ] **Step 3: Commit**

```bash
git add .github
git commit -m "ci: daily and weekly cron workflows"
```

---

### Task 11: README with setup guide

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md`**

```markdown
# Watchlist Curator

Daily/weekly automation: curates YouTube playlists (2-3 videos/day, ≤1 hr)
and publishes a newsletter to GitHub Pages. Spec:
[docs/superpowers/specs/2026-07-05-watchlist-curator-design.md](docs/superpowers/specs/2026-07-05-watchlist-curator-design.md).

## One-time setup

1. **Google / YouTube API**
   - console.cloud.google.com → new project → enable **YouTube Data API v3**.
   - OAuth consent screen: External, add yourself as a test user.
   - Credentials → Create OAuth client ID → **Desktop app** → download JSON
     as `client_secret.json` in the repo root (gitignored).
   - `pip install -r requirements.txt`, then `python scripts/setup_auth.py`
     and complete the browser consent. Note the printed refresh token.
2. **Curate channels**: set env vars `OPENROUTER_API_KEY`,
   `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, then
   `python scripts/curate_channels.py`. Hand-edit `config/channels.yaml` after.
3. **GitHub repo**: push to GitHub. Settings → Secrets and variables →
   Actions → add the four secrets above.
4. **Pages**: Settings → Pages → Deploy from a branch → `main` / `/docs`.
5. Trigger the `daily` workflow manually (Actions tab → daily → Run workflow)
   to verify end to end.

## Config (all hand-editable)

- `config/models.yaml` — OpenRouter model IDs (`research`, `curation`). Swap anytime.
- `config/interests.yaml` — topics + GitHub search keywords.
- `config/feeds.yaml` — RSS sources.
- `config/channels.yaml` — YouTube channels considered daily.

## Local dry run

`python -m src.daily --dry-run` — fetches everything, prints the newsletter,
mutates nothing. Same for `src.weekly`.

## Checks

`python tests/test_core.py`
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with setup guide"
```

---

### Task 12: End-to-end verification (requires user credentials)

These steps need the user's Google/OpenRouter credentials, so they are run WITH the user, not autonomously.

- [ ] **Step 1:** User follows README setup steps 1-2 (Google Cloud project, `setup_auth.py`, `curate_channels.py`). Verify `config/channels.yaml` exists and looks sensible; commit it.
- [ ] **Step 2:** Run `python -m src.daily --dry-run` locally. Expected: printed newsletter markdown with sections and citation links, plus playlist picks totaling ≤60 min. Fix any API-shape breakage found here (this is the step that catches YouTube/OpenRouter response drift).
- [ ] **Step 3:** Run `python -m src.daily` (real run). Verify: playlist named for this week's Sunday exists on YouTube with the picked videos; `docs/newsletters/<today>.md` and `docs/index.md` written. Commit.
- [ ] **Step 4:** Push to GitHub, add secrets, enable Pages, run the `daily` workflow via workflow_dispatch. Verify the commit appears and Pages renders the newsletter.
- [ ] **Step 5:** Commit any fixes: `git commit -m "fix: end-to-end verification fixes"`.
```
