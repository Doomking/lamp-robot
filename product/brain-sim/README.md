# brain/ —— 自写层骨架（语音 + 自主行为），上游零修改

分工结论：**机械 / 电气 / 运动控制复用 LeLamp 上游；语音与自主行为自己写。**
本目录用可运行代码证明这条接缝成立：同一份 `Brain` 代码，今天跑在 MuJoCo 仿真上，
硬件到货后换一行后端构造即可上机，上游仓库一个文件都不改。

## 1. 接缝契约（与 lelamp_runtime 服务层一一对应）

| brain 侧调用 | 上游等价物 | 语义 |
|---|---|---|
| `lamp.play(name)` | `motors.dispatch("play", name)` | 播放 `recordings/<name>.csv`，可打断 |
| `lamp.solid(rgb)` | `rgb.dispatch("solid", (r,g,b))` | 整屏纯色 |
| `lamp.paint(colors)` | `rgb.dispatch("paint", [40×(r,g,b)])` | 8×5=40 灯珠逐点 |
| `lamp.recordings()` | `motors.get_available_recordings()` | 动作词汇表 |
| `lamp.motion_seconds` | （自加）连续运转计时 | 占空比守卫输入 |
| `lamp.rest()/wake()` | （自加）强制冷却 | 文档：连续 >1h 可能烧舵机 |

上游 `AnimationService` 已自带、我们直接继承的语义：可打断事件队列、进入动作的缓动
插值（`duration` 参数）、播完自动回 idle、idle 循环。`SimLamp` 在仿真里复刻了同一套
语义（smoothstep 1.5s 过渡），因此仿真里调好的行为节奏上机不变。

## 2. 复用清单 vs 自写清单

**上游免费给的（不重写）：**
- 机械：STL / URDF / MuJoCo XML、5×ST3215 总线舵机方案、双电源接线文档
- 动作词汇：`recordings/*.csv`（30fps、角度制）。注意 `idle` 不是静止pose，
  而是一段 ~60s 的"环顾"循环（最大偏离均值 63.6°）——"活着"的底噪上游已经录好了
- 运动服务：AnimationService / MotorsService / RGBService（Pi 侧）
- 安全文档：yaw ±90°、连续运转时限、双电源

**自己写的（本目录）：**
- `brain.py`
  - `Intent(kind=emote|color|say)`：语音层与运动层之间唯一的数据协议
  - `VoiceAdapter` Protocol：只要求 `poll(t) -> [Intent]`。MockVoice 是脚本替身；
    换豆包 / Qwen-Omni / OpenAI Realtime / LiveKit 只需实现这一个方法，
    真实适配器从自己的线程/async 循环往队列里 push，`poll` 负责 drain
  - `Autonomy`：4s 呼吸亮度、空闲 9s 后自主 emote（scanning/curious）——
    "没人说话时也活着"的部分，开源仓库里**没有**对应代码
  - `Brain` 仲裁器：voice > autonomy > rest；语音后 6s 静默窗；占空比守卫
    （motion_seconds > 3600 → rest 300s）；全程 `.log` 可审计
- `lamp.py`
  - `SimLamp`：MuJoCo 后端（含下述两处导出缺陷的**内存内**修复）
  - `HardwareLamp`：AnimationService + RGBService(led_count=40) 的懒加载薄包装。
    **尚未上机验证**，接口与 SimLamp 完全同构
- `demo.py`：无硬件、无 API key 的端到端演示 + 六帧 montage

**为什么零上游修改：** runtime `main.py` 的三个坑（硬编码英文 prompt、`sudo -u pi`、
`RGBService(led_count=64)` 与实际 40 灯珠不符）都住在入口文件里；我们用自己的入口
替换它，`led_count=40` 走构造函数参数。 viral 视频里的"跟随/视觉"行为上游根本没有
开源代码，本来就要自写——正好落在本层。

## 3. 仿真导出缺陷（只在内存修，不改上游文件）

1. `robot.xml` 根 body 带 freejoint → 灯会翻倒。移除之，底座焊死在世界系。
2. **基座链反接**：导出树是 `root(立柱) → j2 → j1 → 底座盒(叶子)`，而手臂链是
   `root → j3 → j4 → j5`。直接驱动 j1/j2 会甩底座而不是甩手臂。`_reparent_base()`
   重排为 `底座(焊接) → j1(yaw) → j2(pitch) → 立柱 → j3 → j4 → j5`，并把每个关节轴
   重新表达到新声明坐标系，qpos=0 时世界系几何与原版完全一致。
   功能判别已验证：j1 水平旋转、j2 俯仰、j3 肘、j4/j5 腕，底座全程不动。
3. 模型关节/执行器名是 servo ID `"1".."5"`，不是 CSV 列名 → `SERVO_ID_MAP` 映射。
4. CSV 角度与模型关节方向/范围不一致（如 elbow +83° 超出 j3 范围）→ 逐关节符号自拟合
   + 范围 clamp；yaw/wrist_roll 另加文档 ±90° 限幅。
5. 灯罩 `diffuser_material` 默认灰塑料 → `mat_emission=1` + 颜色×亮度，仿真里才"看得见光"。

## 4. 运行

```bash
python3 -m venv /tmp/lelamp-sim-venv
/tmp/lelamp-sim-venv/bin/pip install mujoco numpy pillow
/tmp/lelamp-sim-venv/bin/python brain/demo.py     # 36s 仿真 → /tmp/lelamp_brain_demo.png
```

demo 脚本：8s wake_up+暖白 → 15s nod+绿 → 21s happy_wiggle+橙 → 30s 自主 curious。
截图时刻 = 意图时刻 + 1.5s 缓动 + 该动作偏离 idle 最大的帧（探针测得）。

## 5. 上机路径（硬件到货后）

1. Pi 上 `uv sync --extra hardware` 装 lelamp_runtime；串口 `/dev/ttyACM0`。
2. 入口 `from lamp import HardwareLamp; lamp = HardwareLamp(led_count=40)`，其余不变。
3. 把 `MockVoice` 换成真语音适配器（Intent.say 处接 TTS；中文 prompt 自己写）。
4. 先空载跑 idle + 单个 emote 验证方向/限幅，再放开自主行为；占空比守卫保持开启。

## 6. 许可提醒

LeLamp 主仓 GPL-3.0：衍生作品分发需同许可开源。lelamp_runtime **无 LICENSE 文件**
（默认版权保留）：本目录只调用其服务接口、并缓存了其 recordings CSV 用于仿真；
若对外分发或商用，先向作者取得书面许可。个人学习复刻风险低，但别把 runtime 代码
混进自有许可的发行物里。
