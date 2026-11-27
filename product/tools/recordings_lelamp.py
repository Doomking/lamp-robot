#!/usr/bin/env python3
"""P1-a: LeLamp recordings -> lampOS V2 格式 / lelamp encoder-counts clips.

LeLamp CSV (brain/recordings, 副本在 product/brain-sim/recordings):
  timestamp,base_yaw.pos,base_pitch.pos,elbow_pitch.pos,wrist_roll.pos,wrist_pitch.pos
  - 绝对时间戳 (~30 fps), 值 = LeRobot RANGE_M100_100 归一化 (-100..100), 不是角度。
V2 hal/recordings CSV:
  timestamp,base_yaw.pos,base_pitch.pos,elbow_pitch.pos,wrist_pitch.pos,wrist_roll.pos
  - 0 起点 @20 fps, 同样归一化; 注意最后两列 wrist 顺序互换。

映射 (P0-② 定稿, product/p0-2-torque-rest.md; 与 brain-sim/lamp.py 一致):
  theta_rad = theta_c + s * k * v_norm
  yaw/roll: theta_c=0, k = s * 0.9 deg/unit
  pitch: theta_c = range 中点 (H1); elbow/wrist: theta_c = 0 (H2); k = s * span/200
  counts = 2048 + theta_deg / 360 * 4096   (homing=0 仿真约定; 实机 homing 逐关节实测后
  需平移 counts 并同步 lean JSON 的 angle_zero_rad —— 待核⑧)

子命令:
  convert   LeLamp CSV -> V2 列序/时基的归一化 CSV (product/recordings-v2/)
  clips     LeLamp CSV -> lelamp counts 的 Rust Clip 片段 (product/body-clips/),
            算法沿用上游 generate_clips.py 的 缩放/收尾归零/限速 管线 (Attribution:
            lampOS/crates/body/tools/generate_clips.py, Apache-2.0)。
            产物是隔离的 fork 工件, 不直接编进上游 data.rs; 实机方向/限幅验证 (待核⑧)
            后再决定替换/并入。
  selftest  映射/重排/重采样/clip 不变量自检 (无需 mujoco)。
"""
from __future__ import annotations
import argparse, csv, json, math, sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REC = ROOT / "product/brain-sim/recordings"
SIM = ROOT / "hardware/simulation"

JOINTS = ["base_yaw", "base_pitch", "elbow_pitch", "wrist_roll", "wrist_pitch"]
SERVO_ID_MAP = {"1": "base_yaw", "2": "base_pitch", "3": "elbow_pitch",
                "4": "wrist_roll", "5": "wrist_pitch"}
SIGN = {"base_yaw": 1, "base_pitch": 1, "elbow_pitch": -1, "wrist_roll": 1, "wrist_pitch": -1}
HYP = {"base_pitch": 0, "elbow_pitch": 1, "wrist_pitch": 1}
# V2 Clip 帧序 (clips.rs): head pitch, head roll, base yaw, shoulder, elbow
CLIP_ORDER = ["wrist_pitch", "wrist_roll", "base_yaw", "base_pitch", "elbow_pitch"]
V2_COLS = ["base_yaw", "base_pitch", "elbow_pitch", "wrist_pitch", "wrist_roll"]
FPS_OUT = 20.0
# 上游 generate_clips.py 的初始管线参数 (lelamp 首版沿用, 实机 ⑧ 后再调):
FASTEST = [900.0, 1300.0, 1000.0, 800.0, 800.0]   # counts/s, CLIP_ORDER 序
FARTHEST = [200, 200, 150, 350, 350]              # counts, CLIP_ORDER 序
SCALE_CAP = 0.8


def ranges_rad() -> dict:
    """从 hardware/simulation/robot.xml 读关节限位 (与 lamp.py 同源, 不依赖 mujoco)。"""
    root = ET.parse(SIM / "robot.xml").getroot()
    out = {}
    for j in root.iter("joint"):
        name = SERVO_ID_MAP.get(j.get("name"))
        if name is None:
            continue
        lo, hi = (float(x) for x in j.get("range").split())
        out[name] = (lo, hi)
    assert set(out) == set(JOINTS), f"robot.xml 关节不全: {out}"
    return out


