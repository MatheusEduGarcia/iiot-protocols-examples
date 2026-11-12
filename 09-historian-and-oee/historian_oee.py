"""
From raw machine signals to OEE: a minimal historian plus the KPI on top.

  1. A machine publishes STATE changes (with a downtime reason) and a PART
     COUNTER to MQTT, exactly like a PLC gateway would. One 8 h shift is
     replayed in a few seconds with timestamps of the real shift.
  2. A historian subscribes and stores every message in SQLite: one narrow
     table (tag, ts, value), the layout every historian uses underneath.
  3. SQL turns those rows into time in state, downtime Pareto, parts per
     hour, and Availability x Performance x Quality = OEE.

Run:  python 09-historian-and-oee/historian_oee.py
"""
import json
import random
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.mqtt import HOST, PORT, client  # noqa: E402

ROOT = f"iiot-examples/09/{uuid.uuid4().hex[:6]}/line-1/filler"
IDEAL_CYCLE_S = 1.2            # ideal rate: 50 parts/min
SHIFT_START = datetime(2026, 11, 12, 6, 0, tzinfo=timezone.utc)
SHIFT_HOURS = 8
PLANNED_BREAK = (timedelta(hours=4), timedelta(minutes=30))   # lunch: not planned production time


# ------------------------------------------------------------------ 1. machine
def simulate_shift(seed: int = 7) -> list[tuple[str, datetime, object]]:
    """Events (tag, ts, value) for one shift: run periods split by stops, counters every minute."""
    rnd = random.Random(seed)
    end = SHIFT_START + timedelta(hours=SHIFT_HOURS)
    br_start = SHIFT_START + PLANNED_BREAK[0]
    br_end = br_start + PLANNED_BREAK[1]
    good = reject = 0
    ev: list = []
    t = SHIFT_START
    while t < end:
        if br_start <= t < br_end:                                   # planned break
            ev.append(("state", t, {"state": "PLANNED_STOP", "reason": "lunch"}))
            t = br_end
            continue
        # a run period, cut short by the break or the end of the shift
        stop_at = min(t + timedelta(minutes=rnd.randint(15, 55)), end, br_start if t < br_start else end)
        ev.append(("state", t, {"state": "RUNNING", "reason": ""}))
        while t < stop_at:
            made = int(60 / IDEAL_CYCLE_S * rnd.uniform(0.80, 0.95))   # slower than ideal
            bad = sum(rnd.random() < 0.015 for _ in range(made))
            good, reject = good + made - bad, reject + bad
            t += timedelta(minutes=1)
            ev.append(("count/good", t, good))
            ev.append(("count/reject", t, reject))
        # most run periods end in an unplanned stop
        if t < end and t != br_start and rnd.random() < 0.7:
            reason = rnd.choice(["jam", "jam", "jam", "material shortage", "changeover", "electrical fault"])
            ev.append(("state", t, {"state": "DOWN", "reason": reason}))
            t = min(t + timedelta(minutes=rnd.randint(3, 20)), end)
    ev.append(("state", end, {"state": "END_OF_SHIFT", "reason": ""}))
    return ev


# ------------------------------------------------------------------ 2. historian
SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    tag   TEXT NOT NULL,
    ts    TEXT NOT NULL,          -- ISO 8601 UTC
    value TEXT NOT NULL           -- JSON, so numbers and objects share one table
);
CREATE INDEX IF NOT EXISTS ix_samples ON samples (tag, ts);
"""


def historian(db: sqlite3.Connection):
    db.executescript(SCHEMA)
    c = client()

    def on_message(_c, _u, m):
        d = json.loads(m.payload)
        db.execute("INSERT INTO samples VALUES (?, ?, ?)",
                   (m.topic[len(ROOT) + 1:], d["ts"], json.dumps(d["value"])))
    c.on_message = on_message
    c.connect(HOST, PORT)
    c.subscribe(f"{ROOT}/#", qos=1)
    c.loop_start()
    return c


def replay(events):
    p = client(); p.connect(HOST, PORT); p.loop_start()
    for tag, ts, value in events:
        p.publish(f"{ROOT}/{tag}", json.dumps({"ts": ts.isoformat(), "value": value}), qos=1)
    time.sleep(1.0); p.loop_stop(); p.disconnect()


# ------------------------------------------------------------------ 3. analytics
STATE_DURATIONS = """
WITH s AS (
  SELECT ts, json_extract(value, '$.state') AS state, json_extract(value, '$.reason') AS reason,
         LEAD(ts) OVER (ORDER BY ts) AS next_ts
  FROM samples WHERE tag = 'state'
)
SELECT state, reason, SUM((julianday(next_ts) - julianday(ts)) * 86400) AS seconds, COUNT(*) AS events
FROM s WHERE next_ts IS NOT NULL
GROUP BY state, reason ORDER BY seconds DESC
"""

PARTS_PER_HOUR = """
WITH c AS (
  SELECT ts, CAST(value AS INTEGER) AS total,
         CAST(value AS INTEGER) - COALESCE(LAG(CAST(value AS INTEGER)) OVER (ORDER BY ts), 0) AS delta
  FROM samples WHERE tag = 'count/good'
)
SELECT strftime('%H:00', ts, '-1 minute') AS hour, SUM(delta) AS good_parts FROM c GROUP BY hour ORDER BY hour
"""


def last(db, tag):
    r = db.execute("SELECT value FROM samples WHERE tag = ? ORDER BY ts DESC LIMIT 1", (tag,)).fetchone()
    return json.loads(r[0]) if r else 0


def oee(db) -> dict:
    rows = db.execute(STATE_DURATIONS).fetchall()
    secs = {}
    for state, _reason, s, _n in rows:
        secs[state] = secs.get(state, 0) + s
    planned = SHIFT_HOURS * 3600 - secs.get("PLANNED_STOP", 0)   # planned production time
    run = secs.get("RUNNING", 0)
    good, reject = last(db, "count/good"), last(db, "count/reject")
    total = good + reject
    a = run / planned
    p = total * IDEAL_CYCLE_S / run
    q = good / total
    return {"planned_s": planned, "run_s": run, "good": good, "reject": reject,
            "availability": a, "performance": p, "quality": q, "oee": a * p * q,
            "downtime": [(r, s, n) for st, r, s, n in rows if st == "DOWN"]}


def main(db_path: str = ":memory:", verbose: bool = True) -> dict:
    db = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
    h = historian(db)
    time.sleep(0.3)
    events = simulate_shift()
    replay(events)
    h.loop_stop(); h.disconnect()
    stored = db.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
    k = oee(db)
    if verbose:
        print(f"historian stored {stored} samples ({len(events)} published)\n")
        print("Parts per hour:")
        for hour, n in db.execute(PARTS_PER_HOUR):
            print(f"  {hour}  {'#' * (n // 150):<22} {n}")
        print("\nDowntime Pareto:")
        for reason, s, n in k["downtime"]:
            print(f"  {reason:<18} {s / 60:5.0f} min  ({n} stops)")
        print(f"\nPlanned time {k['planned_s'] / 3600:.2f} h, run time {k['run_s'] / 3600:.2f} h, "
              f"{k['good']} good + {k['reject']} reject")
        print(f"Availability {k['availability']:.1%} x Performance {k['performance']:.1%} "
              f"x Quality {k['quality']:.1%} = OEE {k['oee']:.1%}")
    k["stored"], k["published"] = stored, len(events)
    return k


if __name__ == "__main__":
    main()
