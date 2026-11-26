# calibration — 逐灯实测配置（必需，非可选）

V2 body **无实测配置拒绝启动**：
- `/etc/lampOS/body/lamp.env` — BODY_POSES（逐关节实测姿态限位）；
- `zone.env` — 逐灯区域配置；
- lean/CoG JSON — 上游 `lampOS/deploy/lamp-4ace/lean-first-software.json` 基于 V1 URDF 且**质量为估算值（1.49kg，"not a measurement"）**，不适用本机。

## 流程
`hardware/simulation/robot.urdf`（结构改造后）→ lamp-lean 重生成 → `lamp-body-measure.service` 实测 → 填 lamp.env / zone.env。

## 参考
- `lampOS/deploy/units/README.md` — 部分部署原则："Leave out what the lamp does not run. A part that is not there is not waited for."
- 逐灯模板占位符：@NAME@ / @SERVO_DEVICE@ / @CAMERA_DEVICE@ / @FAST_CPUS@（Pi5 移植时填）。
