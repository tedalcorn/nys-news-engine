"""Region tags: the ten Regional Economic Development Council regions.

Regional news is usually defined by the outlet's home, not by what the story is about: a check on 11/6 found
regional roundups drawing every item from outlets based in the region, statewide-sounding stories included
(a North Country public radio piece on the statewide election results), and a station's story about a nation
whose territory lies in the next region over. Ted's rule (11/6):
  - small local outlets: their home region, whatever the story says;
  - big outlets (statewide, NYC and the large regional dailies, whose Albany bureaus write statewide stories):
    the places the headline and summary name. A big daily's purely local story that names no place falls back
    to the paper's home region, so it is not left out of its own region.
A story that names no place and comes from a big outlet is statewide: no region.
"""
import re
from urllib.parse import urlparse

REGIONS = ["Western New York", "Finger Lakes", "Southern Tier", "Central New York", "Mohawk Valley",
           "North Country", "Capital Region", "Mid-Hudson", "New York City", "Long Island"]

# Every county, matched only as "X County": bare "Erie", "Orange", "Monroe" or "Washington" mean other things.
COUNTIES = {
    "Western New York": "Allegany Cattaraugus Chautauqua Erie Niagara",
    "Finger Lakes": "Genesee Livingston Monroe Ontario Orleans Seneca Wayne Wyoming Yates",
    "Southern Tier": "Broome Chemung Chenango Delaware Schuyler Steuben Tioga Tompkins",
    "Central New York": "Cayuga Cortland Madison Onondaga Oswego",
    "Mohawk Valley": "Fulton Herkimer Montgomery Oneida Otsego Schoharie",
    "North Country": "Clinton Essex Franklin Hamilton Jefferson Lewis St._Lawrence",
    "Capital Region": "Albany Columbia Greene Rensselaer Saratoga Schenectady Warren Washington",
    "Mid-Hudson": "Dutchess Orange Putnam Rockland Sullivan Ulster Westchester",
    "New York City": "Kings Queens Bronx Richmond New_York",
    "Long Island": "Nassau Suffolk",
}
# Places that are unambiguous when capitalized. Left out on purpose: bare "Albany" (it means the Capitol),
# and names shared with bigger places or common words (Greece, Geneva, Rome, Newark, Troy, Webster, Canton,
# Bath, Amherst, Medina, Waterloo, Fulton, Clay, Erie, Orleans, Wyoming, Ontario, Delaware, Ulster).
PLACES = {
    "Western New York": "Buffalo|Niagara Falls|Niagara County|Jamestown|Olean|Lockport|Tonawanda|Cheektowaga|Lackawanna|"
                        "Dunkirk|Salamanca|Wellsville|Chautauqua|Cattaraugus|Allegany|WNY|Western New York|Seneca Nation",
    "Finger Lakes": "Rochester|Batavia|Canandaigua|Brockport|Irondequoit|Pittsford|Fairport|Perinton|Seneca Falls|"
                    "Penn Yan|Genesee|Letchworth|Finger Lakes|Seneca Lake|Keuka|Canandaigua Lake",
    "Southern Tier": "Binghamton|Elmira|Ithaca|Corning|Endicott|Johnson City|Vestal|Endwell|Hornell|Owego|"
                     "Watkins Glen|Chemung|Chenango|Southern Tier|Cornell",
    "Central New York": "Syracuse|Auburn|Oswego|Cortland|Onondaga|Cayuga|Baldwinsville|Central New York|CNY|Micron|I-81",
    "Mohawk Valley": "Utica|Gloversville|Johnstown|Herkimer|Little Falls|Cooperstown|Oneonta|Cobleskill|Otsego|"
                     "Schoharie|Mohawk Valley|Oneida County",
    "North Country": "Plattsburgh|Watertown|Ogdensburg|Massena|Potsdam|Malone|Saranac Lake|Lake Placid|Tupper Lake|"
                     "Fort Drum|North Country|Adirondacks?|Akwesasne|St\\. Lawrence|Thousand Islands",
    "Capital Region": "Schenectady|Saratoga|Glens Falls|Queensbury|Cohoes|Rensselaer|Lake George|Capital Region|"
                      "Capital District|city of Albany|Albany Common Council|Albany mayor|Mayor Kathy Sheehan",
    "Mid-Hudson": "Kingston|Poughkeepsie|Newburgh|Middletown|Yonkers|White Plains|New Rochelle|Mount Vernon|Peekskill|"
                  "Nyack|Monsey|New Square|Spring Valley|Monticello|Beacon|Cold Spring|New Paltz|Fishkill|Westchester|"
                  "Rockland|Dutchess|Putnam County|Hudson Valley|Mid-Hudson|Catskills?",
    "New York City": "New York City|NYC|Brooklyn|Queens|Bronx|Manhattan|Staten Island|Harlem|Mamdani|NYPD|NYCHA|"
                     "Rikers|five boroughs|City Hall in Manhattan|New York City Council",
    "Long Island": "Long Island|Nassau|Suffolk|Hempstead|Islip|Brookhaven|Babylon|Oyster Bay|Long Beach|Riverhead|"
                   "Hamptons|Montauk|Smithtown|Huntington Station|Southampton|East Hampton",
}
_RX = {r: [re.compile(r"\b(" + "|".join(c.replace("_", " ") for c in COUNTIES[r].split()) + r") County\b"),
           re.compile(r"\b(" + PLACES[r] + r")\b")] for r in REGIONS}

def content_regions(text):
    """Regions whose places the text names (case-sensitive: these are proper nouns)."""
    return [r for r in REGIONS if any(x.search(text) for x in _RX[r])]

