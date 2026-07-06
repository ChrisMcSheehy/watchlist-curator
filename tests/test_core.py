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
    assert "/" in model_for("research")
    assert "/" in model_for("curation")
    assert "/" in model_for("deep_research")


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


def test_parse_llm_json():
    from src.curate import parse_llm_json
    fenced = 'Here you go:\n```json\n{"a": [1, 2]}\n```'
    assert parse_llm_json(fenced) == {"a": [1, 2]}
    assert parse_llm_json('{"b": 1}') == {"b": 1}
    # LLMs emit literal newlines inside markdown string values (json is strict by default)
    assert parse_llm_json('{"md": "line1\nline2"}') == {"md": "line1\nline2"}


def test_seen_video_ids(tmp_dir="tests/_tmp_newsletters"):
    import shutil
    from src.curate import seen_video_ids
    p = pathlib.Path(tmp_dir)
    shutil.rmtree(p, ignore_errors=True)
    p.mkdir(parents=True)
    (p / "2026-07-04.md").write_text(
        "watch [this](https://www.youtube.com/watch?v=abcdefghijk) "
        "and [that](https://youtu.be/AAAAAAAAAAA)", encoding="utf-8")
    assert seen_video_ids(p) == {"abcdefghijk", "AAAAAAAAAAA"}
    shutil.rmtree(p)


def test_write_index(tmp_dir="tests/_tmp_docs"):
    import shutil
    from src.daily import write_index
    root = pathlib.Path(tmp_dir)
    shutil.rmtree(root, ignore_errors=True)
    (root / "newsletters").mkdir(parents=True)
    (root / "newsletters" / "2026-07-05.md").write_text("x", encoding="utf-8")
    (root / "newsletters" / "2026-07-04.md").write_text("x", encoding="utf-8")
    write_index(root)
    idx = (root / "index.md").read_text(encoding="utf-8")
    assert idx.index("2026-07-05.html") < idx.index("2026-07-04.html")  # newest first
    shutil.rmtree(root)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
