# lean-gate-validate（P1-b 门限验证）

独立小 crate（不在 lampOS workspace 内），path 依赖 `lampOS/crates/lean` 与
`lampOS/crates/body`，把 fork 的 env 门控防倾倒规则对着 P0-2 修正后的数值跑一遍：

- 两份 lean JSON（`product/calibration/lean-lelamp{,-ballast}.json`）的 rest0 / idle
  off-axis 与 lean-back，对照 `product/brain-sim/analysis/p0_2_gate_probe.json`
  （MuJoCo + mj_setConst 修正值，容差 0.12 mm：probe  rounding 0.1 + FK 0.0017）。
- `cog::clip_mm()/look_mm()/fold_bound_mm()` 在两种进程环境下的取值：
  - **不设任何 `LAMP_*`**：V1 默认 22 / 16 / 相对门原样透传；V1 lamp-4ace rest
    读数 17.851 mm（cog.rs 自带测试同值）。
  - **b500 部署 env**（见 `product/deploy/lamp-body.env.example`）：78 / 72 /
    绝对门 78 覆盖相对门 63.6；cog 经 `LAMP_LEAN_JSON` 读 ballast JSON 后
    rest0 45.3 / 40.0、idle 63.5 / 58.5；idle→rest0 linear 折叠峰值 74.9 过 78、
    被相对门 63.6 误杀的事实复现。

cog 的环境是 `LazyLock` 每进程读一次，所以**必须跑两个进程**：

```sh
cd product/tools/lean-gate-validate
CARGO_TARGET_DIR=/tmp/lamp-target cargo +1.97.0 run --release          # V1 默认
env LAMP_LEAN_JSON="$PWD/../../calibration/lean-lelamp-ballast.json" \
    LAMP_CLIP_MM=78 LAMP_LOOK_MM=72 LAMP_FOLD_BOUND_MM=78 \
    CARGO_TARGET_DIR=/tmp/lamp-target cargo +1.97.0 run --release      # b500 部署
```

两跑都以 `ALL OK` 结束。工具链 ≥1.91（edition 2024）；lampOS 的
rust-toolchain.toml 钉 1.96.0，本机未装时用 `+1.97.0` 显式覆盖（本 crate 在
lampOS 之外，不受其 toolchain 文件约束）。首次构建需网络拉 glam/sha2 等。

上游回归：`cd lampOS && CARGO_TARGET_DIR=/tmp/lamp-target cargo +1.97.0 test -p lamp-body`
（env 全 unset → 所有门与消息逐字节回到 V1，含 cog 自带测试与新增
`fork_overrides_default_to_v1_and_refuse_a_bad_value`）。
