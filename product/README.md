# product/ — 净新增产品层（无上游对应）

| 目录/文档 | 职责 |
|---|---|
| `battery/` | 市电为主 + 小电池：断电检测 → 线性折叠 rest0 → 保持 T_hold → 释放 → 休眠。V2 无任何断电检测，本模块全净新增。 |
| `calibration/` | 逐灯实测配置：BODY_POSES（body 无它拒启动）、zone.env、lean/CoG JSON 重生成；含 P0-② 定稿的归一化→模型仿射映射与 rest0。 |
| `voice/` | 中文人格 + 语音路线（原型 ①Gemini/②三段式 own-keys，③国产 fork 放 P3）+ own-keys；含 P0-④ 价格调研。 |
| `brain-sim/` | 本地 Python 仿真（源自 LeLamp 工作区 brain/），零硬件验证运动包络/折叠/LED 效果。运行：`/tmp/lelamp-sim-venv/bin/python product/brain-sim/demo.py`。`analysis/` = P0-② 可复现脚本与结果。 |
| `p0-2-torque-rest.md` | **P0-② 定稿**：力矩/伸距/静息/释放/折叠/配重仿真全量结果 + fork P1 补丁清单。 |
| `integration-checklist.md` | **P0-①**：逐层复用/自写边界 + 接缝决策 + 验证清单。 |
