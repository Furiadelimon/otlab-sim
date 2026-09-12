"""Tag behaviours (how a value evolves over time) and fault injection."""
from __future__ import annotations

import math
import random
from typing import Any

from otlab_sim.model import ProcessModel, Tag


def _clamp(v: float, params: dict) -> float:
    lo = params.get("min")
    hi = params.get("max")
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def sine(tag: Tag, t: float, dt: float) -> Any:
    p = tag.behaviour
    lo = p.get("min", 0.0)
    hi = p.get("max", 100.0)
    period = p.get("period_s", 60.0)
    mid = (lo + hi) / 2
    amp = (hi - lo) / 2
    return mid + amp * math.sin(2 * math.pi * t / period)


def ramp(tag: Tag, t: float, dt: float) -> Any:
    p = tag.behaviour
    rate = p.get("rate", 1.0)  # units per second
    lo = p.get("min", float("-inf"))
    hi = p.get("max", float("inf"))
    v = tag.value + rate * dt
    if v > hi or v < lo:
        rate = -rate
        p["rate"] = rate
        v = _clamp(v, p)
    return v


def random_walk(tag: Tag, t: float, dt: float) -> Any:
    p = tag.behaviour
    step = p.get("step", 1.0)
    v = tag.value + random.uniform(-step, step)
    return _clamp(v, p)


def step(tag: Tag, t: float, dt: float) -> Any:
    p = tag.behaviour
    period = p.get("period_s", 30.0)
    low = p.get("low", 0.0)
    high = p.get("high", 1.0)
    phase = int(t // period) % 2
    return high if phase else low


def constant(tag: Tag, t: float, dt: float) -> Any:
    return tag.value


BEHAVIOURS = {
    "sine": sine,
    "ramp": ramp,
    "random_walk": random_walk,
    "step": step,
    "constant": constant,
}


class FaultInjector:
    """Applies timed faults from the scenario section on top of a tag's value.

    Faults: stuck (freezes value), spike (temporary offset), offline (device
    stops answering Modbus while active), drift (growing offset over time).
    """

    def __init__(self, model: ProcessModel):
        self.model = model
        self._active: dict[str, dict] = {}  # tag name -> fault state
        self.device_offline = False

    def update(self, t: float) -> None:
        for ev in self.model.scenario:
            if not ev.applied and t >= ev.at:
                ev.applied = True
                self._start(ev)
            if ev.applied and not ev.reverted and ev.duration_s and t >= ev.at + ev.duration_s:
                ev.reverted = True
                self._stop(ev)

    def _start(self, ev) -> None:
        self._active[ev.tag] = {"fault": ev.fault, "start": ev.at, "magnitude": ev.magnitude}
        if ev.fault == "stuck":
            tag = self.model.get(ev.tag)
            self._active[ev.tag]["frozen_value"] = tag.value
        elif ev.fault == "offline":
            self.model.get(ev.tag).offline = True
            self.device_offline = True

    def _stop(self, ev) -> None:
        self._active.pop(ev.tag, None)
        if ev.fault == "offline":
            self.model.get(ev.tag).offline = False
            self.device_offline = any(
                s["fault"] == "offline" for s in self._active.values()
            )

    def apply(self, tag: Tag, computed_value, t: float):
        state = self._active.get(tag.name)
        if not state:
            return computed_value
        fault = state["fault"]
        if fault == "stuck":
            return state["frozen_value"]
        if fault == "spike":
            return computed_value + state.get("magnitude", 0.0)
        if fault == "drift":
            elapsed = t - state["start"]
            rate = state.get("magnitude", 0.01)
            return computed_value + rate * elapsed
        return computed_value


def tick_model(model: ProcessModel, injector: FaultInjector, t: float, dt: float) -> None:
    """Advance every tag by one tick, then apply any active faults."""
    injector.update(t)
    for tag in model.tags:
        fn = BEHAVIOURS.get(tag.behaviour.get("type", "constant"), constant)
        value = fn(tag, t, dt)
        tag.value = injector.apply(tag, value, t)
