# battery — 保活 + 断电兜底归位（净新增）

设计意图（2026-11-26 确认）：台灯市电为主，电池**不做无线化**，只做两件事：
1. **保活**：短时断电维持逻辑（OrangePi 4 Pro + 舵机逻辑电），避免硬关机；
2. **兜底归位**：持续断电 → **线性**折叠到 rest0 → 力矩保持 T_hold（~60s，待测⑩）→ 释放力矩（500g 配重下沉降不倒，P0-② 已仿真）→ 休眠。

## 能量预算（估算，待核）
一次轻柔折叠 ~0.03–0.1Wh + 逻辑窗口，远小于全无线方案（30–44Wh）。约束是**峰值电流（C-rate）而非能量** → 小容量高倍率电芯（如 18650 30Q）或超级电容（若仅折叠、不长保活）。~50–100g，底座腔体基本不动。

电压耦合舵机版本：2S=7.4V（C001）/ 3S=12V（C018，推荐）。

仿真依据：`../p0-2-torque-rest.md`（P0-②，2026-11-26）+ `../p0-2-cog-correction.md`（2026-11-27 修正，**权威数值**）。

## 净新增组件（V2 完全没有）
- **市电丢失检测**：ADC/GPIO/比较器，采样点在 power-path mux **之前**；
- **power-path mux**：市电优先、电池兜底；
- **薄策略守护进程**：持续丢失（去抖 2s）→ torque ON **线性**折叠到 rest0 → 保持 T_hold（~60s，待测⑩）→ release → 休眠。骨架已交（P1-d，`battery_daemon.py`，sim 冒烟全绿）。折叠门 = P1-b **绝对门** env `LAMP_FOLD_BOUND_MM=78`（b500 linear 峰值 74.9 过门，margin +24.7）；旧 fold-order/relative-gate 补丁与 `LAMP_REST_RELEASE` **取消**——上游 release_arm 只在折叠完成后触发（唯一调用点 body.rs:8089），rest 本就不释放；rest0+b500 释放裕量 +29.4 安全、idle 释放 −14.4 仍倒（correction §6–7）。**正常静息不释放力矩**（V2 rest 零电流假设对 LeLamp 几何不成立）。

## 守护进程骨架（P1-d，battery_daemon.py）

状态机：`MAINS_OK → DEBOUNCE → FOLDING → HOLD → RELEASED → SLEEP`。市电恢复语义：去抖内取消；折叠中恢复**折完再醒**（绝不在路径中途释放/重规划）；HOLD/RELEASED/SLEEP 中恢复直接 wake。SimBackend 驱动 brain-sim SimLamp（rest() 停播放后逐帧写 lamp.state 线性插值到 REST0_NORM + tick）；释放/sleep 在 sim 仅记日志。冒烟全绿（全链路 + 去抖取消/折中恢复/hold 恢复/rest0 收敛 4 分支断言）：

```sh
/tmp/lelamp-sim-venv/bin/python product/battery/battery_daemon.py --sim --fold-s 3 --hold-s 2 --debounce-s 0.5
```

HardwareBackend 为 stub（待⑩ + P1 body 适配器）：折叠必须走 V2 body presets/API（**单总线主**，不得裸写舵机）；市电检测采样在 power-path mux 之前；T_hold 后显式 release 需 body API 或 fork 补丁（开放问题）；sleep = SBC suspend + 舵机电源门，wake = torque-on 从 rest0 起身。

## TODO
实测折叠能耗/峰值电流（⑩）；选电芯 + BMS；配重实际质量/位置复核（⑨）；硬件后端接 body API + 市电检测 + release/sleep/wake 时序。静息稳定性仿真已闭环（P0-②，见 ../p0-2-torque-rest.md，权威数值 ../p0-2-cog-correction.md）；上机复核 wrist 映射带（⑧）后冻结 rest0。
