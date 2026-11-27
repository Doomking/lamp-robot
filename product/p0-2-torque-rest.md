# P0-② 力矩 / 伸距 / 静息 / 释放 / 折叠 / 配重 —— 仿真定稿

2026-11-26 · MuJoCo（`hardware/simulation` + `product/brain-sim/recordings`）·
timestep 0.01s · 接触全开 · **全部工况穿透 pen=0** ·
可复现脚本与结果 JSON：`brain-sim/analysis/`。

> **2026-11-27 修正**：本文 CoG 读数受 MuJoCo `body_subtreemass` 过期 bug 影响，
> xy 全部被缩放 0.8078（偏乐观）。修正值与翻转结论见 **`p0-2-cog-correction.md`**：
> 500g 配重必配；rest0 释放无配重时倒；「230g 头倒」是假象；45/65 门限作废。
> §3–§7 的 CoG/margin 数值为 P0 历史读数，勿再引用；力矩（§1–§2）、仿射映射（§0）、
> rest0 姿态选择（§4）仍有效；§9 补丁清单由修正文档 §8 取代。

## 0. 前提修正：CSV 是归一化值，不是角度（待核① 关闭）

LeLamp recordings CSV = LeRobot **RANGE_M100_100 归一化（−100..100）**，
依据 `lelamp_runtime/config_lelamp_follower.py: use_degrees=False`。
旧 brain-sim 的"逐关节符号自拟合（角度制）"是错误前提 →
**旧 26–34 kg·cm 力矩、"最坏水平肩位 22 kg·cm"、倾倒结论全部作废**。

修正为仿射映射 **θ = θ_c + s·k·v**：
- yaw/roll：θ = s·0.9°·v（±100 → ±90°，对齐文档限幅）；
- pitch/elbow/wrist：k = span/200；θ_c = 范围中点（H1）或模型零位（H2）。

| 关节 | s | 假设 | 模型范围(°) | 中点(°) |
|---|---|---|---|---|
| base_yaw | +1 | — | [−287.7, 72.3] | −107.7 |
| base_pitch | +1 | H1 | [−62.1, 117.9] | 27.9 |
| elbow_pitch | −1 | H2 | [−161.6, 18.4] | −71.6 |
| wrist_roll | +1 | — | [−217, 143] | −37 |
| wrist_pitch | −1 | H2 | [−48.9, 131.1] | 41.1 |

**视觉验证通过**：qpos0 棍图与 CAD 渲染（`hardware/docs/assets/images/1_lamp_3d.png`、
`4_3d_view.png`）完全一致（下臂后倾 ~20°、上臂水平、出光朝前下）→ qpos0 = CAD 零位。
idle 帧 1682 = (7.3, −64.9, 97.8, 13.3, 13.9) → 潜望镜 idle，头部 z≈499mm、脸朝上 ~+20°，
与演示视频相符。出光方向 (−0.7535, +0.6575, 0) 正确。
**遗留**：wrist_pitch 的 H1/H2/符号存在 ±41° 备选带（H2 下 CSV 极值 v>54.3 有 ~14° 饱和、7.2% 帧，
H1 无饱和）；力矩影响 <1 kg·cm、CoG <8% → 上机实测裁决（待核⑧）。

## 1. 质量工况与力矩 / 伸距 / CoG

质量模型：STL 体积×密度（打印件 0.5 g/cm³ 估算；其它塑料 1.09；舵机 55g/个；
金属舵盘 2.7；PCB 1.85）+ 头部电子配重。realistic-upper + 180g 头 → **整机 0.923 kg**。
realistic 打印头壳仅 **37.3g**；A 方案整头（环+摄像头+匀光板+壳）估 **90–120g**。

全 6 段 recordings 逐帧（每 3 帧采样）重力力矩 |qfrc_bias|，kg·cm（max / p50）：

