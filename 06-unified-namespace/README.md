# 06 · Unified Namespace (ISA-95 on MQTT)

One broker as the single source of truth, organised by the ISA-95
equipment hierarchy `enterprise/site/area/line/cell/<data>`. OT producers
(machine state, counters) and IT producers (MES work orders) publish
retained current state to their place in the tree; consumers pick their
slice with wildcards.

## Concepts

* **Hierarchy as the contract**: a consumer only needs the topic structure,
  never the IP or protocol of the producer.
* **Current state, retained**: anyone who connects sees the plant as it is now.
* **Wildcards**: `+` matches one level, `#` the rest of the tree.
* **OT and IT side by side**: the work order lives next to the machine data.

| Consumer | Filter | Sees |
|---|---|---|
| Plant manager São Paulo | `sao-paulo/#` | everything in that site |
| OEE app | `+/+/+/filler/#` | every filler in every site |
| Andon board | `+/+/+/+/state` | every machine state |
| Production planning | `+/+/+/mes/work-order` | every line's order |

## Run

```bash
python 06-unified-namespace/uns.py
```

[← all examples](../README.md)
