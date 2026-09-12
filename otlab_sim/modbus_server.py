"""Async Modbus TCP server exposing the process model.

Layout: float32 tags -> 2 holding registers (big-endian, hi then lo) at
`address`; int16/uint16 tags -> 1 holding register; bool tags -> 1 coil.
The "offline" fault is simulated by shutting the TCP listener down for the
fault's duration, so the device genuinely stops answering Modbus requests.
"""
from __future__ import annotations

import asyncio
import logging

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.server import ServerAsyncStop, StartAsyncTcpServer

from otlab_sim.model import ProcessModel, encode_float32, encode_int

log = logging.getLogger("otlab_sim.modbus")


def build_context(model: ProcessModel) -> ModbusServerContext:
    max_hr = max((t.address + t.register_width() for t in model.tags if t.type != "bool"), default=1)
    max_co = max((t.address + 1 for t in model.tags if t.type == "bool"), default=1)
    holding = ModbusSequentialDataBlock(0, [0] * max(max_hr, 1))
    coils = ModbusSequentialDataBlock(0, [0] * max(max_co, 1))
    slave = ModbusSlaveContext(hr=holding, co=coils, di=coils, ir=holding)
    return ModbusServerContext(slaves=slave, single=True)


def write_tags(context: ModbusServerContext, model: ProcessModel) -> None:
    slave = context[0]
    for tag in model.tags:
        if tag.type == "bool":
            slave.setValues(1, tag.address, [1 if tag.value else 0])
        elif tag.type == "float32":
            hi, lo = encode_float32(float(tag.value))
            slave.setValues(3, tag.address, [hi, lo])
        else:  # int16 / uint16
            slave.setValues(3, tag.address, [encode_int(int(tag.value), tag.type == "int16")])


class ModbusSim:
    """Owns the pymodbus server lifecycle so it can be stopped/restarted
    on demand (used to simulate the "offline" fault)."""

    def __init__(self, model: ProcessModel, host: str, port: int):
        self.model = model
        self.host = host
        self.port = port
        self.context = build_context(model)
        self._task: asyncio.Task | None = None
        self.running = False

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(
            StartAsyncTcpServer(context=self.context, address=(self.host, self.port))
        )
        await asyncio.sleep(0.1)  # let the listener bind
        log.info("Modbus TCP server listening on %s:%s", self.host, self.port)

    async def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        try:
            await ServerAsyncStop()
        except Exception:  # pragma: no cover - defensive, server may differ
            pass
        if self._task:
            self._task.cancel()
        log.info("Modbus TCP server stopped (offline fault or shutdown)")

    def refresh(self) -> None:
        """Push current model values into the datastore, unless offline."""
        if not self.running:
            return
        write_tags(self.context, self.model)
