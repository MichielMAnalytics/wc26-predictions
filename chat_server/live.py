"""
Live WC scores via ESPN's free scoreboard API, cached server-side.

The browser polls /api/live every 30s; this module hits ESPN at most once per TTL
seconds regardless of how many visitors are watching. ESPN's soccer scoreboard is
keyless, reliable, and includes the live minute — better than football-data's free
tier (which only reports live status intermittently).
"""
from __future__ import annotations
import json, time, urllib.request

# whole-tournament window so we don't depend on the server clock; we only forward
# in-progress + finished games, which the client maps to the wall chart.
URL = ("https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
       "?dates=20260611-20260719")
TTL = 25
UA = {"User-Agent": "wc26-predictions/1.0 (live scores)"}

_cache: dict = {"ts": 0.0, "data": []}


def _fetch() -> list[dict]:
    req = urllib.request.Request(URL, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.load(r)
    out = []
    for e in d.get("events", []):
        comp = (e.get("competitions") or [{}])[0]
        cs = comp.get("competitors") or []
        home = next((c for c in cs if c.get("homeAway") == "home"), None)
        away = next((c for c in cs if c.get("homeAway") == "away"), None)
        if not home or not away:
            continue
        st = (e.get("status") or {}).get("type") or {}
        state = st.get("state")            # "pre" | "in" | "post"
        if state not in ("in", "post"):
            continue                       # only live + finished matter
        def num(c):
            try: return int(c.get("score"))
            except (TypeError, ValueError): return None
        out.append({
            "home_abbr": home["team"].get("abbreviation"),
            "away_abbr": away["team"].get("abbreviation"),
            "home": home["team"].get("displayName"),
            "away": away["team"].get("displayName"),
            "state": state,                                  # in / post
            "detail": st.get("shortDetail") or st.get("detail") or "",
            "hs": num(home),
            "as": num(away),
        })
    return out


def live_matches() -> list[dict]:
    now = time.time()
    if not _cache["data"] or now - _cache["ts"] > TTL:
        try:
            _cache["data"] = _fetch()
            _cache["ts"] = now
        except Exception:
            pass  # serve stale data on a transient upstream error
    return _cache["data"]
