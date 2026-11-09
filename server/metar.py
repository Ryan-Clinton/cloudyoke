#!/usr/bin/env python3
"""Airport weather reports (METARs) as a reference source, City of Derry (EGAE) first.

    python server/metar.py --data data --ids EGAE --hours 360

Fetches from the Aviation Weather Center's free API, keeps every report once (by airport, observation
time and the raw text, so a correction is kept beside the original) in data/reference/<ICAO>/<UTC date>.jsonl.
Run it every 30 minutes on a timer: one request returns at most 400 reports, about 13 days at Derry,
so history that isn't collected is lost.

A reference source is not a station: it never goes on the map as one and is never judged. The report's own
cloud codes are kept exactly (CAVOK, NSC, NCD, CLR, SKC, FEW, SCT, BKN, OVC, VV) and never turned into
"clear": NCD only means the ceilometer saw nothing directly overhead, and CAVOK and NSC mean no cloud that
matters to aviation, which can still be cloud that matters to a camera (docs/spec.md section 4).
Standard library only.
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://aviationweather.gov/api/data/metar"
AGENT = "cloudyoke (github.com/Ryan-Clinton/cloudyoke)"
MILE_KM = 1.609344


def fetch(ids, hours):
    url = f"{API}?{urllib.parse.urlencode({'ids': ','.join(ids), 'format': 'json', 'hours': hours})}"
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    return json.loads(body) if body.strip() else []


def visibility_km(visib):
    """The API gives statute miles, as a number or text like "6+". Returns (km, or_more)."""
    if visib is None:
        return None, False
    text = str(visib)
    more = text.endswith("+")
    try:
        return round(float(text.rstrip("+")) * MILE_KM, 1), more
    except ValueError:
        return None, False


def decode(m):
    """One API record as a reference observation: the raw report, its real observation time, and the
    decoded values as the report states them. Nothing here judges clear or cloudy."""
    raw = m.get("rawOb", "")
    km, more = visibility_km(m.get("visib"))
    words = raw.split()
    return {
        "source": "metar",
        "icao": m["icaoId"],
        "obs_time": datetime.fromtimestamp(m["obsTime"], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "raw": raw,
        "auto": "AUTO" in words,
        "correction": "COR" in words,
        "cover": m.get("cover"),                       # the report's overall code, kept as given
        "layers": [{"cover": c.get("cover"), "base_ft": c.get("base")} for c in m.get("clouds") or []],
        "vertical_visibility_ft": next((int(w[2:]) * 100 for w in words if re.fullmatch(r"VV\d{3}", w)), None),
        "visibility_km": km,
        "visibility_or_more": more,
        "weather": m.get("wxString"),
        "temp_c": m.get("temp"),
        "dewpoint_c": m.get("dewp"),
        "wind_dir": m.get("wdir"),
        "wind_kt": m.get("wspd"),
        "pressure_hpa": m.get("altim"),
        "api": {"reportTime": m.get("reportTime"), "receiptTime": m.get("receiptTime"), "metarType": m.get("metarType")},
    }


def store(root, observations):
    """Append the reports not already kept. Returns how many were new."""
    new = 0
    by_day = {}
    for o in observations:
        by_day.setdefault((o["icao"], o["obs_time"][:10]), []).append(o)
    for (icao, day), rows in sorted(by_day.items()):
        path = Path(root) / "reference" / icao / f"{day}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        seen = set()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line)
                    seen.add((r["obs_time"], r["raw"]))
                except (ValueError, KeyError):
                    continue
        lines = []
        for o in sorted(rows, key=lambda r: r["obs_time"]):
            if (o["obs_time"], o["raw"]) not in seen:
                seen.add((o["obs_time"], o["raw"]))
                lines.append(json.dumps(o, separators=(",", ":"), ensure_ascii=False) + "\n")
        if lines:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            try:
                os.write(fd, "".join(lines).encode("utf-8"))
            finally:
                os.close(fd)
            new += len(lines)
    return new


def load(root, icao, start, end):
    """Kept reports for one airport with start <= observation time < end, oldest first."""
    rows = []
    for path in sorted((Path(root) / "reference" / icao).glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                t = datetime.fromisoformat(r["obs_time"].replace("Z", "+00:00"))
            except (ValueError, KeyError):
                continue
            if start <= t < end:
                rows.append((t, r))
    return sorted(rows, key=lambda x: x[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--ids", default="EGAE", help="ICAO codes, comma-separated")
    ap.add_argument("--hours", type=int, default=6, help="how far back to ask for; 360 on a first run")
    a = ap.parse_args()
    ids = [i.strip().upper() for i in a.ids.split(",") if i.strip()]
    try:
        records = fetch(ids, a.hours)
    except OSError as e:
        sys.exit(f"metar: couldn't fetch: {e}")
    new = store(a.data, [decode(m) for m in records if m.get("icaoId") and m.get("obsTime")])
    print(f"metar: {len(records)} reports fetched, {new} new")


if __name__ == "__main__":
    main()
