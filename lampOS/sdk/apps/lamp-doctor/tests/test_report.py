"""The report holds the fixed fields and nothing a person said."""

import pytest

from fake_ops import BadReport, FAILURES, REPORT_FIELDS, strict_check, turn
from lamp_doctor.report import build_report
from lamp_doctor.score import score_day


def test_the_report_is_exactly_the_fixed_schema():
    report = build_report(score_day([turn()]), diagnosis=[])
    assert set(report) == REPORT_FIELDS
    strict_check(report)


def test_a_diagnosis_adds_only_listed_categories_with_counts():
    report = build_report(score_day([turn(heard_wrongly=True)]), diagnosis=["heard_wrongly", "silent_turn"])
    assert {f["category"] for f in report["failures"]} <= set(FAILURES)
    strict_check(report)


def test_an_unlisted_category_is_dropped_not_sent():
    report = build_report(score_day([turn()]), diagnosis=["the user said turn on the lamp", "Anna", "heard_wrongly"])
    assert {f["category"] for f in report["failures"]} <= set(FAILURES)
    assert "Anna" not in repr(report) and "lamp" not in repr(report)


def test_the_strict_check_refuses_what_the_app_must_never_send():
    good = build_report(score_day([turn()]), diagnosis=[])
    for broken in (
        {**good, "note": "she said hello"},
        {**good, "failures": [{"category": "Anna asked for the light", "count": 1}]},
        {**good, "route": "turn the light on"},
    ):
        with pytest.raises(BadReport):
            strict_check(broken)
