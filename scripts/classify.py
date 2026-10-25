#!/usr/bin/env python3
"""Ask a small model what each new story is: its topics and what kind of story it is.

Why: the keyword heuristics in score.py read 8 to 14 words per item (81% of items had no summary before
extract.py started keeping og:description) and could not tell a policy story from a horse-race story from
an editorial that never says "Opinion:". The 10/25 review found the Immigration tag 60% wrong ("ice" inside
"police"), 27 of 34 editorials unflagged, and "policy relevance" rewarding campaign coverage.

What: every item not yet carrying `llm` and published in the last 7 days goes to Claude Haiku in batches of
BATCH, headline + outlet + summary, and comes back with up to three topics from TAGS and one `type`.
score.py prefers these to its keyword guesses when present. Judged once per item, cached on the item.

Cost: input is ~90 tokens an item plus a fixed system prompt; output ~35 tokens an item. Roughly 85 items a
day -> under a cent a day. Every call's usage is added to docs/data/llm_usage.json (totals and by day, in
tokens and dollars) and surfaced on the #review page. Ted asked for a spend update at the end of each week.

Runs only when ANTHROPIC_API_KEY is set (Pi env file / Actions secret, next to the NYT keys) and the
`anthropic` package is importable; otherwise fetch.py skips this step and the page runs on keywords alone.
"""
import json, os, time, datetime as dt

try:
    import anthropic
except ImportError:
    anthropic = None

from score import TAGS

MODEL   = "claude-haiku-5-5"
BATCH   = 25
PER_RUN = 150          # 6 calls; a week's backlog drains over a few refreshes
MAX_AGE_H = 7 * 24
# $ per million tokens, Claude Haiku 5.5 (prompts under 100K): input 0.10, output 0.50, cache read 0.01, cache write 0.125
PRICE = dict(input=0.10, output=0.50, cache_read=0.01, cache_write=0.125)

ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USAGE = os.path.join(ROOT, "docs", "data", "llm_usage.json")

TYPES = {
    "policy":       "reporting on what New York State government is doing or deciding: legislation, the budget, "
                    "agencies, regulations, courts, state programs, the Governor's or Legislature's actions, "
                    "and reporting that examines the effects of state policy",
    "campaign":     "election horse race: polls, endorsements, ads, fundraising, debates, candidate events, "
                    "attacks between candidates, race previews",
    "announcement": "a press release, or a story that only restates one: grants awarded, ribbon cuttings, "
                    "appointments, 'Governor announces', 'Senator X announces'",
    "opinion":      "editorial, op-ed, column, letter, endorsement, analysis clearly labeled as opinion",
    "blotter":      "a crime, arrest, court case, accident or fire story with no state policy dimension",
    "local":        "New York City or county/town/school-district government news with no state role, "
                    "including the Mayor's own actions and NYC Council business",
    "national":     "federal, other-state or foreign news where New York State government is not a party",
    "other":        "anything else: sports, business, culture, human interest",
}

