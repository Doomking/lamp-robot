"""Lamp Doctor, once a day: read the turns, score them, ask the lamp's model, send the schema."""

from __future__ import annotations

from typing import Any

from .diagnose import diagnose
from .report import build_report
from .score import score_day


async def run_day(ops: Any) -> bool:
    """True if a report was sent. Nothing is retried with anything else."""
    records = await ops.turns()
    if not records:
        return False
    day = score_day(records)
    try:
        heard = await ops.conversation()
    except Exception:
        heard = []
    categories = await diagnose(ops, day, heard)
    try:
        await ops.log_send(build_report(day, categories))
    except Exception:
        return False
    return True
