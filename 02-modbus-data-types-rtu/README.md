# 02 · Modbus data types, scaling and RTU framing

Modbus only moves 16-bit registers. Floats, 32-bit counters, signed values,
scaled analog signals and packed status bits are conventions between device
and client, and getting one wrong gives a plausible-looking wrong number.
No server needed: everything here is pure functions.

## Concepts

* **32-bit values in two registers** and the word order problem
  (ABCD vs CDAB): read with the wrong order, 123.456 becomes -1.88e+25.
* **Two's complement** for negative 16-bit values (`0xFFF6` = -10).
* **Linear scaling** of raw counts to engineering units, the same maths as
  `SCALE`/`NORM_X`+`SCALE_X` in a PLC (Siemens analog full scale = 27648).
* **4-20 mA with NAMUR NE43** limits: below 3.8 mA means a broken wire.
* **Status word** with one bit per flag.
* **RTU vs TCP frames** for the same request: RTU ends with a CRC-16, TCP
  starts with an MBAP header and has no CRC.

## Run

```bash
python 02-modbus-data-types-rtu/datatypes.py
```

```
== 32-bit float 123.456 ==
  big    word order -> ['0x42f6', '0xe979']
  little word order -> ['0xe979', '0x42f6']
  read with the wrong word order: -1.88337e+25  <- the classic 'garbage value' bug
...
== the same 'read 2 holding registers at 100' request ==
  RTU : 01 03 00 64 00 02 85 d4  CRC ok: True
  TCP : 00 01 00 00 00 06 01 03 00 64 00 02
  RTU with one flipped bit, CRC ok: False
```

[← all examples](../README.md)
