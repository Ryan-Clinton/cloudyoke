#!/usr/bin/env python3
"""Airport weather reports (METARs) as a reference source: every airport within 150 km of each site.

    python server/metar.py --data data --sites --hours 6         each site's airports, found by distance
    python server/metar.py --data data --ids EGAE --hours 360    named airports (a backfill)
    python server/metar.py --data data --box 50,-11,58,-2        every airport in a box (south,west,north,east)
    python server/metar.py --data data --countries GB,IE,US      every airport's latest report in those countries

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
import bz2
import csv
import gzip
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import airport_names
import registry

API = "https://aviationweather.gov/api/data/metar"
CACHE_METARS = "https://aviationweather.gov/data/cache/metars.cache.csv.gz"       # the latest report from every airport
CACHE_STATIONS = "https://aviationweather.gov/data/cache/stations.cache.json.gz"  # each airport's country and name
LAYER_CODES = ("FEW", "SCT", "BKN", "OVC")       # in rising order of cover
RADIUS_KM = 150                                  # a site's airports: every one reporting within this distance
AGENT = "cloudyoke (github.com/Ryan-Clinton/cloudyoke)"
MILE_KM = 1.609344
CODES = ("CAVOK", "NSC", "NCD", "CLR", "SKC")    # whole-sky codes as they appear in a report's text
TILE_LAT, TILE_LON = 2, 3                        # a box is asked for in tiles: 8° by 9° at once timed out (504, 22 Nov 2026)
TILE_TIMEOUT = 20                                # seconds, so a slow service can't use up the whole run


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
    """Kept reports for one airport with start <= observation time < end, oldest first, from its daily files and
    the compressed bundles older days move into (server/housekeep.py). A report in both counts once."""
    rows, seen = [], set()

    def take(line):
        try:
            r = json.loads(line)
            t = datetime.fromisoformat(r["obs_time"].replace("Z", "+00:00"))
        except (ValueError, KeyError):
            return
        if r.get("icao", icao) == icao and start <= t < end and (r["obs_time"], r.get("raw")) not in seen:
            seen.add((r["obs_time"], r.get("raw")))
            rows.append((t, r))

    for path in sorted((Path(root) / "reference" / icao).glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            take(line)
    for path in sorted((Path(root) / "archive" / "airports").glob("*.jsonl.bz2")):
        if start.strftime("%Y-%m-%d") <= path.name[:10] <= end.strftime("%Y-%m-%d"):
            with bz2.open(path, "rt", encoding="utf-8") as f:
                for line in f:
                    take(line)
    return sorted(rows, key=lambda x: x[0])


def fetch_near(lat, lon, hours, radius_km=RADIUS_KM):
    """Every airport report within radius_km of a position: the API's box search, then the box's corners cut
    off. Airports are found, not listed, so a new site gets its own without anyone choosing them."""
    dlat = radius_km / 111.2
    dlon = min(radius_km / (111.2 * max(math.cos(math.radians(lat)), 0.05)), 179)
    box = f"{max(lat - dlat, -90):.2f},{max(lon - dlon, -180):.2f},{min(lat + dlat, 90):.2f},{min(lon + dlon, 180):.2f}"
    return [m for m in fetch_bbox(box, hours) if m.get("lat") is not None and m.get("lon") is not None
            and registry.distance(lat, lon, m["lat"], m["lon"])[0] <= radius_km]


def fetch_bbox(box, hours, timeout=30):
    url = f"{API}?{urllib.parse.urlencode({'bbox': box, 'format': 'json', 'hours': hours})}"
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
    return json.loads(body) if body.strip() else []


def tiles(south, west, north, east):
    """A box as "south,west,north,east" tiles small enough for the API to answer."""
    out, lat = [], south
    while lat < north:
        lon = west
        while lon < east:
            out.append(f"{lat:g},{lon:g},{min(lat + TILE_LAT, north):g},{min(lon + TILE_LON, east):g}")
            lon += TILE_LON
        lat += TILE_LAT
    return out


def parse_box(text):
    """"south,west,north,east" as four numbers, or ValueError."""
    south, west, north, east = (float(v) for v in text.split(","))
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError(text)
    return south, west, north, east


def unique_records(records):
    """Each report once: neighbouring tiles and a site's search can all return the same one."""
    return list({(m["icaoId"], m["obsTime"], m.get("rawOb")): m for m in records}.values())


