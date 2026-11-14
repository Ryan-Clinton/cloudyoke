#!/usr/bin/env python3
"""Airport weather reports (METARs) as a reference source: every airport within 150 km of each site.

    python server/metar.py --data data --sites --hours 6         each site's airports, found by distance
    python server/metar.py --data data --ids EGAE --hours 360    named airports (a backfill)

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
import math
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import registry

API = "https://aviationweather.gov/api/data/metar"
RADIUS_KM = 150                                  # a site's airports: every one reporting within this distance
AGENT = "cloudyoke (github.com/Ryan-Clinton/cloudyoke)"
MILE_KM = 1.609344
CODES = ("CAVOK", "NSC", "NCD", "CLR", "SKC")    # whole-sky codes as they appear in a report's text


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
        # The report's own code, read from its raw text: the API's "cover" field rewrites NCD as CLR (seen on
        # Belfast's AUTO reports, 9 Nov 2026), and NCD is not clear, so the API's version is only kept beside it
        "cover": next((w for w in words if w in CODES), m.get("cover")),
        "api_cover": m.get("cover"),
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


def fetch_near(lat, lon, hours, radius_km=RADIUS_KM):
    """Every airport report within radius_km of a position: the API's box search, then the box's corners cut
    off. Airports are found, not listed, so a new site gets its own without anyone choosing them."""
    dlat = radius_km / 111.2
    dlon = min(radius_km / (111.2 * max(math.cos(math.radians(lat)), 0.05)), 179)
    box = f"{max(lat - dlat, -90):.2f},{max(lon - dlon, -180):.2f},{min(lat + dlat, 90):.2f},{min(lon + dlon, 180):.2f}"
    url = f"{API}?{urllib.parse.urlencode({'bbox': box, 'format': 'json', 'hours': hours})}"
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    records = json.loads(body) if body.strip() else []
    return [m for m in records if m.get("lat") is not None and m.get("lon") is not None
            and registry.distance(lat, lon, m["lat"], m["lon"])[0] <= radius_km]


def note_positions(root, records):
    """Each airport's name and position in the reference index, so pages can say how far it is from a site."""
    registry.note_references(root, {m["icaoId"]: {"kind": "metar", "name": (m.get("name") or m["icaoId"]).split(",")[0],
                                                   "lat": m["lat"], "lon": m["lon"]}
                                    for m in records if m.get("icaoId") and m.get("lat") is not None})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--ids", help="ICAO codes, comma-separated")
    ap.add_argument("--sites", action="store_true", help=f"every airport within {RADIUS_KM} km of each site in the registry")
    ap.add_argument("--hours", type=int, default=6, help="how far back to ask for; 360 on a first run")
    a = ap.parse_args()
    if not (a.ids or a.sites):
        ap.error("give --ids, --sites or both")
    records, problems = [], []
    if a.ids:
        try:
            records += fetch([i.strip().upper() for i in a.ids.split(",") if i.strip()], a.hours)
        except OSError as e:
            problems.append(f"--ids: {e}")
    if a.sites:
        for sid, s in registry.sites(a.data).items():
            try:
                records += fetch_near(s["lat"], s["lon"], a.hours)
            except OSError as e:
                problems.append(f"{sid}: {e}")
    if problems and not records:
        sys.exit(f"metar: couldn't fetch: {'; '.join(problems)}")
    records = [m for m in records if m.get("icaoId") and m.get("obsTime")]
    note_positions(a.data, records)
    new = store(a.data, [decode(m) for m in records])
    airports = len({m["icaoId"] for m in records})
    print(f"metar: {len(records)} reports from {airports} airports, {new} new"
          + (f"; problems: {'; '.join(problems)}" if problems else ""))


if __name__ == "__main__":
    main()
