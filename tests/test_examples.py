import asyncio
import os

from conftest import load


# 01 ------------------------------------------------------------- Modbus TCP
def test_01_modbus_level_control(modbus_plant):
    client = load("01-modbus-tcp-basics/client.py")
    hist = client.run(seconds=6, port=modbus_plant, verbose=False)
    assert hist[0]["setpoint_pct"] == 70.0
    assert hist[0]["pump_cmd"] is True                 # level 50 % < SP: pump started
    assert hist[-1]["level_pct"] > hist[0]["level_pct"]


# 02 ------------------------------------------------------------- data types
def test_02_datatypes_and_rtu():
    d = load("02-modbus-data-types-rtu/datatypes.py")
    for order in ("big", "little"):
        assert abs(d.regs_to_float32(d.float32_to_regs(123.456, order), order) - 123.456) < 1e-4
    assert d.regs_to_uint32([0x0001, 0x86A0]) == 100000
    assert d.regs_to_int16(0xFFF6) == -10
    assert d.scale(13824, 0, 27648, 0, 10) == 5.0
    assert d.ma_to_eu(2.0, 0, 100)[0] is None
    assert d.rtu_read_holding(1, 100, 2).hex() == "010300640002" + "85d4"   # well-known frame
    assert d.unpack_status(0b10)["running"] is True


# 03 + 04 -------------------------------------------------------- OPC UA
def test_03_04_opcua_model_and_subscription(opcua_server):
    c = load("04-opcua-client-subscriptions/client.py")
    out = asyncio.run(c.run(seconds=4, url=opcua_server, verbose=False))
    assert 0 < out["notifications"] < out["polls"]     # subscription beats polling
    assert out["state"] == "IDLE"                      # Stop() method was applied


# 05 ------------------------------------------------------------- MQTT basics
def test_05_retain_lwt_qos(broker):
    d = load("05-mqtt-qos-retain-lwt/demo.py")
    out = d.main(verbose=False)
    late = out["retained"]["late_subscriber_got"]
    assert len(late) == 1 and late[0][2] is True
    assert out["lwt"]["watcher_saw"] == ["online", "offline"]
    assert out["qos"]["received_after_reconnect"] == [f"qos1-{i}" for i in range(5)]


# 06 ------------------------------------------------------------- UNS
def test_06_uns_filters(broker):
    u = load("06-unified-namespace/uns.py")
    out = u.main(verbose=False)
    assert len(out["Production planning"]) == 3
    assert all(k.endswith("/state") for k in out["Andon board, all states"])
    assert all("/filler/" in k for k in out["OEE app, all fillers"])
    assert all(k.startswith("sao-paulo/") for k in out["Plant manager São Paulo"])


# 07 ------------------------------------------------------------- Sparkplug B
def test_07_sparkplug(broker):
    s = load("07-sparkplug-b/sparkplug_demo.py")
    out = s.main(verbose=False)
    kinds = [line.split()[0] for line in out["log"]]
    assert kinds[:2] == ["NBIRTH", "DBIRTH"] and kinds[-1] == "NDEATH"
    assert any("seq gap" in line for line in out["log"])
    assert out["values"]["Counters/Good"] == 42 and out["online"]["edge-gw-01"] is False


# 08 ------------------------------------------------------------- gateway
def test_08_gateway_report_by_exception(broker, modbus_plant):
    os.environ["MODBUS_PORT"] = str(modbus_plant)
    g = load("08-modbus-to-mqtt-gateway/gateway.py")
    out = g.run(seconds=4, poll_s=0.25, verbose=False)
    assert out["sent"] < out["reads"] / 2


# 09 ------------------------------------------------------------- historian + OEE
def test_09_historian_oee(broker):
    h = load("09-historian-and-oee/historian_oee.py")
    k = h.main(verbose=False)
    assert k["stored"] == k["published"]
    assert abs(k["oee"] - k["availability"] * k["performance"] * k["quality"]) < 1e-9
    assert 0.5 < k["oee"] < 0.95 and abs(k["planned_s"] - 7.5 * 3600) < 1
    downtime = sum(s for _, s, _ in k["downtime"])
    assert abs(k["planned_s"] - k["run_s"] - downtime) < 1


# 10 ------------------------------------------------------------- alarms
def test_10_alarm_rationalisation():
    a = load("10-alarms-isa-18-2/alarms.py")
    out = a.run(verbose=False)
    assert out["naive"] > out["deadband"] > out["isa"] >= 1
    assert out["shelf_during"] == 0 and out["shelf_after"] == 1
