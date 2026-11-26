"""Lamp backends -- one seam, two implementations.

Seam contract (mirrors lelamp_runtime's service layer exactly):
    lamp.play(name)        ==  motors.dispatch("play", name)
    lamp.solid(rgb)        ==  rgb.dispatch("solid", (r, g, b))
    lamp.paint(colors)     ==  rgb.dispatch("paint", [40 x (r, g, b)])
    lamp.recordings()      ==  motors.get_available_recordings()
    lamp.motion_seconds    --  duty-cycle accounting (docs: >1 h continuous can burn servos)

SimLamp      : MuJoCo backend. Replays the project's own recordings/*.csv,
               with AnimationService semantics (interruptible queue, eased
               transition into a recording, auto-return to idle, idle loop).
               Used for development before hardware arrives.
HardwareLamp : thin wrapper around the project's AnimationService + RGBService,
               imported lazily (needs Raspberry Pi + lelamp_runtime + uv sync
               --extra hardware). UNTESTED on real hardware in this repo.

No upstream file is modified. Two export defects are repaired IN MEMORY only:
  1. robot.xml leaves a freejoint on the root body -> the lamp tips over.
  2. the base chain is exported inverted: root(column) -> j2 -> j1 -> base box
     as a LEAF, while the arm hangs root -> j3 -> j4 -> j5. Moving j1/j2 would
     swing the base instead of the arm. We re-parent: weld the base box to the
     world and hang column -> elbow -> wrist -> head off j1(yaw) -> j2(pitch),
     re-expressing each joint axis in its new declaring frame so world-space
     kinematics are unchanged at qpos=0.
Servo IDs in the model ("1".."5") map to CSV column names as SERVO_ID_MAP.
"""
from __future__ import annotations
import copy, csv, math, time
import xml.etree.ElementTree as ET
from pathlib import Path

JOINTS = ["base_yaw", "base_pitch", "elbow_pitch", "wrist_roll", "wrist_pitch"]
SERVO_ID_MAP = {"1": "base_yaw", "2": "base_pitch", "3": "elbow_pitch",
                "4": "wrist_roll", "5": "wrist_pitch"}
FPS = 30


def load_recodings(directory) -> dict:
    out = {}
    for f in sorted(Path(directory).glob("*.csv")):
        with open(f) as fh:
            rows = list(csv.DictReader(fh))
        out[f.stem] = [{(k[:-4] if k.endswith(".pos") else k): float(v)
                        for k, v in r.items() if k != "timestamp"} for r in rows]
    return out


# ---- tiny quat/transform helpers (w, x, y, z) ----
def _qmul(a, b):
    aw, ax, ay, az = a; bw, bx, by, bz = b
    return (aw*bw - ax*bx - ay*by - az*bz, aw*bx + ax*bw + ay*bz - az*by,
            aw*by - ax*bz + ay*bw + az*bx, aw*bz + ax*by - ay*bx + az*bw)


def _qinv(q):
    w, x, y, z = q
    return (w, -x, -y, -z)


def _qrot(q, v):
    w, x, y, z = q
    vx, vy, vz = v
    tx, ty, tz = 2*(y*vz - z*vy), 2*(z*vx - x*vz), 2*(x*vy - y*vx)
    return (vx + w*tx + y*tz - z*ty, vy + w*ty + z*tx - x*tz, vz + w*tz + x*ty - y*tx)


def _T(body):
    p = [float(v) for v in body.get("pos", "0 0 0").split()]
    q = [float(v) for v in body.get("quat", "1 0 0 0").split()]
    return p, q


def _compose(t1, t2):
    p1, q1 = t1; p2, q2 = t2
    r = _qrot(q1, p2)
    return ([p1[i] + r[i] for i in range(3)], _qmul(q1, q2))


def _invert(t):
    p, q = t
    qi = _qinv(q)
    r = _qrot(qi, [-v for v in p])
    return (list(r), qi)


def _setT(body, t):
    p, q = t
    body.set("pos", " ".join(f"{v:.9g}" for v in p))
    body.set("quat", " ".join(f"{v:.9g}" for v in q))


