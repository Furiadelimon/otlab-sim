"""CLI entry point: `python -m otlab_sim run --config examples/pump_station.yaml`."""
from __future__ import annotations

import argparse
import asyncio
import logging
import time

from otlab_sim.behaviours import FaultInjector, tick_model
from otlab_sim.model import ProcessModel
from otlab_sim.modbus_server import ModbusSim
from otlab_sim.opcua_server import OpcuaSim

log = logging.getLogger("otlab_sim")


async def run(config: str, modbus_port: int, opcua_port: int, log_every_s: float) -> None:
    model = ProcessModel.from_yaml(config)
    injector = FaultInjector(model)
    modbus = ModbusSim(model, "0.0.0.0", modbus_port)
    opcua = OpcuaSim(model, "0.0.0.0", opcua_port)

    await modbus.start()
    await opcua.start()

    dt = 1.0 / model.tick_rate_hz
    start = time.monotonic()
    last_log = start
    stop_event = asyncio.Event()

    log.info("otlab-sim running. Tags: %s", ", ".join(t.name for t in model.tags))
    try:
        while not stop_event.is_set():
            now = time.monotonic()
            t = now - start
            tick_model(model, injector, t, dt)

            if injector.device_offline and modbus.running:
                await modbus.stop()
            elif not injector.device_offline and not modbus.running:
                await modbus.start()

            modbus.refresh()
            await opcua.refresh()

            if now - last_log >= log_every_s:
                last_log = now
                values = ", ".join(f"{t.name}={t.value:.2f}" if isinstance(t.value, float)
                                    else f"{t.name}={t.value}" for t in model.tags)
                log.info("[t=%.0fs] %s", t, values)

            await asyncio.sleep(dt)
    except asyncio.CancelledError:
        pass
    finally:
        await modbus.stop()
        await opcua.stop()
        log.info("otlab-sim stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="otlab_sim")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run the simulated process (Modbus TCP + OPC UA)")
    run_p.add_argument("--config", required=True, help="Path to the process YAML file")
    run_p.add_argument("--modbus-port", type=int, default=5020)
    run_p.add_argument("--opcua-port", type=int, default=4840)
    run_p.add_argument("--log-every", type=float, default=10.0, help="Seconds between value logs")
    run_p.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command == "run":
        try:
            asyncio.run(run(args.config, args.modbus_port, args.opcua_port, args.log_every))
        except KeyboardInterrupt:
            log.info("Interrupted, shutting down.")


if __name__ == "__main__":
    main()
