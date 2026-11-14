#!/usr/bin/env python3
"""The first station's other half: reads the Nano's lines over USB (firmware/nano-usb), timestamps them with
this computer's clock, and stores them as readings in the receiver's format (docs/spec.md 5.2), so
night_graph.py and the airport comparison work on them unchanged.

    python server/serial_station.py --port /dev/ttyUSB0 --unit cy-0001 --data data
    python server/serial_station.py --port COM5 --unit cy-0001 --data data          (Windows)

By default it writes straight to data/<unit>/<UTC date>.jsonl, so no server is needed on the night.
With --url and --key it also POSTs to a receiver, keeping what it couldn't send and trying again; the local
copy is written either way, so a host always has their own readings.
Needs the pyserial package (pip install pyserial). Readings are marked hw "nano-usb", so they are never
mistaken for a WiFi station's. The computer's clock must be right (it normally is, set over the internet).
"""
import argparse
import json
import math
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

FIELDS = {"sky": "sky_c", "amb": "sensor_c", "air": "air_c", "hum": "humidity", "pres": "pressure_hpa"}


def parse(line):
    """One Nano line as a dict of its values, or None if it isn't a reading line."""
    words = line.strip().split()
    if len(words) < 2 or words[0] != "CY" or words[1] != "v=1":
        return None
    out = {"errors": []}
    for w in words[2:]:
        key, _, val = w.partition("=")
        if key == "err":
            out["errors"].append(val)
        elif key == "chip":
            out["chip"] = val.upper()
        elif key in FIELDS:
            try:
                v = float(val)
            except ValueError:
                continue
            if math.isfinite(v):
                out[FIELDS[key]] = v
    return out


def reading(values, unit, boot, seq, when):
    """A §5.2 reading from parsed values. Sensor faults become flags; nothing is invented."""
    r = {"sky_c": values.get("sky_c"), "air_c": values.get("air_c"), "humidity": values.get("humidity"),
         "pressure_hpa": values.get("pressure_hpa")}
    readings = {k: round(v, 2) for k, v in r.items() if v is not None}
    flags = []
    if values["errors"] or "sky_c" not in readings or "air_c" not in readings:
        flags.append("sensor_read_failed")
    if values.get("chip") == "58":
        flags.append("bmp280")
    if "sky_c" in readings and not -70 <= readings["sky_c"] <= 60:
        flags.append("sky_out_of_range")
    if "air_c" in readings and not -40 <= readings["air_c"] <= 50:
        flags.append("air_out_of_range")
    caps = [c for c, k in (("sky_temperature", "sky_c"), ("air_temperature", "air_c"), ("humidity", "humidity"),
                           ("pressure", "pressure_hpa")) if k in readings]
    out = {"schema": 1, "unit": unit, "source": "cloudyoke-esp32", "capabilities": caps, "hw": "nano-usb",
           "fw": "nano-usb-1", "boot": boot, "seq": seq, "t": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "t_ok": True,
           "readings": readings, "flags": flags}
    if "sensor_c" in values:
        readings["sensor_c"] = round(values["sensor_c"], 2)   # the MLX90614's own temperature, kept for checking
    return out


def next_boot(data, unit):
    """A restart counter kept beside the data, one up on every start, so seq numbers never repeat."""
    path = Path(data) / unit / "boot.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        boot = int(path.read_text()) + 1
    except (OSError, ValueError):
        boot = 1
    path.write_text(str(boot))
    return boot


def write_local(data, r):
    path = Path(data) / r["unit"] / f"{r['t'][:10]}.jsonl"
    line = json.dumps(r, separators=(",", ":"), allow_nan=False) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line.encode("ascii", "backslashreplace"))
    finally:
        os.close(fd)


def post(url, key, batch):
    req = urllib.request.Request(url, data=json.dumps(batch).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status == 200


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="the Nano's serial port, e.g. /dev/ttyUSB0 or COM5")
    ap.add_argument("--unit", default="cy-0001")
    ap.add_argument("--data", default="data")
    ap.add_argument("--url", help="a receiver to POST to as well as writing files")
    ap.add_argument("--key")
    a = ap.parse_args()
    try:
        import serial
    except ImportError:
        sys.exit("serial_station: needs pyserial (pip install pyserial)")
    if a.url and not a.key:
        sys.exit("serial_station: --url needs --key")
    boot, seq, pending = next_boot(a.data, a.unit), 0, []
    print(f"serial_station: {a.unit}, boot {boot}, reading {a.port}; Ctrl+C to stop", flush=True)
    while True:
        try:
            with serial.Serial(a.port, 115200, timeout=90) as port:
                for raw in port:
                    line = raw.decode("ascii", "replace").strip()
                    values = parse(line)
                    if values is None:
                        if line:
                            print(f"  (nano) {line}", flush=True)
                        continue
                    seq += 1
                    r = reading(values, a.unit, boot, seq, datetime.now(timezone.utc))
                    write_local(a.data, r)                        # always kept here too, sent or not
                    if a.url:
                        pending = (pending + [r])[-360:]          # six hours kept through a drop, as the spec says
                        try:
                            if post(a.url, a.key, pending):
                                pending = []
                        except OSError as e:
                            print(f"  couldn't send ({e}); {len(pending)} kept", flush=True)
                    shown = " ".join(f"{k}={v}" for k, v in r["readings"].items())
                    print(f"{r['t']} {shown} {' '.join(r['flags'])}".rstrip(), flush=True)
        except serial.SerialException as e:
            print(f"serial_station: {e}; trying again in 10 s", flush=True)
            time.sleep(10)
        except KeyboardInterrupt:
            print("serial_station: stopped")
            return


if __name__ == "__main__":
    main()
