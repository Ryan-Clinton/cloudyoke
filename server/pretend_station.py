#!/usr/bin/env python3
"""A pretend reference station, for trying the receiver before real hardware exists. It sends a made-up
night (clear, then cloud arriving at 22:00, a 30-minute power cut, ten wet readings) in batches, then
resends the first batch, as after a lost reply, which should all come back as duplicates.

    python server/pretend_station.py --url http://127.0.0.1:8095/cloudyoke/send --key SECRET --night 2026-11-20

The readings are made up and say so: hw is "pretend". Standard library only.
"""
import argparse
import json
import math
import urllib.request
from datetime import datetime, timedelta, timezone


def night(unit, date, boot=1):
    start = datetime.combine(date, datetime.min.time(), timezone.utc) + timedelta(hours=17)
    for i in range(14 * 60):                          # 17:00 to 07:00, one a minute
        t = start + timedelta(minutes=i)
        if 200 <= i < 230:                            # a 30-minute power cut: no readings at all, so the graph shows a gap
            continue
        cloud = min(max((i - 300) / 20, 0), 1)       # clear until 22:00, then cloud within 20 minutes
        air = 6 - i / 200 + 0.3 * math.sin(i / 37)
        sky = air - 28 + 22 * cloud + 0.8 * math.sin(i / 7) + 0.5 * math.sin(i / 3.1)
        yield {"schema": 1, "unit": unit, "source": "cloudyoke-esp32",
               "capabilities": ["sky_temperature", "air_temperature", "humidity"], "hw": "pretend", "fw": "pretend-0.1",
               "boot": boot, "seq": i + 1, "t": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "t_ok": True,
               "readings": {"sky_c": round(sky, 2), "air_c": round(air, 2), "humidity": round(80 + 10 * cloud, 1)},
               "flags": ["wet"] if 600 <= i < 610 else []}


def send(url, key, batch):
    req = urllib.request.Request(url, data=json.dumps(batch).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8095/cloudyoke/send")
    ap.add_argument("--key", required=True)
    ap.add_argument("--unit", default="cy-0001")
    ap.add_argument("--night", required=True)
    ap.add_argument("--batch", type=int, default=60)
    a = ap.parse_args()
    readings = list(night(a.unit, datetime.strptime(a.night, "%Y-%m-%d").date()))
    totals = {"stored": 0, "duplicates": 0}
    for i in range(0, len(readings), a.batch):
        answer = send(a.url, a.key, readings[i:i + a.batch])
        for k in totals:
            totals[k] += answer.get(k, 0)
    answer = send(a.url, a.key, readings[:a.batch])   # a resend, as after a lost reply: all duplicates
    totals["duplicates"] += answer.get("duplicates", 0)
    print(json.dumps(totals))


if __name__ == "__main__":
    main()
