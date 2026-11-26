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

建议原型期用 ①/②，再规划 ③。待核：ElevenLabs v4_turbo 中文覆盖、Gemini 路线中文质量、国产实时语音价格。
