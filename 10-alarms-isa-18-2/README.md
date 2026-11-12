# 10 · Alarm management (ISA-18.2)

Why `if value > limit` is not an alarm system. The same noisy temperature
signal is fed to three alarm configurations and the alarm rate is compared
against the ISA-18.2 guideline.

## Concepts

* **Alarm states**: `NORMAL`, `UNACK`, `ACKED`, `RTN_UNACK` (returned to
  normal but not acknowledged), `SHELVED`, `OUT_OF_SERVICE`.
* **Deadband (hysteresis)**: clear only below `limit - deadband`.
* **On/off delays**: the condition must last a few seconds.
* **Shelving**: the operator hides a known bad alarm for a limited time; it
  comes back by itself if the condition is still active.
* **Alarm rate**: about 1 per 10 minutes per operator is manageable, more
  than 10 is a flood.

## Run

```bash
python 10-alarms-isa-18-2/alarms.py
```

```
Same signal, 60 minutes, limit 80 C:

  naive      141 activations  ( 23.5 per 10 min)  <- alarm flood
  deadband    18 activations  (  3.0 per 10 min)  <- above target
  isa          3 activations  (  0.5 per 10 min)  <- ok
```

[← all examples](../README.md)