def note_positions(root, records):
    """Each new airport's name and position in the reference index, so pages can say how far it is from a site.
    One already there is left alone, so two feeds spelling a name differently can't keep rewriting the index,
    except to put right a name the AWC cut short (airport_names.FIXES)."""
    known = registry.references(root)
    registry.note_references(root, {m["icaoId"]: {"kind": "metar", "name": airport_names.name(m["icaoId"], m.get("name")),
                                                   "lat": m["lat"], "lon": m["lon"]}
                                    for m in records if m.get("icaoId") and m.get("lat") is not None
                                    and m["icaoId"] not in known})
    fixed = {k: dict(known[k], name=v) for k, v in airport_names.FIXES.items()
             if k in known and known[k].get("kind") == "metar" and known[k].get("name") != v}
    registry.note_references(root, fixed)


def cache_number(text):
    try:
        v = float(text)
    except (TypeError, ValueError):
        return None
    return int(v) if v.is_integer() else v


def cache_record(header, row, name):
    """One row of the worldwide CSV as the same record the JSON API gives, so decode() stores it the same way. The
    CSV repeats its sky_cover and cloud_base_ft_agl columns, so they're read by position."""
    row = row + [""] * (len(header) - len(row))
    d = dict(zip(header, row))
    raw = d["raw_text"]
    clouds = [{"cover": row[i], "base": cache_number(row[i + 1])}
              for i, c in enumerate(header) if c == "sky_cover" and row[i] in LAYER_CODES]
    cover = max((c["cover"] for c in clouds), key=LAYER_CODES.index, default=None)
    q = re.search(r"\bQ(\d{4})\b", raw)         # the report's own hPa, where it gives them; the CSV has inches of mercury
    inches = cache_number(d.get("altim_in_hg"))
    wdir = d.get("wind_dir_degrees") or None
    return {
        "icaoId": d["station_id"],
        "obsTime": int(datetime.fromisoformat(d["observation_time"].replace("Z", "+00:00")).timestamp()),
        "rawOb": raw, "name": name, "lat": cache_number(d.get("latitude")), "lon": cache_number(d.get("longitude")),
        "temp": cache_number(d.get("temp_c")), "dewp": cache_number(d.get("dewpoint_c")),
        "wdir": cache_number(wdir) if cache_number(wdir) is not None else wdir,
        "wspd": cache_number(d.get("wind_speed_kt")), "visib": d.get("visibility_statute_mi") or None,
        "altim": int(q.group(1)) if q else round(inches * 33.8639, 1) if inches is not None else None,
        "cover": cover, "clouds": clouds, "wxString": d.get("wx_string") or None, "metarType": d.get("metar_type") or None,
    }


def cache_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return gzip.decompress(r.read())


def fetch_countries(countries):
    """The latest report from every airport in these countries, from the worldwide file: one request for all."""
    names = {s["icaoId"]: s.get("site") for s in json.loads(cache_get(CACHE_STATIONS))
             if s.get("icaoId") and s.get("country") in countries}
    rows = csv.reader(cache_get(CACHE_METARS).decode("utf-8", "replace").splitlines())
    header = next(r for r in rows if r and r[0] == "raw_text")
    at = header.index("station_id")
    out = []
    for row in rows:
        if len(row) > at and row[at] in names:
            try:
                out.append(cache_record(header, row, names[row[at]]))
            except (ValueError, KeyError):          # one bad row never costs the rest
                continue
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--ids", help="ICAO codes, comma-separated")
    ap.add_argument("--sites", action="store_true", help=f"every airport within {RADIUS_KM} km of each site in the registry")
    ap.add_argument("--box", help="every airport in south,west,north,east, with or without a site")
    ap.add_argument("--countries", help="every airport's latest report in these ISO country codes, comma-separated")
    ap.add_argument("--hours", type=int, default=6, help="how far back to ask for; 360 on a first run")
    a = ap.parse_args()
    if not (a.ids or a.sites or a.box or a.countries):
        ap.error("give --ids, --sites, --box, --countries or a mix")
    try:
        box = parse_box(a.box) if a.box else None
    except ValueError:
        ap.error("--box takes south,west,north,east")
    records, problems = [], []
    if a.countries:
        try:
            records += fetch_countries({c.strip().upper() for c in a.countries.split(",") if c.strip()})
        except (OSError, ValueError, KeyError, StopIteration) as e:
            problems.append(f"--countries: {e}")
    for tile in tiles(*box) if box else []:
        try:
            records += fetch_bbox(tile, a.hours, TILE_TIMEOUT)
        except (OSError, ValueError) as e:      # the rest still count; the next run's window covers this one
            problems.append(f"{tile}: {e}")
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
    records = unique_records(m for m in records if m.get("icaoId") and m.get("obsTime"))
    note_positions(a.data, records)
    new = store(a.data, [decode(m) for m in records])
    airports = len({m["icaoId"] for m in records})
    print(f"metar: {len(records)} reports from {airports} airports, {new} new"
          + (f"; problems: {'; '.join(problems)}" if problems else ""))


if __name__ == "__main__":
    main()
