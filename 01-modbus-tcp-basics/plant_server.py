"""
Modbus TCP server that simulates a small tank with a pump.

Register map (all addresses are 0-based, as sent on the wire):

  Coils (FC01 read / FC05 write, 1 bit, read-write)
    0  PUMP_CMD          1 = pump on (written by the client)
  Discrete inputs (FC02, 1 bit, read-only)
    0  HIGH_LEVEL_SW     level switch, 1 above 90 %
    1  PUMP_RUNNING      feedback contact
  Input registers (FC04, 16 bit, read-only)
    0  LEVEL_x10         tank level in 0.1 %   (e.g. 523 = 52.3 %)
    1  TEMP_x10          water temperature in 0.1 C
  Holding registers (FC03 read / FC06 write, 16 bit, read-write)
    0  LEVEL_SP_x10      level setpoint in 0.1 %
    1  OUTFLOW_PCT       demand valve opening, 0..100 %

Run:  python 01-modbus-tcp-basics/plant_server.py
"""
import asyncio
import logging
import math
import os

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
from pymodbus.server import StartAsyncTcpServer

PORT = int(os.getenv("MODBUS_PORT", "5020"))   # 502 needs admin rights, 5020 does not

FC_COIL, FC_DI, FC_HR, FC_IR = 1, 2, 3, 4


def build_context() -> ModbusServerContext:
    device = ModbusSlaveContext(
        co=ModbusSequentialDataBlock(0, [0] * 10),
        di=ModbusSequentialDataBlock(0, [0] * 10),
        hr=ModbusSequentialDataBlock(0, [0] * 10),
        ir=ModbusSequentialDataBlock(0, [0] * 10),
    )
    device.setValues(FC_HR, 0, [600, 30])        # setpoint 60.0 %, outflow 30 %
    return ModbusServerContext(slaves=device, single=True)


async def simulate(ctx: ModbusServerContext, period: float = 0.2) -> None:
    """Very small process model, updated 5 times per second."""
    dev = ctx[0]
    level, t = 50.0, 0.0
    while True:
        pump_on = bool(dev.getValues(FC_COIL, 0, 1)[0])
        outflow = dev.getValues(FC_HR, 1, 1)[0]
        level += (1.5 * pump_on - 1.0 * outflow / 100) * period
        level = max(0.0, min(level, 100.0))
        t += period
        temp = 22.0 + 0.5 * math.sin(t / 10)

        dev.setValues(FC_DI, 0, [int(level > 90), int(pump_on)])
        dev.setValues(FC_IR, 0, [round(level * 10), round(temp * 10)])
        await asyncio.sleep(period)


async def main(port: int = PORT) -> None:
    ctx = build_context()
    asyncio.create_task(simulate(ctx))
    logging.info("Modbus TCP plant on port %d (unit id 1)", port)
    await StartAsyncTcpServer(context=ctx, address=("0.0.0.0", port))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    asyncio.run(main())
