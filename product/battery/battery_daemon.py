"""battery_daemon.py — 市电丢失兜底状态机（P1-d 骨架）。

设计（product/battery/README.md + p0-2-cog-correction.md §7）：

    MAINS_OK → DEBOUNCE(默认2s) → FOLDING(torque ON, 线性→rest0)
             → HOLD(T_hold≈60s, 待测⑩) → RELEASED → SLEEP

    市电恢复：DEBOUNCE 内取消；FOLDING 中恢复则**折完再醒**（绝不在路径中途
    释放/重规划）；HOLD/RELEASED/SLEEP 中恢复直接 wake。

SimBackend 驱动 brain-sim 的 SimLamp（与 demo.py 同一接缝）：rest() 停播放后
逐帧写 lamp.state 线性插值到 REST0_NORM + tick()。释放力矩在 sim 仅记日志
（rest0+500g 配重沉降 +29.4 已证，P0-2 §7；SimLamp 无断力矩 API）。
注意：sim 的 motion_seconds 在 resting=True 时不计折叠占空比；实机计。

HardwareBackend 是 stub，待⑩ + P1 body 适配器：
  - **单总线主 = V2 body**：折叠必须走 body 的 presets/API，不得裸写舵机
    （LeLamp AnimationService 不并行运行，integration-checklist 接缝决策 1）；
  - 市电检测：GPIO/ADC/比较器，采样点在 power-path mux **之前**；
  - release：上游 release_arm 只在折叠后经 strain guard 触发（body.rs:4686 定义，
    唯一调用点 :8089）；T_hold 后的显式释放需要 body API 或 fork 补丁（开放问题）；
  - sleep：SBC suspend + 舵机电源门；wake：torque-on 从 rest0 起身时序。

冒烟（短 hold/fold，快进仿真时间）：
    /tmp/lelamp-sim-venv/bin/python product/battery/battery_daemon.py \
        --sim --fold-s 3 --hold-s 2 --debounce-s 0.5
"""
from __future__ import annotations

import argparse
import enum
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "product" / "brain-sim"))
from lamp import FPS, JOINTS, SimLamp  # noqa: E402

SIM_DIR = ROOT / "hardware" / "simulation"
RECORDINGS = ROOT / "product" / "brain-sim" / "recordings"

# rest0，CSV 归一化（product/calibration/README.md；模型角 pitch−18/elbow+14/wrist−45，
# yaw=roll=0）。JOINTS 序。上机复核 wrist 映射带（⑧）后冻结。
REST0_NORM = {
    "base_yaw": 0.0,
    "base_pitch": -51.0,
    "elbow_pitch": -15.6,
    "wrist_roll": 0.0,
    "wrist_pitch": 50.0,
}


class State(enum.Enum):
    MAINS_OK = "MAINS_OK"
    DEBOUNCE = "DEBOUNCE"
    FOLDING = "FOLDING"
    HOLD = "HOLD"
    RELEASED = "RELEASED"
    SLEEP = "SLEEP"


class SimBackend:
    """MuJoCo 孪生。市电 = 脚本时间线；折叠 = 直接写 state（torque ON 位置保持）。"""

    def __init__(self, fold_s: float, timeline: list[tuple[float, bool]]):
        self.lamp = SimLamp(SIM_DIR, RECORDINGS, transition_s=1.5)
        self.fold_s = fold_s
        self.timeline = timeline  # [(t, ok)] 升序
        self._fold_from: dict[str, float] | None = None

    def read_mains(self, t: float) -> bool:
        ok = True
        for at, value in self.timeline:
            if t >= at:
                ok = value
            else:
                break
        return ok

    def idle_step(self) -> None:
        self.lamp.tick()  # 正常播放（idle 循环 / emote）

    def begin_fold(self) -> None:
        self.lamp.rest()  # 停播放；torque 保持 ON（SimLamp.rest 不断力矩）
        self._fold_from = dict(self.lamp.state)
        self.lamp.solid((255, 140, 0))  # 琥珀：电池折叠中

    def fold_step(self, p: float) -> None:
        """五关节同步线性插值（P0-2 验证路径：b500 全程 margin ≥ +24.7）。"""
        assert self._fold_from is not None
        p = min(1.0, max(0.0, p))
        self.lamp.state = {
            j: self._fold_from[j] + (REST0_NORM[j] - self._fold_from[j]) * p
            for j in JOINTS
        }
        self.lamp.tick()

    def hold_step(self) -> None:
        self.lamp.tick()  # rest0 位置保持，torque ON（6–7 kg·cm 小电流）

    def release(self) -> None:
        # sim 仅记日志：rest0+b500 释放沉降 +29.4 安全（P0-2 §7），无断力矩 API。
        # 实机：此处断力矩，匀光板触桌 + 腕连杆触底座舵机承接（两处接触）。
        pass

    def sleep(self) -> None:
        self.lamp.solid((0, 0, 0))  # 灯灭；实机另需 SBC suspend + 电源门

    def wake(self) -> None:
        self.lamp.wake()  # 恢复播放（上游 idle 自动返回语义）
        self.lamp.solid((255, 180, 90))


