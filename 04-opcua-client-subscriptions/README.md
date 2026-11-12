# 04 · OPC UA client: browse, subscribe, write, call

A client for the server of example 03 that does what SCADA, MES and
historians do with OPC UA.

## Concepts

* **Browse** the address space to discover the model.
* **Read metadata**: engineering units and range next to the value.
* **Write** a setpoint, and see the server refuse a write to a measurement.
* **Call methods** on the machine object.
* **Subscriptions instead of polling**: the server samples the values and
  pushes only changes. An **absolute deadband** on `Speed` filters noise
  below 5 bottles/min.

## Run

```bash
python 03-opcua-server-model/server.py               # terminal 1
python 04-opcua-client-subscriptions/client.py       # terminal 2
```

```
== metadata == Speed in bottles/min, range 0.0..600.0
== method calls ==
  Start() -> ok
  wrote TargetSpeed = 300
  write to Speed refused by server: BadUserAccessDenied
== subscription for 8 s (publishing interval 500 ms) ==
  14:47:29.1956  State        = 'RUNNING'
  14:47:29.2120  Speed        = 59.6
  14:47:49.0242  GoodCount    = 1
  ...
  30 notifications received; polling the same 4 tags every 250 ms would have been 128 reads.
```

[← all examples](../README.md)
