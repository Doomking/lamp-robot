# P0-② CoG 修正：MuJoCo subtreemass 过期与门限本机化

2026-11-27 · 修正对象 `p0-2-torque-rest.md`（2026-11-26）·
脚本 `brain-sim/analysis/p0_2_cog_fix.py`、`p0_2_gate_probe.py` ·
数据 `p0_2_cog_fix.json`、`p0_2_gate_probe.json`（MuJoCo 4.0.1，timestep 0.01s）。

**TL;DR**

- P0 用 MuJoCo `subtree_com` 读 CoG。`body_subtreemass` 是编译期常量，运行时改
  `body_mass` 后 `mj_forward` 不刷新它，读数 = 新力矩 / 旧总质量 → 全部 CoG xy
  被缩放 0.9225/1.142 = **0.8078**，偏乐观。修复：质量编辑后调 `mj_setConst(m,d)`。
- 修正后翻转的结论：**500g 配重从「推荐」变「必配」**；rest0 释放无配重时从
  「+13.3 安全」变「−6.2 倒」；「230g 头倒」是读数假象，静置头部预算不是约束。
  力矩 / 伸距 / 仿射映射 / rest0 姿态选择不受影响（动力学走实时质量）。
- 决策：门限本机化为 **`LAMP_CLIP_MM=78` / `LAMP_LOOK_MM=72` /
  `LAMP_FOLD_BOUND_MM=78`**（500g 配重工况），fold 相对门改绝对门；
  原计划的 `LAMP_FOLD_ORDER`、`LAMP_REST_RELEASE` 两个补丁取消（§7、§8）。

## 1. 机制与证据

MuJoCo 在 `mj_setConst`（编译/重置时调用）里计算每个 body 的子树质量
`body_subtreemass`。`mj_forward` 只刷新运动学量，不重算它。P0 的
`p0_2_real_mass.py` 在运行时把整机质量从 XML 导出的 1.142kg 改成估算
0.9225kg（打印件 0.5g/cm³），随后 `subtree_com` 仍除以 1.142 →
每个 CoG xy 读数被乘 0.8078。

交叉验证（旧读数 / 0.8078 ≈ 新读数）：

| 量 | P0 旧值 | ÷0.8078 | 修正值 |
|---|---|---|---|
| rest0 静态 off_axis | 56.4 | 69.8 | **69.8** |
| rest0 释放后 CoG xy | (−81.7, 36.4) | (−101.1, 45.1) | **(−101.2, 45.0)** |

动力学（`mj_rne`/CRBA、接触、`mj_step`）用的是实时 `body_mass`，不走
`body_subtreemass` → **P0 的轨迹、沉降、力矩结论仍然有效**，错的只是 CoG 读数
和由它推出的裕量/倾倒判定。

口径注意：P0 的 head_z 用 `xpos`（body 原点），修正脚本用 `xipos`（质心）。
193 vs 141.7、drop 87.7 vs 68.8 是**不同测量点**，不构成矛盾，不可直接对比。

## 2. 旧 → 新对照（矩形 footprint ±95×±80mm，margin = min(95−|cx|, 80−|cy|)）

nb = 无配重 0.9225kg；b500 = 500g 配重 @ world(0,0,5mm)，整机 1.4225kg。

| 工况 | P0 旧值（错） | nb 修正 | b500 修正 |
|---|---|---|---|
| rest0 静态 off / margin | 56.4 / +45.2 | 69.8 / +33.4 | 45.3 / **+55.0** |
| rest0 释放（3s 断力矩） | 89.5 / **+13.3 安全** | 110.7 / **−6.2 倒** | 71.8 / **+29.4 安全** |
| idle 释放 | 149.7 / −49.4 倒 | 174.9 / −73.7 倒 | 113.4 / **−14.4 仍倒** |
| idle→rest0 linear 折叠 min margin | +7.4 | **−13.4 倒** | **+24.7 安全** |
| idle→rest0 staged 折叠 min margin | −5.1 | −28.9 | +14.7 |
| zero→rest0 linear min margin | +45.2 | +33.4 | +55.0 |
| rest0 静置 230g 头 | **−3.5 倒** | +29.1 安全（扫频 140–240g 全安全：36.5→29.1） | — |

