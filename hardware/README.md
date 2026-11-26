# hardware/ — LeLamp 衍生硬件（GPL-3.0）

来源：humancomputerlab/LeLamp @ `4a0ef2c`（2026-11-26 迁入）。

- `3D/*.3mf` — 打印件：LampBase / LampBase Cover / 4×LampArm / LampHead / LampHead-Diffuser
- `simulation/robot.urdf` + `assets/*.stl` — 仿真模型（brain-sim 与 lamp-lean CoG 重生成用）
- `docs/` — 官方组装/舵机/设置文档。⚠️ 官方计算平台为 **Pi Zero 2 W + ReSpeaker Hat**、供电 **2×5V2A**，本项目均需升级（见下）。

## 计划结构改造（硬件适配 V2，而非改 V2 适配硬件）
1. **头部前脸**：LeLamp 原 = 104×79mm 矩形脸 + 8×5 LED 矩阵（README 写 24 颗，BOM 40 颗，不一致）；V2 = **32-LED 圆环 + 中心摄像头**（"ring of light around the camera is its eye"，眨眼=收环、注视=弧指向人）。需重新设计：环座（环外径 ≤79mm 以落入现有包络）+ 中心摄像头凸台 + **环形匀光板**（替代原矩形扩散板）。
2. **摄像头**：Pi CSI/libcamera → **UVC USB**（V2 camera crate 只认 V4L2 MJPG，1280×960）。USB 走臂内布线：原 head↔base 为剥皮以太网线 8 芯，有备用线对。
3. **底座**：Pi Zero 2 W → **Pi5**（Zero2W 4×A53@1GHz/512MB 大概率跑不动 V2 全栈，待核）；腔体 160×190×40mm 需复核。供电改 **12V5A 单电源**（舵机/功放 12V + MP2482 降压 5V3A 供板/环/风扇）。原 5V 舵机轨欠压欠流（STS3215 需 ≥6V）。
4. **舵机**：保留 5× Feetech STS3215 + Waveshare USB 适配器（ID1-5：base_yaw/base_pitch/elbow_pitch/wrist_roll/wrist_pitch，1M baud，/dev/ttyACM0）。推荐 **12V C018 版（30kg·cm）** 对齐 lampOS；国产便宜 C001 7.4V（19.5kg·cm）在最坏水平肩位 ~22kg·cm 下裕量 <1（估算，待核）。
5. **电池**：小容量高倍率电芯，仅保活 + 断电兜底归位，见 `../product/battery/`。

## 不变项
臂连杆几何、舵机 ID/接线协议、折叠收纳概念。

## ⚠️ 静息姿态重力稳定
V2 fold-to-rest 折叠后**释放全部力矩**（零保持电流），依赖静息姿态重力稳定。上游 rest 姿态基于 lamp-4ace 几何；LeLamp 几何不同 → 必须在 brain-sim 验证 + 用本机 URDF 重生成 lean/CoG，否则断电归位会"松手即倒"。
