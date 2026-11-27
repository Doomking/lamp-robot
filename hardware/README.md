# hardware/ — LeLamp 衍生硬件（GPL-3.0）

来源：humancomputerlab/LeLamp @ `4a0ef2c`（2026-11-26 迁入）。

- `3D/*.3mf` — 打印件：LampBase / LampBase Cover / 4×LampArm / LampHead / LampHead-Diffuser
- `simulation/robot.urdf` + `assets/*.stl` — 仿真模型（brain-sim 与 lamp-lean CoG 重生成用）
- `docs/` — 官方组装/舵机/设置文档。⚠️ 官方计算平台为 **Pi Zero 2 W + ReSpeaker Hat**、供电 **2×5V2A**，本项目均需升级（见下）。

## 计划结构改造（硬件适配 V2，而非改 V2 适配硬件）
1. **头部前脸**：LeLamp 原 = 104×79mm 矩形脸 + 8×5 LED 矩阵（README 写 24 颗，BOM 40 颗，不一致）；V2 = **32-LED 圆环 + 中心摄像头**（"ring of light around the camera is its eye"，眨眼=收环、注视=弧指向人）。需重新设计：环座（**A 方案定稿 2026-11-26**：前脸改 ~120–125mm 圆形，参考上游 pocket 内壁 d86.3/外壁 d115.3，装标准 104mm 环）+ 中心摄像头凸台 + **环形匀光板**（替代原矩形扩散板）。
2. **摄像头**：Pi CSI/libcamera → **UVC USB**（V2 camera crate 只认 V4L2 MJPG，1280×960）。USB 走臂内布线：原 head↔base 为剥皮以太网线 8 芯，有备用线对。
3. **底座**：Pi Zero 2 W → **OrangePi 4 Pro 6GB**（lampOS 上游原生板，Allwinner A733：2×A76@2.0GHz + 6×A55，3TOPS NPU 可选；89×56mm，腔体 160×190×40mm 可容纳，需 mounting 转接板）。供电改 **12V5A 单电源**（舵机/功放 12V + MP2482 降压 5V3A 供板/环/风扇）；OPi 供电为 5V3A Type-C 非 PD，与降压输出正好匹配，且无 Pi5 非 PD 电源下 USB 总限流 600mA 的问题。原 5V 舵机轨欠压欠流（STS3215 需 ≥6V）。
4. **舵机**：保留 5× Feetech STS3215 + Waveshare USB 适配器（ID1-5：base_yaw/base_pitch/elbow_pitch/wrist_roll/wrist_pitch，1M baud，/dev/ttyACM0）。推荐 **12V C018 版（30kg·cm）** 对齐 lampOS。**P0-② 修正**：正确归一化映射下全 recordings 最大肩力矩 11.7 kg·cm（230g 头）/ 10.3（180g 头），C001 7.4V（19.5kg·cm）力矩上也够——但 C001 需额外 12→7.4V 降压 + 2S 电池，且 force-limit 600≈18kg·cm 达其堵转 92%（保护弱），C018 仅 60%。C001 仅作降本备选。旧"最坏 22kg·cm/裕量<1"为错误角度映射产物，作废。
5. **电池**：小容量高倍率电芯，仅保活 + 断电兜底归位，见 `../product/battery/`。
6. **麦克风**：弃 ReSpeaker Hat（I2S 阵列，与 V2 不符）→ 锁定上游拓扑 **杰理双麦 ENC（48kHz mono）+ C-Media USB 适配器**（采集 16kHz，`lampOS/docs/hardware.md`），USB 接入零驱动适配。

## 不变项
臂连杆几何、舵机 ID/接线协议、折叠收纳概念。

