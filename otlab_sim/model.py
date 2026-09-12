"""Process model: loads a YAML definition into an in-memory list of Tags."""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any

import yaml

VALID_TYPES = {"int16", "uint16", "float32", "bool"}


@dataclass
class Tag:
    name: str
    type: str
    address: int
    initial: Any
    unit: str = ""
    behaviour: dict = field(default_factory=lambda: {"type": "constant"})
    writable: bool = False
    value: Any = None
    offline: bool = False  # set by the "offline" fault; server stops answering

    def __post_init__(self) -> None:
        if self.type not in VALID_TYPES:
            raise ValueError(f"tag {self.name}: unknown type {self.type!r}")
        if self.value is None:
            self.value = self.initial

    def register_width(self) -> int:
        """Number of 16-bit Modbus registers this tag occupies (bools use coils)."""
        return 2 if self.type == "float32" else 1


@dataclass
class ScenarioEvent:
    at: float
    tag: str
    fault: str
    duration_s: float = 0.0
    magnitude: float = 0.0
    applied: bool = False
    reverted: bool = False


@dataclass
class ProcessModel:
    tags: list[Tag]
    scenario: list[ScenarioEvent]
    tick_rate_hz: float = 2.0

    def get(self, name: str) -> Tag:
        for t in self.tags:
            if t.name == name:
                return t
        raise KeyError(name)

    @classmethod
    def from_yaml(cls, path: str) -> "ProcessModel":
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        tags = [Tag(**t) for t in raw.get("tags", [])]
        scenario = [ScenarioEvent(**s) for s in raw.get("scenario", [])]
        tick_rate = float(raw.get("tick_rate_hz", 2.0))
        return cls(tags=tags, scenario=scenario, tick_rate_hz=tick_rate)


def encode_float32(value: float) -> tuple[int, int]:
    """Encode a float as two big-endian 16-bit Modbus registers (hi, lo)."""
    raw = struct.pack(">f", value)
    hi, lo = struct.unpack(">HH", raw)
    return hi, lo


def decode_float32(hi: int, lo: int) -> float:
    """Decode two big-endian 16-bit Modbus registers back into a float."""
    raw = struct.pack(">HH", hi, lo)
    return struct.unpack(">f", raw)[0]


def encode_int(value: int, signed: bool) -> int:
    """Encode a python int as an unsigned 16-bit register value."""
    if signed and value < 0:
        return value + 0x10000
    return value & 0xFFFF