def coef(rng: dict) -> dict:
    """theta_rad = theta_c + k * v_norm (P0 修正仿射映射)。"""
    c = {}
    for j in JOINTS:
        lo, hi = rng[j]
        s = SIGN[j]
        if j in ("base_yaw", "wrist_roll"):
            c[j] = (0.0, s * math.radians(0.9))
        else:
            tc = (lo + hi) / 2 if HYP[j] == 0 else 0.0
            c[j] = (tc, s * (hi - lo) / 200.0)
    return c


def load_lelamp(path: Path):
    rows = list(csv.DictReader(open(path)))
    t = [float(r["timestamp"]) for r in rows]
    v = {j: [float(r[j + ".pos"]) for r in rows] for j in JOINTS}
    return t, v


def resample(t, v, fps=FPS_OUT):
    """绝对时基 -> 0 起点 @fps, 逐关节线性插值。"""
    t0 = t[0]
    n = int(math.floor((t[-1] - t0) * fps)) + 1
    ts = [k / fps for k in range(n)]
    out = {j: [] for j in JOINTS}
    i = 0
    for tq in ts:
        ta = t0 + tq
        while i < len(t) - 2 and t[i + 1] < ta:
            i += 1
        if ta <= t[0]:
            f = 0.0
        elif ta >= t[-1]:
            f = 1.0
        else:
            f = (ta - t[i]) / (t[i + 1] - t[i])
        for j in JOINTS:
            out[j].append(v[j][i] + (v[j][i + 1] - v[j][i]) * f)
    return ts, out


def to_counts(v, c, rng):
    """归一化 -> lelamp encoder counts (homing=0 约定), 限位内钳制 (与 lamp.py 一致)。"""
    out = {}
    sat = {}
    for j in JOINTS:
        tc, k = c[j]
        lo, hi = rng[j]
        cs = []
        nsat = 0
        for x in v[j]:
            th = tc + k * x
            if th < lo or th > hi:
                nsat += 1
            th = max(lo, min(hi, th))
            cs.append(2048.0 + math.degrees(th) / 360.0 * 4096.0)
        out[j] = cs
        sat[j] = nsat
    return out, sat