## ⚠️ 静息姿态重力稳定（P0-② 仿真已闭环，2026-11-26）
V2 fold-to-rest 折叠后释放全部力矩，依赖静息姿态重力稳定；上游 rest 基于 lamp-4ace 几何，其严格门（头 z<120mm 且 CoG≤22mm）在 LeLamp 几何下 **0 候选**。仿真选定 rest0 =（pitch−18°, elbow+14°, wrist−45°）：头 z 193mm、CoG 56.4mm、裕量 45.2mm。3s 断力矩释放：头下沉 87.7mm 后由匀光板触桌 + 腕连杆触底座舵机承接，沉降后 CoG 裕量 +13.3mm（不倒但非"零电流悬浮"）；idle 直接释放裕量 −49.4mm **必倒** → 释放只允许在折叠之后。
**结论**：正常静息 = 力矩保持（6–7 kg·cm）；fork 不在 rest 调 release_arm。断电兜底 = 电池线性折叠 → 保持 T_hold → 释放 → 休眠。**推荐底座 500g 钢配重**（~64cm³，¥10–20）：rest CoG 36.6mm、沉降后裕量 ≥42mm、线性折叠全程裕量 ≈+33mm。详见 `../product/p0-2-torque-rest.md`；lean/CoG JSON 仍需用本机 URDF + 实测质量经 lamp-lean 重生成。

## 灯环尺寸（P0-③ 实测，2026-11-26，来源 = 上游 CAD，非 LeLamp）

解析 `robots/lamp/hardware/cad/step/*.stp` 的 CIRCLE 实体 + `pcb/head-pwr` Gerber 外形层：

| 特征 | 尺寸 | 依据 |
|---|---|---|
| 上游头部外壳外径 | **~158.7mm**（r79.33） | head-part2 外缘 |
| 前面板（bezel）外径 | ~145.3mm（r72.65） | head-part3 |
| 灯环安装槽 | 环形 pocket：内壁 r43.17（d86.3）/ 外壁 r57.66（d115.3），深约 bezel 后 3.6mm | head-part3 同轴同深圆组 |
| 匀光板（light-cover） | 环形：外径 ~120.3mm / 内径 82.2–87.4mm（阶梯孔） | light-cover.stp |
| 摄像头中心窗口 | ~74mm（r36.99，head-part1） | 相机模组在窗口后方 |
| head-pwr PCB | 56×56mm 方形配电板（**不是灯环板**）→ 灯环为外购件 | Gerber GKO |

**结论**：安装槽与市售标准 **32×WS2812B 5050 灯环（外径 104mm / 内径 90mm，LED 分布圆 ~97mm）** 完全吻合（104<115.3、90>86.3、LED r48.5 落在 43.2–57.7 槽内）。多家供应商同规格（4tronix / electrokit / ledlightinghut），淘宝 ~¥8–20。待核⑥关闭。

**与 LeLamp 包络的冲突 → 已定稿 A（2026-11-26）**：原计划"环外径 ≤79mm 落入 LeLamp 104×79mm 矩形脸"——**32 位灯环无 ≤79mm 标准件**（最小标准 32 位 = 104mm；66mm 标准件是 24 位）。决策记录：
- **A（✅ 选定）**：头部前脸改 ~120–125mm 圆形（仍小于上游 158mm），用标准 104mm 环；头部本来就要重设计（矩形→圆形+中心摄像头），包络/CoG 变化交 brain-sim 复核。
- **B（回退预案）**：定制 ≤79mm 32-LED PCB（LED 分布圆 ~65mm，5050 间距 6.4mm 可行）；JLC 打样+贴片 ~¥50–100/5 片，保住 LeLamp 原包络，但多一轮 PCB 迭代。
- C（否决）：24 位 66mm 环 + 改 PIXEL_COUNT —— 违反 V2 32px 假设（presets/效果），引入本地补丁。

**决策理由**：头部本来就需矩形→圆形重设计，A 的增量 3D 工作量小；标准环 ¥8–20 现货，避免定制 PCB ~¥50–100 + ~1 周 + 改版风险。**P0-② 已完成**（见 `../product/p0-2-torque-rest.md`）：A 方案头部红线 ≤180g（无配重）/ ≤230g（500g 配重），C018 力矩裕量充足（max 11.7 vs 30 kg·cm），**B 回退不再因力矩需要**；头部实际估重 90–120g，余量大。
