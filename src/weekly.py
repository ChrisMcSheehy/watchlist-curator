import argparse
import re
from datetime import date, timedelta

from . import llm, site, sources, youtube
from .curate import VIDEO_ID_RE
from .daily import DOCS, write_newsletter

WATCHLIST_RE = re.compile(r"^## Today['’]s Watchlist\s*\n(.*?)(?=^## |\Z)",
                          re.MULTILINE | re.DOTALL)


def past_week_daily_files(today):
    # includes today (i=0): no-op on the 05:00 cron (daily runs 05:30),
    # but manual re-runs later in the day pick up that morning's issue
    files = []
    for i in range(0, 8):
        f = DOCS / "newsletters" / f"{(today - timedelta(days=i)).isoformat()}.md"
        if f.exists():
            files.append(f)
    return files


def week_watchlist(daily_texts):
    """Hotlink every video the dailies recommended, deduped by video id.

    Deterministic extraction, no LLM re-search."""
    items, seen = [], set()
    for text in daily_texts:
        m = WATCHLIST_RE.search(text)
        if not m:
            continue
        for line in m.group(1).strip().splitlines():
            if not line.lstrip().startswith("- "):
                continue
            vid = VIDEO_ID_RE.search(line)
            key = vid.group(1) if vid else line.strip()
            if key not in seen:
                seen.add(key)
                items.append(line.rstrip())
    return items


def main(dry_run=False):
    today = date.today()

    daily_files = past_week_daily_files(today)
    dailies = [f.read_text(encoding="utf-8") for f in daily_files]
    try:
        deep_dive = sources.deep_research(seen="\n\n=====\n\n".join(dailies))
    except Exception as e:
        print(f"WARNING: weekly deep research failed: {e}")
        deep_dive = ""

    digest = llm.complete(
        "curation",
        "Synthesize these daily briefings into one weekly digest. HARD LIMIT: a "
        "25-30 minute read (max ~6500 words total) — be selective, not exhaustive. "
        "Markdown. Sections, in this order: "
        "'## Work Watch — Snowflake, dbt & Cortex Code' — THE MOST IMPORTANT "
        "SECTION, it ALWAYS leads the digest (even above The Week in Brief) whenever "
        "the week's material has ANY Snowflake, dbt, or Cortex Code (Snowflake's AI "
        "coding agent) news; group it under '### Snowflake', '### dbt', "
        "'### Cortex Code' (only groups with news), keep every citation, and do NOT "
        "repeat these items in later sections; omit the section only if there is "
        "genuinely no such news this week. "
        "'## The Week in Brief' (narrative summary), "
        "'## Breaking News Recap' (only if any daily had breaking news), "
        "'## Deep Dive' (the CENTREPIECE — a focused long-form read built from the "
        "DEEP RESEARCH section below, organised by topic area with '### Topic' "
        "headings and short '#### Sub-topic' labels; cover the most important "
        "developments in depth and summarise or drop the minor ones rather than "
        "reproducing every detail; keep citations for what you keep; omit only if "
        "empty), "
        "'## Repo Roundup'. Do NOT include a videos/watchlist section; it is added "
        "separately. The deep research uses numbered markers like [3] that map "
        "to the 'Sources:' list at the end of that section — render each marker you "
        "keep as an inline markdown link to its URL, e.g. ([3](https://...)); never "
        "leave a bare [n]. Keep every citation from the dailies too. Do not invent "
        "anything not present in the material.\n\n"
        f"DEEP RESEARCH (this week, across all my interests):\n{deep_dive}\n\n"
        "DAILY BRIEFINGS:\n---\n\n"
        + "\n\n=====\n\n".join(dailies),
        system="You are a personal news curator writing a weekly digest. Respond with markdown only.",
    ) if (dailies or deep_dive) else "No daily briefings were published this week."

    videos = week_watchlist(dailies)
    if videos:
        section = ("This Week's Watchlist\n\nEvery video recommended this week:\n\n"
                   + "\n".join(videos) + "\n")
        # insert after the first section (Work Watch or The Week in Brief); append if bare
        parts = digest.strip().split("\n## ")
        parts.insert(1 if len(parts) > 1 else len(parts), section)
        digest = "\n## ".join(parts)

    if dry_run:
        print(digest)
        return

    try:
        yt = youtube.get_service()
        youtube.get_or_create_playlist(yt, youtube.playlist_name(today))
        youtube.delete_old_playlists(yt)
    except Exception as e:
        print(f"WARNING: playlist ops failed: {e}")

    # tags = union of the week's daily tags; summary is deterministic
    tags = sorted({t for f in daily_files for t in site.parse_issue(f)["tags"]})
    summary = f"The week in review: {len(dailies)} daily briefings distilled, plus a deep dive across all topics."
    path = write_newsletter(today, digest, kind="Weekly", summary=summary, tags=tags)
    print(f"wrote {path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    main(dry_run=p.parse_args().dry_run)
