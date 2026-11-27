"""Run the self-written layer against the project's MuJoCo model + recordings.

    /tmp/lelamp-sim-venv/bin/python product/brain-sim/demo.py

No hardware, no API keys: MockVoice stands in for the realtime voice adapter.
Renders a 6-frame montage to /tmp/lelamp_brain_demo.png.
"""
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lamp import SimLamp
from brain import Brain, MockVoice, Intent, Autonomy

SIM = HERE.parents[1] / "hardware" / "simulation"   # lamp-robot monorepo layout

script = [
    (8.0,  Intent("emote", name="wake_up")),
    (8.0,  Intent("color", rgb=(255, 240, 210))),
    (8.2,  Intent("say", text="Someone's home! Hello.")),
    (15.0, Intent("emote", name="nod")),
    (15.0, Intent("color", rgb=(120, 255, 160))),
    (21.0, Intent("emote", name="happy_wiggle")),
    (21.0, Intent("color", rgb=(255, 170, 60))),
]

lamp = SimLamp(SIM, HERE / "recordings", transition_s=1.5)
brain = Brain(lamp=lamp, voice=MockVoice(script), autonomy=Autonomy(idle_gap_s=9.0))

import mujoco
mujoco.mj_forward(lamp.m, lamp.d)
lamp.m.vis.global_.offwidth = 1920
lamp.m.vis.global_.offheight = 1440
r = mujoco.Renderer(lamp.m, 720, 960)
cam = mujoco.MjvCamera()
cam.distance, cam.azimuth, cam.elevation, cam.lookat = 1.35, 135, -12, [0, 0, 0.28]

# shot times = playback start (intent + 1.5 s ease-in) + peak-deviation frame
shots = {int(round(s * 30)): lab for s, lab in [(2.0, "idle breath"), (9.7, "wake_up"), (18.0, "nod"), (24.6, "happy_wiggle"), (29.5, "back to idle"), (34.1, "autonomy curious")]}
frames, labels = [], []
T = 36.0
t = 0.0
while t < T:
    brain.tick(t)
    k = int(round(t * 30))
    if k in shots:
        r.update_scene(lamp.d, camera=cam)
        frames.append(r.render())
        labels.append(shots[k])
    t += 1 / 30

for ts, msg in brain.log:
    print(f"{ts:6.2f}s  {msg}")
print("motion_seconds:", round(lamp.motion_seconds, 1))

from PIL import Image, ImageDraw, ImageFont
font = ImageFont.load_default(size=30)
labelled = []
for fr, lab in zip(frames, labels):
    img = Image.fromarray(fr)
    bar = Image.new("RGB", (img.width, 48), (16, 20, 26))
    ImageDraw.Draw(bar).text((14, 8), lab, font=font, fill=(235, 235, 235))
    labelled.append(np.concatenate([np.asarray(img), np.asarray(bar)], axis=0))
rows = [np.concatenate(labelled[i:i + 2], axis=1) for i in (0, 2, 4)]
Image.fromarray(np.concatenate(rows, axis=0)).save("/tmp/lelamp_brain_demo.png")
print("saved /tmp/lelamp_brain_demo.png", labels)
