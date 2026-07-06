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
    # strict=False: LLMs emit literal newlines inside the markdown string value
    return json.loads(m.group(0), strict=False)


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
- "playlist_videos": the 2-3 best videos for me to WATCH today, honouring the
  'video_preferences' in my interests above. Hard constraint:
  total minutes <= 60. Each: {{"id", "title", "minutes", "why"}} ('why' = one sentence).
  Fewer or zero picks is fine on a thin day — never pad with mediocre videos.
- "summary": one plain sentence (max 25 words) capturing today's most notable story,
  for the newsletter index page.
- "tags": 3-6 lowercase kebab-case topic tags for this issue, drawn from themes like
  local-llm, snowflake, dbt, llm-dev, breaking-news, hardware, agents, quantization.
- "newsletter_markdown": a newspaper-style daily briefing in markdown.
  LENGTH TARGET: a 5-10 minute read (roughly 1300-2500 words). Readers skim the
  sections they care about, so richness beats brevity — do NOT compress the issue
  to a summary. Sections, in order, omitting any that are truly empty:
  1. "## Breaking News" — ONLY if the material contains a genuinely major event
     (model launch/retirement, major product release, acquisition). Include 2-3
     practical "how to make the most of it" tips.
  2. "## Headlines" — the day's notable items as substantial paragraphs (2-4
     sentences each: what happened, why it matters to me), each with a markdown
     citation link to its source.
  3. "## Today's Watchlist" — the playlist_videos with youtube links
     (https://www.youtube.com/watch?v=ID). For each: 2-3 sentences on why it made
     the cut and the most interesting specific claims from its transcript.
  4. "## Worth a Skim" — REQUIRED whenever any on-topic candidate video did not
     make the playlist: dissect each from its transcript into 2-4 bullet key
     takeaways with links, so I get the substance without the watch time.
  5. "## Repo Watchlist" — the most interesting new repos, 1-2 sentences each on
     why it's cool and what I'd use it for, with links.
Every factual claim needs a linked source. When both a Reddit/social link and a
primary source (official blog, release notes, paper, repo) exist in the material for
the same story, cite the primary source first and the discussion link second; never
cite only Reddit when a primary source is available. Flag rumour/leak-tier items as
unverified. If the DEEP RESEARCH REPORT uses numbered
markers like [3] that map to its trailing 'Sources:' list, render them as inline markdown
links to the URL (e.g. ([3](https://...))) — never leave a bare [n]. Do not invent items
not present in the material above."""
    return parse_llm_json(llm.complete("curation", prompt, system=SYSTEM))
