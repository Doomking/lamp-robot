#!/usr/bin/env python3
"""P1-a: LeLamp 8x5 矩阵 (40 LED) paint 帧 -> lampOS V2 32 灯环帧.

brain 侧接缝语义不变: lamp.paint([40 x (r,g,b)]) (brain-sim/lamp.py)。
本工具是纯函数映射, 供 product 侧 brain->V2 ring 适配器调用; PIXEL_COUNT=32 不改。

矩阵约定 (LeLamp brain/lamp.py, RGBService led_count=40):
  index = row*8 + col, row 0 在上, col 0 在左 (正面看)。
灯环约定 (V2 ring crate, asleep.rs BOTTOM=PIXEL_COUNT/2 => index 16 在底部):
  index 0 在顶部, 正面看顺时针递增 (假设, 实机点亮校验后可用 --ccw/--start 调整)。

映射 = 角度扇区加权混合:
  矩阵格中心 (x=c-3.5, y=2-r), 角度 psi=atan2(y,x);
  环 LED k 角度 phi = pi/2 - 2*pi*(k-start)/32 (顺时针);
  权重 w = max(0, 1 - angdist(phi,psi)/(1.5*2*pi/32)), 归一化后加权混色。
  性质: solid -> solid (权重归一), 黑 -> 黑, 通道不越界, 确定性;
  角点信息保留在对角环段。实机视觉调参 (扩散板后) 属 P2。

用法:
  python3 ring40to32.py selftest
  python3 ring40to32.py map frame.json        # {"colors": [[r,g,b] x40]} -> {"pixels": [[r,g,b] x32]}
"""
from __future__ import annotations
import argparse, json, math, sys

COLS, ROWS, N_RING = 8, 5, 32
SECTOR = 2 * math.pi / N_RING
OVERLAP = 1.5  # 权重覆盖 1.5 个扇区, 相邻环段平滑过渡


def cell_angles():
    a = []
    for r in range(ROWS):
        for c in range(COLS):
            a.append(math.atan2(2 - r, c - 3.5))
    return a


_ANGLES = cell_angles()


def angdist(a, b):
    d = abs(a - b) % (2 * math.pi)
    return min(d, 2 * math.pi - d)


def matrix_to_ring(colors, start=0, ccw=False):
    """colors: 40 x (r,g,b) 行优先 -> 32 x (r,g,b)。"""
    assert len(colors) == COLS * ROWS, f"需要 40 色,  got {len(colors)}"
    out = []
    for k in range(N_RING):
        idx = (k - start) % N_RING
        phi = math.pi / 2 + (2 * math.pi * idx / N_RING if ccw else -2 * math.pi * idx / N_RING)
        ws = [max(0.0, 1.0 - angdist(phi, psi) / (OVERLAP * SECTOR)) for psi in _ANGLES]
        s = sum(ws)
        if s <= 0:
            out.append((0, 0, 0))
            continue
        px = [sum(w * colors[i][ch] for i, w in enumerate(ws)) / s for ch in range(3)]
        out.append(tuple(int(round(min(255.0, max(0.0, v)))) for v in px))
    return out


def selftest():
    # solid 不变
    for rgb in [(0, 0, 0), (255, 180, 90), (10, 200, 30), (255, 255, 255)]:
        px = matrix_to_ring([rgb] * 40)
        assert all(p == rgb for p in px), f"solid {rgb} 破坏: {px[:3]}"
    print("ok solid -> solid (含全黑/全白)")
    # 通道界内 + 确定性
    import random
    rnd = random.Random(7)
    frame = [(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)) for _ in range(40)]
    a = matrix_to_ring(frame); b = matrix_to_ring(frame)
    assert a == b
    assert all(0 <= v <= 255 for p in a for v in p)
    print("ok 随机帧: 确定性 + 通道界内")
    # 方向性: 矩阵左侧亮 -> 环左半 (index 8..24 附近) 亮于右半
    left = [(255, 255, 255) if (i % 8) < 2 else (0, 0, 0) for i in range(40)]
    px = matrix_to_ring(left)
    lum = [sum(p) for p in px]
    left_side = sum(lum[20:29])   # 左弧 (顺时针: 0=顶, 8=右, 16=底, 24=左)
    right_side = sum(lum[4:13])
    assert left_side > right_side * 2, f"方向性失败 left={left_side} right={right_side}"
    print(f"ok 方向性: 左亮帧 -> 环左弧 {left_side} >> 右弧 {right_side}")
    # 顶部亮 -> index 0 附近最亮
    top = [(255, 255, 255) if (i // 8) == 0 else (0, 0, 0) for i in range(40)]
    px = matrix_to_ring(top)
    lum = [sum(p) for p in px]
    assert max(range(32), key=lambda k: lum[k]) in (0, 1, 31), f"顶部定位失败 {lum}"
    print("ok 顶部行 -> 环 index 0 附近")
    # start/ccw 参数一致性: start 旋转等价于索引平移
    f2 = [(i * 6 % 256, 0, 0) for i in range(40)]
    base = matrix_to_ring(f2)
    shifted = matrix_to_ring(f2, start=4)
    assert all(shifted[k] == base[(k - 4) % 32] for k in range(32))
    print("ok start 参数 = 索引平移")
    print("selftest PASS")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["selftest", "map"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--ccw", action="store_true")
    a = ap.parse_args()
    if a.cmd == "selftest":
        selftest()
    else:
        data = json.load(open(a.file)) if a.file else json.load(sys.stdin)
        px = matrix_to_ring([tuple(c) for c in data["colors"]], start=a.start, ccw=a.ccw)
        json.dump({"pixels": [list(p) for p in px]}, sys.stdout)
        print()


if __name__ == "__main__":
    main()
