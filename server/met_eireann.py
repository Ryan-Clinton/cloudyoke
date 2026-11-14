#!/usr/bin/env python3
"""Met Éireann's ceilometers as reference sources: every one within 250 km of a site.

    python server/met_eireann.py --data data --sites --hours 6
    python server/met_eireann.py --data data --stations 17,104 --hours 6

Met Éireann's open-data EDR API (https://opendata2.met.ie/edr/docs) serves ceilometer readings every 15
seconds: up to five cloud layers, each with its base (sent in hundreds of feet, stored in feet) and its cover
in oktas (eighths of the sky; 9 means vertical visibility, the sky hidden, as by fog; -1 and 99 mean
missing), and the lowest base in feet. Licensed CC BY 4.0: "Contains Met Éireann
data". The service is marked experimental. Checked 10 November 2026: it keeps about the last 26 hours,
about an hour behind real time, and answers at most 154 readings (about 38 minutes) per request, so the
window is fetched in 30-minute steps. What arrives is kept; gaps stay gaps.

Every 15-second reading is kept once, by station and time, in data/reference/MET-<station id>/<UTC date>.jsonl
(about 1.7 MB a station a day), so short-lived changes can be studied. A reference source is not a
station: never on the map as one, never judged (docs/spec.md 5.3.1). A ceilometer only sees straight up,
and only cloud it can measure a base for; no reading is turned into "clear". Standard library only.
"""
import argparse
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import registry

API = "https://opendata2.met.ie/edr/collections/observations-ceilometer-nrt-15s/locations"
AGENT = "cloudyoke (github.com/Ryan-Clinton/cloudyoke)"
# Names for the ceilometers whose names are known (the service's location list gives none)
STATIONS = {17: "Malin Head", 104: "Finner", 105: "Belmullet"}
RADIUS_KM = 250                     # a site's ceilometers: the service's, within this distance
ATTRIBUTION = "Contains Met Éireann data, CC BY 4.0"


STEP = timedelta(minutes=30)        # under the 154-readings-a-request cap (about 38 minutes at 15 s)


def fetch_all(station, start, end):
    """Every reading in the window, fetched in STEP-long requests, as one list of observations."""
    out, t = [], start
    while t < end:
        out += decode(station, fetch(station, t, min(t + STEP, end)))
        t += STEP
    return out


def fetch(station, start, end):
    when = f"{start:%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}"
    url = f"{API}/{station}?{urllib.parse.urlencode({'datetime': when, 'f': 'CoverageJSON'})}"
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read(), parse_constant=lambda c: None)


def number(v):
    """A measured value, or None for Met Éireann's -99 (no data) and anything not a finite number."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= -99:
        return None
    return v


def decode(station, coverage):
    """CoverageJSON point series -> one observation per reading, layers kept as reported."""
    times = coverage["domain"]["axes"]["t"]["values"]
    ranges = coverage.get("ranges", {})
    get = lambda name, i: number((ranges.get(name, {}).get("values") or [None] * len(times))[i])
    out = []
    for i, t in enumerate(times):
        layers = []
        for n in range(1, 6):
            # Layer heights come in hundreds of feet (55 is 5,500 ft), unlike the lowest base, which is in feet.
            # Cover is 0-8 oktas or 9 for vertical visibility (sky hidden); -1 and 99 mean missing.
            base, cover = get(f"cloud_layer_base_height_{n}", i), get(f"cloud_layer_cover_{n}", i)
            base = base * 100 if base is not None else None
            cover = cover if cover is not None and 0 <= cover <= 9 else None
            if base is not None or cover:
                layers.append({"base_ft": base, "oktas": cover, "vertical_visibility": cover == 9})
        when = datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(timezone.utc)
        out.append({
            "source": "met-eireann-ceilometer",
            "station": station,
            "name": STATIONS.get(station, coverage.get("custom", {}).get("station_name")),
            "obs_time": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "lowest_base_ft": get("cloud_base_height_lowest", i),
            "layers": layers,
            "attribution": ATTRIBUTION,
        })
    return out


def unique(observations):
    """Every reading once, oldest first (the 30-minute steps can meet at a shared reading)."""
    kept, times = [], set()
    for o in sorted(observations, key=lambda o: o["obs_time"]):
        if o["obs_time"] not in times:
            times.add(o["obs_time"])
            kept.append(o)
    return kept


def store(root, observations):
    new = 0
    by_file = {}
    for o in observations:
        by_file.setdefault((o["station"], o["obs_time"][:10]), []).append(o)
    for (station, day), rows in sorted(by_file.items()):
        path = Path(root) / "reference" / f"MET-{station}" / f"{day}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        seen = set()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    seen.add(json.loads(line)["obs_time"])
                except (ValueError, KeyError):
                    continue
        lines = [json.dumps(o, separators=(",", ":"), ensure_ascii=False) + "\n" for o in rows if o["obs_time"] not in seen]
        if lines:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            try:
                os.write(fd, "".join(lines).encode("utf-8"))
            finally:
                os.close(fd)
            new += len(lines)
    return new


KEPT = timedelta(hours=26)          # how far back the service still has readings


def newest_stored(root, station, now):
    """The latest reading already stored for a station, from the last two days' files, or None."""
    newest = None
    for day in (now - timedelta(days=1), now):
        path = Path(root) / "reference" / f"MET-{station}" / f"{day:%Y-%m-%d}.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():     # a backfill appends out of order
            try:
                t = json.loads(line)["obs_time"]
            except (ValueError, KeyError):
                continue
            newest = max(newest or t, t)
    return datetime.fromisoformat(newest.replace("Z", "+00:00")) if newest else None


