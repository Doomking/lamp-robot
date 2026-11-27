# product/deploy — fork 部署 env（P1-b body / P1-d voice）

`lamp-body.env.example` 是 lamp-body 防倾倒门的 b500 部署值。四个开关全部
env 门控、默认 unset = 上游 V1 行为逐字节不变（`lampOS/crates/body/src/cog.rs`
的 fork 补丁）：

| 开关 | 值 | 作用 | 推导 |
|---|---|---|---|
| `LAMP_LEAN_JSON` | `/etc/lampOS/body/lean-lelamp-ballast.json` | 用本机 500 g 配重几何替换 V1 内置 body model（V1 质量 1.49 kg 是估计值，对本机偏乐观 ~1.238×） | lean-verify.md：FK 误差 0.0017 mm |
| `LAMP_CLIP_MM` | `78` | 录制/指令动作的倾倒门（替换 V1 22 mm）：覆盖 idle 起点 clip 峰值 75.4 + 2.6 裕量，且 < 80（最小退出距） | p0-2-cog-correction.md §6 |
| `LAMP_LOOK_MM` | `72` | 自主跟随/情绪的 lean-back 门（替换 V1 16 mm）：≥ idle 静态 lb 58.5、覆盖 lean_back clip 70.4，距 −x 退出界 95 留 23 | 同上 |
| `LAMP_FOLD_BOUND_MM` | `78` | **绝对**折叠门，替换相对门 max(found, folded)+0.1：idle→rest0 相对门 63.6 会误杀物理安全的 linear 折叠（峰值 74.9，margin +24.7）；78 下 linear 过、staged 84.4 拒 | 同上 §7 |

注意：

- **配重必配**。无配重（nb）时 idle 静态 margin 仅 2.1 mm、release 即倒，
  任何门限都救不了；电池兜底折叠必须 torque ON 走 linear 到 rest0 再释放
  （rest0 b500 release +29.4 安全，idle release −14.4 仍倒）。
- 设定但非法（非正有限数）= 启动 panic，不会静默回退 V1；`LAMP_LEAN_JSON`
  读不到/解析失败同样 panic。
- WARN 门自动跟随 `LAMP_CLIP_MM`（0.85×78 = 66.3）：idle/wake 从 idle 姿态播
  会触发 close 告警但仍播放，属预期。
- 验证：`product/tools/lean-gate-validate/`（两跑：V1 默认 / 本 env）。
- 实机 wrist H1/H2、轴 sign、homing 与配重质量/位置仍待 checklist ⑧⑨ 核定；
  核定后重跑 `product/calibration/gen_lean_json.py` 与 gate probe 再定门。

## lamp-voice.env.example（P1-d）

`LAMP_LOOK_PHRASES="我看看|让我看看|我看一下"`：speak_up.rs fork 补丁（env 门控，unset/空 = V1 逐字节不变）。上游 asks_to_look 按 is_alphabetic 分词（中文"我看看"=一个词）且结束符仅 ASCII → 中文 look 开头双重失败，opening 会被当普通回答读出（#1712 机制）；补丁按前缀匹配 + CJK 结束符（。！，；：、）补齐，| 分隔逐条 trim。

配套（非 env，部署时一并写）：

1. `/etc/lampOS/setup/language = zh`（上游 #4473 语言层：STT 语言、ElevenLabs flash_v2_5 中文音色、英文-only 门跟随）。
2. provider.json 加 `"instruction_file": "/etc/lampOS/voice/instruction.txt"`，内容 = `product/voice/lamp-zh.txt`（中文人格全文，名字小灯；≤16KiB UTF-8）。未配置时上游兜底 built-in 英文 character（含 Always speak English）。
3. 中文技能直接拷贝 + off 状态文件关上游对应：`product/voice/skills-zh/README.md`。
4. `LAMP_HEAD_PET=on` / `LAMP_DESK_TIME=on` 产品 service 已默认，无需重复。
5. 中文 care-lines（`LAMP_CARE_LINES_FILE` / `/etc/lampOS/voice/care-lines.json`）待写（⑫，安全台词人工审校）。
