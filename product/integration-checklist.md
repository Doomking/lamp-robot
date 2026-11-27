# P0-① 集成清单 —— 逐层复用 / 自写边界（2026-11-26）

整体方案：**LeLamp 硬件（hardware/，GPL-3.0）+ lampOS V2 软件（lampOS/，Apache-2.0）**，
monorepo fork = Doomking/lamp-robot，分支 codex/lelamp-integration。
原则：机械/电气/运动控制复用；语音人格/自主行为/电池策略/标定自写；upstream 零修改，
fork 补丁隔离 + pin commit + 定期 rebase（code = truth）。

## 逐层边界

| 层 | 来源 | 复用 / 自写 | 动作 | 验证 | 状态 |
|---|---|---|---|---|---|
| 机械结构 | LeLamp hardware/ + 上游 CAD 参考 | 复用臂/底座；**自写头部 A 方案** | 圆形前脸 ~120–125mm + 104mm 32 灯环 + 中心 UVC 凸台 + 环形匀光板；STL 改型 | brain-sim 包络/CoG（P0-② 质量包络已做）；打印试装 | A 定稿，STL 待改 |
| 电气/供电 | 自写 | 12V5A 单电源 + MP2482 5V3A + 小电池 power-path | 原理图/接线；市电丢失检测（mux 之前采样） | 峰值电流实测（⑩）；断电折叠演练 | 方案定，待制板 |
| 计算/传感 | lampOS 上游原生 | **OrangePi 4 Pro 6GB** + UVC + 杰理双麦 ENC/C-Media | 零 SBC 移植；环 SPI /dev/spidev3.0 | V4L2 MJPG 1280×960 枚举；16kHz 采集 | 选型定 |
| 运动控制 | lampOS V2 body | 复用（**单总线主**）；自写 P1 适配器/转换器/fold 补丁 | recordings normalized→counts；ring 40→32；fold gate/linear/no-release | 空载 idle+单 emote 方向/限幅（⑧） | 仿真闭环，P1 待写 |
| 语音 | V2 voice crate | 复用 gemini\|second + own-keys；**自写中文人格** | lamp.txt 移除 "Always speak English"；中文人格重写；适配器选型 | 中文盲听（②）；Gemini 国内连通（③） | 路线 ①/② 原型，③ P3 |
| 自主行为 | V2 skills/memory/safety | 复用框架；自写中文技能 + 呼吸/空闲 emote | brain-sim 骨架（Autonomy/Brain 仲裁）迁移到 V2 技能 | 占空比守卫、静默窗、可审计日志 | 骨架已验证 |
| 安全 | V2 force-limit/give-way/zone | 复用；force-limit **600 保留**；fold CoG 门本机化 | LAMP_FOLD_COG_GATE_MM=45（带配重）/65 | 实测夹力/倾倒裕量 | 参数定 |
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

1. body.rs：fold CoG gate → env（45/65）；fold_plan lelamp=linear；rest 不 release_arm。
2. recordings 转换器 + ring 40→32 映射。
3. lean/CoG JSON 重生成（lamp-lean）。
4. 中文人格 lamp.txt + 中文技能（sync-skills 部署）。
5. battery 守护进程（去抖 → 线性折叠 → T_hold → release → 休眠）。
6. 头部 A 方案 STL + 匀光板 + 摄像头凸台；500g 配重安装位。

## 参考

- 仿真定稿：`p0-2-torque-rest.md`（力矩/静息/释放/折叠/配重 + 待核）。
- 上游事实：body.rs:4672（fold ≤50 counts/write 后 release_arm）、:8469/:3924（CoG 门 22）、
  :4905（"let go only what gravity holds"）；deploy/units 参考 ExecStart
  （--force-limit 600 --torque on --give-way return 等）。
