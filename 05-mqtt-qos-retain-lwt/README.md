# 05 · MQTT QoS, retained messages and Last Will

Three broker features that make MQTT usable for industrial data, each shown
with a small experiment.

## Concepts

| Feature | Experiment | Lesson |
|---|---|---|
| **Retained message** | publish one retained and one plain value, then connect a new subscriber | a late dashboard gets the current state immediately; use retain for state, not for events |
| **Last Will (LWT)** | a device registers `offline` as its will, then its socket is killed | the broker publishes `offline` on the device's behalf |
| **QoS + persistent session** | a historian with `clean_session=False` goes offline while 5 QoS 0 and 5 QoS 1 messages are sent | only QoS 1 is queued and delivered on reconnect |

## Run

```bash
docker compose up -d          # or any broker on localhost:1883
python 05-mqtt-qos-retain-lwt/demo.py
```

```
1) RETAINED  a subscriber that connected late received:
     retained/level   = 52.3  (retain flag True)
2) LAST WILL  the watcher saw: ['online', 'offline']
3) QoS + persistent session  messages delivered after reconnect: ['qos1-0', 'qos1-1', 'qos1-2', 'qos1-3', 'qos1-4']
```

[← all examples](../README.md)