class HardwareBackend:
    """Stub — 待⑩（折叠峰值电流/T_hold）+ P1 body 适配器。见模块 docstring。"""

    def __init__(self, *_a, **_k):
        raise NotImplementedError(
            "hardware backend awaits ⑩ + P1 body adapter (single-bus master = V2 body); run --sim"
        )


class Daemon:
    """薄策略：只读市电、走状态机、调后端钩子。所有转移写可审计日志。"""

    def __init__(self, backend, debounce_s: float, hold_s: float, log=print):
        self.backend = backend
        self.debounce_s = debounce_s
        self.hold_s = hold_s
        self.log = log
        self.state = State.MAINS_OK
        self.t = 0.0
        self._since = 0.0
        self._recover_after_fold = False

    def _enter(self, new: State, why: str) -> None:
        self.log(f"[t={self.t:7.2f}s] {self.state.value} -> {new.value} ({why})")
        self.state = new
        self._since = self.t

    def tick(self, dt: float) -> None:
        self.t += dt
        mains = self.backend.read_mains(self.t)
        elapsed = self.t - self._since
        s = self.state
        if s is State.MAINS_OK:
            self.backend.idle_step()
            if not mains:
                self._enter(State.DEBOUNCE, "mains lost")
        elif s is State.DEBOUNCE:
            self.backend.idle_step()
            if mains:
                self._enter(State.MAINS_OK, "mains back within debounce: cancelled")
            elif elapsed >= self.debounce_s:
                self.backend.begin_fold()
                self._enter(State.FOLDING, f"lost {elapsed:.1f}s >= debounce {self.debounce_s:g}s")
        elif s is State.FOLDING:
            if mains:
                self._recover_after_fold = True  # 折完再醒，绝不中途释放
            self.backend.fold_step(elapsed / self.backend.fold_s)
            if elapsed >= self.backend.fold_s:
                if self._recover_after_fold:
                    self._recover_after_fold = False
                    self.backend.wake()
                    self._enter(State.MAINS_OK, "fold completed on battery; mains back: wake")
                else:
                    self._enter(State.HOLD, "rest0 reached, torque ON")
        elif s is State.HOLD:
            self.backend.hold_step()
            if mains:
                self.backend.wake()
                self._enter(State.MAINS_OK, "mains back during hold: wake (torque never released)")
            elif elapsed >= self.hold_s:
                self.backend.release()
                self._enter(State.RELEASED, f"held {elapsed:.0f}s: release (rest0+b500 +29.4)")
        elif s is State.RELEASED:
            self.backend.sleep()
            self._enter(State.SLEEP, "torque released: sleep")
        elif s is State.SLEEP:
            self.backend.hold_step()  # sim 保持位置；实机 SBC 已 suspend
            if mains:
                self.backend.wake()
                self._enter(State.MAINS_OK, "mains back: wake (hardware: torque-on rise, ⑩)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sim", action="store_true", help="MuJoCo 孪生（脚本市电时间线）")
    mode.add_argument("--hardware", action="store_true", help="实机（stub，待⑩）")
    ap.add_argument("--debounce-s", type=float, default=2.0)
    ap.add_argument("--fold-s", type=float, default=6.0, help="线性折叠时长（轻柔）")
    ap.add_argument("--hold-s", type=float, default=60.0, help="T_hold，待测⑩")
    ap.add_argument("--outage-s", type=float, default=3.0, help="sim：此时刻市电丢失")
    ap.add_argument("--restore-after-sleep-s", type=float, default=3.0)
    ap.add_argument("--realtime", action="store_true", help="按 30fps 墙钟走（默认快进）")
    args = ap.parse_args(argv)

    if args.hardware:
        print("hardware backend is a stub (⑩ + P1 body adapter); use --sim", file=sys.stderr)
        return 2

    sleep_at = args.outage_s + args.debounce_s + args.fold_s + args.hold_s + 1.0
    restore_at = sleep_at + args.restore_after_sleep_s
    timeline = [(0.0, True), (args.outage_s, False), (restore_at, True)]
    backend = SimBackend(args.fold_s, timeline)
    daemon = Daemon(backend, args.debounce_s, args.hold_s)
    end = restore_at + 4.0
    dt = 1.0 / FPS
    while daemon.t < end:
        daemon.tick(dt)
        if args.realtime:
            time.sleep(dt)
    print(f"final state: {daemon.state.value}; motion_seconds={backend.lamp.motion_seconds:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
