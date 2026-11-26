# lamp-robot

个人台灯机器人：**LeLamp 硬件 × lampOS V2 软件**。市电为主 + 小电池保活/断电兜底归位（非无线化）。

## 血缘与基线
- fork 自 [autonomous-ai/lampOS](https://github.com/autonomous-ai/lampOS)，基线分支 `lamp-voice`（V2），pin **`8a60e6b02f`**（2026-11-26）。
- 硬件来源 [humancomputerlab/LeLamp](https://github.com/humancomputerlab/LeLamp) @ `4a0ef2c`（GPL-3.0），见 `hardware/README.md`。
- lampOS 的 `hal/` 本身即 LeLamp lelamp_runtime 的 fork（@ ee23699），见 `hal/UPSTREAM.md`。
- **计算平台（2026-11-26 确认）**：**OrangePi 4 Pro 6GB**（Allwinner A733：2×A76@2.0GHz + 6×A55，3TOPS NPU 可选）= lampOS 上游原生板（`lampOS/docs/hardware.md`），零 SBC 移植；比 Pi5 便宜（6GB ~¥280 vs Pi5 8GB ~¥600，估算）。已知 A733 warm-reset 挂起 quirk 上游已有 workaround（reset-in-place，见 `lampOS/docs/setup.md`）。

## 目录布局（结构 A：单 fork monorepo）
| 路径 | 内容 | 许可 | 上游同步 |
|---|---|---|---|
| `lampOS/` | V2 Rust 工作区（voice/body/ring/camera/skills/sim） | Apache-2.0 | 定期 rebase；目标零本地补丁（ring SPI 默认 `/dev/spidev3.0` 即 OPi 总线） |
| `hal/` `robots/` `runtimes/` 等 | lampOS 其余部分（V1 参考 + HAL） | Apache-2.0（hal 为 GPL-3.0） | 跟随上游 |
| `hardware/` | LeLamp 3D/URDF/docs + 结构改造（灯环座/中心摄像头/环形匀光板/OrangePi 4 Pro 底座） | GPL-3.0 | 独立演进 |
| `product/` | 净新增：battery / calibration / voice / brain-sim | 随根 Apache-2.0（注意 GPL 边界） | 无上游 |

## 上游跟踪策略
1. pin commit（见上）；2. 补丁隔离（独立 commit、最小 diff）；3. 定期 `git fetch upstream && git rebase upstream/lamp-voice`；4. 以代码为准（文档滞后）；5. 通用修复回馈上游（选定 OPi 4 Pro 后，已知无必需本地补丁）。

## 路线图
- **P0（零硬件）**：LeLamp↔V2 集成清单（OPi 4 Pro 为上游原生板，无 SBC 移植项）；brain-sim 运动包络/折叠验证；中文语音路线选型（sim）。
- **P1（硬件）**：采购（标准 32×WS2812B 灯环 外径104/内径90mm、UVC 摄像头、STS3215 12V C018、OrangePi 4 Pro 6GB、杰理双麦 ENC + C-Media 适配器、12V5A）；头部/底座结构改造；逐灯标定（BODY_POSES / zone.env / lean-CoG）。
- **P2（语音）**：中文人格（重写 `lampOS/deploy/character/lamp.txt`，移除 "Always speak English" 规则）；own-keys 语音路线；自有技能。
- **P3（电池）**：市电丢失检测 → 调用 V2 既有 fold-to-rest → 休眠（净新增，见 `product/battery/`）。

各子目录 README 有详细设计笔记。上游总览见根 `README.md`（lampOS 原文，未改动）。
