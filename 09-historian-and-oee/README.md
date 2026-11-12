# 09 · Historian and OEE from raw signals

From machine signals to a KPI: a shift of state changes (with downtime
reasons) and part counters goes through MQTT into a minimal SQLite
historian, and SQL turns the rows into OEE.

## Concepts

* **Narrow historian table** `(tag, ts, value)`: the layout most historians
  use underneath.
* **State durations with window functions** (`LEAD` over the state changes).
* **Counter deltas** (`LAG`) for parts per hour.
* **Downtime Pareto** by reason.
* **OEE** with the standard definitions:
  * Availability = run time / planned production time (lunch excluded)
  * Performance = parts x ideal cycle time / run time
  * Quality = good parts / total parts

## Run

```bash
python 09-historian-and-oee/historian_oee.py
```

```
Downtime Pareto:
  jam                   36 min  (3 stops)
  electrical fault      32 min  (2 stops)
  material shortage      5 min  (1 stops)

Planned time 7.50 h, run time 6.28 h, 16115 good + 228 reject
Availability 83.8% x Performance 86.7% x Quality 98.6% = OEE 71.6%
```

[← all examples](../README.md)
