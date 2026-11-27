# skills-zh — 中文替换技能（P1-d，净新增）

三个中文技能，替换上游对应技能的**台词/注记**；触发、门控、预算、stop 语义逐条保持上游。

| 本目录 | 替换上游 | kind | 差异 |
|---|---|---|---|
| `head-pat-zh` | `head-pat` | installable | 7 条中文固定台词（priority 8 / expires 3s，即时反应）；门控同上游 |
| `welcome-back-zh` | `welcome-back` | installable | 中文 say 注记（expires 60s，who=true）；**删 [present]**（晨间首次问候变体归上游 bedtime-morning）；yields_to bedtime-morning 保留 |
| `rest-your-eyes-zh` | `rest-your-eyes` | **core** | 中文注记带 `{sitting}`；[budget]/[stop] 与上游共享 wellbeing 组，about/when **保持上游英文原文** |

## 为什么 rest-your-eyes-zh 必须是 core

`{sitting}` 槽只对 **core** 技能填充（`lampOS/docs/skills.md` #7694：core + `[permissions] topics` 含 `room/activity` + `LAMP_DESK_TIME=on`；产品 service 默认 on，见 `deploy/product/lamp-skills.service`）。installable 技能里写 `{sitting}` 会被丢弃。

core 技能**不能**经 `lamp-skills install` / Store 安装（`crates/skills/src/package.rs`："a core skill comes with the lamp, never from a folder or a package"）→ 只能直接拷贝文件夹部署。

## 为什么 [stop] 的 about/when 保持英文原文

`[stop]` 是 wellbeing 组的**共享函数**（`lib.rs`：同 `[budget] group` 或同 `[stop]` 可共享，组内第一个文件夹说了算）。rest-your-eyes-zh 与上游 sip-of-water / stretch-break 等同组；about/when 逐字一致 → 无论哪个文件夹先注册、无论上游技能 off 与否，模型看到的函数描述都不分叉。只有 say 注记中文化。

## 部署（直接拷贝，不走 sync-skills）

`sync-skills.sh` 只同步 build 的 `install::PRODUCT_SKILLS`，**永不读写用户文件夹**（脚本头注："a folder the build doesn't name … is never read or written"）。本目录技能不在 PRODUCT_SKILLS → sync-skills 部署不了它们，也不会覆盖/删除它们。

1. **拷贝三个文件夹**到 `/var/lib/lampOS/skills/`（0755 目录 / 0644 文件）：

   ```sh
   sudo cp -R head-pat-zh welcome-back-zh rest-your-eyes-zh /var/lib/lampOS/skills/
   sudo find /var/lib/lampOS/skills/head-pat-zh /var/lib/lampOS/skills/welcome-back-zh /var/lib/lampOS/skills/rest-your-eyes-zh -type d -exec chmod 0755 {} +
   sudo find /var/lib/lampOS/skills/head-pat-zh /var/lib/lampOS/skills/welcome-back-zh /var/lib/lampOS/skills/rest-your-eyes-zh -type f -exec chmod 0644 {} +
   ```

   lamp-skills 自己热重载文件夹（原子改名即可见）。

2. **关掉上游对应技能**（避免中英双份台词）：把名字逐行写入 off 状态文件——

   ```sh
   printf 'head-pat\nwelcome-back\nrest-your-eyes\n' | sudo tee -a /var/lib/lampos-skills-state/off
   ```

   这是**持久且正确**的机制：`OFF_FILE="off"`（`lib.rs:566`），engine 启动读取（`keep_off_in`）、运行中热重载、跨重启保持；sync-skills **永不写 lamp-skills 状态**。
   ⚠️ 只改 installed skill.toml `enabled=false` 不够：对 build shipped-on 的技能，`sync-skills.sh --apply` 会按 build 文件改回（脚本只保护 shipped-off 技能的用户修改）。off 状态文件才是人的最后选择。

3. **重启读文件夹的部件**：`lamp-voice`、`lamp-expression`（lamp-skills 自己重载）。检查 journal 无 "skill.toml: No such file"。

## 保留上游不动的技能

- `head-pat-wiggle`：摸头后的底座开心扭动，**无台词** → 保留（与 head-pat-zh 配合）。
- `bedtime-morning`：晨间/睡前问候（welcome-back-zh 的 yields_to 对象）。
- `sip-of-water` / `stretch-break` / `comfort-break`：wellbeing 组其余成员，台词暂保留英文（中文化后续批次；[stop] 共享描述已对齐）。

## 必需开关（产品 service 已默认 on）

- `LAMP_HEAD_PET=on`（lamp-controls）：`controls/pet` 话题才有摸头事件 → head-pat-zh 触发源。
- `LAMP_DESK_TIME=on`（lamp-skills + lamp-voice）：`{sitting}` 槽填充。
- `LAMP_SKILLS_ASK`：产品默认 skip；welcome-back-zh 的 `[ask] policy="hello"` 即使 skip 也问 Policy（上游语义）。

## 待核

- near-call 中文名「小灯」：声学呼叫检测（rise dB/窗口）+ STT 转写；`/etc/lampOS/setup/language=zh` 后待实测（voice/README.md ⑪）。
- 台词自然度盲听（与 ② 中文音质盲听同批）。
