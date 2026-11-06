"""Source list for the NYS News Engine.
kind: 'rss' = native feed; 'gnews' = Google News RSS (site: or keyword query) for sites that block scrapers;
      'gov' = governor.ny.gov/news scraped directly (Cloudflare needs a browser TLS fingerprint: curl_cffi);
      'page' / 'nycmayor' = other officials' release lists, scraped directly (fetch.py: fetch_page, fetch_nycmayor);
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
POL_Q = '(Republicans OR Democrats OR GOP OR election OR Mamdani OR "county executive" OR congressional)'

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
 # Syracuse.com's whole feed since 2026-11-06 (was politics only: its health-desk story on Medicaid work requirements in
 # Onondaga County never reached us). local_overflow: what fails the state filter is kept as a local story (see LOCAL below).
 dict(name="Syracuse.com",        domain="syracuse.com",        kind="rss",   url="https://www.syracuse.com/arc/outboundfeeds/rss/?outputType=xml", tier=2, albany_filter=True, local_overflow=True),
 # Big papers searched again with the vocabulary of New York politics that never says "Albany" (a coverage check on 11/6:
 # post-election analysis, Long Island results, NY-21 and the pied-a-terre appeal were all missed). The filter still applies.
 *[dict(name=n, domain=d, kind="gnews", url=gn(f"site:{d} {POL_Q} when:2d"), tier=t, albany_filter=True)
   for n, d, t in (("Newsday","newsday.com",2), ("Times Union","timesunion.com",1), ("Daily News","nydailynews.com",2),
                   ("Buffalo News","buffalonews.com",2))],
 dict(name="Politico",            domain="politico.com",        kind="gnews", url=gn(f'site:politico.com "New York" {POL_Q} when:2d'), tier=1, albany_filter=True, ny_anchor=True),
 # Overlooked statewide and NYC outlets (coverage check, 11/6)
 dict(name="amNY",                domain="amny.com",            kind="rss",   url="https://www.amny.com/feed/",                      tier=2, albany_filter=True),
 dict(name="Documented",          domain="documentedny.com",    kind="rss",   url="https://www.documentedny.com/feed/",              tier=2, albany_filter=True),
 dict(name="Streetsblog NYC",     domain="nyc.streetsblog.org", kind="rss",   url="https://nyc.streetsblog.org/feed",                tier=2, albany_filter=True),
 dict(name="Chalkbeat New York",  domain="chalkbeat.org",       kind="rss",   url="https://www.chalkbeat.org/arc/outboundfeeds/rss/?outputType=xml", tier=2, albany_filter=False, path_rx=r"/newyork/"),
 # --- Watchdogs / think tanks ---
 dict(name="Reinvent Albany",     domain="reinventalbany.org",  kind="rss",   url="https://reinventalbany.org/feed",                 tier=3, albany_filter=False),
 dict(name="Fiscal Policy Institute", domain="fiscalpolicy.org",kind="rss",   url="https://fiscalpolicy.org/feed",                   tier=3, albany_filter=False),
 dict(name="Empire Center",       domain="empirecenter.org",    kind="rss",   url="https://www.empirecenter.org/feed/",              tier=3, albany_filter=False),
 dict(name="Citizens Budget Commission", domain="cbcny.org",    kind="gnews", url=GN.format(q="site:cbcny.org+when:7d"),                     tier=3, albany_filter=False),
 dict(name="Citizens Union",      domain="citizensunion.org",   kind="rss",   url="https://searchlight.citizensunion.org/feed",      tier=3, albany_filter=False),
 # --- Official: every press-release channel is official=True, which puts it under "Filter by official" on the page,
 #     in the Official tab, and out of Picks. Direct scrapes where the office's own list is reachable (added 2026-11-05):
 #     'page' = the office's release list, each new link opened once for its og:title/og:description;
 #     'nycmayor' = nyc.gov's sitemap (the Mayor's news page draws its list by script, the sitemap lists every release).
 dict(name="Governor's Office",   domain="governor.ny.gov",     kind="gov",   url="https://www.governor.ny.gov/news",                tier=3, albany_filter=False, official=True),
 dict(name="Attorney General",    domain="ag.ny.gov",           kind="page",  url="https://ag.ny.gov/press-releases", base="https://ag.ny.gov",
      link_rx=r'href="(/press-release/20\d\d/[^"#?]+)"', tier=3, albany_filter=False, official=True),
 dict(name="Comptroller",         domain="osc.ny.gov",          kind="page",  url="https://www.osc.ny.gov/press", base="https://www.osc.ny.gov",
      link_rx=r'href="(/press/releases/20\d\d/\d\d/[^"#?]+)"', tier=3, albany_filter=False, official=True),
 dict(name="Assembly Speaker",    domain="nyassembly.gov",      kind="page",  url="https://nyassembly.gov/Press/?sec=press-list", base="https://nyassembly.gov",
      link_rx=r'href="(/Press/\?sec=story&(?:amp;)?story=\d+)"', blurb_rx=r'post-blurb">(.*?)</div>', bad_desc="View Speaker Press Releases",
      tier=3, albany_filter=False, official=True),
 # The Majority Leader's nysenate.gov newsroom: she posts few releases there (latest Jan 2026 as of 11/5), but it is her channel.
 dict(name="Senate Majority Leader", domain="nysenate.gov",     kind="page",  url="https://www.nysenate.gov/senators/andrea-stewart-cousins/newsroom?page=1", base="https://www.nysenate.gov",
      link_rx=r'href="(/newsroom/(?:press-releases|articles)/20\d\d/andrea-stewart-cousins/[^"#?]+)"', skip_rx=r"boletin",
      tier=3, albany_filter=False, official=True),
 # Members' releases. The bare site: query also returned bill pages, law PDFs and community office hours.
 dict(name="NY Senate",           domain="nysenate.gov",        kind="gnews", url=gn("site:nysenate.gov/newsroom/press-releases when:7d"),   tier=3, albany_filter=False, official=True),
 dict(name="NYC Mayor",           domain="nyc.gov",             kind="nycmayor", url="https://www.nyc.gov/sitemap.xml",              tier=3, albany_filter=False, official=True),
 # --- Local outlets (added 2026-11-06 after a coverage check showed almost no regional news; Ted: pull them in, mark them local,
 #     score them down). tier 4 = local outlet. Each feed is read whole, minus wire copy, sports, obituaries and
 #     sponsored "press release" pages (fetch.py LOCAL_SKIP); a story that clears the state filter is an ordinary
 #     item, one that doesn't is kept with `local: True` (hidden unless a region or that outlet is chosen, never in
 #     Picks, kept 30 days). Region = the outlet's home (geo.LOCAL_HOME). Feeds checked 11/6.
 dict(name='WIVB'                        , domain='wivb.com'                  , kind="rss", url='https://www.wivb.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='WKBW'                        , domain='wkbw.com'                  , kind="rss", url='https://www.wkbw.com/news/local-news.rss', tier=4, albany_filter=True, local=True),
 dict(name='Investigative Post'          , domain='investigativepost.org'     , kind="rss", url='https://www.investigativepost.org/feed/', tier=4, albany_filter=True, local=True),
 dict(name='Niagara Gazette'             , domain='niagara-gazette.com'       , kind="rss", url='https://www.niagara-gazette.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc', tier=4, albany_filter=True, local=True),
 dict(name='Post-Journal'                , domain='post-journal.com'          , kind="rss", url='https://www.post-journal.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='Olean Times Herald'          , domain='oleantimesherald.com'      , kind="rss", url='https://www.oleantimesherald.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='WHEC'                        , domain='whec.com'                  , kind="rss", url='https://www.whec.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='Rochester First'             , domain='rochesterfirst.com'        , kind="rss", url='https://www.rochesterfirst.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='WXXI News'                   , domain='wxxinews.org'              , kind="rss", url='https://www.wxxinews.org/local-news.rss', tier=4, albany_filter=True, local=True),
 dict(name='FingerLakes1'                , domain='fingerlakes1.com'          , kind="rss", url='https://www.fingerlakes1.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='Finger Lakes Daily News'     , domain='fingerlakesdailynews.com'  , kind="rss", url='https://www.fingerlakesdailynews.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='The Daily News (Batavia)'    , domain='thedailynewsonline.com'    , kind="rss", url='https://www.thedailynewsonline.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc', tier=4, albany_filter=True, local=True),
 dict(name='Rochester Beacon'            , domain='rochesterbeacon.com'       , kind="rss", url='https://www.rochesterbeacon.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='WBNG'                        , domain='wbng.com'                  , kind="rss", url='https://www.wbng.com/arc/outboundfeeds/rss/?outputType=xml', tier=4, albany_filter=True, local=True),
 dict(name='WIVT Binghamton'             , domain='binghamtonhomepage.com'    , kind="rss", url='https://www.binghamtonhomepage.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='WICZ'                        , domain='wicz.com'                  , kind="rss", url='https://www.wicz.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc', tier=4, albany_filter=True, local=True),
 dict(name='WENY'                        , domain='weny.com'                  , kind="rss", url='https://www.weny.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc', tier=4, albany_filter=True, local=True),
 dict(name='WETM'                        , domain='mytwintiers.com'           , kind="rss", url='https://www.mytwintiers.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='Ithaca Voice'                , domain='ithacavoice.org'           , kind="rss", url='https://www.ithacavoice.org/feed/', tier=4, albany_filter=True, local=True),
 dict(name='Ithaca Times'                , domain='ithaca.com'                , kind="rss", url='https://www.ithaca.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc', tier=4, albany_filter=True, local=True),
 dict(name='WSYR'                        , domain='localsyr.com'              , kind="rss", url='https://www.localsyr.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='Oswego County News Now'      , domain='oswegocountynewsnow.com'   , kind="rss", url='https://www.oswegocountynewsnow.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc', tier=4, albany_filter=True, local=True),
 dict(name='Central Current'             , domain='centralcurrent.org'        , kind="rss", url='https://www.centralcurrent.org/feed/', tier=4, albany_filter=True, local=True),
 dict(name='The Citizen (Auburn)'        , domain='auburnpub.com'             , kind="rss", url='https://www.auburnpub.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc', tier=4, albany_filter=True, local=True),
 dict(name='Cortland Standard'           , domain='cortlandstandard.com'      , kind="rss", url='https://www.cortlandstandard.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc', tier=4, albany_filter=True, local=True),
 dict(name='WKTV'                        , domain='wktv.com'                  , kind="rss", url='https://www.wktv.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc', tier=4, albany_filter=True, local=True),
 dict(name='Rome Sentinel'               , domain='romesentinel.com'          , kind="rss", url='https://www.romesentinel.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc', tier=4, albany_filter=True, local=True),
 dict(name='The Daily Star (Oneonta)'    , domain='thedailystar.com'          , kind="rss", url='https://www.thedailystar.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc', tier=4, albany_filter=True, local=True),
 dict(name='WIBX'                        , domain='wibx950.com'               , kind="rss", url='https://www.wibx950.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='WWNY'                        , domain='wwnytv.com'                , kind="rss", url='https://www.wwnytv.com/arc/outboundfeeds/rss/?outputType=xml', tier=4, albany_filter=True, local=True),
 dict(name='Watertown Daily Times'       , domain='nny360.com'                , kind="rss", url='https://www.nny360.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc', tier=4, albany_filter=True, local=True),
 dict(name='Press-Republican'            , domain='pressrepublican.com'       , kind="rss", url='https://www.pressrepublican.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc', tier=4, albany_filter=True, local=True),
 dict(name='NBC5 Plattsburgh'            , domain='mynbc5.com'                , kind="rss", url='https://www.mynbc5.com/topstories-rss', tier=4, albany_filter=True, local=True),
 dict(name='Adirondack Explorer'         , domain='adirondackexplorer.org'    , kind="rss", url='https://www.adirondackexplorer.org/feed', tier=4, albany_filter=True, local=True),
 dict(name='WTEN News10'                 , domain='news10.com'                , kind="rss", url='https://www.news10.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='WNYT'                        , domain='wnyt.com'                  , kind="rss", url='https://www.wnyt.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='Daily Gazette'               , domain='dailygazette.com'          , kind="rss", url='https://www.dailygazette.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc', tier=4, albany_filter=True, local=True),
 dict(name='Troy Record'                 , domain='troyrecord.com'            , kind="rss", url='https://www.troyrecord.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='Post-Star'                   , domain='poststar.com'              , kind="rss", url='https://www.poststar.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc', tier=4, albany_filter=True, local=True),
 dict(name='WAMC'                        , domain='wamc.org'                  , kind="rss", url='https://www.wamc.org/rss.xml', tier=4, albany_filter=True, local=True),
 dict(name='Hudson Valley One'           , domain='hudsonvalleyone.com'       , kind="rss", url='https://www.hudsonvalleyone.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='Yonkers Times'               , domain='yonkerstimes.com'          , kind="rss", url='https://www.yonkerstimes.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='The Examiner News'           , domain='theexaminernews.com'       , kind="rss", url='https://www.theexaminernews.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='Staten Island Advance'       , domain='silive.com'                , kind="rss", url='https://www.silive.com/arc/outboundfeeds/rss/?outputType=xml', tier=4, albany_filter=True, local=True),
 dict(name='QNS'                         , domain='qns.com'                   , kind="rss", url='https://www.qns.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='BK Reader'                   , domain='bkreader.com'              , kind="rss", url='https://www.bkreader.com/rss/', tier=4, albany_filter=True, local=True),
 dict(name='Bronx Times'                 , domain='bxtimes.com'               , kind="rss", url='https://www.bxtimes.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='West Side Rag'               , domain='westsiderag.com'           , kind="rss", url='https://www.westsiderag.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='PIX11'                       , domain='pix11.com'                 , kind="rss", url='https://www.pix11.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='ABC7 New York'               , domain='abc7ny.com'                , kind="rss", url='https://abc7ny.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='NBC New York'                , domain='nbcnewyork.com'            , kind="rss", url='https://www.nbcnewyork.com/news/feed/', tier=4, albany_filter=True, local=True),
 dict(name='Long Island Press'           , domain='longislandpress.com'       , kind="rss", url='https://www.longislandpress.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='LI Life & Politics'          , domain='lilifepolitics.com'        , kind="rss", url='https://www.lilifepolitics.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='Long Island Business News'   , domain='libn.com'                  , kind="rss", url='https://www.libn.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='RiverheadLOCAL'              , domain='riverheadlocal.com'        , kind="rss", url='https://www.riverheadlocal.com/feed/', tier=4, albany_filter=True, local=True),
 dict(name='27east'                      , domain='27east.com'                , kind="rss", url='https://www.27east.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc', tier=4, albany_filter=True, local=True),
 # Local outlets with no working feed (403, 404, timeouts (WGRZ), or stale: Mid-Hudson News's feed stopped 10/28). Through Google, several
 # sites per query (Google takes OR'd site: terms). local=True: what fails the state filter is kept as a local story, as
 # for the feeds; the links are decoded by the resolve-links workflow like every Google link. The Hudson Valley has its
 # own query because none of its main outlets has a usable feed (the 11/6 check caught almost nothing there).
 dict(name="Google News: local outlets 1", domain="", kind="gnews", url=gn("(site:wgrz.com OR site:13wham.com OR site:cbs6albany.com OR site:cnycentral.com OR site:wskg.org OR site:northcountrypublicradio.org OR site:wrvo.org) when:2d"), tier=4, albany_filter=True, sweep=True, local=True),
 dict(name="Google News: local outlets 2", domain="", kind="gnews", url=gn("(site:midhudsonnews.com OR site:dailyfreeman.com OR site:recordonline.com OR site:poughkeepsiejournal.com OR site:rocklanddaily.com OR site:timesunion.com/hudsonvalley) when:2d"), tier=4, albany_filter=True, sweep=True, local=True),
 dict(name="Google News: local outlets 3", domain="", kind="gnews", url=gn("(site:democratandchronicle.com OR site:lohud.com OR site:pressconnects.com OR site:stargazette.com OR site:uticaod.com OR site:ithacajournal.com) when:2d"), tier=4, albany_filter=True, sweep=True, local=True),
 dict(name="Google News: local outlets 4", domain="", kind="gnews", url=gn("(site:liherald.com OR site:hellgatenyc.com OR site:brooklyneagle.com OR site:riverdalepress.com OR site:adirondackdailyenterprise.com OR site:suncommunitynews.com OR site:saratogian.com OR site:oneidadispatch.com) when:2d"), tier=4, albany_filter=True, sweep=True, local=True),
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

# Third gate (2026-11-06): New York politics that names neither Albany nor a state office. The 11/6 coverage
# check missed the GOP's post-election feud, Long Island results, NY-21, the Mamdani-DSA wins and the pied-a-terre appeal:
# every one names New York (or a New York place) and a party, a race or a political office, none says "Albany".
# A POLITICS hit always needs a New York anchor, and the text must not name another state (party words are national).
# Admitted items carry gate = "politics: <term>" for the #review tally. Stories that are really national get typed
# 'national' by the classifier and scored down; this gate only decides what is collected.
POLITICS_TERMS = ["republican","democrat","gop","dsa","democratic socialist","working families party","conservative party",
 "blue wave","red wave","midterm","election","elected","re-elect","reelect","voters","turnout","congress","congressional",
 "congressman","congresswoman","rep.","house seat","county executive","mayor","mamdani","city council","council member",
 "candidate","campaign","poll","siena","endorse","primary","lawmaker","politic","legislation","law ","ordinance",
 "lawsuit","appeals court","federal judge","judge","ruling","statewide","state's"]

# A STATE_TERMS admission is dropped if it reads like a police blotter: "State police seize 5.5 kilograms",
# "Southern State Parkway crash". Albany-term admissions are not checked against this.
BLOTTER = ["crash","collide","arrest","seize","pursuit","shooting","shot ","homicide","killed","killing","murder",
 "missing","fire in","injur","dies","died","dwi","overdose","stabbing","robbery","burglary","fentanyl","seek man","seek woman",
 "hiker","rescue","evacuat","campfire","forest ranger",
 # 11/6: sentencing stories cleared "state prison" ("Geneva man sentenced to prison for raping 14-year-old")
 "sentenc","rape","raping","sex abuse","sexual abuse","child porn","pleads guilty","pleaded guilty"]   # DEC ranger reports name the Department in every dek

# Outlets whose own domains we already cover natively; keyword sweeps drop these to avoid dupes
SWEEP_EXCLUDE_DOMAINS = {"nysfocus.com","cityandstateny.com","politico.com","gothamist.com","nytimes.com","nypost.com","thecity.nyc","reinventalbany.org","fiscalpolicy.org","empirecenter.org"}

# A headline mentioning only a generic "governor" is not necessarily ours: "Gov. Gavin Newsom"
# was clearing the Albany filter. Drop items that carry an out-of-state marker and no NY anchor.
GENERIC_ALBANY = ["governor","gov."]   # match any state's governor; not proof of NY
NY_ANCHORS = ["new york","n.y.","nys","hochul","albany","heastie","stewart-cousins","dinapoli","letitia james",
 "blakeman","mamdani","executive chamber","state senate passes","adirondack","upstate","catskill","empire state","brooklyn","queens","bronx",
 "staten island","manhattan","long island","buffalo","rochester","syracuse","yonkers","mta","nypd",
 "cuny","suny","hudson valley","westchester","nassau","suffolk",
 # added 11/6: New York's regions, cities and counties (geo.py), so "Long Island Republicans" or "Onondaga County's
 # Democrats" counts as New York without naming the state
 "nyc","new york's","new yorkers","rockland","dutchess","putnam","orange county, n","ulster county","sullivan county",
 "long island","hempstead","islip","brookhaven","finger lakes","southern tier","north country","mohawk valley","capital region",
 "western new york","central new york","binghamton","elmira","ithaca","utica","schenectady","saratoga","troy, n","plattsburgh",
 "watertown","poughkeepsie","newburgh","kingston","white plains","new rochelle","niagara","onondaga","monroe county",
 "erie county","albany county","oneida county","broome county","nypd","stefanik","lawler","lalota","garbarino",
 "malliotakis","cornell","micron","fort drum"]   # not Schumer/Jeffries/Gillibrand: their stories are mostly national
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

# Press-release channels, for the page's "Filter by official" box and the Official tab. "NY Assembly" is the retired
# site:nyassembly.gov query, kept so its archived items stay official until they age out.
OFFICIALS = list(dict.fromkeys([s["name"] for s in SOURCES if s.get("official")] + ["State agencies", "NY Assembly"]))
