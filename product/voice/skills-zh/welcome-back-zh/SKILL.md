---
name: welcome-back-zh
description: 有人离开至少五分钟后回到书桌，小灯转向他、灯光变暖、说一句中文短问候，认识就带名字。不打扰路过的人，不在对话中插话。
---

# 欢迎回来（中文版）

上游 `welcome-back` 的中文替换版，到桌前的那声问候。像邻座同事回来时那样：
抬头、一两个字、不多。

- **触发**：`humans/faces/tracked` 上原本没脸处出现脸，且至少五分钟没人；
  20 分钟最多一次；Policy 的 hello 门对每人每小时一次（即使 `LAMP_SKILLS_ASK=skip`
  也问）。
- **睡了一夜后**：上游 bedtime-morning 开着时，清晨第一张脸让位给它的晨间问候
  （`yields_to`）；那个机会被放弃，问候照常。
- **做**：看向脸、暖光（`lights/warm_glow.toml`）、给 voice 一条中文注记，
  只说问候和名字（若知道），一句短话。`who = true` 让注记带上谁在灯前。

简化说明：不带上游 `[present]` 的"晨间首次到桌多问一句今天先做什么"变体
（`LAMP_NUDGES_PRESENT`，默认关）。晨间问候仍由上游 bedtime-morning 负责。

部署时关掉上游 `welcome-back`（见 skills-zh/README.md），避免一次到桌两声问候。