# Big outlets with a home: tagged by content; the home is only the fallback for their purely local stories.
BIG_HOME = {"newsday.com": "Long Island", "buffalonews.com": "Western New York", "timesunion.com": "Capital Region",
            "syracuse.com": "Central New York", "democratandchronicle.com": "Finger Lakes", "lohud.com": "Mid-Hudson",
            "gothamist.com": "New York City", "thecity.nyc": "New York City", "amny.com": "New York City",
            "nydailynews.com": "New York City", "nypost.com": "New York City", "documentedny.com": "New York City",
            "nyc.streetsblog.org": "New York City"}

# Regional editions of statewide brands: the URL path names the region (Spectrum, News 12, the Times Union's
# Hudson Valley section, the Daily Gazette's Adirondack edition). These count as small local outlets.
PATH_HOME = [("spectrumlocalnews.com/nys/rochester", "Finger Lakes"), ("spectrumlocalnews.com/nys/buffalo", "Western New York"),
             ("spectrumlocalnews.com/nys/central-ny", "Central New York"), ("spectrumlocalnews.com/nys/capital-region", "Capital Region"),
             ("spectrumlocalnews.com/nys/hudson-valley", "Mid-Hudson"), ("spectrumlocalnews.com/nys/southern-tier", "Southern Tier"),
             ("spectrumlocalnews.com/nys/mohawk-valley", "Mohawk Valley"), ("spectrumlocalnews.com/nys/north-country", "North Country"),
             ("spectrumlocalnews.com/nys/watertown", "North Country"), ("timesunion.com/hudsonvalley", "Mid-Hudson"),
             ("dailygazette.com/ade", "North Country"), ("bronx.news12.com", "New York City"), ("brooklyn.news12.com", "New York City"),
             ("longisland.news12.com", "Long Island"), ("hudsonvalley.news12.com", "Mid-Hudson"), ("westchester.news12.com", "Mid-Hudson"),
             ("news12.com/bronx", "New York City")]

# Small local outlets -> home region. Every outlet here is also a "local outlet" (tier 4) wherever it comes from,
# its own feed or a keyword sweep. Includes outlets that reach us only through sweeps today.
LOCAL_HOME = {}
for _r, _ds in {
    "Western New York": "wgrz.com wivb.com wkbw.com investigativepost.org niagara-gazette.com post-journal.com "
                        "oleantimesherald.com observertoday.com wellsvillesun.com btpm.org",
    "Finger Lakes": "whec.com 13wham.com rochesterfirst.com wxxinews.org fingerlakes1.com fingerlakesdailynews.com "
                    "thedailynewsonline.com rochesterbeacon.com orleanshub.com fltimes.com mpnnow.com",
    "Southern Tier": "wbng.com binghamtonhomepage.com wicz.com weny.com wskg.org pressconnects.com stargazette.com "
                     "ithacajournal.com ithacavoice.org ithaca.com theithacan.org bupipedream.com the-reporter.net "
                     "eveningtribune.com mytwintiers.com",
    "Central New York": "localsyr.com cnycentral.com oswegocountynewsnow.com centralcurrent.org auburnpub.com wrvo.org "
                        "cortlandstandard.com waer.org cnynews.com evesun.com",
    "Mohawk Valley": "wktv.com uticaod.com romesentinel.com oneidadispatch.com thelcn.com thedailystar.com leaderherald.com wibx950.com",
    "North Country": "wwnytv.com nny360.com northcountrypublicradio.org adirondackexplorer.org pressrepublican.com mynbc5.com "
                     "suncommunitynews.com adirondackdailyenterprise.com",
    "Capital Region": "cbs6albany.com news10.com wnyt.com dailygazette.com saratogian.com troyrecord.com poststar.com wamc.org",
    "Mid-Hudson": "poughkeepsiejournal.com midhudsonnews.com dailyfreeman.com recordonline.com rocklanddaily.com yonkerstimes.com "
                  "hudsonvalleypost.com monseyscoop.com radiocatskill.org riverreporter.com westfaironline.com talkofthesound.com "
                  "hudsonvalleyone.com theexaminernews.com",
    "New York City": "silive.com bushwickdaily.com brooklyneagle.com bkreader.com qns.com bxtimes.com riverdalepress.com "
                     "queenseagle.com ourtownny.com hellgatenyc.com qchron.com westsiderag.com amsterdamnews.com "
                     "manhattantimesnews.com chelseanewsny.com pix11.com abc7ny.com nbcnewyork.com",
    "Long Island": "liherald.com southshorepress.com longisland.com lilifepolitics.com huntingtonnow.com riverheadlocal.com "
                   "easthamptonstar.com longislandpress.com libn.com 27east.com",
}.items():
    for _d in _ds.split(): LOCAL_HOME[_d] = _r

def _dom(d): return (d or "").lower().removeprefix("www.")

def local_home(domain, link=""):
    """Home region when the item comes from a small local outlet (or a regional edition), else None."""
    l = (link or "").lower().replace("://www.", "://")
    for p, r in PATH_HOME:
        if p in l: return r
    for d in (_dom(domain), _dom(urlparse(link or "").netloc)):   # the link's host wins once a Google link is decoded
        if not d or "google." in d: continue
        r = LOCAL_HOME.get(d) or next((r for k, r in LOCAL_HOME.items() if d.endswith("." + k)), None)
        if r: return r
    return None

def is_local_outlet(domain, link=""):
    return local_home(domain, link) is not None

def regions(item):
    home = local_home(item.get("domain"), item.get("link"))
    if home: return [home]
    rs = content_regions(item.get("title", "") + " " + (item.get("summary") or ""))
    if not rs and item.get("local"):
        h = BIG_HOME.get(_dom(item.get("domain"))) or BIG_HOME.get(_dom(urlparse(item.get("link") or "").netloc))
        if h: rs = [h]
    return rs