| 工况 | 肩 base_pitch | 肘 elbow_pitch | 腕 wrist_pitch | 伸距 p50/max (mm) | CoG 最小裕量 (mm) |
|---|---|---|---|---|---|
| exported+50g（导出质量+电子） | 10.1 / 4.8 | 7.0 / 5.5 | 1.2 / 1.1 | 128 / 233 | +9.0 |
| realistic-upper（其它塑料实心） | 6.3 / 2.8 | 4.2 / 3.2 | 0.3 / 0.3 | 128 / 233 | +40.3 |
| realistic-lower（全打印 0.5） | 5.4 / 2.4 | 3.6 / 2.7 | 0.3 / 0.3 | 128 / 233 | +48.2 |
| **NEW-A-180g**（A 方案头部红线） | 10.3 / 5.3 | 7.6 / 6.0 | 1.5 / 1.3 | 128 / 233 | **+7.9** |
| NEW-A-230g | 11.7 / 6.3 | 8.8 / 7.0 | 2.0 / 1.7 | 128 / 233 | **−3.5 倒** |

裕量 = min(95−|CoG_x|, 80−|CoG_y|)，底座足迹 x±95 / y±80mm。
**伸距 max 233mm** → 旧"限伸距 45cm"无意义，作废。

## 2. 舵机选型修正（C018 仍推荐，理由更换）

- 力矩不再是决定因素：C001 7.4V（19.5 kg·cm）对 max 11.7 也够。
- **仍推荐 C018 12V（30 kg·cm）**：① 免额外 12→7.4V 降压 + 2S 电池（C001 需要）；
  ② force-limit 600 ≈ 18 kg·cm = C001 堵转的 **92%**（保护弱）vs C018 的 **60%**。
- C001 = 降本备选。旧"裕量<1"论述作废。

## 3. 头部质量红线与 force-limit

- **无配重：整头 ≤180g**（裕量 +7.9）；230g 倒（−3.5）。
- **500g 配重：≤230g 可救**（裕量 ≈+25，推算见 §7）。A 方案估重 90–120g → 余量大。
- **force-limit 保持 600**：覆盖折叠全程最大保持力矩 11.8 kg·cm（≈18 kg·cm 限幅的 66%）。
  旧"800"建议作废。

## 4. 静息姿态 rest0（待核⑧ 仿真部分闭环）

V2 严格 rest 门（头 z<120mm 且 CoG≤22mm）在 LeLamp 几何下 **0 候选** →
上游 rest 不可直接套用。网格搜索（pitch −60..118 / elbow −160..18 / wrist −45..131，
约束头 z≤200、|CoG|≤60、无穿透）得 5 候选，选 **rest0**：

| 量 | 值 |
|---|---|
| 模型角度 (pitch, elbow, wrist) | **(−18°, +14°, −45°)**，yaw=roll=0 |
| CSV 归一化等价 | ≈ **(0, −51.0, −15.6, 0, +50.0)** |
| 头部 z | 193mm |
| CoG / 倾倒裕量 | 56.4mm / **+45.2mm** |
| 重力保持（肩/肘/腕） | 6.11 / 6.56 / 0.71 kg·cm |

备选：wrist −35/−25/−15/−5（CoG 58.4–64.7mm，裕量 43.1–36.2）。

## 5. 释放（3s 断力矩）——"零保持电流"假设不成立

| 起始姿态 | 头下沉 (mm) → 终 z | 最大关节漂移 | 沉降后 CoG (mm) | 裕量 |
|---|---|---|---|---|
| rest0 | 87.7 → 105.7 | 22° | 89.5 (−81.7, +36.4) | **+13.3** |
| rest2 (wrist−25) | 62.4 → 131.0 | 14.7° | 81.3 | +20.9 |
| qpos0 | 163.4 → 131.5 | 32.3° | 85.4 | +16.2 |
| **idle（未折叠）** | 377.0 → 121.7 | 70.7° | 149.7 | **−49.4 必倒** |

rest0 释放后由**匀光板触桌 + 腕连杆触底座舵机**承接（两处接触，非悬浮）。
结论：
1. **释放只允许在折叠之后**；idle 直接释放必倒。
2. **正常静息 = 力矩保持**（6–7 kg·cm，小电流）；fork **不得**在 rest 调 `release_arm`。
3. 断电兜底流程见 §8。

