#!/usr/bin/env python3
"""Replace Google News redirect links (news.google.com/rss/articles/CBMi...) with the publisher's URL.

The redirect is opaque: Google's article page carries a signature and timestamp, and its batchexecute
endpoint trades them for the real URL. Two requests per link. Each item is tried at most MAX_TRIES times;
the original link stays in `gn_link`, and `id` is left alone so the archive merge still matches it.
"""
import json, re, time
from urllib.parse import quote, urlparse
import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
PER_RUN = 40       # Google answers 429 after ~110 rapid decodes from one IP; 40 per half-hour run is ample
                   # (new Google items arrive at well under that rate) and drains the backlog within a day
MAX_AGE_D = 10     # older Google items fall off the page anyway
MAX_TRIES = 2
SLEEP = 1.5
STOP_AFTER = 5     # consecutive failures: something changed, try next run


class Throttled(Exception): pass


def decode(url):
    aid = urlparse(url).path.rstrip("/").split("/")[-1]
    r = requests.get(f"https://news.google.com/articles/{aid}", headers={"User-Agent": UA}, timeout=15)
    if r.status_code == 429 or "/sorry/" in r.url: raise Throttled()
    sg = re.search(r'data-n-a-sg="([^"]+)"', r.text)
    ts = re.search(r'data-n-a-ts="([^"]+)"', r.text)
    if not (sg and ts):
        return None
    inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
             "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], aid, int(ts.group(1)), sg.group(1)]
    payload = [[["Fbv4je", json.dumps(inner), None, "generic"]]]
    r = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute",
                      headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", "User-Agent": UA},
                      data="f.req=" + quote(json.dumps(payload)), timeout=15)
    real = json.loads(json.loads(r.text.split("\n\n", 1)[1])[0][2])[1]
    return real if isinstance(real, str) and real.startswith("http") and "news.google" not in real else None


def run(items, now_ts, verbose=True):
    todo = [i for i in items if "news.google." in i.get("link", "")
            and i.get("gn_tries", 0) < MAX_TRIES and now_ts - i.get("published_ts", 0) <= MAX_AGE_D * 86400]
    todo.sort(key=lambda i: -i["published_ts"])
    done = fails = streak = 0
    for i in todo[:PER_RUN]:
        try:
            real = decode(i["link"])
        except Throttled:
            if verbose: print("gnlinks: Google returned 429; stopping until next run")
            break
        except Exception:
            real = None
        if real:
            i["gn_link"], i["link"] = i["link"], real
            if not i.get("domain"):
                i["domain"] = urlparse(real).netloc.replace("www.", "")
            done += 1; streak = 0
        else:
            i["gn_tries"] = i.get("gn_tries", 0) + 1
            fails += 1; streak += 1
            if streak >= STOP_AFTER: break
        time.sleep(SLEEP)
    if verbose:
        print(f"\ngnlinks: {done} resolved, {fails} failed, {max(0, len(todo) - done - fails)} left for later")
    return done
