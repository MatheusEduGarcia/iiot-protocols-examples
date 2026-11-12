"""
Unified Namespace (UNS): one MQTT broker as the single source of truth,
organised by the ISA-95 equipment hierarchy:

    enterprise / site / area / line / cell / <data>

Producers (PLC gateways, MES, ERP connectors) publish the CURRENT state of
what they own, retained, to their place in the tree. Consumers subscribe
with wildcards to the part of the business they care about and never need
to know who the producer is.

This script starts three producers, then runs four consumers with
different topic filters to show what each one sees.

Run:  python 06-unified-namespace/uns.py
"""
import json
import random
import sys
import threading
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.mqtt import HOST, PORT, client  # noqa: E402

ENTERPRISE = f"acme-{uuid.uuid4().hex[:4]}"      # unique root so reruns start clean

# What lives where (ISA-95: site > area > line > cell)
EQUIPMENT = [
    ("sao-paulo", "packaging", "line-1", "filler"),
    ("sao-paulo", "packaging", "line-1", "capper"),
    ("sao-paulo", "packaging", "line-2", "filler"),
    ("curitiba", "molding", "line-7", "press-01"),
]


def topic(site, area, line, cell, leaf):
    return f"{ENTERPRISE}/{site}/{area}/{line}/{cell}/{leaf}"


def plc_gateway(stop: threading.Event):
    """OT producer: machine state and counters (retained = current state)."""
    c = client(); c.connect(HOST, PORT); c.loop_start()
    counts = {e: 0 for e in EQUIPMENT}
    while not stop.is_set():
        for e in EQUIPMENT:
            counts[e] += random.randint(0, 3)
            state = random.choice(["RUNNING"] * 8 + ["STOPPED", "FAULTED"])
            c.publish(topic(*e, "state"), json.dumps({"value": state, "ts": time.time()}), retain=True)
            c.publish(topic(*e, "count/good"), json.dumps({"value": counts[e], "ts": time.time()}), retain=True)
        time.sleep(0.2)
    c.loop_stop(); c.disconnect()


def mes_connector():
    """IT producer: the order running on each line lives next to the machine data."""
    c = client(); c.connect(HOST, PORT); c.loop_start()
    for site, area, line, _ in EQUIPMENT:
        c.publish(f"{ENTERPRISE}/{site}/{area}/{line}/mes/work-order",
                  json.dumps({"order": f"WO-{random.randint(1000, 9999)}", "sku": "BOTTLE-500ML", "target": 12000}),
                  qos=1, retain=True).wait_for_publish()
    c.loop_stop(); c.disconnect()


def consumer(name: str, filt: str, seconds: float = 1.0) -> dict:
    snapshot = {}
    c = client()
    c.on_message = lambda cl, u, m: snapshot.__setitem__(m.topic[len(ENTERPRISE) + 1:], json.loads(m.payload))
    c.connect(HOST, PORT); c.subscribe(f"{ENTERPRISE}/{filt}"); c.loop_start()
    time.sleep(seconds)
    c.loop_stop(); c.disconnect()
    return snapshot


def clear_retained(seen_topics):
    c = client(); c.connect(HOST, PORT); c.loop_start()
    for t in seen_topics:
        c.publish(f"{ENTERPRISE}/{t}", b"", retain=True)
    time.sleep(0.3); c.loop_stop(); c.disconnect()


CONSUMERS = [
    ("Plant manager São Paulo", "sao-paulo/#"),
    ("OEE app, all fillers",    "+/+/+/filler/#"),
    ("Andon board, all states", "+/+/+/+/state"),
    ("Production planning",     "+/+/+/mes/work-order"),
]


def main(verbose: bool = True) -> dict:
    stop = threading.Event()
    t = threading.Thread(target=plc_gateway, args=(stop,), daemon=True)
    t.start()
    mes_connector()
    time.sleep(0.6)
    results = {name: consumer(name, f) for name, f in CONSUMERS}
    stop.set(); t.join()
    everything = consumer("all", "#", 0.5)
    clear_retained(everything)

    if verbose:
        print(f"UNS root: {ENTERPRISE}/   ({len(everything)} topics in the namespace)\n")
        for (name, f) in CONSUMERS:
            snap = results[name]
            print(f"{name}  subscribes '{f}'  -> {len(snap)} topics")
            for k in sorted(snap)[:6]:
                v = snap[k]
                print(f"     {k:<44} {v.get('value', v.get('order'))}")
            if len(snap) > 6:
                print(f"     ... {len(snap) - 6} more")
            print()
    return {"all": everything, **results}


if __name__ == "__main__":
    main()