SYSTEM = (
    "You classify headlines for a reading tool used by staff in the New York Governor's office to follow "
    "Albany policy coverage. For each item you get an outlet, a headline and sometimes a one-sentence summary. "
    "Return, for each item, up to three topics from the fixed list (fewest that fit; an empty list is fine), "
    "one type from the fixed list, and whether the piece is investigative.\n\n"
    "Topics: " + "; ".join(TAGS.keys()) + ".\n\n"
    "Types:\n" + "\n".join(f"- {k}: {v}" for k, v in TYPES.items()) + "\n\n"
    "Rules. A story about a candidate's record or plans on a policy question is 'campaign' if framed by the "
    "race and 'policy' if framed by the policy. A story that names the Governor only in passing is not "
    "automatically 'policy'. A newspaper endorsement ('Jane Doe for Assembly District 12') is 'opinion'. "
    "Mayor Mamdani acting as mayor, with no state role, is 'local'. 'investigative' is true only when the "
    "outlet's own reporting rests on records, data, documents or an inquiry it conducted, not when the story "
    "reports someone else's investigation or audit. Judge from the text given; do not guess beyond it."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n":      {"type": "integer"},
                    "topics": {"type": "array", "items": {"type": "string", "enum": list(TAGS.keys())}},   # the API rejects maxItems; the prompt says three and the code truncates
                    "type":   {"type": "string", "enum": list(TYPES.keys())},
                    "investigative": {"type": "boolean"},
                },
                "required": ["n", "topics", "type", "investigative"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def _load_usage():
    try:
        return json.load(open(USAGE))
    except Exception:
        return dict(model=MODEL, calls=0, items=0, input_tokens=0, output_tokens=0,
                    cache_read_tokens=0, cache_write_tokens=0, cost_usd=0.0, by_day={}, last=None)


def _record(u, usage, n_items, now_ts):
    cin  = getattr(usage, "input_tokens", 0) or 0
    cout = getattr(usage, "output_tokens", 0) or 0
    cr   = getattr(usage, "cache_read_input_tokens", 0) or 0
    cw   = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cost = (cin * PRICE["input"] + cout * PRICE["output"] + cr * PRICE["cache_read"] + cw * PRICE["cache_write"]) / 1e6
    day  = dt.datetime.utcfromtimestamp(now_ts).strftime("%Y-%m-%d")
    d = u["by_day"].setdefault(day, dict(calls=0, items=0, input_tokens=0, output_tokens=0, cost_usd=0.0))
    for tgt in (u, d):
        tgt["calls"] += 1; tgt["items"] += n_items
        tgt["input_tokens"] += cin + cr + cw; tgt["output_tokens"] += cout
        tgt["cost_usd"] = round(tgt["cost_usd"] + cost, 6)
    u["cache_read_tokens"] = u.get("cache_read_tokens", 0) + cr
    u["cache_write_tokens"] = u.get("cache_write_tokens", 0) + cw
    u["last"] = dt.datetime.utcfromtimestamp(now_ts).strftime("%Y-%m-%dT%H:%M:%SZ")
    u["model"] = MODEL
    return cost


def candidates(items, now_ts):
    pool = [i for i in items if "llm" not in i and (now_ts - i.get("published_ts", 0)) <= MAX_AGE_H * 3600]
    pool.sort(key=lambda x: -x.get("published_ts", 0))     # newest first: the top of the page gets judged first
    return pool[:PER_RUN]


def _ask(client, batch):
    lines = [dict(n=k, outlet=i.get("outlet", ""), headline=i.get("title", ""), summary=i.get("summary", "") or None)
             for k, i in enumerate(batch)]
    resp = client.messages.create(
        model=MODEL, max_tokens=4000,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": json.dumps(lines, ensure_ascii=False)}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("refusal")
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)["items"], resp.usage


def run(items, now_ts, verbose=True):
    """Classify new items in place. Returns the number judged this run (0 when the step is off)."""
    if anthropic is None or not os.environ.get("ANTHROPIC_API_KEY"):
        if verbose: print("\nclassify: off (no ANTHROPIC_API_KEY or anthropic package)")
        return 0
    todo = candidates(items, now_ts)
    if verbose: print(f"\nclassify: {len(todo)} items to judge")
    if not todo: return 0
    client = anthropic.Anthropic(max_retries=2, timeout=60.0)
    u = _load_usage(); done = 0
    for s in range(0, len(todo), BATCH):
        batch = todo[s:s + BATCH]
        try:
            rows, usage = _ask(client, batch)
        except anthropic.RateLimitError as e:
            print(f"  classify: rate limited, stopping this run ({e.__class__.__name__})"); break
        except anthropic.APIStatusError as e:
            print(f"  classify: API error {e.status_code}, stopping this run"); break
        except anthropic.APIConnectionError:
            print("  classify: connection error, stopping this run"); break
        except Exception as e:
            print(f"  classify: {type(e).__name__}: {e}"); break
        cost = _record(u, usage, len(batch), now_ts)
        for r in rows:
            k = r.get("n")
            if not isinstance(k, int) or k < 0 or k >= len(batch): continue
            batch[k]["llm"] = dict(type=r["type"], topics=r["topics"][:3], inv=bool(r["investigative"]), ts=int(now_ts))
            done += 1
        for i in batch:              # a row the model skipped is not retried every run
            i.setdefault("llm", dict(type="other", topics=[], inv=False, ts=int(now_ts), miss=True))
        if verbose:
            print(f"  {len(batch):3d} items  in {usage.input_tokens:5d} (+{getattr(usage,'cache_read_input_tokens',0) or 0} cached)  "
                  f"out {usage.output_tokens:4d}  ${cost:.4f}")
        time.sleep(0.5)
    json.dump(u, open(USAGE, "w"), indent=1)
    if verbose: print(f"classify: {done} judged; ${u['cost_usd']:.4f} spent to date over {u['calls']} calls")
    return done


def summary(items, now_ts, days=7):
    """For meta.json: spend to date and what the model said about the last week."""
    u = _load_usage()
    cut = now_ts - days * 86400
    wk = [i for i in items if i.get("llm") and i["published_ts"] >= cut]
    types = {}
    for i in wk: types[i["llm"]["type"]] = types.get(i["llm"]["type"], 0) + 1
    return dict(model=u.get("model", MODEL), calls=u.get("calls", 0), items=u.get("items", 0),
                cost_usd=round(u.get("cost_usd", 0.0), 4), last=u.get("last"),
                week=dict(classified=len(wk), unclassified=sum(1 for i in items if not i.get("llm") and i["published_ts"] >= cut),
                          types=dict(sorted(types.items(), key=lambda kv: -kv[1])),
                          investigative=sum(1 for i in wk if i["llm"].get("inv"))),
                by_day={k: v for k, v in sorted(u.get("by_day", {}).items())[-14:]})
