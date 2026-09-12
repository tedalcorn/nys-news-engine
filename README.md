# NYS News Engine

Personal reading tool: Albany policy coverage aggregated and ranked for reporting depth,
modeled on Josh Greenman's [nycnewsengine.com](https://nycnewsengine.com/) but pointed at
state government. **Live at <https://tedalcorn.org/nys-news-engine/>** (unlisted; `noindex`).

## How it works

`scripts/fetch.py` pulls every source in `scripts/sources.py`, normalizes items, drops anything
from general outlets that doesn't hit an Albany keyword, dedupes by URL and by normalized title
(keeping the higher-tier outlet), scores each story, merges with the archive, and writes
`docs/data/items.json` and `docs/data/meta.json`. `docs/index.html` renders that client-side
with search, outlet and topic filters, a date window, and toggles for investigative signals,
Governor-plus-Legislature co-mentions, and hiding opinion.

A GitHub Action (`.github/workflows/refresh.yml`) runs the fetch every 30 minutes and commits
any change; GitHub Pages serves `docs/`. Retention is 180 days. The repo is the off-device
backup: every refresh is a commit.

## Sources

| Source | How | Tier |
|---|---|---|
| New York Focus, City & State, Politico NY Playbook | native RSS | 1 |
| Times Union, NY State of Politics (Spectrum) | Google News RSS `site:` query | 1 |
| Gothamist, NYT NY Region, NY Post (politics, metro), The City | native RSS, Albany-filtered | 2 |
| Newsday, Daily News, Gotham Gazette | Google News RSS, Albany-filtered | 2 |
| Reinvent Albany, Fiscal Policy Institute, Empire Center | native RSS | 3 |
| Citizens Budget Commission, Governor's Office, NY Senate, NY Assembly | Google News RSS | 3 |
| Keyword sweeps: "Hochul"; Heastie / Stewart-Cousins / state budget / Executive Chamber | Google News RSS, cross-outlet | 2 |

Google News is the fallback for sites that block scrapers (Cloudflare 403s on the native feeds).
Its links redirect through news.google.com; titles arrive with an " - Outlet" suffix that is stripped.

## Scoring (`scripts/score.py`)

Outlet tier (30/20/12) + investigative signals (FOIL, records, audit, obtained, data show…; up to 24)
+ policy relevance (up to 18) + 12 if both the Governor and the Legislature appear − 15 opinion
− 8 breaking/live − 30 sports/entertainment + a 20-point recency term decaying over three days.
Topic tags (Budget, Housing, Public safety, Health, Education & child care, Transit, Environment
& energy, Elections, Ethics & process, Immigration, Economy & labor) come from keyword lists.
All heuristic; tune the lists in `score.py`.

## Run locally

```
pip install feedparser requests
python scripts/fetch.py
python -m http.server 8742 --directory docs   # then open http://localhost:8742/
```

## Caveats

Paywalled outlets (Politico, Times Union, Newsday, NYT) contribute headlines and snippets only.
The Albany keyword filter on general feeds will miss stories that don't name the Governor,
the Legislature or Albany in the headline or lede. Google News coverage of official sites
(governor.ny.gov, nysenate.gov) is partial. Scores are a starting point, not a judgment.
