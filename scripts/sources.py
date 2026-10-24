"""Source list for the NYS News Engine.
kind: 'rss' = native feed; 'gnews' = Google News RSS (site: or keyword query) for sites that block scrapers;
      'gov' = governor.ny.gov/news scraped directly (Cloudflare needs a browser TLS fingerprint: curl_cffi);
      'nyt' = NYT developer API (Top Stories for the NY Region front + Article Search); silently skipped unless NYT_API_KEY is set.
Google News queries carry a `when:Nd` operator: without it Google returns its 100 most *relevant* hits,
many of them months old, and recent releases never surface (that is why Official went stale).
tier: 1 = Albany-specialist / accountability; 2 = strong general outlet; 3 = official / advocacy / watchdog release.
      Cross-outlet sweeps are tier 2: they return whatever outlet Google finds (Fox, local TV), which the page
      must not color as official. score.py docks sweeps instead, so they still rank below the outlet feeds.
albany_filter: True = general feed, keep only items that match Albany keywords, or STATE_TERMS (see fetch.py).
ny_anchor: True = national feed; a STATE_TERMS hit must also name New York (a "state senator" in Texas is not ours).
loose_anchor: True = unfiltered sweep whose query requires "New York" somewhere on the page; the headline+dek must
      still name New York or carry an Albany term without naming another state (Czech and Azerbaijani "state
      budget" stories were getting through).
"""
from urllib.parse import quote_plus
GN = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
def gn(query): return GN.format(q=quote_plus(query))

# State government beyond the Governor and the Legislature: courts, the AG and Comptroller, agencies,
# individual lawmakers. Added 2026-10-23 after a week of daily press clips showed the engine missing state
# stories that never name Hochul or Albany (a federal judge striking down the body-armor law, the State
# Police chief of staff search, AG-race coverage). Google caps a query at 100 hits and silently drops the
# when: limit on long OR chains (a 15-term version returned Times Union items up to 177 days old), so the
# terms are split into two short queries per outlet; fetch.py also drops Google items older than GN_MAX_AGE_DAYS.
STATE_QA = '("attorney general" OR DiNapoli OR "Court of Appeals" OR "state law" OR "Board of Elections" OR "Public Service Commission")'
STATE_QB = '("state police" OR Assemblymember OR Assemblyman OR Assemblywoman OR "state senator" OR Medicaid OR DOCCS OR SUNY)'
ALB_Q = '(Hochul OR Albany OR legislature OR Heastie OR "Stewart-Cousins" OR "state budget")'

