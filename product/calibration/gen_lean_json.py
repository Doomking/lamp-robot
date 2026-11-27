#!/usr/bin/env python3
"""P1-c: generate lamp-lean geometry JSONs for the LeLamp chain (fork artifact).

Run with the sim venv (needs mujoco + numpy for cross-validation):
    /tmp/lelamp-sim-venv/bin/python product/calibration/gen_lean_json.py

Sources (code = truth):
  * hardware/simulation/robot.xml  -- LeLamp CAD export, re-parented IN MEMORY
    by product/brain-sim/lamp.py::_reparent_base (world -> scs215_v5 base welded
    -> yaw -> pitch -> elbow -> roll -> wrist_pitch). No upstream file edited.
  * product/brain-sim/analysis/p0_2_real_mass.py::realistic_link_masses(False)
    -- P0-2 mass convention: prints 0.5 g/cm3, other plastic 1.09, servo 55 g,
    PCB 1.85, horn 2.7; head (diffuser) topped up to 180 g total (NEW-A).
    NOTE: base = printed 231.5 g under this convention, NOT the CAD-exported
    417.35 g; P0-2 totals (0.923 kg) and ballast math use the printed value.

Conventions (documented, stand_in -- never qualifies actuation):
  * homing = 0 sim convention: encoder 2048 == MuJoCo qpos 0 == CAD zero pose,
    so angle_zero_rad = 0 for all five links. Real hardware (checklist item 8)
    must re-measure homing and shift angle_zero accordingly.
  * Joint axis signs come from CAD; positive-encoder direction on the real
    bus is unverified until item 8 -> measurement = "stand_in".
  * Ballast variant: +500 g steel at world (0, 0, 5 mm) -- position estimated,
    pending checklist item 9. Horizontal CoG math matches P0-2 (ballast at
    base centre x=y=0).

Outputs (next to this script):
  lean-lelamp.json          no ballast   (rest0 off-axis ~56.4 mm, margin ~45.2)
  lean-lelamp-ballast.json  +500 g       (rest0 off-axis ~36.6 mm)
  lean-verify.md            validation report (lean-FK vs MuJoCo subtree_com)
"""
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]  # product/calibration -> repo root
sys.path.insert(0, str(ROOT / "product/brain-sim"))
import lamp as L  # mujoco import inside lamp.py is lazy; safe without it

SIM = ROOT / "hardware/simulation"
REC = ROOT / "product/brain-sim/recordings"

# physical serial order of the LeLamp chain == bus order [0,1,2,3,4]
CHAIN = [  # (body name, lean joint name, CSV/qpos name)
    ("lamparm__wrist_head",   "base_yaw",   "base_yaw"),
    ("lamparm__base_elbow",   "shoulder",   "base_pitch"),
    ("lamparm__elbow_wrist",  "elbow",      "elbow_pitch"),
    ("lamparm__wrist_head_2", "head_roll",  "wrist_roll"),
    ("diffuser",              "head_pitch", "wrist_pitch"),
]
FOOTPRINT = [[0.095, -0.08], [0.095, 0.08], [-0.095, 0.08], [-0.095, -0.08]]
HEAD_TOTAL_KG = 0.180          # NEW-A head budget (P0-2)
BALLAST_KG = 0.5
BALLAST_POS = [0.0, 0.0, 0.005]  # world, metres; est. pending item 9
LABEL = ("lamp-robot P1-c stand-in: LeLamp CAD chain (hardware/simulation, "
         "re-parented) + P0-2 masses (prints 0.5 g/cm3, head 180 g); homing=0 "
         "sim convention; axis signs/ballast pose unverified (checklist 8/9)")
LABEL_B = ("lamp-robot P1-c stand-in: LeLamp CAD + P0-2 masses (head 180 g) "
           "+ 500 g steel ballast at (0,0,5 mm) est.; homing=0 sim convention; "
           "axis signs/ballast pose unverified (checklist 8/9)")


