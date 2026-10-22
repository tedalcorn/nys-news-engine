# NYS News Engine

Personal reading tool: Albany policy coverage aggregated and ranked for reporting depth,
modeled on Josh Greenman's [nycnewsengine.com](https://nycnewsengine.com/) but pointed at
state government. **Live at <https://tedalcorn.org/nys-news-engine/>** (unlisted; `noindex`).

## How it works

`scripts/fetch.py` pulls every source in `scripts/sources.py`, normalizes items, drops anything
from general outlets that doesn't hit an Albany keyword, dedupes by URL and by normalized title
(keeping the higher-tier outlet, and a direct link over a Google redirect), scores each story,
merges with the archive, and writes `docs/data/items.json` and `docs/data/meta.json`.
`docs/index.html` renders that client-side: Picks (ranked, 72h), Latest (chronological),
Official (Governor, Senate, Assembly), Paywalled; search, outlet and topic filters, a date window,
and toggles for investigative signals, Governor-plus-Legislature co-mentions, and hiding opinion.
Dot color is the source tier: red = Albany specialist, blue = general outlet, green = official or advocacy.

### Refresh (every 30 minutes, two independent runners)

| Runner | When | How |
|---|---|---|
| Raspberry Pi `weather` (primary) | :00 and :30 | systemd timer `nys-news-refresh.timer` runs `~/nys-news-engine/run_refresh.sh`: pull, fetch, commit, push over a write-only deploy key. Two consecutive failures push an ntfy alert to Ted's phone. |
| GitHub Actions (backstop) | :15 and :45 | `.github/workflows/refresh.yml`, same scripts. GitHub throttles cron workflows (observed ~6 runs/day for a `*/30` schedule), so this is not relied on. |
| Watchdog | every 3 h | `.github/workflows/watchdog.yml` reads the live `meta.json`; if it is older than 2.5 h it opens an issue mentioning @tedalcorn, and closes it when refreshes resume. |

Both runners `git reset --hard origin/main` before fetching and retry on a rejected push, so they
never conflict. `meta.json` records which runner produced the current data (`runner`) and unique
stories per day (`per_day`). The page shows a red "refresh overdue" flag when data is older than 2 h.
GitHub Pages serves `docs/`. Retention is 180 days. The repo is the off-device backup.

## Sources

| Source | How | Tier |
|---|---|---|
| New York Focus, City & State, Politico NY Playbook | native RSS | 1 |
| Times Union, NY State of Politics (Spectrum) | Google News RSS `site:` query | 1 |
| Gothamist, NY Post (politics, metro), The City | native RSS, Albany-filtered | 2 |
| New York Times | NY Region RSS, Albany-filtered, plus the NYT developer API (Top Stories for the NY Region front + Article Search) filtered on the Times' own person/place/subject tags when `NYT_API_KEY` is set | 2 |
| Newsday, Daily News, Gotham Gazette | Google News RSS, Albany-filtered | 2 |
| Reinvent Albany, Fiscal Policy Institute, Empire Center | native RSS | 3 |
| Citizens Budget Commission, NY Senate, NY Assembly | Google News RSS | 3 |
| Governor's Office | **governor.ny.gov/news scraped directly** (two pages, exact timestamps, Spanish duplicates dropped; needs `curl_cffi` for a browser TLS fingerprint past Cloudflare), with Google News as fallback | 3 |
| Keyword sweeps: "Hochul"; Heastie / Stewart-Cousins / state budget / Executive Chamber | Google News RSS, cross-outlet | 2 |

Every Google News query carries a `when:Nd` operator. Without it Google returns its 100 most
*relevant* hits, many of them months old, and recent items never surface (this is what made the
Official tab go stale). Google News links redirect through news.google.com; titles arrive with an
" - Outlet" suffix that is stripped.

## Scoring (`scripts/score.py`)

Outlet tier (30/20/12) + investigative signals (FOIL, records, audit, obtained, data show…; up to 32)
+ policy relevance (up to 18) + 12 if both the Governor and the Legislature appear − 15 opinion
− 8 breaking/live − 30 sports/entertainment + a 20-point recency term decaying over three days
+ a long-form bonus when the extractor has a word count. Topic tags come from keyword lists.
All heuristic; tune the lists in `score.py`.

## Run locally

```
pip install feedparser requests curl_cffi trafilatura
NYT_API_KEY=... python scripts/fetch.py        # key optional; NYT API is skipped without it
python -m http.server 8742 --directory docs   # then open http://localhost:8742/
```

## Operating notes

- **Pi:** `ssh weather-ts` → `systemctl status nys-news-refresh.timer`, `journalctl -u nys-news-refresh -n 50`.
  Code lives in `~/nys-news-engine/repo` (a normal clone; `git pull` to update), venv in `~/nys-news-engine/.venv`,
  secrets in `~/nys-news-engine/env`. Deploy key `~/.ssh/nys_news_engine_deploy` (repo setting "pi-weather refresh").
- **NYT key:** one key, per-product. Enable "Article Search API" and "Top Stories API" on the app at
  developer.nytimes.com/my-apps; a key without them returns 401 and the source logs `ERROR`, nothing else breaks.
  The key is a repo secret (`NYT_API_KEY`) and in the Pi's env file.
- **Google News variance:** the same query returns different counts from different IPs; a source showing `ok 0`
  on one runner and `ok 10` on the other is normal.

## Caveats

Paywalled outlets (Politico, Times Union, Newsday, NYT) contribute headlines and snippets only.
The Albany keyword filter on general feeds will miss stories that don't name the Governor,
the Legislature or Albany in the headline or lede. Google News has all but stopped indexing the
Daily News, and Gotham Gazette publishes rarely, so both run near zero. Senate and Assembly
coverage via Google News is partial. Scores are a starting point, not a judgment.