SOURCES = [
 # --- Albany specialists (native) ---
 dict(name="New York Focus",      domain="nysfocus.com",        kind="rss",   url="https://nysfocus.com/feed",                       tier=1, albany_filter=False),
 dict(name="City & State",        domain="cityandstateny.com",  kind="rss",   url="https://www.cityandstateny.com/rss/all/",         tier=1, albany_filter=True),
 dict(name="City & State",        domain="cityandstateny.com",  kind="gnews", url=GN.format(q="site:cityandstateny.com+(Hochul+OR+Albany+OR+legislature+OR+Assembly+OR+%22state+Senate%22+OR+%22state+budget%22)+when:3d"), tier=1, albany_filter=False),
 dict(name="Politico NY Playbook",domain="politico.com",        kind="rss",   url="https://rss.politico.com/new-york-playbook.xml",  tier=1, albany_filter=False),
 # --- Albany specialists (blocked; via Google News) ---
 dict(name="Times Union",         domain="timesunion.com",      kind="gnews", url=GN.format(q="site:timesunion.com+(Hochul+OR+legislature+OR+Assembly+OR+%22state+Senate%22+OR+%22state+budget%22+OR+Heastie+OR+%22Stewart-Cousins%22)+when:3d"), tier=1, albany_filter=True),
 dict(name="NY State of Politics",domain="nystateofpolitics.com",kind="gnews",url=GN.format(q="site:nystateofpolitics.com+when:3d"),        tier=1, albany_filter=False),
 dict(name="Newsday",             domain="newsday.com",         kind="gnews", url=GN.format(q="site:newsday.com+(Hochul+OR+Albany+OR+legislature+OR+Blakeman)+when:3d"), tier=2, albany_filter=True),
 dict(name="Daily News",          domain="nydailynews.com",     kind="gnews", url=GN.format(q="site:nydailynews.com+(Hochul+OR+Albany+OR+legislature)+when:3d"), tier=2, albany_filter=True),
 dict(name="Times Union",         domain="timesunion.com",      kind="gnews", url=gn(f"site:timesunion.com {STATE_QA} when:3d"), tier=1, albany_filter=True),
 dict(name="Times Union",         domain="timesunion.com",      kind="gnews", url=gn(f"site:timesunion.com {STATE_QB} when:3d"), tier=1, albany_filter=True),
 dict(name="Newsday",             domain="newsday.com",         kind="gnews", url=gn(f"site:newsday.com {STATE_QA} when:3d"), tier=2, albany_filter=True),
 dict(name="Newsday",             domain="newsday.com",         kind="gnews", url=gn(f"site:newsday.com {STATE_QB} when:3d"), tier=2, albany_filter=True),
 dict(name="Daily News",          domain="nydailynews.com",     kind="gnews", url=gn(f"site:nydailynews.com {STATE_QA} when:3d"), tier=2, albany_filter=True),
 dict(name="Daily News",          domain="nydailynews.com",     kind="gnews", url=gn(f"site:nydailynews.com {STATE_QB} when:3d"), tier=2, albany_filter=True),
 dict(name="Politico",            domain="politico.com",        kind="gnews", url=gn(f'site:politico.com "New York" {ALB_Q} when:3d'), tier=1, albany_filter=True, ny_anchor=True),
 dict(name="Gotham Gazette",      domain="gothamgazette.com",   kind="gnews", url=GN.format(q="site:gothamgazette.com+when:7d"),            tier=2, albany_filter=True),
 # --- General outlets (native, filtered) ---
 dict(name="Gothamist",           domain="gothamist.com",       kind="rss",   url="https://gothamist.com/feed",                      tier=2, albany_filter=True),
 dict(name="New York Times",      domain="nytimes.com",         kind="rss",   url="https://rss.nytimes.com/services/xml/rss/nyt/NYRegion.xml", tier=2, albany_filter=True),
 dict(name="New York Times",      domain="nytimes.com",         kind="nyt",   url="",                                                tier=2, albany_filter=True),
 dict(name="NY Post Politics",    domain="nypost.com",          kind="rss",   url="https://nypost.com/politics/feed/",               tier=2, albany_filter=True, ny_anchor=True),
 dict(name="NY Post Metro",       domain="nypost.com",          kind="rss",   url="https://nypost.com/metro/feed/",                  tier=2, albany_filter=True),
 dict(name="The City",            domain="thecity.nyc",         kind="rss",   url="https://www.thecity.nyc/feed/",                   tier=2, albany_filter=True),
 # WSJ: Google matches site-wide sidebars, so most hits are unrelated; the filter keeps the few that name Albany.
 # (AP was tried 2026-10-23 and dropped: every AP item in a week of press clips was national.)
 dict(name="Wall Street Journal", domain="wsj.com",             kind="gnews", url=gn('site:wsj.com (Hochul OR Albany OR "New York state") when:7d'), tier=2, albany_filter=True, ny_anchor=True),
 # --- Upstate (added 2026-10-23 from the clips comparison) ---
 dict(name="Buffalo News",        domain="buffalonews.com",     kind="gnews", url=gn(f"site:buffalonews.com {ALB_Q} when:3d"),    tier=2, albany_filter=True),
 dict(name="Buffalo News",        domain="buffalonews.com",     kind="gnews", url=gn(f"site:buffalonews.com {STATE_QA} when:3d"), tier=2, albany_filter=True),
 dict(name="Buffalo News",        domain="buffalonews.com",     kind="gnews", url=gn(f"site:buffalonews.com {STATE_QB} when:3d"), tier=2, albany_filter=True),
 dict(name="Syracuse.com",        domain="syracuse.com",        kind="rss",   url="https://www.syracuse.com/arc/outboundfeeds/rss/category/politics/?outputType=xml", tier=2, albany_filter=True),
 dict(name="FingerLakes1",        domain="fingerlakes1.com",    kind="rss",   url="https://www.fingerlakes1.com/feed/",              tier=2, albany_filter=True),
 dict(name="Adirondack Explorer", domain="adirondackexplorer.org", kind="rss", url="https://www.adirondackexplorer.org/feed",         tier=2, albany_filter=True),
 # --- Watchdogs / think tanks ---
 dict(name="Reinvent Albany",     domain="reinventalbany.org",  kind="rss",   url="https://reinventalbany.org/feed",                 tier=3, albany_filter=False),
 dict(name="Fiscal Policy Institute", domain="fiscalpolicy.org",kind="rss",   url="https://fiscalpolicy.org/feed",                   tier=3, albany_filter=False),
 dict(name="Empire Center",       domain="empirecenter.org",    kind="rss",   url="https://www.empirecenter.org/feed/",              tier=3, albany_filter=False),
 dict(name="Citizens Budget Commission", domain="cbcny.org",    kind="gnews", url=GN.format(q="site:cbcny.org+when:7d"),                     tier=3, albany_filter=False),
 dict(name="Citizens Union",      domain="citizensunion.org",   kind="rss",   url="https://searchlight.citizensunion.org/feed",      tier=3, albany_filter=False),
 # --- Official ---
 dict(name="Governor's Office",   domain="governor.ny.gov",     kind="gov",   url="https://www.governor.ny.gov/news",                tier=3, albany_filter=False),
 dict(name="Governor's Office",   domain="governor.ny.gov",     kind="gnews", url=GN.format(q="site:governor.ny.gov+when:3d"),               tier=3, albany_filter=False),
 dict(name="NY Senate",           domain="nysenate.gov",        kind="gnews", url=GN.format(q="site:nysenate.gov+when:7d"),                  tier=3, albany_filter=False),
 dict(name="NY Assembly",         domain="nyassembly.gov",      kind="gnews", url=GN.format(q="site:nyassembly.gov+when:7d"),                tier=3, albany_filter=False),
 # --- Cross-outlet keyword sweeps (catch what the feeds miss) ---
 dict(name="Google News: Hochul", domain="",                    kind="gnews", url=GN.format(q="%22Hochul%22+when:2d"),                       tier=2, albany_filter=False, sweep=True),
 dict(name="Google News: Legislature", domain="",               kind="gnews", url=GN.format(q="%22New+York%22+(Heastie+OR+%22Stewart-Cousins%22+OR+%22state+budget%22+OR+%22Executive+Chamber%22)+when:2d"), tier=2, albany_filter=False, sweep=True, loose_anchor=True),
 # Wider state-government sweeps: kept only if they clear STATE_TERMS with a New York anchor (fetch.py),
 # and every item they admit carries `gate` so the #review page can show which terms let noise in.
 dict(name="Google News: Courts & statewide officials", domain="", kind="gnews", url=gn('"New York" ("Letitia James" OR "attorney general James" OR DiNapoli OR "state comptroller" OR "Court of Appeals" OR "Appellate Division" OR "state law" OR unconstitutional) when:2d'), tier=2, albany_filter=True, ny_anchor=True, sweep=True),
 dict(name="Google News: State agencies", domain="", kind="gnews", url=gn('"New York" ("Board of Elections" OR "Public Service Commission" OR DOCCS OR NYSERDA OR "Department of Environmental Conservation" OR "state Health Department" OR "Office of Mental Health" OR "Adirondack Park Agency" OR "Board of Regents" OR Thruway) when:2d'), tier=2, albany_filter=True, ny_anchor=True, sweep=True),
 dict(name="Google News: Lawmakers", domain="", kind="gnews", url=gn('"New York" (Assemblymember OR Assemblyman OR Assemblywoman OR "state Sen." OR "state senator" OR "Senate District" OR "Assembly District") when:2d'), tier=2, albany_filter=True, ny_anchor=True, sweep=True),
]

