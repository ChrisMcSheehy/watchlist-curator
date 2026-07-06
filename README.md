# Signal

A self-curating newsletter and YouTube playlist manager. Every morning it reads
your corner of the internet — curated YouTube channels, RSS feeds, GitHub
trending, and a live web-search sweep — and publishes **The Daily Signal**: a
5-10 minute briefing with a watchlist of 2-3 videos (≤1 hr total), headlines
with citations, video dissections, and classified repo picks. Sundays it adds a
long-form weekly digest with a Perplexity deep-research centrepiece.

- **Read it:** https://chrismcsheehy.github.io/signal/
- **Watch it:** https://www.youtube.com/@Data-Signal/playlists (weekly playlists, 30-day retention)
- **Subscribe:** https://chrismcsheehy.github.io/signal/feed.xml

## How it works

```
GitHub Actions cron (daily 05:30 UTC, weekly Sun 05:00 UTC)
  ├─ fetch: channel uploads + auto-captions   (src/youtube.py)
  │         RSS feeds, GitHub trending        (src/sources.py)
  │         web-search news sweep             (research model)
  ├─ curate: one LLM call ranks videos and    (src/curate.py)
  │          writes the issue as JSON
  ├─ act:    add picks to this week's playlist, delete playlists >30 days old
  └─ publish: markdown → static site + search index + RSS  (src/site.py)
              committed to docs/, served by GitHub Pages
```

No database, no build step — the repo is the state. Weekly digests hotlink
every video the dailies recommended (deterministic extraction, no re-search).

## Models (config/models.yaml)

| Role | Model | Job | Cost |
|---|---|---|---|
| `research` | perplexity/sonar | daily news sweep with real web search | cents/run |
| `curation` | deepseek-v4-pro`:floor` | ranking + writing (cheapest provider routing) | cents/run |
| `deep_research` | perplexity/sonar-deep-research | weekly deep dive | ~$2/run |

Swap models freely — but `research`/`deep_research` must be search-capable
(Sonar family or any `:online` model); a plain chat model will invent news.
Actual per-call cost is logged in every Actions run (`[llm] ... cost=$`).

## Config (all hand-editable, no code changes)

- `config/interests.yaml` — topics, GitHub keywords, `hero_topics` (site hero), `video_preferences` (playlist taste)
- `config/models.yaml` — OpenRouter model per role
- `config/feeds.yaml` — RSS sources (finding feeds: try `/feed`, `/rss.xml`; every GitHub repo has `releases.atom`)
- `config/channels.yaml` — YouTube channels considered daily (regenerate via `scripts/curate_channels.py`)

## One-time setup

1. **Google / YouTube API**: console.cloud.google.com → new project → enable
   **YouTube Data API v3** → OAuth client (Desktop app) → download as
   `client_secret.json` in the repo root (gitignored). Publish the OAuth app
   ("In production") or the refresh token expires in 7 days. The Google account
   **must have a YouTube channel** (youtube.com → create channel) or playlist
   calls fail with "Channel not found".
2. `pip install -r requirements.txt`, then `python scripts/setup_auth.py` →
   note the printed refresh token.
3. Set env vars `OPENROUTER_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
   `GOOGLE_REFRESH_TOKEN`, then `python scripts/curate_channels.py` to generate
   `config/channels.yaml` from your subscriptions.
4. **GitHub**: push, add those four values as Actions secrets, enable Pages
   (Deploy from a branch → `main` / `/docs`).
5. Trigger the `daily` workflow manually (Actions tab) to verify end to end.

## Local dry run & checks

```
python -m src.daily --dry-run    # full pipeline, prints the issue, mutates nothing
python -m src.weekly --dry-run   # same for the digest (spends the deep-research call)
python tests/test_core.py        # assert-based test suite, no framework
python -m src.site               # rebuild the static site from docs/newsletters/
```

## Operational notes

- Same-day re-runs overwrite that day's issue; a seen-video ledger
  (`docs/newsletters/seen_videos.txt`) keeps recommendations deduped anyway.
- Feed health is logged every run (`feed <url>: N items`) — watch for dead feeds.
- Workflow pushes are merge-safe: on races the run rebases, rebuilds the site
  from the merged newsletters, and amends.
- YouTube playlist inserts retry on transient 409s; a failed YouTube step never
  blocks the newsletter (and vice versa).