idle 静态（潜望镜 idle，帧 1682，yaw 6.56°）：

| | off_axis | margin | lean_back（yaw 归零） |
|---|---|---|---|
| nb | 98.0 | **+2.1**（临界） | 90.2 |
| b500 | 63.5 | +34.8 | 58.5 |

rest0 lean_back：nb +61.6，b500 **+40.0**。

## 3. 结论翻转与保留

翻转：

1. **500g 配重必配**。证据链：nb rest0 释放 −6.2；nb idle→rest0 linear 折叠
   −13.4；nb idle 静态 margin 仅 +2.1，且从 idle 播 clip 时 idle/nod/wake_up
   帧级 margin 为 −12.8/−2.0/−17.6（curious/happy/scan 也只剩 0.7/0.9/1.8）。
   无配重时「站着不动」勉强成立，任何行为或断力矩都倒。
2. **静置头部预算不是约束**。140–240g 头在 rest0 全安全；危险在 release/fold
   动力学，不在静置。旧「整头 ≤180g 红线」作废（180g 仍是质量模型取值）。
3. **旧 45/65 门限作废**。那是 margin 口径且基于错误 CoG；cog.rs 实际门限
   管的是 off_axis 与 lean_back（§4），不是矩形 margin。

保留：

- 仿射映射（CSV 归一化 → 模型角度）、qpos0 = CAD 零位视觉验证。
- 力矩结论：rest0 重力保持 6.11/6.56/0.71 kg·cm、折叠最大保持 11.8、
  force-limit 600、C018 12V 选型。
- rest0 姿态选择：CoG 缩放是全局均匀的，候选排序不变，(−18°, +14°, −45°)
  仍是最优；只是其 CoG/margin 数值按 §2 更新。
- 「释放只允许在折叠之后」「idle 直接释放必倒」（b500 下仍 −14.4）。
- 断电兜底流程骨架（§7）。

一处精确化：nb 从 rest0 播 clip 的帧级 margin 其实全为正（24.1–32.9）——
idle clip 的 off_axis 82.4 虽超过最小退出距离 80，但方向偏 −x（退出界 95）。
nb 不可用的依据是上面第 1 条，不是「rest0 clip 必倒」。CLIP_MM=78 仍会拒掉
82.4 的 idle clip（标量门保守，接受）。

## 4. cog.rs 门限的真实口径（HEAD 0d51bd07f8 源码坐标）

- `off_axis_mm = hypot(cx,cy)`，任意方向；`lean_back_mm = −cx`（base yaw
  归零到 `angle_zero`，本机 JSON 约定 = 0）。两者都走 lamp-lean FK。
- **CLIP_MM（22）**：clip 任一帧 off_axis 超限 → 整段拒播
  （body.rs:8484）；≥85% 触发 close 告警（8497）。
- **LOOK_MM（16）**：自主姿态的 lean_back 上限，超限按 halving×10 截断
  （`limit_lean_back`）。
- 运动门 ceiling（body.rs:9188–9192）：`gesturing || !upright → CLIP_MM，
  否则 LOOK_MM`。**折叠/起立过程走 CLIP_MM 门**，且只查 lean_back。
- fold 门（body.rs:4436）：`bound = max(off_axis(起点), off_axis(折叠终点))
  + 0.1`，路径采样超限 → Together/InTurn 都拒 → `NoFold::Tips`。相对口径。
- 启动时没有静态 rest CoG 硬门：rest0 经 `--home/--stand`（counts）给定，
  22mm 只在运动/clip 门生效。旧 §4「V2 严格 rest 门 0 候选」指文档口径，
  不构成部署障碍。

**lean_back 语义错位**：V1 零位臂朝 +x，−x 是「后仰」。LeLamp CAD 零位臂朝
≈148°（偏 −x），−x 实为臂的「前倾」方向；rest0 lean_back = +40（b500）在臂
坐标系里是前倾。门限仍作为 CoG −x 分量的限制器有效，但名字与物理方向不符，
调参时按「−x 分量」理解，不要按「后仰」直觉。

**已知局限（上游语义，fork 不改）**：自主运动门只查 lean_back（−x 分量），
横向 cy 无独立门；横向稳定性依赖姿态包络 + 配重。V1 时代两个门限都很小
（16/22mm）且底座重，这个缺口不显著；本机门限放大后在此记录。