## 6. 折叠路径（idle → rest0）

| 路径 | 最小裕量 (mm) | 最大保持 (kg·cm) | 穿透 |
|---|---|---|---|
| **linear（五关节同步线性）** | **+7.4** | 10.4 | 0 |
| staged（上游腕→肘→肩顺序） | **−5.1 瞬态倒** | 11.8 | 0 |
| zero → rest0 linear | +45.2 | 9.4 | 0 |

→ **fork 对 lelamp 用 linear 折叠**（上游 staged 顺序在 LeLamp 几何下产生瞬态倾倒）；
HAL 机型保留 staged。500g 配重下 linear 全程裕量 ≈+33、staged ≈+25（推算，§7）。

## 7. 配重（底座钢块，推荐 500g 标配）

把 rest CoG 压到门限所需配重（置于底座中心，CoG 线性缩放）：

| 目标 CoG 门 | 所需配重 |
|---|---|
| 22mm（V2 原门） | 1.44 kg（**否决**） |
| 40mm | 0.38 kg |
| 50mm | 0.12 kg |

**推荐 500g 钢**（~64cm³，如 150×80×5.3mm，¥10–20，底座腔体可容纳）：
- rest CoG **36.6mm**（脚本值）；1000g → 27.1mm。
- 沉降后（释放）CoG ≈58mm、裕量 **≥42mm**（由 §5 沉降 xy 缩放推算）。
- linear 折叠最小裕量 ≈**+33mm**、staged ≈**+25mm**（推算）。
- 救 230g 头：裕量 ≈**+25mm**（推算）。
- 推算假设配重位于底座中心；实际质量/位置 → 待核⑨。

## 8. 断电兜底流程（修订）

市电丢失 → 去抖 → **电池线性折叠到 rest0** → 力矩保持 **T_hold（~60s，待测⑩）** →
释放（配重下沉降不倒）→ 休眠。
旧"折叠后立即零电流释放"修订为"保持 T_hold 后释放"，给市电恢复留窗口、
避免电池承担长时间保持电流。

## 9. fork P1 补丁清单（body.rs，隔离补丁，不动 upstream 语义）

> 本节已被 `p0-2-cog-correction.md` §8 取代：45/65 门限作废（口径错误）；
> fold-order 与 rest-release 补丁取消；新清单 = LAMP_LEAN_JSON / LAMP_CLIP_MM=78 /
> LAMP_LOOK_MM=72 / LAMP_FOLD_BOUND_MM=78。以下保留为 P0 历史记录。

1. fold CoG 门 22 → 环境变量 **`LAMP_FOLD_COG_GATE_MM`**（lelamp：45 带配重 / 65 不带）。
2. `fold_plan` → lelamp 用 **linear**（HAL 保留 staged）。
3. rest **不 `release_arm`**（正常静息力矩保持）。
4. lean/CoG JSON 用本机质量（0.923kg + 500g 配重）经 **lamp-lean** 重生成。
5. recordings 转换器 + ring 40→32 映射（见 `integration-checklist.md`）。

## 10. 待核状态更新

- ① CSV 语义/映射：**关闭**（归一化 + 仿射，视觉验证）。
- ⑧ 静息稳定性：**仿真闭环**；上机 wrist band + rest0 冻结仍待核。
- ⑨ 配重实际质量/位置：新增，待核。
- ⑩ 折叠峰值电流 / T_hold：新增，待测。
- ②③④ 语音侧见 `voice/README.md`。

## 复现

```bash
/tmp/lelamp-sim-venv/bin/python product/brain-sim/analysis/p0_2_final.py
/tmp/lelamp-sim-venv/bin/python product/brain-sim/analysis/p0_2_release.py
/tmp/lelamp-sim-venv/bin/python product/brain-sim/analysis/render3.py   # → /tmp/r_*.png
```
