# voice — 中文人格 + 语音路线（决策中）

## 人格（P1-d 已交）
- **中文人格 = `lamp-zh.txt`（本目录，名字「小灯」）**：部署到 `/etc/lampOS/voice/instruction.txt`，并在 voice provider.json 加 `"instruction_file"` 字段指向它（read_private ≤16KiB UTF-8）。产品 `deploy/product/settings/voice-provider.json` 原无此字段 → fork 部署时添加。
- 英文规则有**两处**：built-in CHAT_INSTRUCTION / CAMERA_CHAT_INSTRUCTION（config.rs，仅 instruction_file 未配置时兜底）+ shipped `lamp.txt` 首条 "Always speak English"。instruction_file 覆盖后两者均不生效，**无需改上游文件**。
- **上游已有中文语言层（#4473）**：`/etc/lampOS/setup/language` 写 `zh` → STT 语言、ElevenLabs `eleven_flash_v2_5` 中文音色、英文-only 门跟随；character 不含 "Always speak English" 时自动追加中文规则（与 lamp-zh.txt 一致无冲突）。**部署两者都要**：language=zh + instruction_file。
- **中文技能 `skills-zh/`（3 个）直接拷贝部署 + off 状态文件关上游对应**，不走 sync-skills（它只同步 PRODUCT_SKILLS、永不读写用户文件夹；rest-your-eyes-zh 是 core 本就不能 install）。详见 `skills-zh/README.md`。
- **look 开头中文补丁（speak_up.rs，env 门控）**：上游 asks_to_look 按 is_alphabetic 分词（中文"我看看"=一个词）且结束符仅 ASCII → 中文 look 开头双重失败，opening 被当普通回答读出（#1712 机制）。fork 补丁 `LAMP_LOOK_PHRASES="我看看|让我看看|我看一下"` 前缀匹配 + CJK 结束符；unset/空 = V1 逐字节不变。部署见 `../deploy/lamp-voice.env.example`。
- **中文 care-lines 待写（⑫）**：上游 shipped 英文兜底（`LAMP_CARE_LINES_FILE` / `/etc/lampOS/voice/care-lines.json`）；安全相关台词需人工审校，不机翻。

## 路线（lampOS/crates/voice/src/coordinator/second.rs）
- `LAMP_VOICE_ROUTE` 缺省/`gemini` = Gemini Live（默认）；`second` = 产品三段式 Deepgram STT → DeepSeek LLM → ElevenLabs TTS（需 LAMP_VOICE_SECOND_CONFIG）。合法值仅 gemini|second。
- `LAMP_OWN_KEYS=on` → DeepSeek+Deepgram+ElevenLabs 全自有 key，零 relay 依赖。

## 麦克风（已定，2026-11-26）
锁定上游拓扑：**杰理双麦 ENC（48kHz mono）+ C-Media USB 适配器**，采集 16kHz（`lampOS/docs/hardware.md`）。弃 LeLamp ReSpeaker Hat。

## 待决策（用户在中国）
1. **Gemini Live own-key**：最快，但 Google 国内访问风险；
2. **产品三段式 own-keys**：DeepSeek 国内 OK，Deepgram/ElevenLabs 海外弱链；
3. **国产全栈 fork**：国内访问最佳、改动最深，放 P3。

建议原型期用 ①/②，再规划 ③（国产 flash 级成本已探明 ~1 元/h 量级，见下）。

## 调研更新（2026-11-26，P0-④）
- **ElevenLabs v4_turbo**（2026-09 发布）：官方称 Mandarin 为改进最大的语言之一，90+ 语言，TTFB ~150ms → "中文覆盖"基本关闭，**中文音质盲听仍待核**。
- **阿里云百炼（北京官方价）**：
  - `qwen-audio-3.1-realtime-flash`：音频输入 6 元/M tok、输出 12 元/M tok；音频 tok≈秒×12.5 → 纯音频 ≈0.27 元/h（入）+ 0.54 元/h（出），另计上下文累积；文本 in 40 / out 150 元/M tok → 1.8 / 6.75 元/h。**按活跃对话计费，适合台灯**。
  - `qwen-audio-3.1-live`：0.00333 元/秒 ≈ **12 元/h，空闲也计费** → 常开台灯不划算；免费额度 36000s。
  - `qwen3.8-omni-flash-realtime` 存在，价格待核。
- **豆包端到端实时**：2025 年 PDF 引用 34.74 / 9.00 元/h（旧价，**待核现价**；volc conversation-ai-billing 页存在）。
- 结论：③ 国产 fork 的成本论据增强（flash 级 ~1 元/h 活跃对话）；原型期仍 ①/②。

## 待核（更新）
② ElevenLabs/Gemini 中文音质盲听；③ Gemini 国内连通性；④ 豆包实时现价；qwen3.8-omni-flash-realtime 价格；⑪ near-call 中文名「小灯」（声学呼叫 rise dB/窗口 + STT 转写，language=zh 后待实测）；⑫ 中文 care-lines 人工审校。