## 5. 门限推导（b500 部署值）

clip 帧级数据（MuJoCo 逐帧；off_axis 与 lean-FK 交叉验证一致，见
`calibration/lean-verify.md`，203 poses FK 误差 0.0017mm）：

| clip | rest0 起点 max off / min margin | idle 起点 max off / min margin |
|---|---|---|
| curious | 47.8 / 52.8 | 64.2 / 33.8 |
| happy_wiggle | 49.0 / 47.9 | 64.8 / 34.0 |
| idle | 53.4 / 48.7 | **75.4 / 25.1** |
| nod | 47.1 / 53.0 | 65.9 / 32.1 |
| scanning | 45.3 / 52.5 | 63.5 / 34.6 |
| wake_up | 49.2 / 49.0 | 74.4 / **22.0** |

（以上为 b500；lean_back 最大值：rest0 起点 47.2，idle 起点 70.4。）

**`LAMP_CLIP_MM=78`**：

1. 覆盖全部 b500 clip（max off 75.4，余量 2.6mm），且这些帧的矩形 margin
   全 ≥22.0 —— 拒播门放行的是已逐帧验证安全的动作。
2. 低于最小退出距离 80（纯 y 方向）；off_axis 是方向无关标量，78 是保守代理。
3. 拒掉 nb idle clip（82.4）与 nb idle 起点全部 clip（≥98）——无配重时
   行为门自动收紧，与物理一致。
4. 折叠/起立运动门 ceiling 同为 78：b500 linear 折叠路径 lean_back max
   68.9 ≤ 78，放行。
5. WARN_SHARE 0.85 → 66.3mm：从 idle 播 idle（75.4）/wake_up（74.4）会报
   close（信息性，不拒播）。接受。

**`LAMP_LOOK_MM=72`**：

1. 必须 ≥ idle 静态 lean_back 58.5，否则自主行为到不了 idle（rest0 为 40.0）。
2. 覆盖 clip 级 lean_back 包络 70.4，自主探索留同等幅度。
3. 距 −x 退出界 95 留 23mm。nb idle lean_back 90.2 > 72 → 无配重时自主
   idle 不可达，与其 margin 2.1 的物理事实一致。

**`LAMP_FOLD_BOUND_MM=78`**：见 §6。

22mm 原门为何不追：rest0 off_axis 在 b500 下仍 45.3；要压到 22 需总质量
≈2.93kg（配重 ≈2.0kg，按 nb 力矩 64.4 kg·mm 线性折算），超出底座腔体与
成本预算。工程取舍 = 500g 配重 + 本机化门限，而不是追 V1 的 22mm。

## 6. fold 相对门问题与绝对门补丁

b500 从 idle 折叠：bound = max(63.5, 45.3) + 0.1 = **63.6**；linear 路径
off_axis 峰值 **74.9 > 63.6** → 上游 `fold_plan` 拒；staged 84.4 也拒 →
`NoFold::Tips`。**物理上 linear 全程 margin ≥ +24.7，是安全的**——相对门
（「不许比起点/终点更偏」）在 LeLamp 几何下误杀：折叠中段臂先外摆再收回，
off_axis 必然短暂超过两端。

补丁：`LAMP_FOLD_BOUND_MM` 设定时以绝对值替换相对 bound（cog.rs 提供
`fold_bound_mm(relative)`）。取 78：

- b500 linear 74.9 ≤ 78 → Together（即 linear）直接通过，**不需要
  `LAMP_FOLD_ORDER` 强制顺序补丁**；staged 84.4 > 78 仍拒（其 margin +14.7
  虽正，但无需放行更差路径）。
- nb linear 115.5 > 78 仍拒 → 无配重时拒绝危险折叠的行为保留。
- 绝对门比「相对+slack」更安全：起点已经很偏（off > 78）时相对门会放行
  更偏的路径，绝对门不会。
- 错误消息按模式切换措辞；默认（未设 env）输出与上游逐字节一致。

## 7. 释放 / 折叠运行规则（电池兜底）

源码事实：`release_arm`（body.rs:4672）唯一调用点在 8075，条件是
`release_due`（strain guard 的 unlifted/hot seat，9862/9891）且
`down_steps ≥ REST_STEPS`——**释放只发生在坐下（折叠到 --folded-arm）之后**，
正常静息本来就是力矩保持。

