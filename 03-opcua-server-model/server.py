"""
OPC UA server with a real information model, not a flat list of tags.

Address space (browse it with UaExpert or with example 04):

  Objects
  └── Plant
      └── Line1
          └── Filler01                      (object, type FillerType)
              ├── State          String      IDLE / RUNNING / FAULTED
              ├── Speed          Double      bottles/min   (EngineeringUnits, EURange)
              ├── GoodCount      UInt32
              ├── RejectCount    UInt32
              ├── Temperature    Double      degC
              ├── Setpoints
              │   └── TargetSpeed Double     writable
              ├── Start()        method
              ├── Stop()         method
              └── ResetCounters() method

Concepts: object types, folders, typed variables, engineering units,
writable vs read-only, methods with server-side validation.

Run:  python 03-opcua-server-model/server.py
"""
import asyncio
import logging
import math
import os
import random

from asyncua import Server, ua
from asyncua.common.methods import uamethod

ENDPOINT = os.getenv("OPCUA_ENDPOINT", "opc.tcp://0.0.0.0:4841/iiot-examples/")
NS_URI = "urn:iiot-protocols-examples:plant"

# UNECE codes used by OPC UA EUInformation (Part 8)
UNIT_PER_MIN = ("bottles/min", "per minute", 4405556)   # UNECE "C94" (reciprocal minute)
UNIT_DEGC = ("°C", "degree Celsius", 4408652)          # UNECE "CEL"


def eu(display, desc, code):
    return ua.EUInformation(NamespaceUri="http://www.opcfoundation.org/UA/units/un/cefact",
                            UnitId=code, DisplayName=ua.LocalizedText(display),
                            Description=ua.LocalizedText(desc))


async def add_analog(parent, idx, name, value, unit, lo, hi):
    """AnalogItemType variable with EngineeringUnits and EURange properties."""
    var = await parent.add_variable(idx, name, value, varianttype=ua.VariantType.Double,
                                    datatype=ua.NodeId(ua.ObjectIds.Double))
    await var.add_property(0, "EngineeringUnits", eu(*unit))
    await var.add_property(0, "EURange", ua.Range(Low=lo, High=hi))
    return var


async def build(server: Server):
    idx = await server.register_namespace(NS_URI)

    # A reusable object type: every filler in the plant would share it
    filler_type = await server.nodes.base_object_type.add_object_type(idx, "FillerType")

    plant = await server.nodes.objects.add_folder(idx, "Plant")
    line = await plant.add_folder(idx, "Line1")
    filler = await line.add_object(idx, "Filler01", objecttype=filler_type.nodeid)

    v = {
        "State": await filler.add_variable(idx, "State", "IDLE"),
        "Speed": await add_analog(filler, idx, "Speed", 0.0, UNIT_PER_MIN, 0, 600),
        "GoodCount": await filler.add_variable(idx, "GoodCount", 0, ua.VariantType.UInt32),
        "RejectCount": await filler.add_variable(idx, "RejectCount", 0, ua.VariantType.UInt32),
        "Temperature": await add_analog(filler, idx, "Temperature", 21.0, UNIT_DEGC, -20, 120),
    }
    setpoints = await filler.add_object(idx, "Setpoints")
    target = await setpoints.add_variable(idx, "TargetSpeed", 400.0, ua.VariantType.Double)
    await target.set_writable()                      # only setpoints are writable

    @uamethod
    async def start(parent):
        if await v["State"].read_value() == "FAULTED":
            return "rejected: reset the fault first"
        await v["State"].write_value("RUNNING")
        return "ok"

    @uamethod
    async def stop(parent):
        await v["State"].write_value("IDLE")
        return "ok"

    @uamethod
    async def reset_counters(parent):
        await v["GoodCount"].write_value(0, ua.VariantType.UInt32)
        await v["RejectCount"].write_value(0, ua.VariantType.UInt32)
        if await v["State"].read_value() == "FAULTED":
            await v["State"].write_value("IDLE")
        return "ok"

    out = [ua.VariantType.String]
    await filler.add_method(idx, "Start", start, [], out)
    await filler.add_method(idx, "Stop", stop, [], out)
    await filler.add_method(idx, "ResetCounters", reset_counters, [], out)
    return v, target


async def simulate(v, target, period=0.5):
    t, speed, good, bad, last_good = 0.0, 0.0, 0.0, 0.0, 0
    while True:
        t += period
        state = await v["State"].read_value()
        sp = await target.read_value()
        if state == "RUNNING":
            speed += (sp - speed) * 0.2 + random.uniform(-3, 3)
            made = speed / 60 * period
            rej = made * 0.02
            good += made - rej
            bad += rej
            if random.random() < 0.002:
                await v["State"].write_value("FAULTED")
        else:
            speed *= 0.5
        if await v["GoodCount"].read_value() != last_good:  # ResetCounters() was called
            good, bad = 0.0, 0.0
        last_good = int(good)
        await v["Speed"].write_value(max(speed, 0.0))
        await v["GoodCount"].write_value(int(good), ua.VariantType.UInt32)
        await v["RejectCount"].write_value(int(bad), ua.VariantType.UInt32)
        await v["Temperature"].write_value(21 + speed / 40 + math.sin(t / 20))
        await asyncio.sleep(period)


async def main(endpoint: str = ENDPOINT):
    server = Server()
    await server.init()
    server.set_endpoint(endpoint)
    server.set_server_name("IIoT examples: filler line")
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])   # lab only
    v, target = await build(server)
    async with server:
        logging.info("OPC UA server at %s", endpoint)
        await simulate(v, target)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("asyncua").setLevel(logging.WARNING)
    asyncio.run(main())
