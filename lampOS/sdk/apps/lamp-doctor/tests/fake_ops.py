"""A fake of Ten's ops for Lamp Doctor, until lamp-control builds them.

Everything the app assumes about `turns`, `model.ask` and `log.send` is here
and nowhere else, so a change of shape on #8726 is a change in this file.
"""

from __future__ import annotations

FAILURES = ("heard_wrongly", "slow_first_sound", "call_held", "answer_cut_off", "tool_timeout", "silent_turn")

# Ten's design on #8726 (12:52): the lamp fills `build` itself, an app's value is dropped, so the app sends none.
REPORT_FIELDS = {
    "turns", "answered_within_5s", "heard_to_first_sound_ms_median", "heard_to_first_sound_ms_p90", "asked_again",
    "held", "cut_ins", "tool_timeouts", "stuck", "tier", "score", "failures", "route", "diagnosis_version",
}


class BadReport(Exception):
    code = "bad_report"


class RateLimited(Exception):
    code = "rate_limited"


def turn(**over):
    """A turn record as the voice would hand it over: no text of any kind."""
    record = {
        "turn": 1, "at": 29_000_000, "route": "live", "build": "16220", "outcome": "answered",
        "heard_to_first_sound_ms": 2000, "cut_ins": 0, "calls": [], "words_heard": 5, "words_said": 12,
        "heard_wrongly": False, "name_missed": False, "held_then_repeated": False,
    }
    record.update(over)
    return record


def strict_check(report: dict) -> None:
    """lamp-control's `log.send` check: the fixed schema or nothing."""
    extra = set(report) - REPORT_FIELDS
    missing = REPORT_FIELDS - set(report)
    if extra or missing:
        raise BadReport(f"fields: extra {sorted(extra)}, missing {sorted(missing)}")
    if not isinstance(report["failures"], list):
        raise BadReport("failures: a list of {category, count}")
    for item in report["failures"]:
        if not isinstance(item, dict) or set(item) != {"category", "count"}:
            raise BadReport("failures: each is {category, count}")
        if item["category"] not in FAILURES:
            raise BadReport(f"failures: {item['category']!r} is not a listed category")
        if not isinstance(item["count"], int) or isinstance(item["count"], bool) or item["count"] < 0:
            raise BadReport(f"failures.{item['category']}: not a count")
    for name in ("route", "diagnosis_version", "tier"):
        if not isinstance(report[name], str) or len(report[name]) > 24 or " " in report[name]:
            raise BadReport(f"{name}: a short word")
    for name in REPORT_FIELDS - {"failures", "route", "diagnosis_version", "tier"}:
        value = report[name]
        if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise BadReport(f"{name}: a number")


class FakeOps:
    """What an app that holds turns, conversation, model.ask and log.send can call."""

    def __init__(self, turns, answer="[]", cap=1, heard=()):
        self._turns, self._answer, self._cap, self._heard = list(turns), answer, cap, list(heard)
        self.asked, self.sent, self.refused = [], [], []

    async def turns(self, since=None):
        return list(self._turns)

    async def conversation(self, since=None):
        return list(self._heard)

    async def model_ask(self, prompt, input=None, max_chars=400):
        if len(self.asked) >= self._cap:
            raise RateLimited("the daily cap")
        self.asked.append({"prompt": prompt, "input": input, "max_chars": max_chars})
        return {"text": self._answer[:max_chars]}

    async def log_send(self, report):
        try:
            strict_check(report)
        except BadReport:
            self.refused.append(report)
            raise
        self.sent.append(report)
        return {"accepted": True}
