# 头部 A 方案制造规格（P1-e，2026-11-27）

状态：**设计定稿**（hardware/README.md P0-③ + P0-② 修正）；3mf 改型待做。
权威数值 = `p0-2-cog-correction.md` + `calibration/README.md`；本文是打印/装配的制造基线。
旧文档（p0-2-torque-rest.md、hardware/README.md ⚠️ 节）的 CoG/裕量/红线数值已被修正取代。

## 0. 改动范围

| 文件（hardware/3D/） | 改动 |
|---|---|
| `LampHead.3mf` | 矩形脸 104×79mm → **圆形前脸 Ø120–125mm**；环安装槽；中心 UVC 凸台 |
| `LampHead - Diffuser.3mf` | 矩形扩散板 → **环形匀光板**（OD~120.3 / ID82.2–87.4mm 阶梯孔） |
| `LampBase.3mf` | **500g 配重凹槽** + OrangePi 4 Pro 转接安装位 + 电芯空间 |
| 4×`LampArm*.3mf`、`LampBase - Cover.3mf` | **不动**（臂连杆几何 = 不变项） |

## 1. 头部前脸

- 圆形前脸 **Ø120–125mm**（< 上游外壳 158.7mm；> LeLamp 原 104×79mm 矩形脸）。
- **环安装槽**：内壁 d86.3 / 外壁 d115.3mm，深 ~3.6mm（上游 head-part3 CAD 实测，hardware/README.md P0-③）。
- **灯环**：标准 **32×WS2812B 5050**，OD104 / ID90mm，LED 分布圆 ~97mm（r48.5 落在槽 43.2–57.7 内）。现货淘宝 ~¥8–20（估算）。数据走 SPI（OrangePi **spidev3.0**）。**替代** LeLamp 40 颗 8×5 矩阵；ring paint 40→32 映射 = `tools/ring40to32.py`（batch1 已交），PIXEL_COUNT=32 上游假设不改。
- **中心 UVC 凸台**：上游相机窗口 ~Ø74mm（head-part1）；UVC 模组（V4L2 MJPG 1280×960，V2 camera 只认此路径）板级镜头，凸台高度/俯仰按模组实物尺寸定（**模组选型待核**）。USB 走臂内备用线对（原 head↔base 剥皮以太网 8 芯）。**替代** Pi CSI/libcamera。
- **环形匀光板**：OD~120.3 / ID82.2–87.4mm 阶梯孔（上游 light-cover.stp 参考）。**rest0 释放后匀光板触桌** = 两处承接之一（另一处：腕连杆触底座舵机，p0-2-torque-rest.md §5）→ 底面平整、耐磨、触桌无声。
- 出光方向朝前下（qpos0 = CAD 零位视觉验证不变）。

## 2. 质量预算（权威 = correction doc）

- 头部模型值 **180g**（打印件 0.5g/cm³ 估算）；A 方案实际估重 **90–120g**（环+摄像头+匀光板+壳）。
- **140–240g 头在 rest0 全安全**（correction §3）：静置头部预算**不是约束**；旧「整头 ≤180g 红线」作废。危险在 release/fold 动力学，不在静置。
- 整机 **b500 = 1.4225kg**（0.9225 + 500g 配重）；footprint **x±95 / y±80mm 不变**。
- STL 改型后**必做**：brain-sim 包络/CoG 复核 → 实测质量更新模型 → `calibration/gen_lean_json.py` 重生成 lean JSON → `tools/lean-gate-validate/` 双跑再冻结门限。

## 3. 配重（必配，非可选）

- **150×80×5.3mm 钢板 ≈499g**（7.85g/cm³），world **(0, 0, 5mm)** = 底座底部内腔。
- LampBase.3mf 开凹槽（建议 150.5×80.5×5.5mm 留装配公差）+ 固定（螺钉/胶/盖板）；位置偏差直接进 CoG → **⑨ 上机必核实际质量/位置**，核后重跑两个脚本再冻结门限。
- 无配重（nb）：idle 静态 margin 仅 +2.1mm、rest0 释放 −6.2、idle 释放即倒 → **任何门限都救不了**（correction §3）。
- 成本 ~¥10–20（估算）。

## 4. 底座腔体（概念不变，布局更新）

- 腔体 160×190×40mm：OrangePi 4 Pro 6GB（89×56mm，转接板）+ MP2482 5V3A + 12V5A 输入 + 小电芯（~50–100g，battery/README.md）+ Waveshare USB 舵机适配器（ID1-5，/dev/ttyACM0）。
- 麦克风：杰理双麦 ENC + C-Media USB（上游拓扑，16kHz）；功放 12V。
- **市电丢失检测采样点在 power-path mux 之前**（battery/README.md）。

## 5. 门限与部署（P1-b 已交，⑧⑨ 核后冻结）

`LAMP_CLIP_MM=78 / LAMP_LOOK_MM=72 / LAMP_FOLD_BOUND_MM=78` + `LAMP_LEAN_JSON=/etc/lampOS/body/lean-lelamp-ballast.json`（deploy/lamp-body.env.example）。
b500 关键值：rest0 off 45.3 / margin 55.0；rest0 释放 **+29.4 安全**；idle→rest0 linear 峰值 74.9（过 78，margin +24.7）；idle 释放 **−14.4 倒**。

## 6. 验证清单

1. 打印试装：环槽配合 / 匀光板卡扣 / UVC 凸台 / 配重凹槽。
2. 称头部实际质量 → 更新质量模型 → 重生成 lean JSON + gate probe。
3. ⑧ wrist H1/H2 + 轴 sign + homing 上机裁决 → 冻结 rest0。
4. ⑨ 配重质量/位置复核 → 冻结门限。
5. ⑩ 折叠峰值电流 / T_hold → 电芯选型（battery）。

## BOM 估算（2026-11-27，现货价区间）

| 项 | 规格 | 估算 |
|---|---|---|
| 灯环 | 32×WS2812B 5050 OD104/ID90 | ¥8–20 |
| UVC 摄像头 | V4L2 MJPG 1280×960 板级 | ¥30–60 |
| 配重钢板 | 150×80×5.3mm ≈499g | ¥10–20 |
| 匀光板/头壳 | PETG/PLA 打印（0.5g/cm³ 估算） | 材料费 |
