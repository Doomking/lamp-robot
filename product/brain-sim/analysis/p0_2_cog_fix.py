#!/usr/bin/env python3
"""P1 correction: P0-2 CoG numbers were read from MuJoCo subtree_com with a
STALE body_subtreemass. MuJoCo (4.0.1) computes body_subtreemass at compile
time; runtime body_mass edits are NOT picked up by mj_forward, so
subtree_com = fresh_moment / stale_total (1.142 kg exported vs 0.9225 kg
realistic) -> every P0 CoG xy was scaled by 0.8078 (optimistic).

Fix: mujoco.mj_setConst(m, d) after mass edits. This script recomputes the
P0 headline cases correctly and measures the cog.rs gate metrics
(off_axis = hypot(cx,cy); lean_back = -cx at yaw zero) for the LeLamp clips,
which are the quantities CLIP_MM / LOOK_MM actually bound -- NOT the
rectangular tip margin P0 quoted.

Run: /tmp/lelamp-sim-venv/bin/python product/brain-sim/analysis/p0_2_cog_fix.py
Out: p0_2_cog_fix.json (next to this script).
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "product/brain-sim"))
sys.path.insert(0, str(ROOT / "product/calibration"))
src = open(HERE / "p0_2_real_mass.py").read().split("sim = L.SimLamp")[0]
g = {"__name__": "rm", "__file__": str(HERE / "p0_2_real_mass.py")}
exec(src, g)
import lamp as L
import mujoco
import numpy as np
import gen_lean_json as G

SIM = str(ROOT / "hardware/simulation")
REC = str(ROOT / "product/brain-sim/recordings")
sim = L.SimLamp(SIM, REC)
m, d = sim.m, sim.d
JOINTS = ["base_yaw", "base_pitch", "elbow_pitch", "wrist_roll", "wrist_pitch"]
adr = {j: sim.jmap[j][1] for j in JOINTS}
mm = g["realistic_link_masses"](False)
head_real = mm["diffuser"][0]
exported = {n: (m.body_mass[m.body(n).id], m.body_ipos[m.body(n).id].copy(),
                m.body_inertia[m.body(n).id].copy()) for n in mm}
B = None  # base world transform, from re-parented xml
import xml.etree.ElementTree as ET
world = ET.fromstring(L._reparent_base((ROOT / "hardware/simulation/robot.xml").read_text())).find("worldbody")
B = L._T(world.find("body[@name='scs215_v5']"))


def apply(head_extra, ballast):
    for n, (M, C) in mm.items():
        b = m.body(n).id
        if n == "diffuser":
            M += head_extra
        m.body_mass[b] = M
        m.body_ipos[b] = C
        m.body_inertia[b] = exported[n][2] * (M / exported[n][0])
    if ballast:
        b = m.body("scs215_v5").id
        M0, C0 = mm["scs215_v5"]
        pb = L._qrot(L._qinv(B[1]), [G.BALLAST_POS[k] - B[0][k] for k in range(3)])
        m.body_mass[b] = M0 + G.BALLAST_KG
        m.body_ipos[b] = [(M0 * C0[k] + G.BALLAST_KG * pb[k]) / (M0 + G.BALLAST_KG) for k in range(3)]
    mujoco.mj_setConst(m, d)  # THE FIX: refresh compile-time derived masses


def setdeg(p, e, w, yaw=0.0, roll=0.0):
    d.qpos[:] = 0
    d.qpos[adr["base_yaw"]] = math.radians(yaw)
    d.qpos[adr["base_pitch"]] = math.radians(p)
    d.qpos[adr["elbow_pitch"]] = math.radians(e)
    d.qpos[adr["wrist_roll"]] = math.radians(roll)
    d.qpos[adr["wrist_pitch"]] = math.radians(w)
    d.qvel[:] = 0


def setnorm(f):
    d.qpos[:] = 0
    for j in JOINTS:
        tc, k = sim.jmap[j][3]
        lo, hi = sim.jmap[j][2]
        v = f.get(j, 0.0)
        if j in ("base_yaw", "wrist_roll"):
            v = max(-100.0, min(100.0, v))
        d.qpos[adr[j]] = max(lo, min(hi, tc + k * v))
    d.qvel[:] = 0


def readout():
    mujoco.mj_forward(m, d)
    c = d.subtree_com[m.body("scs215_v5").id]
    cx, cy = float(c[0]) * 1000, float(c[1]) * 1000
    hz = float(d.xipos[m.body("diffuser").id][2]) * 1000
    return {"off_axis_mm": round(math.hypot(cx, cy), 1),
            "margin_mm": round(min(95 - abs(cx), 80 - abs(cy)), 1),
            "cog_xy_mm": [round(cx, 1), round(cy, 1)],
            "head_z_mm": round(hz, 1)}


def release(setter, secs=3.0):
    setter()
    mujoco.mj_forward(m, d)
    h0 = float(d.xipos[m.body("diffuser").id][2]) * 1000
    fr = m.actuator_forcerange.copy()
    m.actuator_forcerange[:] = 0
    for _ in range(int(secs / m.opt.timestep)):
        mujoco.mj_step(m, d)
    m.actuator_forcerange[:] = fr
    r = readout()
    r["head_drop_mm"] = round(h0 - r["head_z_mm"], 1)
    return r


def fold(a, b, staged):
    worst, worst_off = 1e9, 0.0
    N = 48
    for s in range(N + 1):
        t = s / N
        if staged:
            q = a.copy()
            q[4] = a[4] + (b[4] - a[4]) * min(1, t * 3)
            q[2] = a[2] + (b[2] - a[2]) * min(1, max(0, t * 3 - 1))
            q[1] = a[1] + (b[1] - a[1]) * min(1, max(0, t * 3 - 2))
        else:
            q = a + (b - a) * t
        d.qpos[:] = 0
        for k, j in enumerate(JOINTS):
            d.qpos[adr[j]] = q[k]
        d.qvel[:] = 0
        r = readout()
        worst = min(worst, r["margin_mm"])
        worst_off = max(worst_off, r["off_axis_mm"])
    return {"min_margin_mm": round(worst, 1), "max_off_axis_mm": round(worst_off, 1)}


def qarr(p, e, w):
    return np.array([0.0, math.radians(p), math.radians(e), 0.0, math.radians(w)])


out = {"fix": "mj_setConst after runtime mass edits; P0 CoG xy scaled by 0.9225/1.142=0.8078",
       "total_mass_kg": None, "cases": {}}
idle_q = np.zeros(5)
setnorm(sim.rec["idle"][1682])
idle_q = d.qpos[[adr[j] for j in JOINTS]].copy()
rest_q = qarr(-18, 14, -45)
zero_q = np.zeros(5)

for tag, ballast in (("nb", False), ("b500", True)):
    apply(0.180 - head_real, ballast)
    out["total_mass_kg"] = round(float(m.body_mass.sum()), 4)
    c = {}
    setdeg(-18, 14, -45)
    c["rest0_static"] = readout()
    c["rest0_release"] = release(lambda: setdeg(-18, 14, -45))
    c["idle_release"] = release(lambda: setnorm(sim.rec["idle"][1682]))
    c["fold_idle_linear"] = fold(idle_q, rest_q, False)
    c["fold_idle_staged"] = fold(idle_q, rest_q, True)
    c["fold_zero_linear"] = fold(zero_q, rest_q, False)
    out["cases"][tag] = c

# head budget sweep at rest0, no ballast
apply(0.180 - head_real, False)
sweep = []
for head_g in range(140, 241, 10):
    apply(head_g / 1000 - head_real, False)
    setdeg(-18, 14, -45)
    r = readout()
    sweep.append({"head_g": head_g, "margin_mm": r["margin_mm"], "off_axis_mm": r["off_axis_mm"]})
out["head_sweep_nb"] = sweep

# clip gate metrics via the generated lean JSONs (end-to-end check of P1-a/c)
clips = json.load(open(ROOT / "product/body-clips/lelamp_clips.json"))
geo_nb = json.load(open(ROOT / "product/calibration/lean-lelamp.json"))
geo_b = json.load(open(ROOT / "product/calibration/lean-lelamp-ballast.json"))
CLIP2BUS = [2, 3, 4, 1, 0]  # [hp,hr,yaw,shoulder,elbow] -> bus [yaw,shoulder,elbow,roll,pitch]
BUSN = ["base_yaw", "shoulder", "elbow", "head_roll", "head_pitch"]


def counts_of(q):
    return [2048 + float(v) / math.tau * 4096 for v in q]


def gate_metrics(geo, start_counts, frames):
    mx_off, mx_lb = 0.0, 0.0
    for fr in frames:
        cnt = [start_counts[i] + fr[CLIP2BUS[i]] for i in range(5)]
        rad = {BUSN[i]: (cnt[i] - 2048) * math.tau / 4096 for i in range(5)}
        c = G.lean_fk(geo, rad)
        mx_off = max(mx_off, math.hypot(c[0], c[1]) * 1000)
        rad0 = dict(rad)
        rad0["base_yaw"] = 0.0  # yaw_zero = 0 (homing=0 convention)
        c0 = G.lean_fk(geo, rad0)
        mx_lb = max(mx_lb, -c0[0] * 1000)
    return round(mx_off, 1), round(mx_lb, 1)


rest_counts = counts_of(rest_q)
idle_counts = counts_of(idle_q)
gates = {}
for name, cl in clips.items():
    gates[name] = {}
    for start, sc in (("rest0", rest_counts), ("idle", idle_counts)):
        for tag, geo in (("nb", geo_nb), ("b500", geo_b)):
            off, lb = gate_metrics(geo, sc, cl["frames"])
            gates[name]["%s_%s" % (start, tag)] = {"max_off_axis_mm": off, "max_lean_back_mm": lb}
out["clip_gates"] = gates

json.dump(out, open(HERE / "p0_2_cog_fix.json", "w"), indent=1, ensure_ascii=False)
print("total mass:", out["total_mass_kg"])
for tag in ("nb", "b500"):
    print("==", tag, "==")
    for k, v in out["cases"][tag].items():
        print(" ", k, v)
print("head sweep nb:", [(s["head_g"], s["margin_mm"]) for s in sweep])
print("clip gates:")
for name, gg in gates.items():
    print(" ", name, {k: v["max_off_axis_mm"] for k, v in gg.items()})
