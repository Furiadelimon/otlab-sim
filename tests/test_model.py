import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from otlab_sim.behaviours import FaultInjector, random_walk, sine, tick_model
from otlab_sim.model import ProcessModel, decode_float32, encode_float32

EXAMPLE_YAML = os.path.join(os.path.dirname(__file__), "..", "examples", "pump_station.yaml")


def test_load_yaml_produces_expected_tags():
    model = ProcessModel.from_yaml(EXAMPLE_YAML)
    names = {t.name for t in model.tags}
    assert "tank_level" in names
    assert "pump1_running" in names
    assert model.get("tank_level").type == "float32"
    assert model.get("pump1_running").type == "bool"


def test_float32_register_roundtrip():
    for value in (0.0, 1.5, -42.75, 100.0, 3.140625):
        hi, lo = encode_float32(value)
        assert 0 <= hi <= 0xFFFF and 0 <= lo <= 0xFFFF
        assert decode_float32(hi, lo) == value


def test_sine_behaviour_stays_within_bounds():
    model = ProcessModel.from_yaml(EXAMPLE_YAML)
    tag = model.get("tank_level")
    for t in range(0, 1200, 10):
        v = sine(tag, t, 0.5)
        assert tag.behaviour["min"] - 1e-6 <= v <= tag.behaviour["max"] + 1e-6


def test_random_walk_changes_value_within_step():
    model = ProcessModel.from_yaml(EXAMPLE_YAML)
    tag = model.get("inlet_flow")
    before = tag.value
    tag.value = random_walk(tag, 1.0, 0.5)
    assert abs(tag.value - before) <= tag.behaviour["step"] + 1e-9


def test_stuck_fault_freezes_value():
    model = ProcessModel.from_yaml(EXAMPLE_YAML)
    injector = FaultInjector(model)
    tag = model.get("tank_level")

    tick_model(model, injector, t=299.0, dt=0.5)  # before the fault starts
    tick_model(model, injector, t=300.0, dt=0.5)  # fault activates, freezes value
    frozen = tag.value
    for t in (305, 320, 350):
        tick_model(model, injector, t=t, dt=0.5)
        assert tag.value == frozen
    tick_model(model, injector, t=361.0, dt=0.5)  # duration elapsed, unfreezes
    assert model.get(tag.name).offline is False
