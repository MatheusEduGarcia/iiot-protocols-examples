"""
Sparkplug B on top of MQTT: the parts that plain MQTT leaves open.

  * Fixed topic namespace   spBv1.0/<group>/<message type>/<edge node>[/<device>]
  * BIRTH certificates      NBIRTH / DBIRTH declare every metric, its type and an alias
  * Aliases                 DDATA then carries numbers instead of names (small payloads)
  * State awareness         NDEATH (MQTT will) + bdSeq tell the host the node is gone
  * Sequence numbers        seq 0..255 lets the host detect a lost message
  * Protobuf payloads       typed, compact, language neutral

The script runs an edge node with one device and a host application that
decodes everything, then kills the edge node to show the death certificate.

Run:  python 07-sparkplug-b/sparkplug_demo.py
"""
import json
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import sparkplug_b_pb2 as spb  # noqa: E402
from common.mqtt import HOST, PORT, client  # noqa: E402

GROUP = f"plant-{uuid.uuid4().hex[:4]}"
EDGE, DEVICE = "edge-gw-01", "filler-01"
NS = "spBv1.0"

# Sparkplug B datatype codes (spec table 'Data Types')
INT32, UINT64, FLOAT, DOUBLE, BOOLEAN, STRING = 3, 8, 9, 10, 11, 12
VALUE_FIELD = {INT32: "int_value", UINT64: "long_value", FLOAT: "float_value",
               DOUBLE: "double_value", BOOLEAN: "boolean_value", STRING: "string_value"}

DEVICE_METRICS = [          # name, alias, datatype, initial value
    ("Process/Speed", 1, FLOAT, 0.0),
    ("Process/Running", 2, BOOLEAN, False),
    ("Counters/Good", 3, INT32, 0),
    ("Counters/Reject", 4, INT32, 0),
    ("Info/Recipe", 5, STRING, "BOTTLE-500ML"),
]


def now_ms() -> int:
    return int(time.time() * 1000)


def metric(p, name=None, alias=None, datatype=None, value=None):
    m = p.metrics.add()
    if name is not None:
        m.name = name
    if alias is not None:
        m.alias = alias
    m.timestamp = now_ms()
    if datatype is not None:
        m.datatype = datatype
        setattr(m, VALUE_FIELD[datatype], value)
    return m


class EdgeNode:
    def __init__(self):
        self.seq = 0
        self.bdseq = 0
        self.c = client(f"{GROUP}-{EDGE}")
        death = spb.Payload(timestamp=now_ms())
        metric(death, "bdSeq", datatype=UINT64, value=self.bdseq)
        # NDEATH is registered as the MQTT will: the broker sends it if we die
        self.c.will_set(f"{NS}/{GROUP}/NDEATH/{EDGE}", death.SerializeToString(), qos=1)
        self.c.connect(HOST, PORT, keepalive=5)
        self.c.loop_start()

    def _next_seq(self) -> int:
        s = self.seq
        self.seq = (self.seq + 1) % 256
        return s

    def publish(self, mtype: str, payload, device: str | None = None):
        payload.timestamp = now_ms()
        payload.seq = self._next_seq()
        t = f"{NS}/{GROUP}/{mtype}/{EDGE}" + (f"/{device}" if device else "")
        self.c.publish(t, payload.SerializeToString(), qos=0).wait_for_publish()
        return payload

    def birth(self):
        nb = spb.Payload()
        metric(nb, "bdSeq", datatype=UINT64, value=self.bdseq)
        metric(nb, "Node Control/Rebirth", datatype=BOOLEAN, value=False)
        self.publish("NBIRTH", nb)
        db = spb.Payload()
        for name, alias, dt, v in DEVICE_METRICS:
            metric(db, name, alias, dt, v)
        self.publish("DBIRTH", db, DEVICE)

    def data(self, changes: dict):
        """Report by exception: only changed metrics, by alias, no names."""
        p = spb.Payload()
        by_name = {n: (a, dt) for n, a, dt, _ in DEVICE_METRICS}
        for name, value in changes.items():
            alias, dt = by_name[name]
            metric(p, alias=alias, datatype=dt, value=value)
        return self.publish("DDATA", p, DEVICE)

    def crash(self):
        self.c.loop_stop()
        self.c.socket().close()          # no DISCONNECT: the broker fires NDEATH


class HostApplication:
    """What Ignition, a historian or an MES connector does with Sparkplug."""

    def __init__(self):
        self.aliases: dict[tuple, str] = {}
        self.values: dict[str, object] = {}
        self.node_online = {}
        self.expected_seq = None
        self.log: list[str] = []
        self.c = client(f"{GROUP}-host")
        self.c.on_message = self.on_message
        self.c.connect(HOST, PORT)
        self.c.subscribe(f"{NS}/{GROUP}/#", qos=1)
        self.c.loop_start()

    def on_message(self, _c, _u, msg):
        parts = msg.topic.split("/")
        mtype, node = parts[2], parts[3]
        dev = parts[4] if len(parts) > 4 else None
        p = spb.Payload.FromString(msg.payload)

        if mtype in ("NBIRTH", "DBIRTH", "NDATA", "DDATA"):
            if self.expected_seq is not None and p.seq != self.expected_seq and mtype != "NBIRTH":
                self.log.append(f"seq gap! expected {self.expected_seq}, got {p.seq} -> request rebirth")
            self.expected_seq = (p.seq + 1) % 256

        if mtype == "NBIRTH":
            self.node_online[node] = True
        if mtype == "DBIRTH":
            for m in p.metrics:
                self.aliases[(node, dev, m.alias)] = m.name
                self.values[m.name] = getattr(m, m.WhichOneof("value"))
        if mtype == "DDATA":
            for m in p.metrics:
                name = self.aliases.get((node, dev, m.alias), f"<unknown alias {m.alias}>")
                self.values[name] = getattr(m, m.WhichOneof("value"))
        if mtype == "NDEATH":
            self.node_online[node] = False

        names = [m.name or self.aliases.get((node, dev, m.alias), f"alias {m.alias}") for m in p.metrics]
        self.log.append(f"{mtype:<7} {node + ('/' + dev if dev else ''):<22} seq={p.seq if p.HasField('seq') else '-':<3} "
                        f"{len(msg.payload):>3} bytes  {', '.join(names)}")

    def close(self):
        self.c.loop_stop(); self.c.disconnect()


def main(verbose: bool = True) -> dict:
    host = HostApplication()
    time.sleep(0.3)
    edge = EdgeNode()
    edge.birth()
    good = 0
    for i in range(6):
        good += 7
        last = edge.data({"Process/Speed": 400.0 + i * 3.5, "Process/Running": True, "Counters/Good": good})
        time.sleep(0.15)
    edge.seq = (edge.seq + 1) % 256          # simulate one lost message
    edge.data({"Counters/Reject": 1})
    time.sleep(0.3)
    edge.crash()
    time.sleep(1.5)
    host.close()

    as_json = json.dumps({"Process/Speed": 417.5, "Process/Running": True, "Counters/Good": good, "timestamp": now_ms()})
    if verbose:
        print("Host application log:")
        for line in host.log:
            print("  " + line)
        print("\nCurrent values resolved from aliases:", host.values)
        print("Edge node online:", host.node_online)
        print(f"\nLast DDATA: {last.ByteSize()} bytes of protobuf vs {len(as_json)} bytes for the same data in JSON")
    return {"log": host.log, "values": host.values, "online": host.node_online}


if __name__ == "__main__":
    main()
