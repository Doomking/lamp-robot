# analysis/ — P0-② 可复现仿真脚本

依赖：`/tmp/lelamp-sim-venv`（mujoco + numpy）。从仓库根目录运行：

```bash
/tmp/lelamp-sim-venv/bin/python product/brain-sim/analysis/p0_2_final.py     # 力矩/伸距/CoG + rest 搜索
/tmp/lelamp-sim-venv/bin/python product/brain-sim/analysis/p0_2_release.py   # 释放/折叠/配重（读 rest_cands）
/tmp/lelamp-sim-venv/bin/python product/brain-sim/analysis/render3.py        # 映射视觉验证 → /tmp/r_*.png
/tmp/lelamp-sim-venv/bin/python product/brain-sim/analysis/p0_2_real_mass.py # 独立快查（已被 final 取代）
/tmp/lelamp-sim-venv/bin/python product/brain-sim/analysis/p0_2_cog_fix.py    # CoG 修正（mj_setConst）+ clip 门限指标
/tmp/lelamp-sim-venv/bin/python product/brain-sim/analysis/p0_2_gate_probe.py # idle/fold 门判定 + clip 逐帧 margin
```

> **2026-11-27**：final/release/real_mass 的 CoG 读数受 `body_subtreemass` 过期 bug
> 影响（xy ×0.8078，偏乐观），以 `p0_2_cog_fix.json` / `p0_2_gate_probe.json` 为准；
> 力矩/轨迹结论不受影响。详见 `../../p0-2-cog-correction.md`。

- `p0_2_final.py` → `p0_2_final_torques.json` + `p0_2_rest_cands.json`；
  `p0_2_release.py` → `p0_2_release.json`。JSON 为 2026-11-26 参考运行输出，
  重跑原地覆盖（git diff 可见）。
- `realistic_link_masses()`（p0_2_real_mass.py）被 final/release 复用：
  STL 体积×密度（打印件 0.5 g/cm³ 估算，其它塑料 1.09；舵机 55g/个；金属舵盘 2.7；PCB 1.85）。
- 全部工况 pen=0；timestep 0.01s；接触全开；重力力矩 = |qfrc_bias|/9.80665×100 kg·cm。
- `p0_2_cog_fix.py` → `p0_2_cog_fix.json`；`p0_2_gate_probe.py` → `p0_2_gate_probe.json`
  （2026-11-27 修正运行输出，重跑原地覆盖）。
- 结论文档：`../../p0-2-torque-rest.md`（P0）+ `../../p0-2-cog-correction.md`（修正）。
