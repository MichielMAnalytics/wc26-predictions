"""
WC26 predictions explainer agent.

A transparency layer over the prediction model: an Anthropic tool-use agent that
answers visitor questions about HOW the predictions were produced. Every factual
claim is grounded in the model's own outputs via tools that read the real files
(MODEL.md + data/model/*.csv + data/predictions/*) — the agent is instructed not
to invent numbers, only to report what the tools return.

Streaming agentic loop built on the official `anthropic` SDK (manual loop so we
can stream text deltas and per-tool status to the browser over SSE).
"""

from __future__ import annotations

import csv
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

import anthropic

# ---------------------------------------------------------------------------
# Paths — the repo root holds MODEL.md and the data/ tree.
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
MODEL_DIR = DATA / "model"
PRED_DIR = DATA / "predictions"

MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# Small CSV/JSON loaders (cached — the files are tiny and change only on a
# model rebuild, in which case the service is restarted).
# ---------------------------------------------------------------------------


@lru_cache(maxsize=None)
def _read_text(path: str) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""


@lru_cache(maxsize=None)
def _read_csv(path: str) -> tuple[dict[str, str], ...]:
    p = Path(path)
    if not p.exists():
        return ()
    with p.open(encoding="utf-8") as f:
        return tuple(dict(row) for row in csv.DictReader(f))


@lru_cache(maxsize=None)
def _read_json(path: str) -> Any:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _match_team(query: str) -> str | None:
    """Resolve a fuzzy team name against the 48 teams in the sim table."""
    rows = _read_csv(str(MODEL_DIR / "sim_team_probs.csv"))
    names = [r["team"] for r in rows]
    q = _norm(query)
    if not q:
        return None
    for n in names:                       # exact (normalised)
        if _norm(n) == q:
            return n
    for n in names:                       # substring either direction
        nn = _norm(n)
        if q in nn or nn in q:
            return n
    return None


# ---------------------------------------------------------------------------
# Tool implementations — each returns plain text/JSON the model can quote.
# ---------------------------------------------------------------------------


def t_get_methodology() -> str:
    """Full model write-up: pipeline, why Dixon-Coles, backtest, market layer."""
    return _read_text(str(REPO / "MODEL.md")) or "MODEL.md not found."


def t_get_headline_picks() -> str:
    summary = _read_json(str(PRED_DIR / "_summary.json")) or {}
    return json.dumps(
        {
            "champion_pick": summary.get("champion"),
            "runner_up": summary.get("runner"),
            "third_place": summary.get("third"),
            "note": (
                "Champion bet uses a 50/50 blend of the model's Monte-Carlo "
                "title probability and vig-free bookmaker implied probability. "
                "Use get_team_outlook for the exact per-team numbers."
            ),
        },
        ensure_ascii=False,
        indent=2,
    )


def t_list_teams() -> str:
    """Every team with Elo, Elo rank, and simulated champion probability."""
    sim = {r["team"]: r for r in _read_csv(str(MODEL_DIR / "sim_team_probs.csv"))}
    ratings = sorted(
        _read_csv(str(MODEL_DIR / "ratings.csv")),
        key=lambda r: float(r["elo"]),
        reverse=True,
    )
    out = []
    rank = 0
    for r in ratings:
        team = r["team"]
        if team not in sim:
            continue          # ratings.csv covers all intl teams; keep the 48 in the sim
        rank += 1
        out.append(
            {
                "team": team,
                "elo": float(r["elo"]),
                "elo_rank_of_48": rank,
                "p_champion": float(sim[team]["p_champion"]),
            }
        )
    out.sort(key=lambda x: x["p_champion"], reverse=True)
    return json.dumps(out, ensure_ascii=False, indent=2)


