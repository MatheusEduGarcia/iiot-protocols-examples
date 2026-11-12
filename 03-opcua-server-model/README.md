# 03 · OPC UA server with an information model

An OPC UA server that exposes a filler machine as a structured object, not
a flat list of tags: object type, folders, typed variables with engineering
units and ranges, writable setpoints and methods.

```
Objects
└── Plant
    └── Line1
        └── Filler01            (FillerType)
            ├── State           IDLE / RUNNING / FAULTED
            ├── Speed           bottles/min, EURange 0..600
            ├── GoodCount, RejectCount
            ├── Temperature     degC
            ├── Setpoints/TargetSpeed   (the only writable variable)
            └── Start(), Stop(), ResetCounters()
```

## Concepts

* **Information model**: the address space describes the machine, so a
  client discovers what exists instead of reading a spreadsheet of tags.
* **Object types**: every filler shares `FillerType`; clients can find all
  instances of a type.
* **AnalogItem properties**: `EngineeringUnits` (UNECE codes) and `EURange`
  travel with the value.
* **Access levels**: writes to measured values are refused by the server.
* **Methods** with server-side validation (`Start()` is refused while
  `FAULTED`).

## Run

```bash
python 03-opcua-server-model/server.py
```

Endpoint `opc.tcp://localhost:4841/iiot-examples/`, no security (lab only).
Browse it with [UaExpert](https://www.unified-automation.com/products/development-tools/uaexpert.html)
or with example 04.

[← all examples](../README.md)
