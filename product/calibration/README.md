# calibration — 逐灯实测配置（必需，非可选）

V2 body **无实测配置拒绝启动**：
- `/etc/lampOS/body/lamp.env` — BODY_POSES（逐关节实测姿态限位）；
- `zone.env` — 逐灯区域配置；
- lean/CoG JSON — 上游 `lampOS/deploy/lamp-4ace/lean-first-software.json` 基于 V1 URDF 且**质量为估算值（1.49kg，"not a measurement"）**，不适用本机。

## 流程
`hardware/simulation/robot.urdf`（结构改造后）→ lamp-lean 重生成 → `lamp-body-measure.service` 实测 → 填 lamp.env / zone.env。

## 参考
- `lampOS/deploy/units/README.md` — 部分部署原则："Leave out what the lamp does not run. A part that is not there is not waited for."
- 逐灯模板占位符：@NAME@ / @SERVO_DEVICE@ / @CAMERA_DEVICE@ / @FAST_CPUS@（部署时逐灯填；A733 大核 = 2×A76）。

## 关节映射（P0-② 定稿，2026-11-26）
LeLamp recordings CSV = LeRobot RANGE_M100_100 归一化（−100..100），**非角度制**
（lelamp_runtime `config_lelamp_follower.py: use_degrees=False`）。
仿射映射 θ = θ_c + s·k·v（模型角度）：yaw/roll θ = s·0.9°·v（±100 → ±90°）；
pitch/elbow/wrist k = span/200，θ_c = 范围中点（H1）或模型零位（H2）。

| 关节 | s | 假设 | 模型范围(°) | θ_c(°) |
|---|---|---|---|---|
| base_yaw | +1 | — | [−287.7, 72.3] | 0 |
| base_pitch | +1 | H1 | [−62.1, 117.9] | 27.9 |
| elbow_pitch | −1 | H2 | [−161.6, 18.4] | 0 |
| wrist_roll | +1 | — | [−217, 143] | 0 |
| wrist_pitch | −1 | H2 | [−48.9, 131.1] | 0 |

qpos0 = CAD 零位已视觉验证（idle 帧 1682 → 潜望镜 idle，头部 z≈499mm）。
**wrist_pitch 存在 ±41° 备选带**（H1 vs H2 / 符号）：H2 下 CSV 极值（v>54.3）有 ~14°
范围饱和（7.2% 帧），H1 备选无饱和；仿真力矩影响 <1 kg·cm、CoG <8%，上机必须实测裁决（⑧）。

## rest0（P0-② 仿真选定）
模型角度 (pitch, elbow, wrist) = (−18°, +14°, −45°)，yaw=roll=0。
CSV 归一化等价 ≈ **(0, −51.0, −15.6, 0, +50.0)**。
头部 z 193mm（xpos）；CoG off_axis **69.8mm（无配重）/ 45.3mm（500g 配重）**，
margin +33.4 / +55.0（2026-11-27 修正，见 ../p0-2-cog-correction.md；旧 56.4/45.2 作废）；
重力保持 6.11/6.56/0.71 kg·cm。
→ 填入 BODY_POSES rest；正常静息力矩保持，上游只在 strain 坐下后释放
（500g 配重下 rest0 释放安全 +29.4，见 ../p0-2-cog-correction.md §7）。

## lean JSON（P1-c 生成，2026-11-27）

`gen_lean_json.py` 从 `hardware/simulation/robot.xml`（内存重父级，不改上游文件）
+ P0 质量模型生成 lamp-lean 几何：

- `lean-lelamp.json`（0.9225kg 无配重）/ `lean-lelamp-ballast.json`（1.4225kg，500g @ world z5mm，位置待核⑨）；
- `lean-verify.md`：lean-FK vs MuJoCo，203 poses × 2 变体，max 误差 0.0017mm PASS；
- 部署用 ballast 版，经 `LAMP_LEAN_JSON` 覆盖 cog.rs 内嵌 JSON（P1-b 补丁）；
- homing=0 / angle_zero=0 为仿真约定，上机⑧后重测平移。

重生成：`/tmp/lelamp-sim-venv/bin/python product/calibration/gen_lean_json.py`（原地覆盖）。

## 上机验证流程（wrist band ⑧）
1. 空载（头部拆下或支撑）逐关节单动：±100 归一化指令 → 观察实际方向与角度；
2. 对照上表确认 s 与 θ_c；wrist_pitch 重点核对 rest0 指令（CSV +50）是否低头 45°；
3. 确认后更新 lamp.env BODY_POSES + 本表；再跑 idle + 单 emote 全幅验证。
