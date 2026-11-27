#!/usr/bin/env python3
"""P1 gate probe: the quantities cog.rs / fold_plan actually bound, recomputed
with the mj_setConst fix (see p0_2_cog_fix.py).

Adds three things the fix JSON does not carry:
  1. idle / rest0 static lean_back (-cx at yaw zero) -> LOOK_MM floor;
  2. fold-gate bound (relative, upstream) vs fold-path off_axis AND lean_back
     -> whether fold_plan accepts the physically-safe linear fold;
  3. per-clip rectangular tip margin per frame (MuJoCo), not just the
     off_axis proxy -> direct evidence for CLIP_MM.

Run: /tmp/lelamp-sim-venv/bin/python product/brain-sim/analysis/p0_2_gate_probe.py
Out: p0_2_gate_probe.json (next to this script).
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "product/brain-sim"))
sys.path.insert(0, str(ROOT / "product/calibration"))
src = open(HERE / "p0_2_cog_fix.py").read().split('out = {"fix"')[0]
g = {"__name__": "cogfix", "__file__": str(HERE / "p0_2_cog_fix.py")}
exec(src, g)
apply, setdeg, setnorm, readout = g["apply"], g["setdeg"], g["setnorm"], g["readout"]
sim, m, d, adr, JOINTS = g["sim"], g["m"], g["d"], g["adr"], g["JOINTS"]
import mujoco
import numpy as np

rest_q = g["qarr"](-18, 14, -45)
clips = json.load(open(ROOT / "product/body-clips/lelamp_clips.json"))
CLIP2BUS = [2, 3, 4, 1, 0]  # clip [hp,hr,yaw,shoulder,elbow] -> qpos order


def set_q(q):
    d.qpos[:] = 0
    for k, j in enumerate(JOINTS):
        d.qpos[adr[j]] = q[k]
    d.qvel[:] = 0


def lb(r):
    return -r["cog_xy_mm"][0]


res = {}
for tag, ballast in (("nb", False), ("b500", True)):
    apply(0.180 - g["head_real"], ballast)
    setnorm(sim.rec["idle"][1682])
    iq = d.qpos[[adr[j] for j in JOINTS]].copy()
    r_idle = readout()
    q0 = iq.copy(); q0[0] = 0.0
    set_q(q0)
    r_idle_y0 = readout()
    set_q(rest_q)
    r_rest = readout()
    paths = {}
    for staged in (False, True):
        mx_off, mx_lb, mn_margin = 0.0, -1e9, 1e9
        N = 96
        for s in range(N + 1):
            t = s / N
            q = iq.copy()
            if staged:
                q[4] = iq[4] + (rest_q[4] - iq[4]) * min(1, t * 3)
                q[2] = iq[2] + (rest_q[2] - iq[2]) * min(1, max(0, t * 3 - 1))
                q[1] = iq[1] + (rest_q[1] - iq[1]) * min(1, max(0, t * 3 - 2))
            else:
                q = iq + (rest_q - iq) * t
            set_q(q)
            r = readout()
            mx_off = max(mx_off, r["off_axis_mm"])
            mn_margin = min(mn_margin, r["margin_mm"])
            q0 = q.copy(); q0[0] = 0.0
            set_q(q0)
            mx_lb = max(mx_lb, lb(readout()))
        paths["staged" if staged else "linear"] = {
            "max_off_axis_mm": round(mx_off, 1), "max_lean_back_mm": round(mx_lb, 1),
            "min_margin_mm": round(mn_margin, 1)}
    bound = max(r_idle["off_axis_mm"], r_rest["off_axis_mm"]) + 0.1
    # per-clip per-frame rectangular margin, from rest0 and from idle
    clip_margins = {}
    for name, cl in clips.items():
        clip_margins[name] = {}
        for start, sq in (("rest0", rest_q), ("idle", iq)):
            mn, mx_off = 1e9, 0.0
            for fr in cl["frames"]:
                q = sq.copy()
                for i in range(5):
                    q[i] += fr[CLIP2BUS[i]] * math.tau / 4096
                set_q(q)
                r = readout()
                mn = min(mn, r["margin_mm"])
                mx_off = max(mx_off, r["off_axis_mm"])
            clip_margins[name][start] = {
                "min_margin_mm": round(mn, 1), "max_off_axis_mm": round(mx_off, 1)}
    res[tag] = {
        "idle_static": r_idle, "idle_static_lean_back_mm": round(lb(r_idle_y0), 1),
        "idle_yaw_deg": round(math.degrees(iq[0]), 2),
        "rest0_static": r_rest, "rest0_lean_back_mm": round(lb(r_rest), 1),
        "fold_gate_bound_mm": round(bound, 1),
        "fold_linear_passes_gate": paths["linear"]["max_off_axis_mm"] <= bound,
        "fold_staged_passes_gate": paths["staged"]["max_off_axis_mm"] <= bound,
        "fold_paths": paths,
        "clip_margins": clip_margins,
    }
print(json.dumps(res, indent=1, ensure_ascii=False))
json.dump(res, open(HERE / "p0_2_gate_probe.json", "w"), indent=1)
