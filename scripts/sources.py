"""Source list for the NYS News Engine.
kind: 'rss' = native feed; 'gnews' = Google News RSS (site: or keyword query) for sites that block scrapers.
tier: 1 = Albany-specialist / accountability; 2 = strong general outlet; 3 = official / advocacy / watchdog release.
albany_filter: True = general feed, keep only items that match Albany keywords (see fetch.py).
"""
GN = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"

SOURCES = [
 # --- Albany specialists (native) ---
 dict(name="New York Focus",      domain="nysfocus.com",        kind="rss",   url="https://nysfocus.com/feed",                       tier=1, albany_filter=False),
 dict(name="City & State",        domain="cityandstateny.com",  kind="rss",   url="https://www.cityandstateny.com/rss/all/",         tier=1, albany_filter=True),
 dict(name="City & State",        domain="cityandstateny.com",  kind="gnews", url=GN.format(q="site:cityandstateny.com+(Hochul+OR+Albany+OR+legislature+OR+Assembly+OR+%22state+Senate%22+OR+%22state+budget%22)"), tier=1, albany_filter=False),
 dict(name="Politico NY Playbook",domain="politico.com",        kind="rss",   url="https://rss.politico.com/new-york-playbook.xml",  tier=1, albany_filter=False),
 # --- Albany specialists (blocked; via Google News) ---
 dict(name="Times Union",         domain="timesunion.com",      kind="gnews", url=GN.format(q="site:timesunion.com+(Hochul+OR+legislature+OR+Assembly+OR+%22state+Senate%22+OR+%22state+budget%22+OR+Heastie+OR+%22Stewart-Cousins%22)"), tier=1, albany_filter=True),
 dict(name="NY State of Politics",domain="nystateofpolitics.com",kind="gnews",url=GN.format(q="site:nystateofpolitics.com"),        tier=1, albany_filter=False),
 dict(name="Newsday",             domain="newsday.com",         kind="gnews", url=GN.format(q="site:newsday.com+(Hochul+OR+Albany+OR+legislature+OR+Blakeman)"), tier=2, albany_filter=True),
 dict(name="Daily News",          domain="nydailynews.com",     kind="gnews", url=GN.format(q="site:nydailynews.com+(Hochul+OR+Albany+OR+legislature)"), tier=2, albany_filter=True),
 dict(name="Gotham Gazette",      domain="gothamgazette.com",   kind="gnews", url=GN.format(q="site:gothamgazette.com"),            tier=2, albany_filter=True),
 # --- General outlets (native, filtered) ---
 dict(name="Gothamist",           domain="gothamist.com",       kind="rss",   url="https://gothamist.com/feed",                      tier=2, albany_filter=True),
 dict(name="NYT New York",        domain="nytimes.com",         kind="rss",   url="https://rss.nytimes.com/services/xml/rss/nyt/NYRegion.xml", tier=2, albany_filter=True),
 dict(name="NY Post Politics",    domain="nypost.com",          kind="rss",   url="https://nypost.com/politics/feed/",               tier=2, albany_filter=True),
 dict(name="NY Post Metro",       domain="nypost.com",          kind="rss",   url="https://nypost.com/metro/feed/",                  tier=2, albany_filter=True),
 dict(name="The City",            domain="thecity.nyc",         kind="rss",   url="https://www.thecity.nyc/feed/",                   tier=2, albany_filter=True),
 # --- Watchdogs / think tanks ---
 dict(name="Reinvent Albany",     domain="reinventalbany.org",  kind="rss",   url="https://reinventalbany.org/feed",                 tier=3, albany_filter=False),
 dict(name="Fiscal Policy Institute", domain="fiscalpolicy.org",kind="rss",   url="https://fiscalpolicy.org/feed",                   tier=3, albany_filter=False),
 dict(name="Empire Center",       domain="empirecenter.org",    kind="rss",   url="https://www.empirecenter.org/feed/",              tier=3, albany_filter=False),
 dict(name="Citizens Budget Commission", domain="cbcny.org",    kind="gnews", url=GN.format(q="site:cbcny.org"),                     tier=3, albany_filter=False),
 # --- Official ---
 dict(name="Governor's Office",   domain="governor.ny.gov",     kind="gnews", url=GN.format(q="site:governor.ny.gov"),               tier=3, albany_filter=False),
 dict(name="NY Senate",           domain="nysenate.gov",        kind="gnews", url=GN.format(q="site:nysenate.gov"),                  tier=3, albany_filter=False),
 dict(name="NY Assembly",         domain="nyassembly.gov",      kind="gnews", url=GN.format(q="site:nyassembly.gov"),                tier=3, albany_filter=False),
 # --- Cross-outlet keyword sweeps (catch what the feeds miss) ---
 dict(name="Google News: Hochul", domain="",                    kind="gnews", url=GN.format(q="%22Hochul%22"),                       tier=3, albany_filter=False, sweep=True),
 dict(name="Google News: Legislature", domain="",               kind="gnews", url=GN.format(q="%22New+York%22+(Heastie+OR+%22Stewart-Cousins%22+OR+%22state+budget%22+OR+%22Executive+Chamber%22)"), tier=3, albany_filter=False, sweep=True),
]

# Keep general-feed items only if they hit one of these (case-insensitive, title+summary)
ALBANY_TERMS = [
 "hochul","legislature","assembly","state senate","stewart-cousins","heastie","governor","gov.",
 "state budget","blakeman","state lawmakers","state legislat","executive chamber","dob ","division of the budget",
 "state of the state","article vii","ortt","ed ra","kpk","persichilli","mahanna","comptroller dinapoli",
 "essential plan","seqra","mta","tier 6","chapter amendment","one-house","big ugly","message of necessity",
]

# Outlets whose own domains we already cover natively; keyword sweeps drop these to avoid dupes
SWEEP_EXCLUDE_DOMAINS = {"nysfocus.com","cityandstateny.com","politico.com","gothamist.com","nytimes.com","nypost.com","thecity.nyc","reinventalbany.org","fiscalpolicy.org","empirecenter.org"}
