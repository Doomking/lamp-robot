"""The day's score from turn records: numbers only, no text, no model.

A record is what the `turns` grant gives (docs/apps.md, #8726): times,
outcome, counts, the route and the build, never words. Only the keys read
below are read; anything else in a record is ignored.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

WITHIN_S = 5000
FAILURES = ("heard_wrongly", "slow_first_sound", "call_held", "answer_cut_off", "tool_timeout", "silent_turn")

# A placeholder for #7452's depth scale until Backend's table is in: the
# deepest tool a turn used sets the day's tier. A tool not listed is T1.
DEPTH = {
    "set_light": "T1", "get_time": "T1", "set_volume": "T1", "gesture": "T1",
    "reminders": "T2", "weather": "T2", "web_search": "T2", "tell_story": "T2", "remember": "T2",
    "play_music": "T3", "mail": "T3", "calendar": "T3", "timer": "T3",
    "start_agent_task": "T4", "confirm_agent_task": "T4", "make_skill": "T4", "use_skill": "T4",
}


def _percentile(values: list[int], p: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p * len(ordered)) - 1)]


def _median(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else round((ordered[mid - 1] + ordered[mid]) / 2)


def _commonest(records: list[dict[str, Any]], key: str) -> str:
    counts = Counter(str(r.get(key)) for r in records if r.get(key) is not None)
    return counts.most_common(1)[0][0] if counts else "unknown"


def score_day(records: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(records)
    if n == 0:
        return {"turns": 0, "score": None, "tier": None, "failures": {}}
    sounds = [r["heard_to_first_sound_ms"] for r in records if r.get("heard_to_first_sound_ms") is not None]
    quick = sum(1 for s in sounds if s <= WITHIN_S)
    calls = [c for r in records for c in r.get("calls", [])]
    timed_out_turns = sum(1 for r in records if any(c.get("timed_out") for c in r.get("calls", [])))
    outcome = Counter(r.get("outcome") for r in records)
    failures = Counter({
        "heard_wrongly": sum(1 for r in records if r.get("heard_wrongly") or r.get("name_missed")),
        "slow_first_sound": sum(1 for s in sounds if s > WITHIN_S),
        "call_held": outcome["held"],
        "answer_cut_off": sum(1 for r in records if r.get("cut_ins", 0) > 0),
        "tool_timeout": timed_out_turns,
        "silent_turn": sum(1 for r in records if r.get("outcome") == "stuck" and not r.get("words_heard")),
    })
    within = quick / n
    value = 100 * (
        0.5 * within
        + 0.2 * (1 - outcome["asked_again"] / n)
        + 0.1 * (1 - outcome["held"] / n)
        + 0.1 * (1 - outcome["stuck"] / n)
        + 0.1 * (1 - timed_out_turns / n)
    )
    depth = max((DEPTH.get(c.get("name"), "T1") for c in calls), default="T1")
    return {
        "turns": n,
        "answered_within_5s": round(100 * within, 1),
        "heard_to_first_sound_ms_median": _median(sounds),
        "heard_to_first_sound_ms_p90": _percentile(sounds, 0.9),
        "asked_again": outcome["asked_again"],
        "held": outcome["held"],
        "cut_ins": sum(r.get("cut_ins", 0) for r in records),
        "tool_timeouts": sum(1 for c in calls if c.get("timed_out")),
        "stuck": outcome["stuck"],
        "tier": depth,
        "score": max(0, min(100, round(value))),
        "failures": {name: count for name, count in failures.items() if count},
        "route": _commonest(records, "route"),
        "build": _commonest(records, "build"),
    }
