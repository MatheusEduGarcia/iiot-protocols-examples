# 07 · Sparkplug B

Sparkplug B is a specification on top of MQTT that fixes what plain MQTT
leaves open: topic layout, payload encoding, data types and state.

## Concepts

* **Topic namespace** `spBv1.0/<group>/<type>/<edge node>[/<device>]`.
* **Birth certificates**: `NBIRTH`/`DBIRTH` list every metric with its type
  and a numeric **alias**.
* **Aliases**: later `DDATA` messages carry only aliases and changed values
  (57 bytes here vs 98 bytes of JSON).
* **State awareness**: `NDEATH` is the MQTT will, with a `bdSeq` to match it
  to the right session.
* **Sequence numbers** `0..255`: the host detects the missing message and
  would request a rebirth.
* **Protobuf** payloads, from [`sparkplug_b.proto`](sparkplug_b.proto)
  (a subset of the Eclipse Tahu definition with the same field numbers).

## Run

```bash
python 07-sparkplug-b/sparkplug_demo.py
```

```
NBIRTH  edge-gw-01             seq=0    64 bytes  bdSeq, Node Control/Rebirth
DBIRTH  edge-gw-01/filler-01   seq=1   176 bytes  Process/Speed, Process/Running, Counters/Good, ...
DDATA   edge-gw-01/filler-01   seq=2    57 bytes  Process/Speed, Process/Running, Counters/Good
...
seq gap! expected 8, got 9 -> request rebirth
NDEATH  edge-gw-01             seq=-    27 bytes  bdSeq
```

Regenerate the Python bindings with
`python -m grpc_tools.protoc -I. --python_out=. sparkplug_b.proto`.

[← all examples](../README.md)
