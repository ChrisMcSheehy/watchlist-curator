# Watchlist Curator

Daily/weekly automation: curates YouTube playlists (2-3 videos/day, ≤1 hr)
and publishes a newsletter to GitHub Pages. Spec:
[docs/superpowers/specs/2026-07-05-watchlist-curator-design.md](docs/superpowers/specs/2026-07-05-watchlist-curator-design.md).

## One-time setup

1. **Google / YouTube API**
   - console.cloud.google.com → new project → enable **YouTube Data API v3**.
   - OAuth consent screen: External, add yourself as a test user.
   - Credentials → Create OAuth client ID → **Desktop app** → download JSON
     as `client_secret.json` in the repo root (gitignored).
   - `pip install -r requirements.txt`, then `python scripts/setup_auth.py`
     and complete the browser consent. Note the printed refresh token.
2. **Curate channels**: set env vars `OPENROUTER_API_KEY`,
   `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, then
   `python scripts/curate_channels.py`. Hand-edit `config/channels.yaml` after.
3. **GitHub repo**: push to GitHub. Settings → Secrets and variables →
   Actions → add the four secrets above.
4. **Pages**: Settings → Pages → Deploy from a branch → `main` / `/docs`.
5. Trigger the `daily` workflow manually (Actions tab → daily → Run workflow)
   to verify end to end.

## Config (all hand-editable)

- `config/models.yaml` — OpenRouter model IDs (`research`, `curation`). Swap anytime.
- `config/interests.yaml` — topics + GitHub search keywords.
- `config/feeds.yaml` — RSS sources.
- `config/channels.yaml` — YouTube channels considered daily.

## Local dry run

`python -m src.daily --dry-run` — fetches everything, prints the newsletter,
mutates nothing. Same for `src.weekly`.

## Checks

`python tests/test_core.py`
