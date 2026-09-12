"""Async OPC UA server exposing the process model under one "Process" object.

Every tag becomes a child variable of the Process object. Variables are
read-only by default; a tag with `writable: true` in the YAML accepts client
writes (e.g. a pump start/stop command from an HMI under test).
"""
from __future__ import annotations

import logging

from asyncua import Server

from otlab_sim.model import ProcessModel

log = logging.getLogger("otlab_sim.opcua")

NAMESPACE_URI = "https://otlab-sim.local/process"


class OpcuaSim:
    def __init__(self, model: ProcessModel, host: str, port: int):
        self.model = model
        self.host = host
        self.port = port
        self.server: Server | None = None
        self.nodes: dict[str, object] = {}

    async def start(self) -> None:
        self.server = Server()
        await self.server.init()
        self.server.set_endpoint(f"opc.tcp://{self.host}:{self.port}/otlab-sim/")
        self.server.set_server_name("otlab-sim")
        idx = await self.server.register_namespace(NAMESPACE_URI)
        objects = self.server.get_objects_node()
        process = await objects.add_object(idx, "Process")
        for tag in self.model.tags:
            node = await process.add_variable(idx, tag.name, tag.value)
            if tag.writable:
                await node.set_writable()
            self.nodes[tag.name] = node
        await self.server.start()
        log.info("OPC UA server listening on opc.tcp://%s:%s/otlab-sim/", self.host, self.port)

    async def stop(self) -> None:
        if self.server:
            await self.server.stop()

    async def refresh(self) -> None:
        for tag in self.model.tags:
            node = self.nodes.get(tag.name)
            if node is None:
                continue
            if tag.writable:
                # allow client writes to stick between ticks: only push the
                # simulated value for read-only tags.
                continue
            await node.write_value(tag.value)
