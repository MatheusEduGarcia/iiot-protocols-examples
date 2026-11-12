# 08 · Modbus to MQTT gateway with report by exception

What an edge gateway does between a Modbus device and the IT side: a tag
table, polling, deadband filtering, heartbeat and signal quality.

## Concepts

* **Tag table**: name, function code, address, scaling, unit, deadband.
* **Report by exception**: poll fast, publish only when a value moves more
  than its deadband (91 % less upstream traffic in the sample run).
* **Heartbeat**: a flat value is still republished every 30 s, so consumers
  can tell "unchanged" from "dead".
* **Quality**: if the device stops answering, `_gateway/device` turns `bad`;
  if the gateway dies, its Last Will sets `_gateway/status` to `offline`.

## Run

```bash
python 01-modbus-tcp-basics/plant_server.py     # the device
python 08-modbus-to-mqtt-gateway/gateway.py     # the gateway
```

```
...
  publish level           81.0 %
  publish level           82.2 %
  publish temperature     22.1 degC
  publish level           83.4 %
...
420 tag reads, 38 MQTT publishes (91 % less upstream traffic)
```

Stop the plant server while the gateway runs to see the quality change.

[← all examples](../README.md)