def _reparent_base(robot_xml: str) -> str:
    """Weld base box to world; restore base -> yaw(1) -> pitch(2) -> column chain."""
    root = ET.fromstring(robot_xml)
    world = root.find("worldbody")
    column = world.find("body")                                   # lamparm__base_elbow
    wrist = column.find("body[@name='lamparm__wrist_head']")
    base = wrist.find("body[@name='scs215_v5']")                   # lamp_base + cover
    elbow = column.find("body[@name='lamparm__elbow_wrist']")
    j1, j2 = base.find("joint"), wrist.find("joint")
    A, B = _T(wrist), _compose(_T(wrist), _T(base))
    new_base = copy.deepcopy(base)
    new_base.remove(new_base.find("joint"))                       # welded: no joint
    _setT(new_base, B)
    new_yaw = copy.deepcopy(wrist)
    new_yaw.remove(new_yaw.find("joint"))
    new_yaw.remove(new_yaw.find("body[@name='scs215_v5']"))
    _setT(new_yaw, _compose(_invert(B), A))
    j1n = copy.deepcopy(j1)                                       # yaw axis: was in base frame
    j1n.set("axis", " ".join(f"{v:.9g}" for v in _qrot(_T(base)[1], (0, 0, 1))))
    new_yaw.insert(0, j1n)
    new_pitch = copy.deepcopy(column)
    new_pitch.remove(new_pitch.find("freejoint"))
    for child in list(new_pitch):
        if child.tag == "body":
            new_pitch.remove(child)
    _setT(new_pitch, _invert(A))
    j2n = copy.deepcopy(j2)                                       # pitch axis: was in wrist frame
    j2n.set("axis", " ".join(f"{v:.9g}" for v in _qrot(A[1], (0, 0, 1))))
    new_pitch.insert(0, j2n)
    column.remove(elbow)
    new_pitch.append(elbow)                                       # arm subtree unchanged
    new_yaw.append(new_pitch)
    new_base.append(new_yaw)
    world.remove(column)
    world.append(new_base)
    return ET.tostring(root, encoding="unicode")


