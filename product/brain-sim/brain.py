"""The self-written layer: voice adapter + autonomous behavior + arbitration.

Upstream gives us the body and the reflex arc (services, recordings, idle loop).
This module is the part the open-source repo does NOT contain:
  * VoiceAdapter  -- plug in Doubao / Qwen-Omni / OpenAI realtime, or LiveKit.
                     It only has to emit Intents; it never touches motors.
  * Autonomy      -- breathing light, idle curiosity, proactive reminders.
                     Expresses itself ONLY through the seam (play/solid),
                     so the same code runs on SimLamp and HardwareLamp.
  * Brain         -- arbiter: voice > autonomy > rest; duty-cycle guard.
"""
from __future__ import annotations
import math, random
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Intent:
    kind: str                      # "emote" | "color" | "say"
    name: str = ""                 # recording name for emote
    rgb: tuple = (255, 255, 255)   # for color
    text: str = ""                 # for say (TTS swap point on hardware)


class VoiceAdapter(Protocol):
    def poll(self, t: float) -> list[Intent]:
        """Return intents due at sim/wall time t. Real adapters push from their
        own thread/async loop into a queue; poll() drains it."""
        ...


class MockVoice:
    """Scripted stand-in so the whole loop runs before any API key exists."""

    def __init__(self, script):
        self.script = sorted(script, key=lambda e: e[0])
        self.i = 0

    def poll(self, t):
        out = []
        while self.i < len(self.script) and self.script[self.i][0] <= t:
            out.append(self.script[self.i][1])
            self.i += 1
        return out


class Autonomy:
    """'Alive when nobody talks to it' -- the lampOS idle-mode idea, seam-only."""

    def __init__(self, idle_gap_s=12.0, emotes=("scanning", "curious"), seed=7):
        self.idle_gap = idle_gap_s
        self.emotes = emotes
        self.rng = random.Random(seed)
        self.last_emote = 0.0

    def brightness(self, t, voice_active):
        if voice_active:
            return 1.0
        return 0.35 + 0.20 * (0.5 + 0.5 * math.sin(2 * math.pi * t / 4.0))  # 4 s breath

    def maybe_emote(self, t, last_voice_t):
        if t - last_voice_t > self.idle_gap and t - self.last_emote > self.idle_gap:
            self.last_emote = t
            return self.rng.choice(self.emotes)
        return None


@dataclass
class Brain:
    lamp: object
    voice: VoiceAdapter
    autonomy: Autonomy = field(default_factory=Autonomy)
    voice_window_s: float = 6.0     # autonomy stays quiet this long after voice
    rest_s: float = 300.0           # forced cool-down after duty budget
    log: list = field(default_factory=list)
    _last_voice: float = -1e9
    _rest_until: float = -1e9

    def tick(self, t):
        lamp = self.lamp
        # duty-cycle guard (docs: >1 h continuous operation can burn servos)
        if not lamp.resting and lamp.motion_seconds > lamp.duty_budget:
            lamp.rest()
            self._rest_until = t + self.rest_s
            self.log.append((t, "REST: duty budget reached, cooling down"))
        if lamp.resting:
            if t >= self._rest_until:
                lamp.wake()
                self.log.append((t, "WAKE: rest finished"))
            else:
                lamp.brightness = 0.08
                lamp.tick()
                return
        for intent in self.voice.poll(t):
            self._last_voice = t
            if intent.kind == "emote":
                lamp.play(intent.name)
                self.log.append((t, f"voice -> emote {intent.name}"))
            elif intent.kind == "color":
                lamp.solid(intent.rgb)
                self.log.append((t, f"voice -> color {intent.rgb}"))
            elif intent.kind == "say":
                self.log.append((t, f"say: {intent.text}"))  # TTS swap point
        voice_active = t - self._last_voice < self.voice_window_s
        if not voice_active:
            emote = self.autonomy.maybe_emote(t, self._last_voice)
            if emote:
                lamp.play(emote)
                self.log.append((t, f"autonomy -> emote {emote}"))
        lamp.brightness = self.autonomy.brightness(t, voice_active)
        lamp.tick()