- b500 rest0 释放 +29.4 安全 → **保留上游释放行为，取消 `LAMP_REST_RELEASE`
  补丁**。旧 §5「fork 不得在 rest 调 release_arm」的担忧由「只在折叠后释放」
  的上游语义 + 配重共同消解。
- idle 释放 b500 仍 −14.4 → **电池兜底必须 torque ON 线性折叠到 rest0，
  绝不在 idle 直接释放**。
- 兜底流程（沿用旧 §8，数值更新）：市电丢失 → 去抖 → 电池供电 torque ON
  linear 折叠到 rest0（b500 全程 margin ≥ +24.7）→ 保持 T_hold（~60s，待测⑩）
  → 释放（沉降后 +29.4）→ 休眠。市电恢复窗口内保持力矩 6–7 kg·cm 小电流。

## 8. 影响面：P1-b 补丁清单（取代旧 §9）

全部 env 门控，未设 env 时上游默认行为逐字节不变（含测试与错误消息）。

cog.rs：

1. `LAMP_LEAN_JSON`：运行时路径覆盖内嵌 `lean-first-software.json`
   （LazyLock；设定但读取/解析失败 → panic，安全关键不做静默回退）。
2. `LAMP_CLIP_MM` / `LAMP_LOOK_MM`：`pub fn clip_mm()/look_mm()`（LazyLock，
   默认 = 常量 22/16）；常量保留供上游测试引用。
3. `LAMP_FOLD_BOUND_MM`：`pub fn fold_bound_mm(relative) -> f64` +
   `fold_bound_absolute() -> bool`。

body.rs（精确替换，各 1 处）：

4. 8484 / 8497：`cog::CLIP_MM` → `cog::clip_mm()`。
5. 9189 / 9191：→ `cog::clip_mm()` / `cog::look_mm()`。
6. 4436：bound 经 `cog::fold_bound_mm(...)`。
7. 4492–4494：NoFold::Tips 消息按 `fold_bound_absolute()` 切换措辞与数值。

取消：`LAMP_FOLD_ORDER`（§6）、`LAMP_REST_RELEASE`（§7）、
`LAMP_FOLD_COG_GATE_MM=45/65`（口径错误，§3）。

部署 env（`product/deploy/`，P1-b 落地）：

```bash
LAMP_LEAN_JSON=/etc/lampOS/body/lean-lelamp-ballast.json
LAMP_CLIP_MM=78
LAMP_LOOK_MM=72
LAMP_FOLD_BOUND_MM=78
```

配套产物（本批提交）：recordings-v2（V2 列序 20fps）、body-clips（饱和
idle 108 / wake 25 帧）、calibration（lean-lelamp{,-ballast}.json + 生成器 +
FK 验证）、tools（recordings_lelamp.py / ring40to32.py）。

## 9. 已知局限与待核

- 质量模型仍是估算（打印件 0.5g/cm³；头 180g；配重 500g @ world z5mm）。
  78/72 的余量（2.6mm / 23mm）对估算误差的容忍有限 → **⑨ 配重实际质量/位置
  上机必核**，核后重跑两个脚本再冻结门限。150×80×5.3mm 钢 ≈ 499g（7.85g/cm³）。
- ⑩ 折叠峰值电流 / T_hold 待测；⑧ wrist H1/H2 备选带与轴 sign 待上机裁决。
- 自主运动横向（cy）无独立门（§4 局限）；clip 与 idle/rest0 包络已逐帧验证，
  包络外的自主姿态由 LOOK_MM + 关节限位约束。
- lean_back 语义错位（§4）：调参按 −x 分量理解。

## 10. 复现

```bash
/tmp/lelamp-sim-venv/bin/python product/brain-sim/analysis/p0_2_cog_fix.py
/tmp/lelamp-sim-venv/bin/python product/brain-sim/analysis/p0_2_gate_probe.py
```

前者重算 P0 标题工况 + clip 门限指标（lean-FK）；后者补 idle/rest0 静态
lean_back、fold 门 bound 判定、clip 逐帧矩形 margin（MuJoCo）。JSON 原地覆盖。
