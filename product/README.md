# product/ — 净新增产品层（无上游对应）

| 目录 | 职责 |
|---|---|
| `battery/` | 市电为主 + 小电池：断电检测 → 调用 V2 既有 fold-to-rest → 休眠。V2 无任何断电检测，本模块全净新增。 |
| `calibration/` | 逐灯实测配置：BODY_POSES（body 无它拒启动）、zone.env、lean/CoG JSON 重生成。 |
| `voice/` | 中文人格 + 语音路线（决策中）+ own-keys。 |
| `brain-sim/` | 本地 Python 仿真（源自 LeLamp 工作区 brain/），零硬件验证运动包络/折叠/LED 效果。运行：`python3 brain-sim/demo.py`。 |