def cmd_convert(outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    for p in sorted(REC.glob("*.csv")):
        t, v = load_lelamp(p)
        ts, vr = resample(t, v)
        dst = outdir / p.name
        with open(dst, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["timestamp"] + [j + ".pos" for j in V2_COLS])
            for k, tq in enumerate(ts):
                w.writerow([f"{tq:.4f}"] + [f"{vr[j][k]:.6f}" for j in V2_COLS])
        print(f"convert {p.name}: {len(t)} rows @{1/((t[-1]-t[0])/(len(t)-1)):.1f}fps -> {len(ts)} rows @20fps, 列序 wrist pitch/roll 互换")
    print(f"-> {outdir}")


def clip_from_counts(name, ts, counts):
    """上游管线: 首帧偏移 -> 整体缩放 -> 末半秒归零 -> 限速。返回 (step_ms, frames, scale, slow)。"""
    n = len(ts)
    frames = [[counts[j][k] for j in CLIP_ORDER] for k in range(n)]
    off = [[fr[i] - frames[0][i] for i in range(5)] for fr in frames]
    peak = [max(abs(o[i]) for o in off) for i in range(5)]
    scale = round(min([SCALE_CAP] + [FARTHEST[i] / peak[i] * 0.95 for i in range(5) if peak[i] > 0]), 2)
    off = [[o[i] * scale for i in range(5)] for o in off]
    tail = min(10, n - 1)
    last = off[-1][:]
    for k in range(tail + 1):
        share = k / tail
        for i in range(5):
            off[n - 1 - tail + k][i] -= last[i] * share if k < tail else last[i]
    for i in range(5):
        off[-1][i] = 0.0
    dt = (ts[-1] - ts[0]) / (n - 1)
    speed = [max(abs(off[k + 1][i] - off[k][i]) / dt for k in range(n - 1)) for i in range(5)]
    slow = max(1.0, max(s / f for s, f in zip(speed, FASTEST)))
    step_ms = round(dt * 1000 * slow)
    frames = [[round(o[i]) for i in range(5)] for o in off]
    return step_ms, frames, scale, slow


def cmd_clips(outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    rng = ranges_rad(); c = coef(rng)
    rs = ["// Generated by product/tools/recordings_lelamp.py clips (P1-a, fork 工件).",
          "// 源: product/brain-sim/recordings/*.csv (LeLamp, GPL-3.0 硬件仓库的演示数据);",
          "// 映射: P0-② 修正仿射 (theta_c + s*k*v) -> counts = 2048 + theta_deg/360*4096, homing=0 仿真约定。",
          "// 管线沿用上游 lampOS/crates/body/tools/generate_clips.py (Apache-2.0): 首帧偏移/整体缩放/收尾归零/限速。",
          "// 帧序 = V2 clips.rs: [head pitch, head roll, base yaw, shoulder, elbow]。",
          "// 未编进上游 clips/data.rs: 实机方向/限幅验证 (集成清单 待核⑧) 后再并入。",
          "// Clip 结构见 lampOS/crates/body/src/clips.rs。",
          "use super::{Clip};", ""]
    table = []
    preview = {}
    for p in sorted(REC.glob("*.csv")):
        t, v = load_lelamp(p)
        ts, vr = resample(t, v)
        counts, sat = to_counts(vr, c, rng)
        step_ms, frames, scale, slow = clip_from_counts(p.stem, ts, counts)
        const = p.stem.upper()
        lo = [min(f[i] for f in frames) for i in range(5)]
        hi = [max(f[i] for f in frames) for i in range(5)]
        rs.append(f'/// `{p.name}` (LeLamp), {scale:.2} of its size, {len(frames)} frames {step_ms} ms apart:')
        rs.append(f'/// {len(frames)*step_ms/1000:.1f} s. Offsets from {lo} to {hi}.')
        rs.append(f'pub const {const}: Clip = Clip {{')
        rs.append(f'    name: "{p.stem}",')
        rs.append(f'    step_ms: {step_ms},')
        rs.append('    frames: &[')
        for f in frames:
            rs.append('        [' + ', '.join(str(x) for x in f) + '],')
        rs.append('    ],')
        rs.append('};')
        rs.append('')
        sat_s = ", ".join(f"{j}:{sat[j]}" for j in JOINTS if sat[j])
        table.append(f"| {p.stem} | {len(frames)} | {step_ms} | {len(frames)*step_ms/1000:.1f}s | {scale:.2f} | x{slow:.2f} | {lo} .. {hi} | {sat_s or '-'} |")
        preview[p.stem] = {"step_ms": step_ms, "frames": frames, "scale": scale, "slow": slow,
                           "saturated_frames": sat}
        print(f"clip {p.stem:12} {len(frames):4} frames {step_ms:4} ms scale {scale:.2f} slow x{slow:.2f} sat {sat_s or '-'}")
    rs.append(f'pub const ALL: [&Clip; {len(table)}] = [' + ', '.join('&' + p.stem.upper() for p in sorted(REC.glob('*.csv'))) + '];')
    (outdir / "lelamp_clips.rs").write_text("\n".join(rs) + "\n")
    (outdir / "lelamp_clips.json").write_text(json.dumps(preview, indent=1))
    md = ["# lelamp clips (P1-a 生成, 勿手改)", "",
          "生成: `python3 product/tools/recordings_lelamp.py clips`。homing=0 仿真约定; 实机 ⑧ 后重生成。",
          "饱和帧 = 仿射映射超出关节限位被钳制的帧数 (wrist H2 带 7.2% 为 P0 已知, 待核⑧)。", "",
          "| clip | frames | step_ms | 时长 | scale | slow | offsets lo..hi (counts) | 饱和帧 |",
          "|---|---|---|---|---|---|---|---|"] + table
    (outdir / "clips-table.md").write_text("\n".join(md) + "\n")
    print(f"-> {outdir}/lelamp_clips.rs / .json / clips-table.md")


def cmd_selftest():
    rng = ranges_rad(); c = coef(rng)
    # 1) rest0 (P0-②): CSV (0,-51.0,-15.6,0,+50.0) -> model deg (0,-18,+14,0,-45)
    rest0 = {"base_yaw": 0.0, "base_pitch": -51.0, "elbow_pitch": -15.6, "wrist_roll": 0.0, "wrist_pitch": 50.0}
    want = {"base_yaw": 0.0, "base_pitch": -18.0, "elbow_pitch": 14.0, "wrist_roll": 0.0, "wrist_pitch": -45.0}
    for j in JOINTS:
        th = math.degrees(c[j][0] + c[j][1] * rest0[j])
        assert abs(th - want[j]) < 0.6, f"rest0 {j}: {th:.2f} != {want[j]}"
    print("ok rest0 仿射映射 ->", {j: round(math.degrees(c[j][0] + c[j][1] * rest0[j]), 1) for j in JOINTS})
    # 2) 列序互换 + 时基归一 round-trip (合成 30fps 绝对时基正弦)
    t = [843.0 + k / 30.0 for k in range(120)]
    v = {j: [30.0 * math.sin(2 * math.pi * 0.5 * (k / 30.0) + i) for k in range(120)] for i, j in enumerate(JOINTS)}
    ts, vr = resample(t, v)
    assert abs(ts[0]) < 1e-9 and abs(ts[1] - 0.05) < 1e-9
    err = max(abs(vr[j][k] - (30.0 * math.sin(2 * math.pi * 0.5 * ts[k] + i))) for i, j in enumerate(JOINTS) for k in range(len(ts)))
    assert err < 1.0, f"重采样误差 {err}"
    print(f"ok 重采样 30fps绝对 -> 20fps零点, 正弦最大误差 {err:.3f} (归一化单位)")
    # 3) 全部 recordings: counts 0..4095, clip 首末帧归零, 限速
    for p in sorted(REC.glob("*.csv")):
        t, v = load_lelamp(p)
        ts, vr = resample(t, v)
        counts, sat = to_counts(vr, c, rng)
        for j in JOINTS:
            assert all(0.0 <= x <= 4095.0 for x in counts[j]), f"{p.stem} {j} counts 越界"
        step_ms, frames, scale, slow = clip_from_counts(p.stem, ts, counts)
        assert frames[0] == [0] * 5 or True  # 首帧偏移定义上为 0 (缩放/归零后仍 0)
        assert frames[0] == [0] * 5, f"{p.stem} 首帧非零 {frames[0]}"
        assert frames[-1] == [0] * 5, f"{p.stem} 末帧非零 {frames[-1]}"
        dt = step_ms / 1000.0
        for i in range(5):
            sp = max(abs(frames[k + 1][i] - frames[k][i]) / dt for k in range(len(frames) - 1))
            assert sp <= FASTEST[i] * 1.02 + 1.0, f"{p.stem} joint{i} 超速 {sp}"
        print(f"ok {p.stem:12} counts 界内, 首末归零, 限速 (sat {sum(sat.values())} 帧)")
    print("selftest PASS")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["convert", "clips", "selftest"])
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    if a.cmd == "convert":
        cmd_convert(a.out or ROOT / "product/recordings-v2")
    elif a.cmd == "clips":
        cmd_clips(a.out or ROOT / "product/body-clips")
    else:
        cmd_selftest()


if __name__ == "__main__":
    main()
