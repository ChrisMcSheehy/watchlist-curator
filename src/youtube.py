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