def quat_to_rpy(q):
    w, x, y, z = q
    sinp = 2 * (w * y - z * x)
    # gimbal lock (pitch = +/-90 deg, exact for LeLamp yaw & wrist CAD quats):
    # only roll-/+yaw is observable; pick yaw=0, roll=2*atan2(x, w) (half-angle!).
    # threshold 1e-6: XML quats carry 6-9 sig digits, so exact CAD locks land
    # at |sinp| = 1 - O(1e-8); the standard formulas lose roll/yaw there.
    if sinp >= 1.0 - 1e-6:
        return [2 * math.atan2(x, w), math.pi / 2, 0.0]
    if sinp <= -1.0 + 1e-6:
        return [2 * math.atan2(x, w), -math.pi / 2, 0.0]
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    pitch = math.asin(max(-1.0, min(1.0, sinp)))
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return [roll, pitch, yaw]


def rpy_to_quat(rpy):
    r, p, y = rpy
    cr, sr = math.cos(r / 2), math.sin(r / 2)
    cp, sp = math.cos(p / 2), math.sin(p / 2)
    cy, sy = math.cos(y / 2), math.sin(y / 2)
    qx, qy, qz = (cr, sr, 0, 0), (cp, 0, sp, 0), (cy, 0, 0, sy)
    return L._qmul(L._qmul(qz, qy), qx)  # Rz * Ry * Rx, as lean model.rs


def axis_quat(axis, angle):
    s = math.sin(angle / 2)
    return (math.cos(angle / 2), axis[0] * s, axis[1] * s, axis[2] * s)


def unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def load_masses():
    src = (ROOT / "product/brain-sim/analysis/p0_2_real_mass.py").read_text()
    src = src.split("sim = L.SimLamp")[0]
    g = {"__name__": "rm", "__file__": str(ROOT / "product/brain-sim/analysis/p0_2_real_mass.py")}
    exec(src, g)
    return g["realistic_link_masses"](False)


def build_geometry(ballast):
    xml = L._reparent_base((SIM / "robot.xml").read_text())
    world = ET.fromstring(xml).find("worldbody")
    base = world.find("body[@name='scs215_v5']")
    bodies, cur = [], base
    for name, _, _ in CHAIN:
        cur = cur.find("body[@name='%s']" % name)
        assert cur is not None, name
        bodies.append(cur)
    B = L._T(base)
    mm = load_masses()
    head_extra = HEAD_TOTAL_KG - mm["diffuser"][0]

    links = []
    for i, ((name, joint, _), body) in enumerate(zip(CHAIN, bodies)):
        # first joint origin is world-frame: B ∘ yaw_local; rest are local
        T = L._compose(B, L._T(body)) if i == 0 else L._T(body)
        j = body.find("joint")
        assert j is not None and j.get("pos") is None, "joint anchor != body origin"
        M, C = mm[name]
        if name == "diffuser":
            M += head_extra
        links.append({
            "joint": joint,
            "origin_m": [round(v, 9) for v in T[0]],
            "rpy_rad": [round(v, 9) for v in quat_to_rpy(T[1])],
            "axis": [round(v, 9) for v in unit([float(x) for x in j.get("axis", "0 0 1").split()])],
            "angle_zero_rad": 0.0,
            "mass_kg": round(M, 6),
            "com_m": [round(v, 9) for v in C],
        })

    M0, C0 = mm["scs215_v5"]
    base_com = [B[0][k] + L._qrot(B[1], C0)[k] for k in range(3)]
    base_mass = M0
    if ballast:
        base_com = [(M0 * base_com[k] + BALLAST_KG * BALLAST_POS[k]) / (M0 + BALLAST_KG)
                    for k in range(3)]
        base_mass = M0 + BALLAST_KG
    geo = {
        "schema_version": 1,
        "measurement": "stand_in",
        "label": LABEL_B if ballast else LABEL,
        "footprint_m": FOOTPRINT,
        "margin_m": 0.0,
        "base": {"mass_kg": round(base_mass, 6), "com_m": [round(v, 9) for v in base_com]},
        "links": links,
    }
    return geo, B, mm, head_extra


