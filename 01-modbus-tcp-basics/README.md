# 01 · Modbus TCP basics

The four Modbus data tables, read and written from Python against a
simulated tank, then used to close a level control loop.

## Concepts

| Table | Size | Access | Function codes | Used here for |
|---|---|---|---|---|
| Coils | 1 bit | read/write | 01 read, 05/15 write | pump command |
| Discrete inputs | 1 bit | read only | 02 | level switch, pump feedback |
| Input registers | 16 bit | read only | 04 | level, temperature (x10) |
| Holding registers | 16 bit | read/write | 03 read, 06/16 write | setpoint, valve opening |

* **Addresses are 0-based on the wire.** Documentation often says `40001`
  for holding register 0: that "4" is the table, not part of the address.
* **Unit id** selects the device behind a gateway (here `1`).
* **Scaling by convention:** `523` means `52.3 %` because the map says x10.
* **Port 5020** is used because 502 needs admin rights.

## Run

```bash
python 01-modbus-tcp-basics/plant_server.py     # terminal 1
python 01-modbus-tcp-basics/client.py           # terminal 2
```

```
level  49.5 %  SP 70.0 %  pump ON   temp 22.1 C
level  50.7 %  SP 70.0 %  pump ON   temp 22.1 C
level  51.9 %  SP 70.0 %  pump ON   temp 22.2 C
...
```

## Try

* Open the server with a Modbus tool (Modbus Poll, QModMaster) on port 5020.
* Change `band` in `control_step` and watch how often the pump switches.

[← all examples](../README.md)
