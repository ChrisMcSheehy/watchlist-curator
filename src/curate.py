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
