"""The report `log.send` takes: the fixed schema, built from the day's numbers.

Nothing in it comes from what a person said: the numbers are the score's, and
the only text is a category from the fixed list, a route, a build and a tier.
"""

from __future__ import annotations

from typing import Any

from .score import FAILURES

DIAGNOSIS_VERSION = "1"
# The fixed schema of `log.send` (grant `report`, Ten's design on #8726). No `build`: the lamp fills it itself.
FIELDS = (
    "turns", "answered_within_5s", "heard_to_first_sound_ms_median", "heard_to_first_sound_ms_p90", "asked_again",
    "held", "cut_ins", "tool_timeouts", "stuck", "tier", "score", "failures", "route", "diagnosis_version",
)


def build_report(day: dict[str, Any], diagnosis: list[str]) -> dict[str, Any]:
    failures = dict(day.get("failures", {}))
    for name in diagnosis:
        # A category the model names and the records did not count goes in as 1: flagged, not counted.
        if name in FAILURES:
            failures.setdefault(name, 1)
    report = {name: day.get(name) for name in FIELDS if name not in ("failures", "diagnosis_version")}
    report["failures"] = [{"category": name, "count": failures[name]} for name in FAILURES if name in failures]
    report["diagnosis_version"] = DIAGNOSIS_VERSION
    return {name: report[name] for name in FIELDS}
