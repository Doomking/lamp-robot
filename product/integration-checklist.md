# P0-① 集成清单 —— 逐层复用 / 自写边界（2026-11-26，2026-11-27 更新批次状态）

整体方案：**LeLamp 硬件（hardware/，GPL-3.0）+ lampOS V2 软件（lampOS/，Apache-2.0）**，
monorepo fork = Doomking/lamp-robot，分支 codex/lelamp-integration。
原则：机械/电气/运动控制复用；语音人格/自主行为/电池策略/标定自写；upstream 零修改，
fork 补丁隔离 + pin commit + 定期 rebase（code = truth）；权威数值以 p0-2-cog-correction.md 为准。

## 逐层边界

| 层 | 来源 | 复用 / 自写 | 动作 | 验证 | 状态 |
|---|---|---|---|---|---|
| 机械结构 | LeLamp hardware/ + 上游 CAD 参考 | 复用臂/底座；**自写头部 A 方案** | 圆形前脸 ~120–125mm + 104mm 32 灯环 + 中心 UVC 凸台 + 环形匀光板；STL 改型 | brain-sim 包络/CoG（P0-② 质量包络已做）；打印试装 | A 定稿 + 制造规格已交（P1-e hardware-spec-head-a.md）；3mf 待改 |
| 电气/供电 | 自写 | 12V5A 单电源 + MP2482 5V3A + 小电池 power-path | 原理图/接线；市电丢失检测（mux 之前采样） | 峰值电流实测（⑩）；断电折叠演练 | 方案定，待制板 |
| 计算/传感 | lampOS 上游原生 | **OrangePi 4 Pro 6GB** + UVC + 杰理双麦 ENC/C-Media | 零 SBC 移植；环 SPI /dev/spidev3.0 | V4L2 MJPG 1280×960 枚举；16kHz 采集 | 选型定 |
| 运动控制 | lampOS V2 body | 复用（**单总线主**）；自写 P1 适配器/转换器/fold 补丁 | recordings normalized→counts；ring 40→32；fold 绝对门 env（order/release 补丁取消） | 空载 idle+单 emote 方向/限幅（⑧） | 转换器/环映射（batch1）+ 门控（P1-b）已交；上机适配待⑧ |
| 语音 | V2 voice crate | 复用 gemini\|second + own-keys + 语言层（#4473 zh）；**自写中文人格** | lamp-zh.txt（instruction_file 覆盖）+ language=zh + LAMP_LOOK_PHRASES 补丁 | 中文盲听（②）；Gemini 国内连通（③）；near-call 小灯（⑪） | 人格/look 补丁已交（P1-d） |
| 自主行为 | V2 skills/memory/safety | 复用框架；自写中文技能 + 呼吸/空闲 emote | skills-zh 直接拷贝 + off；brain-sim 骨架（Autonomy/Brain 仲裁）迁移到 V2 技能 | 占空比守卫、静默窗、可审计日志 | 中文技能已交（P1-d）；仲裁迁移待续 |
| 安全 | V2 force-limit/give-way/zone | 复用；force-limit **600 保留**；fold CoG 门本机化 | LAMP_CLIP_MM=78 / LOOK_MM=72 / FOLD_BOUND_MM=78 + LAMP_LEAN_JSON（b500） | 实测夹力/倾倒裕量 | P1-b 已交（env 门控，926 测试绿）；⑧⑨ 核后冻结 |
| 部署 | V2 deploy/units + sync-skills | 复用；自写 lamp.env/zone.env/lean JSON | lamp-lean 重生成（0.923kg+500g）；lamp-body-measure 实测 | body 启动自检（无配置拒启动） | 待上机 |
| 许可 | NOTICE | Apache-2.0 root / GPL-3.0 hal+hardware | 分发合规；lelamp_runtime 无 LICENSE → 不混入自有许可发行物 | 分发前审查 | NOTICE 已立 |

## 接缝决策（关键）

1. **单总线主 = V2 body**。LeLamp AnimationService 不并行运行；brain-sim 接缝契约
   （play/solid/paint/recordings/motion_seconds）映射到 V2 body/presets API（P1 适配器）。
2. **recordings 转换器（自写 P1）**：LeLamp CSV（归一化 −100..100）→ V2 counts：
   `counts = 2048 + (θ_deg − homing) / 360 × 4096`，θ_deg 由仿射映射求得（calibration/），
   homing 逐关节实测。注意差异：V2 hal/recordings 最后两列 wrist **互换**、
   时基 0@20fps vs LeLamp 绝对时间@30fps → 转换器需重排列 + 时基归一/重采样。
3. **ring paint 40→32（自写 P1）**：8×5 矩阵 → 32 环逐点映射，保持 brain 侧 paint 语义；
   PIXEL_COUNT=32 不改（上游 presets/效果假设）。
4. **calibration**：BODY_POSES rest = rest0（CSV ≈ (0, −51.0, −15.6, 0, +50.0)）+ 实测限位；
   lean/CoG JSON 用 P0-② 质量经 lamp-lean 重生成；zone.env 逐灯。
5. **UVC / 麦克风 / SBC 原生 ✓**：V2 camera 只认 V4L2 MJPG；杰理双麦 ENC + C-Media USB
   16kHz 为上游拓扑；OrangePi 4 Pro 为上游原生板 → 零驱动/移植适配。

## P1 任务清单（fork 补丁，隔离在 product/ 或 fork patch）

1. ✅ P1-b：cog.rs 门限 env 化（LAMP_CLIP_MM / LOOK_MM / FOLD_BOUND_MM + LEAN_JSON，unset = V1 逐字节）；fold_plan linear / rest no-release 补丁**取消**——上游释放只在折叠后，linear 由绝对门放行（correction §6–7）。
2. ✅ batch1：product/tools/recordings_lelamp.py + ring40to32.py（转换器 + 环映射）。
3. ✅ P1-c：product/calibration/gen_lean_json.py（FK 误差 0.0017mm）+ lean-lelamp-ballast.json。
4. ✅ P1-d：lamp-zh.txt（instruction_file 覆盖）+ skills-zh 3 技能（**直接拷贝 + off，非 sync-skills**）+ LAMP_LOOK_PHRASES 补丁。
5. ◐ P1-d：battery_daemon.py 骨架已交（sim 冒烟全绿）；硬件后端待⑩。
6. ◐ P1-e：hardware-spec-head-a.md 制造规格已交；3mf 改型待做。

## 参考

- 仿真定稿：`p0-2-torque-rest.md`（力矩/静息/释放/折叠/配重 + 待核）。
- **权威修正**：`p0-2-cog-correction.md`（2026-11-27，mj_setConst 质量/CoG 修正；门限 78/72/78、b500 rest0 释放 +29.4 / idle 释放 −14.4、linear 峰值 74.9；旧数值作废）。
- 上游事实（fork 后坐标）：cog.rs `clip_mm()/look_mm()/fold_bound_mm()` env API（unset = V1）；body.rs release_arm **唯一调用点 :8089**（release_due + down_steps≥REST_STEPS → 释放只在折叠完成后）；deploy/units 参考 ExecStart（--force-limit 600 --torque on --give-way return 等）。
- 部署：`deploy/lamp-body.env.example`（P1-b）+ `deploy/lamp-voice.env.example`（P1-d）；**500g 钢配重必配**（150×80×5.3mm ≈499g @ world(0,0,5mm)，无配重任何门限救不了）。