# Keep general-feed items only if they hit one of these (case-insensitive, title+summary)
ALBANY_TERMS = [
 "hochul","legislature","assembly","state senate","stewart-cousins","heastie","governor","gov.",
 "state budget","blakeman","state lawmakers","state legislat","executive chamber","dob ","division of the budget",
 "state of the state","article vii","ortt","ed ra","kpk","persichilli","mahanna","comptroller dinapoli",
 "essential plan","seqra","mta","tier 6","chapter amendment","one-house","big ugly","message of necessity",
]

# Second gate for the same feeds: state government that doesn't name the Governor or the Legislature.
# An item admitted only by one of these records the term as `gate`; review them at the page's #review.
STATE_TERMS = [
 "state police","letitia james","attorney general james","state attorney general","new york attorney general",
 "ny attorney general","attorney general's office","attorney general candidate","attorney general race","attorney general debate","dinapoli","state comptroller","court of appeals","appellate division",
 "state law","state's law","new york law","state ban","unconstitutional","struck down","second amendment","2nd amendment","board of elections","public service commission",
 "doccs","state prison","suny","nyserda","department of environmental conservation","state health department",
 "department of health","office of mental health","adirondack park agency","board of regents","state education department",
 "thruway","state agency","state agencies","state officials","state funding","state aid","state grant","medicaid","assemblymember",
 "assemblyman","assemblywoman","assembly member","state sen.","state senator","senate district","assembly district",
 "ballot proposal","ballot question","constitutional amendment","state worker","state employee",
]

