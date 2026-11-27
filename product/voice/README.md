# voice — 中文人格 + 语音路线（决策中）

## 人格
- 载体 = 纯文本 `lampOS/deploy/character/lamp.txt`（经 instruction_file 注入，部署到 /etc/lampOS/voice/instruction.txt）。
- ⚠️ 上游第一条规则硬编码 **"Always speak English, whatever language you hear"** → 中文化必须移除。
- 中文人格在本目录重写，经部署脚本下发；自有技能放 `lampOS/skills/`（SKILL.md + skill.toml），用 `lampOS/deploy/sync-skills.sh` 部署（默认 dry-run，--apply 生效，原子改名热加载，永不删用户技能）。

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
② ElevenLabs/Gemini 中文音质盲听；③ Gemini 国内连通性；④ 豆包实时现价；qwen3.8-omni-flash-realtime 价格。
