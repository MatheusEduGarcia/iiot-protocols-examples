"""
Modbus only moves 16-bit registers. Everything else (floats, 32-bit
counters, scaled analog values, packed status bits, the RTU frame itself)
is a convention between the device and the client. This file shows the
conventions you meet on real equipment, with no library magic.

Run:  python 02-modbus-data-types-rtu/datatypes.py
"""
import struct

# --------------------------------------------------------------------- 32-bit values
def float32_to_regs(value: float, word_order: str = "big") -> list[int]:
    """IEEE-754 float -> two registers. word_order 'big' = ABCD, 'little' = CDAB (word swap)."""
    hi, lo = struct.unpack(">HH", struct.pack(">f", value))
    return [hi, lo] if word_order == "big" else [lo, hi]


def regs_to_float32(regs: list[int], word_order: str = "big") -> float:
    hi, lo = regs if word_order == "big" else regs[::-1]
    return struct.unpack(">f", struct.pack(">HH", hi, lo))[0]


def regs_to_uint32(regs: list[int], word_order: str = "big") -> int:
    hi, lo = regs if word_order == "big" else regs[::-1]
    return (hi << 16) | lo


def regs_to_int16(reg: int) -> int:
    """Registers are unsigned on the wire; negative numbers use two's complement."""
    return reg - 0x10000 if reg & 0x8000 else reg


# --------------------------------------------------------------------- scaling
def scale(raw: float, raw_lo: float, raw_hi: float, eu_lo: float, eu_hi: float, clamp: bool = True) -> float:
    """Linear scaling raw counts -> engineering units (what SCALE / NORM_X+SCALE_X do in a PLC)."""
    v = eu_lo + (raw - raw_lo) * (eu_hi - eu_lo) / (raw_hi - raw_lo)
    return max(min(v, max(eu_lo, eu_hi)), min(eu_lo, eu_hi)) if clamp else v


def ma_to_eu(ma: float, eu_lo: float, eu_hi: float) -> tuple[float | None, str]:
    """4-20 mA loop with NAMUR NE43 limits: <3.8 or >20.5 mA is a failed signal."""
    if ma < 3.8:
        return None, "LOW SIGNAL FAULT (wire break?)"
    if ma > 20.5:
        return None, "HIGH SIGNAL FAULT (short circuit?)"
    return scale(ma, 4, 20, eu_lo, eu_hi), "OK"


# --------------------------------------------------------------------- packed bits
STATUS_BITS = ["ready", "running", "fault", "local_mode", "door_open", "estop_ok"]


def unpack_status(word: int) -> dict[str, bool]:
    return {name: bool(word >> i & 1) for i, name in enumerate(STATUS_BITS)}


# --------------------------------------------------------------------- RTU framing
def crc16_modbus(data: bytes) -> int:
    """CRC-16/MODBUS: poly 0xA001 (reflected 0x8005), init 0xFFFF."""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def rtu_read_holding(unit: int, address: int, count: int) -> bytes:
    """Build an RTU request: [unit][FC03][addr hi lo][count hi lo][CRC lo hi]."""
    pdu = struct.pack(">BBHH", unit, 0x03, address, count)
    crc = crc16_modbus(pdu)
    return pdu + struct.pack("<H", crc)            # CRC goes low byte first


def rtu_check(frame: bytes) -> bool:
    return crc16_modbus(frame[:-2]) == struct.unpack("<H", frame[-2:])[0]


def tcp_read_holding(transaction: int, unit: int, address: int, count: int) -> bytes:
    """Same request over TCP: MBAP header instead of CRC."""
    pdu = struct.pack(">BHH", 0x03, address, count)
    return struct.pack(">HHHB", transaction, 0, len(pdu) + 1, unit) + pdu


if __name__ == "__main__":
    print("== 32-bit float 123.456 ==")
    for order in ("big", "little"):
        regs = float32_to_regs(123.456, order)
        print(f"  {order:6} word order -> {[hex(r) for r in regs]}")
    wrong = regs_to_float32(float32_to_regs(123.456, "big"), "little")
    print(f"  read with the wrong word order: {wrong:.6g}  <- the classic 'garbage value' bug")

    print("\n== 32-bit counter split in two registers ==")
    print("  regs [0x0001, 0x86A0] ->", regs_to_uint32([0x0001, 0x86A0]))

    print("\n== signed 16-bit ==")
    print("  raw 0xFFF6 ->", regs_to_int16(0xFFF6), "(a temperature of -1.0 C at x10)")

    print("\n== analog scaling ==")
    print("  Siemens raw 13824 of 0..27648 on 0..10 bar ->", scale(13824, 0, 27648, 0, 10), "bar")
    for ma in (4.0, 12.0, 20.0, 2.1):
        print(f"  {ma:4.1f} mA on 0..150 C ->", ma_to_eu(ma, 0, 150))

    print("\n== packed status word 0b100011 ==")
    print(" ", unpack_status(0b100011))

    print("\n== the same 'read 2 holding registers at 100' request ==")
    rtu = rtu_read_holding(1, 100, 2)
    print("  RTU :", rtu.hex(" "), " CRC ok:", rtu_check(rtu))
    print("  TCP :", tcp_read_holding(1, 1, 100, 2).hex(" "))
    bad = rtu[:-1] + bytes([rtu[-1] ^ 0x01])
    print("  RTU with one flipped bit, CRC ok:", rtu_check(bad))
