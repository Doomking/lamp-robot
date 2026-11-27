---
name: rest-your-eyes-zh
description: 在桌前久坐（约 45 分钟）后，小灯轻轻歪头、灯光柔一档，用一句中文短话建议让眼睛歇歇、看看远处。一天最多四次，白天才说，对话中/低头读写时/夜里不说。
---

# 让眼睛歇歇（中文版）

上游 `rest-your-eyes` 的中文替换版。灯的眼睛看的是脸不是屏幕：久坐 = 在桌前
坐了很久。触发要脸持续在桌前 45 分钟（`near 0.14`，2 分钟内的离开不算断），
且 eyes 的 `sitting_s` 也满 45 分钟（换人重算）。

做：小歪头（curious，3 秒）+ 灯光柔一档 + 一句中文注记交给 voice 措辞。注记带
`{sitting}` 槽（`LAMP_DESK_TIME=on` 时填入实测久坐时长，voice 被追问"我坐多久了"
时口径一致）——该槽只对 core 技能填充，所以本技能 `kind = "core"`，经直接拷贝
部署（不在 build 的 PRODUCT_SKILLS 里，sync-skills.sh / lamp-update install 都不碰）。

预算：wellbeing 组每小时一次；连续两次没人理会歇到明早；一天最多四次。
`[stop]` 共享上游 `wellbeing_nudges` 函数（同 wellbeing 组），about/when 保持
英文原文以免共享描述分叉；说"别提醒我歇眼睛"仍能停掉它。

部署时关掉上游 `rest-your-eyes`（见 skills-zh/README.md）。上游 sip-of-water /
stretch-break / comfort-break 保留（注记英文，voice 按中文人格仍说中文）。