class SimLamp:
    """MuJoCo twin of the service-layer seam. Degrees in CSV -> rad in model."""

    def __init__(self, sim_dir, recordings_dir, transition_s=1.5,
                 yaw_limit_deg=90.0, duty_budget_s=3600.0):
        import mujoco, numpy as np
        self._mj, self._np = mujoco, np
        sim_dir = Path(sim_dir)
        robot = _reparent_base((sim_dir / "robot.xml").read_text())
        robot = robot[robot.index(">", robot.index("<mujoco")) + 1:robot.rindex("</mujoco>")]
        scene = (sim_dir / "scene.xml").read_text()
        scene = scene.replace('<include file="robot.xml" />', robot)
        assets = {f"assets/{p.name}": p.read_bytes() for p in (sim_dir / "assets").iterdir()}
        self.m = mujoco.MjModel.from_xml_string(scene, assets)
        self.d = mujoco.MjData(self.m)
        self.rec = load_recodings(recordings_dir)
        self.transition = max(1, int(transition_s * FPS))
        self.yaw_limit = yaw_limit_deg
        self.duty_budget = duty_budget_s
        self.motion_seconds = 0.0
        self.resting = False
        # CSV joint name -> (ctrl slot, qpos adr, range, sign)
        self.jmap = {}
        for i in range(self.m.njnt):
            sid = mujoco.mj_id2name(self.m, mujoco.mjtObj.mjOBJ_JOINT, i)
            name = SERVO_ID_MAP.get(sid)
            if name is None:
                continue
            slot = mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_ACTUATOR, sid)
            lo, hi = self.m.jnt_range[i]
            deg = [f[name] for frames in self.rec.values() for f in frames]
            fit = lambda s: sum(lo <= math.radians(s * v) <= hi for v in deg) / len(deg)
            sign = 1 if fit(1) >= fit(-1) else -1
            self.jmap[name] = (slot, self.m.jnt_qposadr[i], (lo, hi), sign)
        assert set(self.jmap) == set(JOINTS), f"joint map incomplete: {self.jmap}"
        self.state = {j: 0.0 for j in JOINTS}
        self._name, self._frames, self._idx = "idle", self.rec["idle"], 0
        self._interp_left, self._interp_from, self._interp_to = 0, None, None
        self.color, self.brightness = (255, 180, 90), 0.4
        self._mat = next((i for i in range(self.m.nmat)
                          if "diffuser" in (mujoco.mj_id2name(self.m, mujoco.mjtObj.mjOBJ_MATERIAL, i) or "")), None)
        if self._mat is not None:
            self.m.mat_emission[self._mat] = 1.0   # LED panel reads as light, not grey plastic
        for _ in range(100):
            self._apply()
            mujoco.mj_step(self.m, self.d)

    def recordings(self):
        return sorted(self.rec)

    def play(self, name):
        if name not in self.rec or self.resting:
            return
        self._name, self._frames, self._idx = name, self.rec[name], 0
        self._interp_from = dict(self.state)
        self._interp_to = self._frames[0]
        self._interp_left = self.transition

    def solid(self, rgb):
        self.color = tuple(rgb)

    def paint(self, colors):
        n = len(colors) or 1
        self.color = tuple(sum(c[i] for c in colors) // n for i in range(3))

    def rest(self):
        self.resting = True

    def wake(self):
        self.resting = False

    def tick(self):
        """Advance one 30 fps frame of the playback engine + physics."""
        if not self.resting:
            if self._interp_left > 0:
                p = 1.0 - self._interp_left / self.transition
                p = p * p * (3 - 2 * p)  # smoothstep, like AnimationService easing
                self.state = {j: self._interp_from[j] + (self._interp_to[j] - self._interp_from[j]) * p
                              for j in JOINTS}
                self._interp_left -= 1
            elif self._idx < len(self._frames):
                self.state = dict(self._frames[self._idx])
                self._idx += 1
            elif self._name != "idle":
                self.play("idle")           # auto-return, as upstream
            else:
                self._idx = 0               # idle loop, as upstream
            self.motion_seconds += 1.0 / FPS
        self._apply()
        for _ in range(3):
            self._mj.mj_step(self.m, self.d)
        if self._mat is not None:
            glow = 0.25 + 0.75 * self.brightness
            self.m.mat_rgba[self._mat][:3] = [v / 255.0 * glow for v in self.color]

    def _apply(self):
        for j, (slot, adr, (lo, hi), sign) in self.jmap.items():
            deg = self.state[j]
            if j in ("base_yaw", "wrist_roll"):   # docs: yaw servos +-90 deg from center
                deg = max(-self.yaw_limit, min(self.yaw_limit, deg))
            rad = max(lo, min(hi, math.radians(sign * deg)))
            self.d.ctrl[slot] = rad


class HardwareLamp:
    """Wraps upstream services unchanged. Run on the Pi inside lelamp_runtime."""

    def __init__(self, port="/dev/ttyACM0", lamp_id="lelamp", led_count=40, transition_s=1.5):
        from lelamp.service.motors.animation_service import AnimationService
        from lelamp.service.rgb.rgb_service import RGBService
        self._anim = AnimationService(port=port, lamp_id=lamp_id, fps=FPS, duration=transition_s)
        self._rgb = RGBService(led_count=led_count)   # 8x5 matrix = 40, not main.py's 64
        self._anim.start()
        self._rgb.start()
        self._t0 = time.monotonic()
        self.resting = False
        self.duty_budget = 3600.0   # Brain's guard reads these two on both backends
        self.brightness = 1.0       # (sim uses brightness for glow; hardware PWM owns it)

    @property
    def motion_seconds(self):
        return time.monotonic() - self._t0   # continuous-operation clock

    def recordings(self):
        return self._anim.get_available_recordings()

    def play(self, name):
        if not self.resting:
            self._anim.dispatch("play", name)

    def solid(self, rgb):
        self._rgb.dispatch("solid", tuple(rgb))

    def paint(self, colors):
        self._rgb.dispatch("paint", list(colors))

    def rest(self):
        self.resting = True
        self._rgb.dispatch("solid", (0, 0, 0))

    def wake(self):
        self.resting = False

    def tick(self):
        pass  # upstream service thread owns the 30 fps loop
