"""
Edge gateway: poll a Modbus TCP device, publish to MQTT by exception.

Polling is cheap on the plant network; publishing every poll is not cheap
upstream (broker, historian, cloud). A gateway therefore:

  * reads a TAG TABLE (address, type, scaling, unit), like any commercial gateway
  * publishes a value only when it moves more than its DEADBAND,
  * plus a HEARTBEAT so a flat value is still refreshed now and then,
  * carries quality: if the device stops answering, tags go 'bad' and the
    gateway's own status tells the consumers why.

Uses the simulated tank of example 01 as the device. Start it first:
    python 01-modbus-tcp-basics/plant_server.py
then:
    python 08-modbus-to-mqtt-gateway/gateway.py
"""
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from pymodbus.client import ModbusTcpClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.mqtt import HOST, PORT, client  # noqa: E402

MODBUS_HOST = os.getenv("MODBUS_HOST", "localhost")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "5020"))
ROOT = os.getenv("UNS_ROOT", "iiot-examples/site-01/utilities/tank-01")


@dataclass
class Tag:
    name: str
    fc: int                 # 1 coil, 2 discrete input, 3 holding, 4 input register
    address: int
    scale: float = 1.0
    unit: str = ""
    deadband: float = 0.0   # in engineering units; 0 = any change
    heartbeat_s: float = 30.0
    last_value: object = field(default=None, repr=False)
    last_sent: float = field(default=0.0, repr=False)


TAGS = [
    Tag("level",        4, 0, 0.1, "%",   deadband=1.0),
    Tag("temperature",  4, 1, 0.1, "degC", deadband=0.2),
    Tag("level_sp",     3, 0, 0.1, "%"),
    Tag("outflow",      3, 1, 1.0, "%"),
    Tag("pump_cmd",     1, 0),
    Tag("high_level",   2, 0),
    Tag("pump_running", 2, 1),
]


def read_tag(m: ModbusTcpClient, t: Tag):
    fn = {1: m.read_coils, 2: m.read_discrete_inputs, 3: m.read_holding_registers, 4: m.read_input_registers}[t.fc]
    r = fn(t.address, count=1, slave=1)
    if r.isError():
        raise IOError(r)
    if t.fc in (1, 2):
        return bool(r.bits[0])
    return round(r.registers[0] * t.scale, 3)


def changed(t: Tag, value, now: float) -> bool:
    if t.last_value is None or now - t.last_sent >= t.heartbeat_s:
        return True
    if isinstance(value, bool):
        return value != t.last_value
    return abs(value - t.last_value) > t.deadband


def run(seconds: float = 30, poll_s: float = 0.5, verbose: bool = True) -> dict:
    mq = client("tank-01-gateway")
    mq.will_set(f"{ROOT}/_gateway/status", "offline", qos=1, retain=True)
    mq.connect(HOST, PORT)
    mq.loop_start()
    mq.publish(f"{ROOT}/_gateway/status", "online", qos=1, retain=True)
    m = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT, timeout=1)

    polls = sent = 0
    device_ok = None
    t_end = time.time() + seconds
    while time.time() < t_end:
        now = time.time()
        try:
            if not m.connected:
                m.connect()
            values = {t.name: read_tag(m, t) for t in TAGS}
            ok = True
        except Exception:
            values, ok = {}, False
        polls += 1

        if ok != device_ok:                                     # quality change
            device_ok = ok
            mq.publish(f"{ROOT}/_gateway/device", "good" if ok else "bad: no response", qos=1, retain=True)
            if verbose:
                print(f"device quality -> {'GOOD' if ok else 'BAD'}")

        for t in TAGS:
            if t.name in values and changed(t, values[t.name], now):
                payload = {"value": values[t.name], "unit": t.unit, "quality": "good", "ts": round(now, 3)}
                mq.publish(f"{ROOT}/{t.name}", json.dumps(payload), qos=0, retain=True)
                t.last_value, t.last_sent = values[t.name], now
                sent += 1
                if verbose:
                    print(f"  publish {t.name:<13} {values[t.name]!s:>6} {t.unit}")
        time.sleep(poll_s)

    m.close()
    mq.publish(f"{ROOT}/_gateway/status", "offline", qos=1, retain=True).wait_for_publish()
    mq.loop_stop(); mq.disconnect()
    reads = polls * len(TAGS)
    if verbose:
        print(f"\n{reads} tag reads, {sent} MQTT publishes "
              f"({100 * (1 - sent / max(reads, 1)):.0f} % less upstream traffic)")
    return {"reads": reads, "sent": sent}


if __name__ == "__main__":
    run()