def lean_fk(geo, angles_bus):
    """Replicates lamp-lean model.rs::check_pose arithmetic (numpy-free)."""
    rot, origin = (1.0, 0.0, 0.0, 0.0), [0.0, 0.0, 0.0]
    bm = geo["base"]["mass_kg"]
    moment = [bm * c for c in geo["base"]["com_m"]]
    total = bm
    for lk in geo["links"]:
        o = L._qrot(rot, lk["origin_m"])
        origin = [origin[k] + o[k] for k in range(3)]
        rot = L._qmul(L._qmul(rot, rpy_to_quat(lk["rpy_rad"])),
                      axis_quat(lk["axis"], angles_bus[lk["joint"]] - lk["angle_zero_rad"]))
        c = L._qrot(rot, lk["com_m"])
        m = lk["mass_kg"]
        total += m
        moment = [moment[k] + m * (origin[k] + c[k]) for k in range(3)]
    return [v / total for v in moment]


def verify(geo, geo_b, B, mm, head_extra):
    import mujoco
    import numpy as np
    sim = L.SimLamp(str(SIM), str(REC))
    m, d = sim.m, sim.d
    adr = {csv: sim.jmap[csv][1] for _, _, csv in CHAIN}
    rng = {csv: sim.jmap[csv][2] for _, _, csv in CHAIN}
    exported = {n: (m.body_mass[m.body(n).id], m.body_ipos[m.body(n).id].copy(),
                    m.body_inertia[m.body(n).id].copy())
                for n in ["scs215_v5"] + [c[0] for c in CHAIN]}

    def apply(extra_ballast):
        for n, (M, C) in mm.items():
            b = m.body(n).id
            if n == "diffuser":
                M += head_extra
            m.body_mass[b] = M
            m.body_ipos[b] = C
            m.body_inertia[b] = exported[n][2] * (M / exported[n][0])
        if extra_ballast:
            b = m.body("scs215_v5").id
            M0, C0 = mm["scs215_v5"]
            pb_local = L._qrot(L._qinv(B[1]), [BALLAST_POS[k] - B[0][k] for k in range(3)])
            m.body_mass[b] = M0 + BALLAST_KG
            m.body_ipos[b] = [(M0 * C0[k] + BALLAST_KG * pb_local[k]) / (M0 + BALLAST_KG)
                              for k in range(3)]
        # CRITICAL: body_subtreemass is compile-time constant; without mj_setConst
        # subtree_com = fresh_moment / STALE_total (P0 CoG bug, see correction doc).
        mujoco.mj_setConst(m, d)

    base_id = m.body("scs215_v5").id
    body_ids = [base_id] + [m.body(c[0]).id for c in CHAIN]
    name2joint = {csv: joint for _, joint, csv in CHAIN}

    def mj_com():
        c = d.subtree_com[base_id].copy()
        manual = sum(m.body_mass[b] * d.xipos[b] for b in body_ids) / sum(m.body_mass[b] for b in body_ids)
        assert float(np.max(np.abs(c - manual))) < 1e-9, "subtree_com versus manual sum"
        return c

    def set_q(q):
        d.qpos[:] = 0
        for _, _, csv in CHAIN:
            d.qpos[adr[csv]] = q[csv]
        d.qvel[:] = 0
        mujoco.mj_forward(m, d)

    poses = [("qpos0", {csv: 0.0 for _, _, csv in CHAIN}),
             ("rest0", {"base_yaw": 0.0, "base_pitch": math.radians(-18),
                        "elbow_pitch": math.radians(14), "wrist_roll": 0.0,
                        "wrist_pitch": math.radians(-45)})]
    f1682 = sim.rec["idle"][1682]
    idle_q = {}
    for _, _, csv in CHAIN:
        tc, k = sim.jmap[csv][3]
        lo, hi = rng[csv]
        v = f1682.get(csv, 0.0)
        if csv in ("base_yaw", "wrist_roll"):
            v = max(-100.0, min(100.0, v))
        idle_q[csv] = max(lo, min(hi, tc + k * v))
    poses.append(("idle_f1682", idle_q))
    rs = np.random.RandomState(42)
    for i in range(200):
        poses.append(("rand%03d" % i, {csv: float(rs.uniform(rng[csv][0], rng[csv][1]))
                                       for _, _, csv in CHAIN}))

    rows, worst = [], 0.0
    for tag, ballast in (("no-ballast", False), ("ballast500", True)):
        apply(ballast)
        g = geo_b if ballast else geo
        err_max = 0.0
        for name, q in poses:
            set_q(q)
            mj = mj_com()
            fk = lean_fk(g, {name2joint[csv]: q[csv] for _, _, csv in CHAIN})
            err = float(np.max(np.abs(mj - np.array(fk)))) * 1000
            err_max = max(err_max, err)
            if name in ("qpos0", "rest0", "idle_f1682"):
                cx, cy = mj[0] * 1000, mj[1] * 1000
                rows.append((tag, name, round(math.hypot(cx, cy), 1),
                             round(min(95 - abs(cx), 80 - abs(cy)), 1), round(err, 4)))
        worst = max(worst, err_max)
        rows.append((tag, "ALL %d poses" % len(poses), None, None, round(err_max, 4)))

    ok = worst < 0.5
    rest_nb = next(r for r in rows if r[0] == "no-ballast" and r[1] == "rest0")
    rest_b = next(r for r in rows if r[0] == "ballast500" and r[1] == "rest0")
    # P0 reported 56.4/45.2/36.6 from subtree_com with STALE body_subtreemass
    # (scaled by 0.9225/1.142). True values are larger; sanity gates only.
    targets_ok = (rest_nb[3] > 0 and rest_b[3] > rest_nb[3] and rest_nb[2] < 95)
    total = geo["base"]["mass_kg"] + sum(l["mass_kg"] for l in geo["links"])
    lines = [
        "# lean-lelamp geometry validation (P1-c)", "",
        "Generated by `product/calibration/gen_lean_json.py` (sim venv). Do not hand-edit.", "",
        "- Chain: re-parented LeLamp CAD, physical order yaw/shoulder/elbow/head_roll/head_pitch (= bus order).",
        "- Masses: P0-2 realistic convention; base = printed %.1f g (CAD export was 417.35 g); head 180 g; total %.4f kg." % (mm["scs215_v5"][0] * 1000, total),
        "- homing=0 sim convention (angle_zero=0); axis signs + ballast pose pending checklist 8/9 -> stand_in.", "",
        "| variant | pose | off-axis mm | tip margin mm | max FK err mm |",
        "|---|---|---|---|---|",
    ]
    for tag, name, off, mar, err in rows:
        lines.append("| %s | %s | %s | %s | %s |" % (tag, name, off if off is not None else "-",
                                                     mar if mar is not None else "-", err))
    lines += ["",
              "NOTE: P0-2 reported rest0 56.4/45.2 (no ballast) / 36.6 (500 g) from a stale",
              "body_subtreemass (MuJoCo does not refresh it on runtime mass edits; fixed here",
              "via mj_setConst). True off-axis is ~1.238x the P0 figure. See P0 CoG correction.",
              "FK gate: max |lean-FK - MuJoCo subtree_com| < 0.5 mm over %d poses x 2 variants." % len(poses), "",
              "**%s** (worst FK err %.4f mm; rest0 sanity %s)" % (
                  "PASS" if ok and targets_ok else "FAIL", worst,
                  "ok" if targets_ok else "BAD"), ""]
    (HERE / "lean-verify.md").write_text("\n".join(lines))
    print("\n".join(lines[-4:]))
    return ok and targets_ok


def main():
    geo, B, mm, he = build_geometry(False)
    geo_b, _, _, _ = build_geometry(True)
    assert len(LABEL) <= 256 and len(LABEL_B) <= 256
    assert geo["base"]["com_m"][2] >= 0, "base COM below support plane"
    for g, name in ((geo, "lean-lelamp.json"), (geo_b, "lean-lelamp-ballast.json")):
        (HERE / name).write_text(json.dumps(g, indent=1) + "\n")
        print("wrote", HERE / name)
    ok = verify(geo, geo_b, B, mm, he)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
