"""
Three MQTT features every IIoT system leans on, each shown with a small
experiment against a real broker (Mosquitto on localhost by default).

  1. Retained messages  a late subscriber still gets the last known value
  2. Last Will (LWT)    the broker announces 'offline' when a device dies
  3. QoS + sessions     what is kept for a subscriber that was offline

Run:  python 05-mqtt-qos-retain-lwt/demo.py      (MQTT_HOST to change broker)
"""
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.mqtt import HOST, PORT, client  # noqa: E402

ROOT = f"iiot-examples/05/{uuid.uuid4().hex[:6]}"   # unique per run, no clash with old retained data


def collect(topic: str, seconds: float = 1.0, **kw) -> list[tuple[str, str, bool]]:
    got = []
    c = client(**kw)
    c.on_message = lambda cl, u, m: got.append((m.topic, m.payload.decode(), m.retain))
    c.connect(HOST, PORT)
    c.subscribe(topic, qos=1)
    c.loop_start()
    time.sleep(seconds)
    c.loop_stop()
    c.disconnect()
    return got


def retained() -> dict:
    pub = client()
    pub.connect(HOST, PORT)
    pub.loop_start()
    pub.publish(f"{ROOT}/retained/level", "52.3", qos=1, retain=True).wait_for_publish()
    pub.publish(f"{ROOT}/plain/level", "52.3", qos=1, retain=False).wait_for_publish()
    pub.loop_stop()
    pub.disconnect()
    # A dashboard that connects AFTER the publish:
    late = collect(f"{ROOT}/+/level")
    # Clean up: an empty retained payload deletes the retained message
    cl = client(); cl.connect(HOST, PORT); cl.loop_start()
    cl.publish(f"{ROOT}/retained/level", b"", retain=True).wait_for_publish(); cl.loop_stop(); cl.disconnect()
    return {"late_subscriber_got": late}


def last_will() -> dict:
    status = f"{ROOT}/device/status"
    watcher = []
    w = client()
    w.on_message = lambda cl, u, m: watcher.append(m.payload.decode())
    w.connect(HOST, PORT)
    w.subscribe(status, qos=1)
    w.loop_start()

    dev = client("plc-gateway-01")
    dev.will_set(status, "offline", qos=1, retain=True)     # registered at CONNECT time
    dev.connect(HOST, PORT, keepalive=5)
    dev.loop_start()
    dev.publish(status, "online", qos=1, retain=True).wait_for_publish()
    time.sleep(0.5)
    # Simulate a power cut: drop the TCP socket without sending DISCONNECT
    dev.loop_stop()
    dev.socket().close()
    time.sleep(1.5)        # the broker notices the closed socket and publishes the will
    w.loop_stop()
    w.disconnect()
    return {"watcher_saw": watcher}


def qos_and_sessions() -> dict:
    topic = f"{ROOT}/events"
    sub_id = f"historian-{uuid.uuid4().hex[:4]}"
    # 1) historian subscribes with a persistent session, then goes offline
    h = client(sub_id, clean_session=False)
    h.connect(HOST, PORT)
    h.subscribe(topic, qos=1)
    h.loop_start(); time.sleep(0.3); h.loop_stop(); h.disconnect()

    # 2) while it is offline, a device publishes 5 messages at QoS 0 and 5 at QoS 1
    p = client(); p.connect(HOST, PORT); p.loop_start()
    for i in range(5):
        p.publish(topic, f"qos0-{i}", qos=0)
        p.publish(topic, f"qos1-{i}", qos=1).wait_for_publish()
    time.sleep(0.3); p.loop_stop(); p.disconnect()

    # 3) historian comes back with the same client id and clean_session=False
    got = []
    h = client(sub_id, clean_session=False)
    h.on_message = lambda cl, u, m: got.append(m.payload.decode())
    h.connect(HOST, PORT)
    h.loop_start(); time.sleep(1.0); h.loop_stop()
    h.unsubscribe(topic); h.disconnect()
    return {"received_after_reconnect": got}


def main(verbose: bool = True) -> dict:
    out = {"retained": retained(), "lwt": last_will(), "qos": qos_and_sessions()}
    if verbose:
        r = out["retained"]["late_subscriber_got"]
        print("1) RETAINED  a subscriber that connected late received:")
        for t, v, ret in r:
            print(f"     {t.split('/', 3)[-1]:<16} = {v}  (retain flag {ret})")
        print("   -> only the retained topic arrived. Use retain for state, not for events.\n")
        print("2) LAST WILL  the watcher saw:", out["lwt"]["watcher_saw"])
        print("   -> 'offline' was published by the BROKER after the socket died.\n")
        got = out["qos"]["received_after_reconnect"]
        print("3) QoS + persistent session  messages delivered after reconnect:", got)
        print("   -> QoS 1 was queued for the offline subscriber, QoS 0 was dropped.")
    return out


if __name__ == "__main__":
    main()