def window_start(now, hours, newest):
    """From the newest stored reading (less a margin), or the last `hours` if that's earlier, never past
    what the service keeps. The feed can stall for most of a day and then publish its backlog all at once
    (10-11 Nov 2026: nothing after 14:30 until 14:00 the next day), so a fixed window would slide past it."""
    start = now - timedelta(hours=hours)
    if newest is not None:
        start = min(start, newest - timedelta(minutes=15))
    return max(start, now - KEPT)


def locations():
    """Every ceilometer the service has: {id: (lat, lon)}."""
    req = urllib.request.Request(f"{API}?f=json", headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        features = json.loads(r.read()).get("features", [])
    return {int(f["id"]): (f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0]) for f in features}


def near_sites(root, places, radius_km=RADIUS_KM):
    """The ceilometers within radius_km of any site in the registry. Ireland's network only, so a site
    elsewhere simply has none: each country's ceilometers are a collector of their own."""
    sites = registry.sites(root).values()
    return sorted(i for i, (lat, lon) in places.items()
                  if any(registry.distance(s["lat"], s["lon"], lat, lon)[0] <= radius_km for s in sites))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--hours", type=int, default=3,
                    help="at least this far back, and further to the newest reading already stored; the service keeps about 26")
    ap.add_argument("--stations", help="Met Éireann EDR location ids, comma-separated")
    ap.add_argument("--sites", action="store_true", help=f"every ceilometer within {RADIUS_KM} km of a site in the registry")
    a = ap.parse_args()
    end = datetime.now(timezone.utc)
    try:
        places = locations()
    except (OSError, ValueError, KeyError) as e:
        sys.exit(f"met_eireann: couldn't list the ceilometers: {e}")
    wanted = [int(s) for s in (a.stations or "").split(",") if s.strip()]
    if a.sites:
        wanted += [i for i in near_sites(a.data, places) if i not in wanted]
    if not wanted:
        print("met_eireann: no ceilometers near any site")
        return
    registry.note_references(a.data, {f"MET-{i}": {"kind": "ceilometer", "name": STATIONS.get(i, f"Met Éireann ceilometer {i}"),
                                                    "lat": places[i][0], "lon": places[i][1]} for i in wanted if i in places})
    failed = 0
    for station in wanted:
        start = window_start(end, max(1, a.hours), newest_stored(a.data, station, end))
        try:
            obs = unique(fetch_all(station, start, end))
        except (OSError, ValueError, KeyError) as e:
            print(f"met_eireann: {station}: couldn't fetch: {e}")
            failed += 1
            continue
        name = next((o["name"] for o in obs if o.get("name")), None)
        if name and station in places:       # the service names a station only in its readings
            registry.note_references(a.data, {f"MET-{station}": {"kind": "ceilometer", "name": name,
                                                                 "lat": places[station][0], "lon": places[station][1]}})
        print(f"met_eireann: {name or station}: {len(obs)} readings fetched, {store(a.data, obs)} new")
    sys.exit(1 if failed and failed == len(wanted) else 0)


if __name__ == "__main__":
    main()
