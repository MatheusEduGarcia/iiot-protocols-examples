"""
Alarm management the ISA-18.2 way: why a plain 'if value > limit' is not
an alarm system.

The same noisy temperature signal is fed to three alarm configurations:

  naive       limit only                 -> chattering, alarm flood
  deadband    limit + 2 C hysteresis     -> clears only well below the limit
  isa         deadband + 5 s on-delay    -> ignores short spikes

Each alarm follows the ISA-18.2 state model:

  NORMAL --(condition)--> UNACK --(ack)--> ACKED --(clears)--> NORMAL
                            \\--(clears)--> RTN_UNACK --(ack)--> NORMAL
  plus SHELVED (operator hides it for a while) and OUT_OF_SERVICE.

Run:  python 10-alarms-isa-18-2/alarms.py
"""
import math
import random
from dataclasses import dataclass, field
from enum import Enum


class State(str, Enum):
    NORMAL = "NORMAL"
    UNACK = "UNACK"              # active, not acknowledged      (flashing on the HMI)
    ACKED = "ACKED"              # active, acknowledged          (steady)
    RTN_UNACK = "RTN_UNACK"      # returned to normal, not acked
    SHELVED = "SHELVED"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"


@dataclass
class HighAlarm:
    tag: str
    limit: float
    deadband: float = 0.0        # alarm clears at limit - deadband
    on_delay_s: float = 0.0      # condition must last this long to raise
    off_delay_s: float = 0.0     # and this long to clear
    priority: str = "HIGH"
    state: State = State.NORMAL
    active: bool = False
    _timer: float = 0.0
    shelved_until: float | None = None
    events: list = field(default_factory=list)

    def update(self, value: float, t: float, dt: float) -> None:
        if self.state == State.OUT_OF_SERVICE:
            return
        if self.state == State.SHELVED and self.shelved_until is not None and t >= self.shelved_until:
            self.shelved_until = None                    # shelving expires on its own
            if self.active:                              # still bad: announce it now
                self.state = State.UNACK
                self.events.append((t, "ACTIVE", value))
            else:
                self.state = State.NORMAL

        # 1) process condition with hysteresis and timers
        want = value > self.limit if not self.active else value > self.limit - self.deadband
        if want != self.active:
            self._timer += dt
            if self._timer >= (self.on_delay_s if want else self.off_delay_s):
                self.active, self._timer = want, 0.0
                self._transition(t, value)
        else:
            self._timer = 0.0

    def _transition(self, t, value):
        if self.state == State.SHELVED:
            return                                       # tracked, but not annunciated
        if self.active:
            if self.state in (State.NORMAL, State.RTN_UNACK):
                self.state = State.UNACK
                self.events.append((t, "ACTIVE", value))
        else:
            self.state = State.NORMAL if self.state == State.ACKED else State.RTN_UNACK
            self.events.append((t, "CLEAR", value))

    def ack(self, t):
        if self.state == State.UNACK:
            self.state = State.ACKED
        elif self.state == State.RTN_UNACK:
            self.state = State.NORMAL
        self.events.append((t, "ACK", None))

    def shelve(self, t, minutes):
        self.state, self.shelved_until = State.SHELVED, t + minutes * 60
        self.events.append((t, "SHELVED", minutes))

    @property
    def activations(self) -> int:
        return sum(1 for e in self.events if e[1] == "ACTIVE")


def temperature(t: float, rnd: random.Random) -> float:
    """Slow drift that sits near the 80 C limit for a few minutes, with noise and spikes."""
    base = 72 + 9 * math.sin(2 * math.pi * t / 1200)            # 20 min cycle, peaks at 81 C
    spike = 6 if rnd.random() < 0.003 else 0                   # occasional 1-sample spike
    return base + rnd.gauss(0, 0.8) + spike


def run(minutes: float = 60, dt: float = 1.0, seed: int = 3, verbose: bool = True) -> dict:
    alarms = {
        "naive": HighAlarm("TT-101", 80),
        "deadband": HighAlarm("TT-101", 80, deadband=2.0),
        "isa": HighAlarm("TT-101", 80, deadband=2.0, on_delay_s=5, off_delay_s=5),
    }
    rnd = random.Random(seed)
    t = 0.0
    while t < minutes * 60:
        v = temperature(t, rnd)
        for a in alarms.values():
            a.update(v, t, dt)
            if a.state == State.UNACK and rnd.random() < 0.05:      # operator acks after ~20 s
                a.ack(t)
        t += dt

    # Shelving demo: a known bad sensor is shelved for 30 min
    shelf = HighAlarm("TT-999", 50)
    shelf.shelve(0, 30)
    for s in range(0, 20 * 60, 10):
        shelf.update(60.0, s, 10)
    during = shelf.activations
    for s in range(20 * 60, 40 * 60, 10):
        shelf.update(60.0, s, 10)

    if verbose:
        print(f"Same signal, {minutes:.0f} minutes, limit 80 C:\n")
        for name, a in alarms.items():
            rate = a.activations / (minutes / 10)
            flag = "  <- alarm flood" if rate > 10 else ("  <- above target" if rate > 1 else "  <- ok")
            print(f"  {name:<9} {a.activations:4d} activations  ({rate:5.1f} per 10 min){flag}")
        print("\n  ISA-18.2 guideline: about 1 alarm per 10 minutes per operator is manageable;")
        print("  more than 10 per 10 minutes is a flood.\n")
        print("Event journal of the 'isa' alarm (first 8):")
        for ev in alarms["isa"].events[:8]:
            tt, kind, val = ev
            print(f"  {int(tt // 60):02d}:{int(tt % 60):02d}  {kind:<7} {'' if val is None else f'{val:.1f} C'}")
        print(f"\nTT-999 shelved for 30 min while its condition stays active:")
        print(f"  announced while shelved: {during}   after the shelf expired: "
              f"{shelf.activations - during} (state {shelf.state.value})")
    return {k: a.activations for k, a in alarms.items()} | {"shelf_during": during, "shelf_after": shelf.activations - during, "shelf_state": shelf.state}


if __name__ == "__main__":
    run()
