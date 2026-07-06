import argparse
from datetime import date, timedelta

from . import llm, sources, youtube
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

    try:
        deep_dive = sources.deep_research()
    except Exception as e:
        print(f"WARNING: weekly deep research failed: {e}")
        deep_dive = ""

    dailies = past_week_dailies(today)
    digest = llm.complete(
        "curation",
        "Synthesize these daily briefings into one weekly digest (20-30 min read). "
        "Markdown. Sections: '## The Week in Brief' (narrative summary), "
        "'## Breaking News Recap' (only if any daily had breaking news), "
        "'## Best of the Watchlist' (standout videos of the week with links), "
        "'## Snowflake & dbt Deep Dive' (from the DEEP RESEARCH section below; omit if empty), "
        "'## Repo Roundup'. Keep every citation link from the dailies and deep research "
        "that you reference. Do not invent anything not present in the material.\n\n"
        f"DEEP RESEARCH (Snowflake/dbt, this week):\n{deep_dive}\n\n"
        "DAILY BRIEFINGS:\n---\n\n"
        + "\n\n=====\n\n".join(dailies),
        system="You are a personal news curator writing a weekly digest. Respond with markdown only.",
    ) if (dailies or deep_dive) else "No daily briefings were published this week."

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
