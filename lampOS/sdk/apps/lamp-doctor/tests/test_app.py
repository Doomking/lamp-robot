"""A whole day against a fake of Ten's ops: what leaves is the schema, always."""

import asyncio
import json

from fake_ops import FakeOps, strict_check, turn
from lamp_doctor.app import run_day

SENTENCE = "turn the bedroom light blue please Anna"


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, 10))


def test_a_day_sends_one_report_and_it_passes_the_strict_check():
    ops = FakeOps([turn(turn=i) for i in range(5)], answer='["silent_turn"]')
    sent = run(run_day(ops))
    assert sent is True
    assert len(ops.sent) == 1 and not ops.refused
    strict_check(ops.sent[0])
    assert ops.sent[0]["turns"] == 5


def test_a_model_that_echoes_the_heard_sentence_does_not_get_it_out():
    ops = FakeOps([turn(turn=1)], answer=json.dumps([SENTENCE, "heard_wrongly"]), heard=[{"heard": SENTENCE}])
    run(run_day(ops))
    assert not ops.refused
    wire = json.dumps(ops.sent)
    assert "Anna" not in wire and "bedroom" not in wire and SENTENCE not in wire


def test_heard_words_may_go_to_the_model_but_never_to_log_send():
    ops = FakeOps([turn(turn=1)], answer='["heard_wrongly"]', heard=[{"heard": SENTENCE}])
    run(run_day(ops))
    assert not any(SENTENCE in json.dumps(r) for r in ops.sent)


def test_no_turns_sends_nothing():
    ops = FakeOps([])
    assert run(run_day(ops)) is False
    assert ops.sent == [] and ops.asked == []


def test_a_day_with_the_cap_already_reached_still_reports():
    ops = FakeOps([turn(turn=1)], cap=0)
    assert run(run_day(ops)) is True
    assert {f["category"] for f in ops.sent[0]["failures"]} <= {"heard_wrongly", "slow_first_sound",
        "call_held", "answer_cut_off", "tool_timeout", "silent_turn"}


def test_a_refused_report_is_not_retried_with_anything_else():
    ops = FakeOps([turn(turn=1)])
    calls = []
    original = ops.log_send

    async def refuse(report):
        calls.append(report)
        raise __import__("fake_ops").BadReport("no")

    ops.log_send = refuse
    assert run(run_day(ops)) is False
    assert len(calls) == 1
