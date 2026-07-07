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
    try:
        # strict=False: LLMs emit literal newlines inside the markdown string value
        return json.loads(m.group(0), strict=False)
    except json.JSONDecodeError:
        # the run already paid for this response; make it debuggable from logs
        print(f"UNPARSEABLE LLM OUTPUT (first 2000 chars):\n{text[:2000]}")
        raise


SEEN_LEDGER = NEWSLETTERS / "seen_videos.txt"
REPO_RE = re.compile(r"github\.com/([\w.-]+/[\w.-]+)")


def seen_video_ids(folder=NEWSLETTERS):
    ids = set()
    for f in pathlib.Path(folder).glob("*.md"):
        ids |= set(VIDEO_ID_RE.findall(f.read_text(encoding="utf-8")))
    # append-only ledger survives same-day newsletter overwrites
    if SEEN_LEDGER.exists():
        ids |= set(SEEN_LEDGER.read_text(encoding="utf-8").split())
    return ids


def remember_videos(video_ids):
    old = SEEN_LEDGER.read_text(encoding="utf-8").split() if SEEN_LEDGER.exists() else []
    SEEN_LEDGER.write_text("\n".join(dict.fromkeys(old + list(video_ids))) + "\n",
                           encoding="utf-8")


def seen_repos(folder=NEWSLETTERS):
    repos = set()
    for f in pathlib.Path(folder).glob("*.md"):
        repos |= {r.lower().removesuffix(".git")
                  for r in REPO_RE.findall(f.read_text(encoding="utf-8"))}
    return repos


SYSTEM = (
    "You are a personal news curator producing a daily briefing for a data/AI "
    "engineer. You are precise, skeptical of hype, and always cite sources as "
    "markdown links."
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

Produce TWO parts, in this exact order.

PART 1 — the newsletter itself, as plain markdown (do NOT wrap it in code fences
or JSON). A newspaper-style daily briefing.
  LENGTH TARGET: a 5-10 minute read (roughly 1300-2500 words). Readers skim the
  sections they care about, so richness beats brevity — do NOT compress the issue
  to a summary. Sections, in order, omitting any that are truly empty:
  1. "## Work Watch — Snowflake, dbt & Cortex Code" — THE MOST IMPORTANT SECTION,
     it ALWAYS comes first (even above Breaking News) whenever the material has ANY
     Snowflake, dbt, or Cortex Code (Snowflake's AI coding agent) news. Cover every
     such item as a substantial paragraph with a citation link, grouped under
     "### Snowflake", "### dbt", "### Cortex Code" (only the groups that have news).
     Pull these items UP here and do NOT repeat them in the sections below. Omit the
     whole section ONLY when there is genuinely no Snowflake/dbt/Cortex Code news.
  2. "## Breaking News" — ONLY if the material contains a genuinely major event
     (model launch/retirement, major product release, acquisition) that is NOT
     already covered under Work Watch. Include 2-3 practical "how to make the most
     of it" tips.
  3. "## Today's Watchlist" — your 2-3 recommended videos to watch today (the
     same ones you list in PART 2), each with a youtube link
     (https://www.youtube.com/watch?v=ID). For each: 2-3 sentences on why it made
     the cut and the most interesting specific claims from its transcript.
  4. "## Headlines" — the day's notable items as substantial paragraphs (2-4
     sentences each: what happened, why it matters to me), each with a markdown
     citation link to its source.
  5. "## Worth a Skim" — 2-3 dissections of on-topic candidate videos that did
     not make the playlist (omit the section only when no such videos exist):
     each dissected from its transcript into 2-4 bullet key takeaways with
     links, so I get the substance without the watch time.
  6. "## Repo Watchlist" — the most interesting repos, GROUPED by topic under
     "### dbt", "### Snowflake", "### Local LLMs", "### LLM Development" (only
     the groups that apply). 1-2 sentences each on why it's cool and what I'd
     use it for, with links.
  7. "## Trending Repos" — one line each for the remaining notable repos from
     the material (name link + what it is). Prefix the line with ✅ when the
     repo is directly relevant to my interests; leave unmarked otherwise.
Every factual claim needs a linked source. When both a Reddit/social link and a
primary source (official blog, release notes, paper, repo) exist in the material for
the same story, cite the primary source first and the discussion link second; never
cite only Reddit when a primary source is available. Flag rumour/leak-tier items as
unverified. If the DEEP RESEARCH REPORT uses numbered
markers like [3] that map to its trailing 'Sources:' list, render them as inline markdown
links to the URL (e.g. ([3](https://...))) — never leave a bare [n]. Do not invent items
not present in the material above.

PART 2 — on a line by itself the marker ===METADATA===, then a single JSON object
(and nothing after it) with exactly these keys:
- "playlist_videos": the videos you featured in "## Today's Watchlist", best
  first, honouring the 'video_preferences' in my interests above. TARGET: 2-3 —
  only fewer on a genuinely thin day. Hard constraint: total minutes <= 60.
  Each: {{"id", "title", "minutes", "why"}} ('why' = one sentence).
- "summary": one plain sentence (max 25 words) capturing today's most notable story,
  for the newsletter index page.
- "tags": 3-6 lowercase kebab-case topic tags for this issue, drawn from themes like
  local-llm, snowflake, dbt, llm-dev, breaking-news, hardware, agents, quantization."""
    # keep the big markdown body OUT of any JSON string: the newsletter is plain
    # text (PART 1), only the small metadata block (PART 2) is parsed as JSON, so a
    # stray quote/newline in a 2000-word briefing can't break the whole response
    for attempt in range(2):
        text = llm.complete("curation", prompt, system=SYSTEM)
        body, sep, meta = text.rpartition("===METADATA===")
        try:
            if not sep:
                raise ValueError("no ===METADATA=== marker in curation output")
            data = parse_llm_json(meta)
            data["newsletter_markdown"] = body.strip()
            return data
        except ValueError:  # JSONDecodeError and "no marker/object" both subclass it
            if attempt:
                raise
            print("curation output unparseable, retrying once")
