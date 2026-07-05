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


def test_model_for():
    from src.llm import model_for
    assert model_for("research") == "perplexity/sonar-deep-research"
    assert "/" in model_for("curation")


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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
