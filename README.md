# NYS News Engine

Personal reading tool: Albany policy coverage aggregated and ranked for reporting depth,
modeled on Josh Greenman's [nycnewsengine.com](https://nycnewsengine.com/) but pointed at
state government. **Live at <https://tedalcorn.org/nys-news-engine/>** (unlisted; `noindex`).

## How it works

`scripts/fetch.py` pulls every source in `scripts/sources.py`, normalizes items, drops anything
from general outlets that doesn't pass the keyword gate (below), dedupes by URL and by normalized title
(keeping the higher-tier outlet, and a direct link over a Google redirect), scores each story,
groups different outlets' coverage of the same story (`scripts/cluster.py`), merges with the archive,
and writes `docs/data/items.json` and `docs/data/meta.json`.
`docs/index.html` renders that client-side: Picks (ranked, 72h), Latest (chronological),
Official (Governor, Senate, Assembly), Paywalled; search, outlet and topic filters, a date window,
and toggles for investigative signals, Governor-plus-Legislature co-mentions, and hiding opinion.
Dot color is the source tier: red = Albany specialist, blue = general outlet, green = official or advocacy.

### Story grouping (`scripts/cluster.py`)

A Governor's announcement arrives as ten or more differently worded headlines. Each item gets a `cid`
(its story's lead item id); the page shows one row per story with the other outlets folded under
"+N more". Matching is TF-IDF cosine over headline words (dek at half weight) against each open story's
centroid, within 72 hours, threshold 0.32, at least two distinctive words shared. A second item from an
outlet already in the story joins only if near-identical (Empire Center's regional "What They Make"
posts stay separate). Official releases, opinion, and native think-tank posts are never grouped.
Tuned 2026-10-23 on a week of archive: 0.28 began merging unrelated items, 0.36 split one announcement
four ways. Headline counts ("N stories today", Latest) count stories, not items.

### Keyword gate, and the review page

General feeds keep an item if it hits an Albany term (`ALBANY_TERMS`: Hochul, Legislature, budget…).
Since 2026-10-23 a second list, `STATE_TERMS`, also admits state government that names neither:
courts and rulings, the AG and Comptroller, agencies, individual lawmakers and districts. A state-term
admission must name New York when the feed is national (`ny_anchor`) or the text names another state,
and is dropped if it reads like a police blotter (`BLOTTER`). "County legislature" never counts as the
Legislature. Every item admitted this way, or by the three state-government sweeps, records the term in
`gate`. **`/nys-news-engine/#review`** (not in the nav) lists the last week of them with a tally by term;
`meta.json` carries the same tally as `gates`. When a term mostly admits noise, cut it in `sources.py`.

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
| Politico (news articles beyond Playbook), Wall Street Journal | Google News RSS `site:`, Albany-filtered | 1 / 2 |
| Buffalo News, Syracuse.com (politics), FingerLakes1, Adirondack Explorer | Google News `site:` (Buffalo) or native RSS, filtered | 2 |
| Citizens Union (Searchlight essays) | native RSS | 3 |
| Times Union, Newsday, Daily News, Buffalo News: state-government terms | two extra Google News `site:` queries each (`STATE_QA`, `STATE_QB`) | as outlet |
| Keyword sweeps: "Hochul"; Heastie / Stewart-Cousins / state budget / Executive Chamber (the latter needs a NY anchor or an Albany term with no other state named) | Google News RSS, cross-outlet | 2 (docked 12 in scoring) |
| State-government sweeps: courts & statewide officials; agencies; lawmakers | Google News RSS, cross-outlet, NY anchor required, `gate` recorded | 2 (docked 12 in scoring) |

Added 2026-10-23 after comparing a week of daily press clips with the engine: most
misses came from outlets already covered, cut by the keyword gate, not from missing outlets. AP was
tried and dropped (every AP clip that week was national news).

Every Google News query carries a `when:Nd` operator. Without it Google returns its 100 most
*relevant* hits, many of them months old, and recent items never surface (this is what made the
Official tab go stale). Google also silently ignores `when:` on long OR chains, so fetch.py drops any
Google News item older than 10 days (`GN_MAX_AGE_DAYS`) and the state-term queries are split in two. Google News links redirect through news.google.com; titles arrive with an
" - Outlet" suffix that is stripped. `scripts/gnlinks.py` swaps the redirect for the publisher's URL (the original
stays in `gn_link`): the redirect is a dead end for anyone signed into a Google Workspace account that blocks
Google News, and the real URL lets the extractor read the article. Google answers 429 after ~110 rapid decodes
from one IP, so it does 40 per run and stops at the first 429. Items whose resolved URL is a `/sports/` or
`/entertainment/` path are dropped. Albany terms match at word starts (short ones as whole words): as bare
substrings, "ed ra" (Assemblyman Ed Ra) matched "heated race".

## Scoring (`scripts/score.py`)

Outlet tier (30/20/12) + investigative signals (FOIL, records, audit, obtained, data show…; up to 32)
+ policy relevance (up to 18) + 12 if both the Governor and the Legislature appear − 15 opinion
− 8 breaking/live − 30 sports/entertainment + a 20-point recency term decaying over three days
+ a long-form bonus (+3 at 700 words, +6 at 1,200, +12 at 2,000; the NYT API word count is kept over the
paywall stub the extractor sees) + 5 when the headline names Hochul or the governor. Paywall status falls back
to the outlet's known policy (`HARD_PAYWALL` / `METERED` in `extract.py`) for items never fetched. Topic tags come from keyword lists.
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
  Two keys, because the NYT issues one key per app: `NYT_API_KEY` (Article Search) and `NYT_TOPSTORIES_KEY` (Top Stories), both repo secrets and both in the Pi's env file.
- **Google News variance:** the same query returns different counts from different IPs; a source showing `ok 0`
  on one runner and `ok 10` on the other is normal.

## Caveats

Paywalled outlets (Politico, Times Union, Newsday, NYT) contribute headlines and snippets only.
The keyword gate on general feeds still misses stories whose headline and lede name neither an
Albany term nor a state-government term. Story grouping can split one story in two or, rarely, merge
two; the threshold is in `cluster.py`. Google News has all but stopped indexing the
Daily News, and Gotham Gazette publishes rarely, so both run near zero. Senate and Assembly
coverage via Google News is partial. Scores are a starting point, not a judgment.