# A STATE_TERMS admission is dropped if it reads like a police blotter: "State police seize 5.5 kilograms",
# "Southern State Parkway crash". Albany-term admissions are not checked against this.
BLOTTER = ["crash","collide","arrest","seize","pursuit","shooting","shot ","homicide","killed","killing","murder",
 "missing","fire in","injur","dies","died","dwi","overdose","stabbing","robbery","burglary","fentanyl","seek man","seek woman",
 "hiker","rescue","evacuat","campfire","forest ranger"]   # DEC ranger reports name the Department in every dek

# Outlets whose own domains we already cover natively; keyword sweeps drop these to avoid dupes
SWEEP_EXCLUDE_DOMAINS = {"nysfocus.com","cityandstateny.com","politico.com","gothamist.com","nytimes.com","nypost.com","thecity.nyc","reinventalbany.org","fiscalpolicy.org","empirecenter.org"}

# A headline mentioning only a generic "governor" is not necessarily ours: "Gov. Gavin Newsom"
# was clearing the Albany filter. Drop items that carry an out-of-state marker and no NY anchor.
GENERIC_ALBANY = ["governor","gov."]   # match any state's governor; not proof of NY
NY_ANCHORS = ["new york","n.y.","nys","hochul","albany","heastie","stewart-cousins","dinapoli","letitia james",
 "blakeman","mamdani","executive chamber","state senate passes","adirondack","upstate","catskill","empire state","brooklyn","queens","bronx",
 "staten island","manhattan","long island","buffalo","rochester","syracuse","yonkers","mta","nypd",
 "cuny","suny","hudson valley","westchester","nassau","suffolk"]
OUT_OF_STATE = ["newsom","california","texas","florida","desantis","abbott","illinois","chicago",
 "new jersey","pennsylvania","shapiro","connecticut","massachusetts","boston","ohio","georgia",
 "michigan","virginia","arizona","colorado","washington state","oregon","nevada","wisconsin",
 "new mexico","haaland","maryland","minnesota","sherrill","ciattarelli","spanberger","vermont","maine","kentucky",
 "louisiana","tennessee","los angeles","karen bass","carolina","iowa","kansas","oklahoma","utah","idaho","montana","alaska","hawaii"]

# NYT API items (facet names: Person:/Location:/Subject:/Organization:) are kept when a NY-specific facet
# matches, or a generic state-government facet appears alongside a New York location, or title+abstract
# clears ALBANY_TERMS. Generic facets alone ("Subject:Legislatures") pull in Texas and Australia.
NYT_FACETS = ["hochul","heastie","stewart-cousins","blakeman","dinapoli","new york state","albany (ny)",
 "executive chamber","metropolitan transportation authority","new york state legislature"]
NYT_GENERIC = ["legislature","governors (us)","state budget","budgets and budgeting","medicaid","elections, governors"]
