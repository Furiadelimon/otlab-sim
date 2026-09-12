# otlab-sim

Test your SCADA/HMI/OPC UA gateway against realistic simulated field devices in 60 seconds. One YAML, Modbus TCP + OPC UA, fault injection.

otlab-sim is an OT/industrial lab-in-a-box for SCADA/HMI integrators. From a single YAML file describing a process (tags, units, behaviours), it exposes the *same* simulated process simultaneously as a Modbus TCP server and an OPC UA server, with a scenario engine that moves values realistically over time and can inject timed faults — so you can test a gateway, HMI screen, or historian connector without any physical hardware on the bench.

## Quickstart

### Docker

```bash
docker compose up --build
```

This starts the bundled `examples/pump_station.yaml` process on Modbus TCP port `5020` and OPC UA port `4840`.

### Local (pip)

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m otlab_sim run --config examples/pump_station.yaml --modbus-port 5020 --opcua-port 4840
```

Press Ctrl+C to stop; both servers shut down cleanly.

## YAML reference

```yaml
tick_rate_hz: 2          # how often (Hz) the simulation updates values

tags:
  - name: tank_level      # unique tag name, also used as the OPC UA variable name
    type: float32         # int16 | uint16 | float32 | bool
    unit: "%"             # free-text, informational only
    address: 0            # Modbus register (or coil, for bool) address
    initial: 50.0         # starting value
    writable: false       # if true, OPC UA clients may write this variable
    behaviour:
      type: sine           # sine | ramp | random_walk | step | constant
      min: 0
      max: 100
      period_s: 600         # sine/step: seconds per full cycle
      rate: 1.0              # ramp: units/second
      step: 1.5               # random_walk: max change per tick

scenario:                  # optional timed faults, evaluated against elapsed
                            # simulation time (seconds since start)
  - at: 120                 # inject at t=120s
    tag: pressure
    fault: spike             # stuck | spike | offline | drift
    magnitude: 3.0
    duration_s: 15
```

Fault types:

- **stuck** — the tag's value freezes at whatever it was when the fault started.
- **spike** — a fixed offset (`magnitude`) is added to the tag's normal value for the duration.
- **drift** — an offset that grows linearly (`magnitude` units/second) for the duration.
- **offline** — the Modbus TCP listener is stopped for the duration, simulating a device that has genuinely dropped off the bus (connections are refused, not just stale).

## Register map

- `float32` tags occupy **2 holding registers** at `address` and `address+1`, big-endian (high word first, then low word) — the common "ABCD" Modbus float encoding.
- `int16` / `uint16` tags occupy **1 holding register** at `address`.
- `bool` tags occupy **1 coil** at `address` (not a holding register bit).

The bundled `examples/pump_station.yaml` documents its own map in a header comment.

## Roadmap

- More built-in behaviours (PID-following, correlated multi-tag noise)
- A YAML schema validator with helpful error messages
- Prometheus metrics endpoint for the simulator itself
- Optional TLS for OPC UA

## Pro scenario packs and custom plants

The core simulator is free (MIT) and will stay that way. Two paid layers are planned so the project can sustain itself:

**Pro scenario pack** (planned one-time purchase, ~39 EUR/USD, no subscription):
- Multi-device plants (several coordinated Modbus/OPC UA endpoints modeling one site)
- IEC 62443-flavored anomaly scenarios for security/resilience testing
- A CI/CD test harness for running gateway regression tests against otlab-sim in a pipeline
- Integration guides for WinCC, Ignition, and Node-RED

**Custom simulated plant for your project** (fixed-price service): send us your register map / tag list and we deliver a ready-to-run otlab-sim configuration that mirrors your devices, so your SCADA/HMI team can integrate before hardware arrives.

Interested in either? Please open an issue with the `pro-interest` label or comment on the pinned issue. That is how we decide what to build first. No payment is possible yet; nothing is sold until it exists.

## Known limitations

- Single-slave Modbus context only (unit id 1); no multi-device Modbus simulation yet.
- OPC UA writes to `writable` tags are accepted but not validated against type/range.
- No persistence: restarting the process resets all tag values to their YAML `initial`.

## License

MIT, see [LICENSE](LICENSE).
