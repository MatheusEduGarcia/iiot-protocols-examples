"""
Modbus TCP client: read every data type, then close the loop with a
simple on/off level controller (the kind of logic a PLC or an edge box runs).

Run the server first, then:
    python 01-modbus-tcp-basics/client.py
"""
import os
import time

from pymodbus.client import ModbusTcpClient

HOST = os.getenv("MODBUS_HOST", "localhost")
PORT = int(os.getenv("MODBUS_PORT", "5020"))
UNIT = 1


def read_all(c: ModbusTcpClient) -> dict:
    coils = c.read_coils(0, count=1, slave=UNIT)                 # FC01
    di = c.read_discrete_inputs(0, count=2, slave=UNIT)          # FC02
    hr = c.read_holding_registers(0, count=2, slave=UNIT)        # FC03
    ir = c.read_input_registers(0, count=2, slave=UNIT)          # FC04
    for r in (coils, di, hr, ir):
        if r.isError():
            raise RuntimeError(r)
    return {
        "pump_cmd": coils.bits[0],
        "high_level": di.bits[0],
        "pump_running": di.bits[1],
        "level_pct": ir.registers[0] / 10,     # scaling: raw x10
        "temp_c": ir.registers[1] / 10,
        "setpoint_pct": hr.registers[0] / 10,
        "outflow_pct": hr.registers[1],
    }


def control_step(c: ModbusTcpClient, s: dict, band: float = 2.0) -> bool:
    """On/off control with hysteresis: pump on below SP-band, off above SP+band."""
    want = s["pump_cmd"]
    if s["level_pct"] < s["setpoint_pct"] - band:
        want = True
    elif s["level_pct"] > s["setpoint_pct"] + band or s["high_level"]:
        want = False
    if want != s["pump_cmd"]:
        c.write_coil(0, want, slave=UNIT)                          # FC05
    return want


def run(seconds: float = 20, host: str = HOST, port: int = PORT, verbose: bool = True) -> list[dict]:
    history = []
    with ModbusTcpClient(host, port=port, timeout=2) as c:
        c.write_register(0, 700, slave=UNIT)                       # FC06: setpoint 70.0 %
        t_end = time.time() + seconds
        while time.time() < t_end:
            s = read_all(c)
            s["pump_cmd"] = control_step(c, s)
            history.append(s)
            if verbose:
                print(f"level {s['level_pct']:5.1f} %  SP {s['setpoint_pct']:4.1f} %  "
                      f"pump {'ON ' if s['pump_cmd'] else 'off'}  temp {s['temp_c']:.1f} C")
            time.sleep(1)
    return history


if __name__ == "__main__":
    run()
