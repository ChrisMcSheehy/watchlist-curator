import os
import re
import time
from datetime import date, datetime, timedelta, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

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
    # ponytail: first page only (50 playlists); paginate if the account ever exceeds that
    return yt.playlists().list(part="id,snippet", mine=True, maxResults=50).execute().get("items", [])


def get_or_create_playlist(yt, name):
    for pl in _my_playlists(yt):
        if pl["snippet"]["title"] == name:
            return pl["id"]
    body = {
        "snippet": {"title": name, "description":
                    "Week of " + name + " — full writeups: "
                    "https://chrismcsheehy.github.io/watchlist-curator/"},
        "status": {"privacyStatus": "private"},
    }
    return yt.playlists().insert(part="snippet,status", body=body).execute()["id"]


def add_video(yt, playlist_id, video_id, attempts=3):
    # playlistItems.insert intermittently 409s (SERVICE_UNAVAILABLE); retry with backoff
    for i in range(attempts):
        try:
            yt.playlistItems().insert(part="snippet", body={"snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
            }}).execute()
            return
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(5 * (i + 1))


def delete_old_playlists(yt, days=30):
    cutoff = date.today() - timedelta(days=days)
    for pl in _my_playlists(yt):
        d = playlist_date(pl["snippet"]["title"])
        if d and d < cutoff:
            yt.playlists().delete(id=pl["id"]).execute()