def t_get_team_outlook(team: str) -> str:
    name = _match_team(team)
    if not name:
        return f"No team matching {team!r} among the 48 finalists. Use list_teams."

    sim = next(
        (r for r in _read_csv(str(MODEL_DIR / "sim_team_probs.csv")) if r["team"] == name),
        {},
    )
    rating = next(
        (r for r in _read_csv(str(MODEL_DIR / "ratings.csv")) if r["team"] == name), {}
    )
    adj = next(
        (r for r in _read_csv(str(MODEL_DIR / "adjustments.csv")) if r["team"] == name), {}
    )
    mkt = next(
        (r for r in _read_csv(str(MODEL_DIR / "market_odds.csv")) if r["team"] == name), {}
    )

    result = {
        "team": name,
        "elo": float(rating["elo"]) if rating.get("elo") else None,
        "elo_matches": int(rating["n_matches"]) if rating.get("n_matches") else None,
        "simulated_probabilities_30k_runs": {
            k: float(sim[k]) for k in sim if k != "team"
        },
        "availability_form_market_adjustment": {
            "d_attack_logspace": float(adj["d_atk"]) if adj.get("d_atk") else None,
            "d_defence_logspace": float(adj["d_def"]) if adj.get("d_def") else None,
            "notes": adj.get("notes", ""),
            "explanation": (
                "Capped (+/-0.20 log-space) nudge to attack/defence from Part-2 "
                "injury & momentum research plus a bookmaker market z-score. "
                "Positive d_attack = stronger attack."
            ),
        },
        "market": {
            "group": mkt.get("group"),
            "outright_american_odds": mkt.get("outright_american"),
            "p_champion_bookmaker_vigfree": (
                float(mkt["p_champion_market"]) if mkt.get("p_champion_market") else None
            ),
            "p_groupwin_bookmaker_vigfree": (
                float(mkt["p_groupwin_market"]) if mkt.get("p_groupwin_market") else None
            ),
        },
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


def t_get_group_predictions(group: str) -> str:
    g = (group or "").strip().upper()
    standings = [
        r for r in _read_csv(str(PRED_DIR / "group_standings.csv")) if r["group"].upper() == g
    ]
    matches = [
        r for r in _read_csv(str(PRED_DIR / "group_matches.csv")) if r["group"].upper() == g
    ]
    if not standings:
        groups = sorted({r["group"] for r in _read_csv(str(PRED_DIR / "group_standings.csv"))})
        return f"No group {group!r}. Available groups: {', '.join(groups)}."
    return json.dumps(
        {
            "group": g,
            "predicted_final_standings": standings,
            "predicted_matches": matches,
            "legend": {
                "pred": "EV-optimal scoreline (argmax of 30*P(outcome)+15*P(exact))",
                "p_home/p_draw/p_away": "Dixon-Coles outcome probabilities",
                "exp_points": "expected Scorito points from the picked score",
            },
        },
        ensure_ascii=False,
        indent=2,
    )


def t_get_knockout_bracket(round: str = "") -> str:
    rows = _read_csv(str(PRED_DIR / "knockout.csv"))
    r = (round or "").strip().upper()
    if r:
        rows = [x for x in rows if x["round"].upper() == r]
        if not rows:
            avail = sorted({x["round"] for x in _read_csv(str(PRED_DIR / "knockout.csv"))})
            return f"No round {round!r}. Available rounds: {', '.join(avail)}."
    return json.dumps(
        {
            "rounds_note": "Modal simulated bracket. 'advances' = team progressing.",
            "matches": list(rows),
        },
        ensure_ascii=False,
        indent=2,
    )


def t_get_match_prediction(home: str = "", away: str = "") -> str:
    h, a = _match_team(home) or home, _match_team(away) or away
    hits = []
    for r in _read_csv(str(PRED_DIR / "group_matches.csv")):
        if {_norm(r["home"]), _norm(r["away"])} & {_norm(h), _norm(a)}:
            hits.append({"stage": "group", **r})
    for r in _read_csv(str(PRED_DIR / "knockout.csv")):
        if {_norm(r["home"]), _norm(r["away"])} & {_norm(h), _norm(a)}:
            hits.append({"stage": "knockout", **r})
    if not hits:
        return (
            f"No predicted fixture involving {home!r}/{away!r}. Note the bracket is the "
            "modal simulation, so a specific knockout meeting may not occur in it."
        )
    return json.dumps(hits, ensure_ascii=False, indent=2)


def t_get_top_scorers() -> str:
    data = _read_json(str(PRED_DIR / "_topscorers.json")) or {}
    return json.dumps(
        {
            "golden_boot_by_expected_goals": data.get("golden_boot", []),
            "scorito_position_weighted_value": data.get("scorito", []),
            "explanation": (
                "exp_goals = expected tournament goals from age-decayed career "
                "international scoring rate * expected matches played (from the sim). "
                "scorito ev weights goals by Scorito's position multipliers, which is "
                "why attacking defenders/midfielders surface as value picks."
            ),
        },
        ensure_ascii=False,
        indent=2,
    )


TOOL_IMPLS = {
    "get_methodology": t_get_methodology,
    "get_headline_picks": t_get_headline_picks,
    "list_teams": t_list_teams,
    "get_team_outlook": t_get_team_outlook,
    "get_group_predictions": t_get_group_predictions,
    "get_knockout_bracket": t_get_knockout_bracket,
    "get_match_prediction": t_get_match_prediction,
    "get_top_scorers": t_get_top_scorers,
}

TOOLS: list[dict] = [
    {
        "name": "get_methodology",
        "description": (
            "Return the full model write-up (MODEL.md): the pipeline, why Dixon-Coles + "
            "Elo + Monte Carlo were chosen, the out-of-sample backtest numbers, the "
            "injury/form adjustment layer, and the bookmaker market layer. Call this first "
            "for any 'how does the model work / why' question."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_headline_picks",
        "description": "The headline submission: champion, runner-up, third-place picks.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_teams",
        "description": (
            "List all 48 finalists with Elo rating, Elo rank, and simulated champion "
            "probability, sorted by title chance. Use for overview / ranking questions."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_team_outlook",
        "description": (
            "Everything the model says about one team: Elo, full simulated round-by-round "
            "probabilities (advance, R16, QF, SF, final, champion) from 30k Monte-Carlo "
            "runs, the exact injury/form/market attack & defence adjustment with its notes, "
            "and the vig-free bookmaker probabilities. Use for any single-team question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"team": {"type": "string", "description": "Team name (fuzzy ok)."}},
            "required": ["team"],
        },
    },
    {
        "name": "get_group_predictions",
        "description": (
            "Predicted final standings and every predicted match (scoreline + outcome "
            "probabilities + expected Scorito points) for one group (A-L)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"group": {"type": "string", "description": "Group letter A-L."}},
            "required": ["group"],
        },
    },
    {
        "name": "get_knockout_bracket",
        "description": (
            "The simulated knockout bracket: each tie's predicted scoreline, who advances, "
            "and outcome probabilities. Optionally filter to a round (R32, R16, QF, SF, F)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"round": {"type": "string", "description": "Optional: R32/R16/QF/SF/F."}},
        },
    },
    {
        "name": "get_match_prediction",
        "description": "Find the model's predicted fixture(s) involving one or two named teams.",
        "input_schema": {
            "type": "object",
            "properties": {
                "home": {"type": "string"},
                "away": {"type": "string"},
            },
        },
    },
    {
        "name": "get_top_scorers",
        "description": (
            "Top-scorer model output: Golden Boot ranking by expected goals, plus the "
            "Scorito position-weighted value picks, with the methodology."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]

SYSTEM = """You are the transparency assistant for a Scorito World Cup 2026 \
prediction model. Visitors ask how the predictions on this wall chart were produced. \
Your job is to explain the model HONESTLY, EXACTLY, and in plain language.

Core rules:
- Be fully transparent. Never invent numbers. Every quantitative claim must come from a \
tool result in this conversation. If a tool doesn't have it, say so plainly.
- Quote the real figures (probabilities, Elo, adjustments, expected goals) and say which \
part of the model they come from. Round sensibly for readability but stay faithful.
- Reach for tools eagerly: get_methodology for "how/why" questions; get_team_outlook for a \
team; get_group_predictions / get_knockout_bracket for fixtures; get_top_scorers for scorers; \
list_teams / get_headline_picks for overviews. Call multiple tools when useful.
- Be honest about limits and uncertainty: the model's own backtest shows deep-run picks are \
edges, not certainties (WC2022 was upset-heavy); the injury/form layer is a capped prior, not \
fit from data; market odds are a one-off snapshot. Surface these when relevant.
- Keep answers tight and readable for a chat bubble: a short direct answer first, then the \
key supporting numbers. Use compact markdown (short paragraphs, the occasional list). \
Avoid walls of text and avoid dumping raw JSON.
- Stay on topic: this model and these WC2026 predictions. Politely decline unrelated requests.
"""


def run_agent(history: list[dict], user_message: str) -> Iterator[dict]:
    """
    Stream one assistant turn as a sequence of events:
      {"type": "tool",  "name": ...}   a tool is being called (status line)
      {"type": "text",  "text": ...}   a chunk of the answer
      {"type": "done"}                 turn complete
      {"type": "error", "text": ...}   something failed
    `history` is the prior [{"role","content"}] messages (text only); it is not mutated.
    """
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    messages: list[dict] = list(history) + [{"role": "user", "content": user_message}]

    try:
        for _ in range(6):  # cap the tool loop
            with client.messages.stream(
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM,
                tools=TOOLS,
                messages=messages,
                thinking={"type": "adaptive"},
                extra_body={"output_config": {"effort": "medium"}},
            ) as stream:
                for event in stream:
                    if (
                        event.type == "content_block_delta"
                        and getattr(event.delta, "type", None) == "text_delta"
                    ):
                        yield {"type": "text", "text": event.delta.text}
                    elif (
                        event.type == "content_block_start"
                        and getattr(event.content_block, "type", None) == "tool_use"
                    ):
                        yield {"type": "tool", "name": event.content_block.name}

                final = stream.get_final_message()

            if final.stop_reason != "tool_use":
                break

            messages.append({"role": "assistant", "content": final.content})
            results = []
            for block in final.content:
                if block.type == "tool_use":
                    fn = TOOL_IMPLS.get(block.name)
                    try:
                        out = fn(**(block.input or {})) if fn else f"Unknown tool {block.name}"
                    except Exception as exc:  # never let a tool crash the turn
                        out = f"Tool error: {exc}"
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": out}
                    )
            messages.append({"role": "user", "content": results})

        yield {"type": "done"}
    except anthropic.APIStatusError as exc:
        yield {"type": "error", "text": f"Model API error ({exc.status_code})."}
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "text": f"Unexpected error: {exc}"}
