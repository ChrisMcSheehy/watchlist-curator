import argparse
import pathlib
import yaml
from datetime import date

from . import curate, site, sources, youtube

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def channel_ids():
    data = yaml.safe_load((ROOT / "config" / "channels.yaml").read_text())
    return [c["id"] for c in data["channels"]]


def write_newsletter(today, markdown, kind="Daily", summary="", tags=None):
    suffix = "" if kind == "Daily" else "-weekly"
    path = DOCS / "newsletters" / f"{today.isoformat()}{suffix}.md"
    front = yaml.safe_dump(
        {"title": f"{kind} Watchlist — {today.isoformat()}",
         "summary": summary, "tags": tags or []},
        allow_unicode=True, sort_keys=False)
    path.write_text(f"---\n{front}---\n\n" + markdown + "\n", encoding="utf-8")
    site.build()
    return path


def main(dry_run=False):
    today = date.today()
    yt = None
    videos = []
    try:
        yt = youtube.get_service()
        videos = youtube.recent_videos(yt, channel_ids())
        for v in videos:
            v["transcript"] = youtube.captions(v["id"])
    except Exception as e:
        # spec: YouTube failure must not block the newsletter
        print(f"WARNING: YouTube fetch failed, publishing without videos: {e}")
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

    path = write_newsletter(today, result["newsletter_markdown"],
                            summary=result.get("summary", ""),
                            tags=result.get("tags", []))
    print(f"wrote {path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="print newsletter, mutate nothing")
    main(dry_run=p.parse_args().dry_run)
