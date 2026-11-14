#!/usr/bin/env python3
"""The weather satellite's view of each site: a rough cloud verdict from 10.5 µm infrared, a reference beside the
site's own sensor, as the airport reports are.

    python server/satellite.py --data data                 every site in the registry, the newest pictures
    python server/satellite.py --data data --hours 6       and any picture of the last 6 hours not yet kept
    python server/satellite.py --at 55.07,-6.51            one place, printed, nothing kept

Each site is seen by the geostationary satellite most nearly overhead (the smallest angle from the point under
it), and not at all past 66° from it, where the view is too slanted to trust:

    Meteosat (MTG-I1, 0°)          Europe, Africa, the Atlantic's east   EUMETSAT's map service, grey levels
    GOES-East (75.2° W)            the Americas' east, the Atlantic's west   NASA GIBS, °C
    GOES-West (137.2° W)           the Americas' west, the Pacific's east    NASA GIBS, °C
    Himawari-9 (140.7° E)          East Asia, Australia, the West Pacific    NASA GIBS, °C

The method is telescopeyoke's clouds.py (github.com/Ryan-Clinton/telescopeyoke): cloud tops are cold, clear land
and sea warm, and the site's 6 km patch is compared with a clear-sky stand-in. Two stand-ins, the colder-reading
of which wins (the clearer one):

- the box round the site (3.4° of latitude by 7.4° of longitude): its warmest tenth;
- the site's own history: the warmest tenth of its patch at the same time of day (within 90 minutes) over the
  last 7 days, once there are 20 such pictures. Without it, a site under an overcast as wide as the box
  compared itself with cloud and read "probably clear".

Meteosat's picture comes as grey levels with no published temperature scale (an overlap with GOES-East on 14
November 2026 put it at roughly 0.4 °C a level), so its thresholds stay telescopeyoke's, in levels; GIBS gives
°C, and its thresholds are the same steps in °C:

    colder than the stand-in by more than 20 levels (8 °C): "cloud";  less than 10 (4 °C): "probably clear"

It is a rough measure, not calibrated against anything at the site; the site's sensor is what it is compared
against (seen.py). Privacy (docs/spec.md 6): a site is judged at the centre of its 0.05° cell, never at a position
someone gave. Keeps one line per site and picture in data/satellite/<site>/<UTC date>.jsonl. Contains EUMETSAT
data, © EUMETSAT; GOES and Himawari imagery from NASA GIBS (NOAA, JMA). Standard library only.
"""
import argparse
import json
import math
import os
import re
import struct
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import registry

AGENT = "cloudyoke (github.com/Ryan-Clinton/cloudyoke)"
EUMETSAT_WMS = "https://view.eumetsat.int/geoserver/wms"
EUMETSAT_CAPABILITIES = "https://view.eumetsat.int/geoserver/mtg_fd/ir105_hrfi/ows"
GIBS_WMS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
GIBS_COLOURS = "https://gibs.earthdata.nasa.gov/colormaps/v1.3/Clean_Longwave_Infrared_Window_Band.xml"
SATELLITES = {
    # key: name, longitude under it, service, layer, units, cloud above, clear below, picture size, patch half-width,
    # minutes after which the newest picture is stale (GIBS runs about 1.5 hours behind)
    "meteosat": dict(name="Meteosat", sub_lon=0.0, service="eumetsat", layer="mtg_fd:ir105_hrfi", units="levels",
                     cloud_above=20, clear_below=10, size=(1110, 510), patch=4, stale_min=40),
    "goes-east": dict(name="GOES-East", sub_lon=-75.2, service="gibs", layer="GOES-East_ABI_Band13_Clean_Infrared",
                      units="°C", cloud_above=8, clear_below=4, size=(370, 170), patch=1, stale_min=180),
    "goes-west": dict(name="GOES-West", sub_lon=-137.2, service="gibs", layer="GOES-West_ABI_Band13_Clean_Infrared",
                      units="°C", cloud_above=8, clear_below=4, size=(370, 170), patch=1, stale_min=180),
    "himawari": dict(name="Himawari", sub_lon=140.7, service="gibs", layer="Himawari_AHI_Band13_Clean_Infrared",
                     units="°C", cloud_above=8, clear_below=4, size=(370, 170), patch=1, stale_min=180),
}
MAX_ANGLE = 66                      # degrees from the point under the satellite: past this, no verdict
WEST_EAST, SPAN = 3.7, 1.7          # the box: degrees of longitude each way and latitude either side
CLEAR_PERCENTILE = 10
OWN_DAYS, OWN_WINDOW_MIN, OWN_MIN_PICTURES = 7, 90, 20
STEP_MIN = 10                       # a new picture every 10 minutes from each satellite
STALE_MIN = 40                      # Meteosat's; each satellite has its own in SATELLITES
GIBS_BEHIND_H = 3                   # how far back GIBS pictures are looked for on each run

cell = registry.cell                # the centre of the 0.05° cell (spec 6): the only position a site is judged at


def choose(lat, lon):
    """The satellite most nearly overhead, or None when every one sees the site past MAX_ANGLE."""
    best, angle = None, 999
    for key, s in SATELLITES.items():
        a = math.degrees(math.acos(math.cos(math.radians(lat)) * math.cos(math.radians(lon - s["sub_lon"]))))
        if a < angle:
            best, angle = key, a
    return best if angle <= MAX_ANGLE else None


def verdict(margin, sat="meteosat"):
    s = SATELLITES[sat]
    if margin > s["cloud_above"]:
        return "cloud"
    return "probably clear" if margin < s["clear_below"] else "thin or broken cloud"


def luma(r, g, b):
    """Pillow's RGB to grey (ITU-R 601, rounded)."""
    return (r * 19595 + g * 38470 + b * 7471 + 0x8000) >> 16


def png_lines(data):
    """An 8-bit, non-interlaced PNG as (width, height, colour type, channels, palette, unfiltered byte rows)."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    i, idat, palette = 8, [], None
    while i < len(data):
        n, kind = struct.unpack(">I4s", data[i:i + 8])
        body = data[i + 8:i + 8 + n]
        if kind == b"IHDR":
            w, h, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            palette = [body[j:j + 3] for j in range(0, len(body), 3)]
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
        i += 12 + n
    if depth != 8 or interlace:
        raise ValueError(f"PNG with bit depth {depth}, interlace {interlace}: not handled")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[colour]
    raw = zlib.decompress(b"".join(idat))
    stride = w * channels
    rows, prev, pos = [], bytearray(stride), 0
    for _ in range(h):
        kind, line = raw[pos], bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        for x in range(stride):
            a = line[x - channels] if x >= channels else 0
            b = prev[x]
            c = prev[x - channels] if x >= channels else 0
            if kind == 1:
                line[x] = (line[x] + a) & 255
            elif kind == 2:
                line[x] = (line[x] + b) & 255
            elif kind == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        rows.append(line)
    return w, h, colour, channels, palette, rows


def png_grey(data):
    """An 8-bit PNG as (width, height, rows of grey levels 0-255), grey as Pillow's convert("L") gives it, so
    the numbers match telescopeyoke's. Palette, grey and RGB(A) pictures."""
    w, h, colour, channels, palette, lines = png_lines(data)
    if colour == 3:
        lut = [luma(*p) for p in palette]
        return w, h, [[lut[v] for v in line] for line in lines]
    if colour in (0, 4):
        return w, h, [list(line[::channels]) for line in lines]
    return w, h, [[luma(line[x], line[x + 1], line[x + 2]) for x in range(0, w * channels, channels)] for line in lines]


_COLOURS = {}


def gibs_colours(timeout=30):
    """GIBS's infrared colour map: {(r, g, b): °C at the middle of its step}."""
    if not _COLOURS:
        body, _ = _get(GIBS_COLOURS, timeout)
        for entry in re.findall(r"<ColorMapEntry[^>]*>", body.decode()):
            rgb, value = re.search(r'rgb="([^"]+)"', entry), re.search(r'value="[\(\[]([^,]+),([^\]\)]+)', entry)
            if not rgb or not value or 'nodata="true"' in entry:
                continue
            lo, hi = value.groups()
            lo = float(lo) if "INF" not in lo else float(hi) - 1
            hi = float(hi) if "INF" not in hi else lo + 1
            _COLOURS.setdefault(tuple(int(v) for v in rgb.group(1).split(",")), (lo + hi) / 2)
    return _COLOURS


def png_celsius(data, colours):
    """A GIBS infrared PNG as rows of °C (None where there is no data), each colour read as the nearest one in
    the colour map, since the service's resampling can blend neighbouring colours."""
    w, h, colour, channels, palette, lines = png_lines(data)
    if colour not in (2, 6):
        raise ValueError("expected an RGB picture from GIBS")
    known, rows = {}, []
    for line in lines:
        row = []
        for x in range(0, w * channels, channels):
            if channels == 4 and line[x + 3] == 0:
                row.append(None)
                continue
            rgb = (line[x], line[x + 1], line[x + 2])
            if rgb not in known:
                known[rgb] = colours.get(rgb)
                if known[rgb] is None:
                    near = min(colours, key=lambda c: (c[0] - rgb[0]) ** 2 + (c[1] - rgb[1]) ** 2 + (c[2] - rgb[2]) ** 2)
                    known[rgb] = colours[near]
            row.append(known[rgb])
        rows.append(row)
    return w, h, rows


def percentile(values, q):
    """numpy's default (linear) percentile."""
    s = sorted(values)
    k = (len(s) - 1) * q / 100
    lo = math.floor(k)
    return s[lo] + (s[min(lo + 1, len(s) - 1)] - s[lo]) * (k - lo)


def box(lat, lon):
    """The box round a site, kept inside the map's edges; returns (south, west, north, east)."""
    south, north = max(lat - SPAN, -90), min(lat + SPAN, 90)
    west, east = lon - WEST_EAST, lon + WEST_EAST
    if west < -180:
        west, east = -180, -180 + 2 * WEST_EAST
    if east > 180:
        west, east = 180 - 2 * WEST_EAST, 180
    return south, west, north, east


def judge(w, h, rows, patch=4, at=None):
    """(the site's coldness, the box's clear-sky stand-in), coldness growing with cold (grey levels, or minus °C);
    the site at pixel `at` (x, y), the centre by default. None for the site when it has no data."""
    x, y = at if at else (round(w / 2), h // 2)
    values = [rows[j][i] for j in range(max(y - patch, 0), min(y + patch + 1, h))
              for i in range(max(x - patch, 0), min(x + patch + 1, w)) if rows[j][i] is not None]
    everything = [v for row in rows for v in row if v is not None]
    if not values or len(everything) < w * h / 4:
        return None, None
    return sum(values) / len(values), percentile(everything, CLEAR_PERCENTILE)


def _get(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get("Content-Type", "")


def picture_time(timeout=15):
    """When Meteosat's newest picture was taken (UTC), from the service's own capabilities."""
    body, _ = _get(f"{EUMETSAT_CAPABILITIES}?service=WMS&version=1.3.0&request=GetCapabilities", timeout)
    for node in ET.fromstring(body).iter():
        if node.tag.rsplit("}", 1)[-1] == "Dimension" and node.get("name") == "time" and node.get("default"):
            return datetime.fromisoformat(node.get("default").replace("Z", "+00:00"))
    raise ValueError("the service didn't say when its newest picture was taken")


def measure(sat, lat, lon, when, timeout=60):
    """(the site's coldness, the box's stand-in) in one satellite's picture at `when`; (None, None) when the
    picture has no data there yet."""
    s = SATELLITES[sat]
    south, west, north, east = box(lat, lon)
    w, h = s["size"]
    url = EUMETSAT_WMS if s["service"] == "eumetsat" else GIBS_WMS
    params = {"service": "WMS", "version": "1.3.0", "request": "GetMap", "layers": s["layer"], "styles": "",
              "crs": "EPSG:4326", "bbox": f"{south:.3f},{west:.3f},{north:.3f},{east:.3f}", "width": w, "height": h,
              "format": "image/png", "time": when.strftime("%Y-%m-%dT%H:%M:00Z")}
    if s["service"] == "gibs":
        params["transparent"] = "true"
    body, kind = _get(f"{url}?{urllib.parse.urlencode(params)}", timeout)
    if not kind.startswith("image/png"):
        # The services sometimes answer with an error page instead of a picture
        raise ValueError(f"the service sent {kind or 'something unnamed'}, not a picture")
    at = (round((lon - west) / (east - west) * w), round((north - lat) / (north - south) * h))
    if s["service"] == "eumetsat":
        w, h, rows = png_grey(body)
    else:
        w, h, rows = png_celsius(body, gibs_colours())
        rows = [[-v if v is not None else None for v in row] for row in rows]
    return judge(w, h, rows, s["patch"], at)


def own_clear(history, when, sat):
    """The site's own clear-sky stand-in: the warmest tenth of its patch at this time of day over the last
    OWN_DAYS days, from this satellite, or None with fewer than OWN_MIN_PICTURES such pictures."""
    minute = when.hour * 60 + when.minute
    same = [r["here"] for t, r in history
            if r.get("satellite", "meteosat") == sat and r.get("here") is not None and timedelta(0) < when - t <= timedelta(days=OWN_DAYS)
            and min(abs(t.hour * 60 + t.minute - minute), 1440 - abs(t.hour * 60 + t.minute - minute)) <= OWN_WINDOW_MIN]
    return percentile(same, CLEAR_PERCENTILE) if len(same) >= OWN_MIN_PICTURES else None


def look(sat, lat, lon, when, history=()):
    here, clear_box = measure(sat, lat, lon, when)
    if here is None:
        return None
    clear_own = own_clear(history, when, sat)
    clear = min(clear_box, clear_own) if clear_own is not None else clear_box
    margin = here - clear
    return {"obs_time": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "satellite": sat, "units": SATELLITES[sat]["units"],
            "here": round(here, 1), "clear": round(clear, 1), "clear_box": round(clear_box, 1),
            "clear_own": round(clear_own, 1) if clear_own is not None else None,
            "margin": round(margin, 1), "verdict": verdict(margin, sat)}


def load_sites(root):
    """The registry's sites, each already snapped to its 0.05° cell."""
    return registry.sites(root)


def kept(root, site):
    """Every kept row for a site, as (time, row)."""
    out = []
    for path in (Path(root) / "satellite" / site).glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                out.append((datetime.fromisoformat(r["obs_time"].replace("Z", "+00:00")), r))
            except (ValueError, KeyError):
                continue
    return sorted(out, key=lambda x: x[0])


def kept_times(root, site):
    return {r["obs_time"] for _, r in kept(root, site)}


def keep(root, site, row):
    folder = Path(root) / "satellite" / site
    folder.mkdir(parents=True, exist_ok=True)
    fd = os.open(folder / f"{row['obs_time'][:10]}.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, (json.dumps(row, separators=(",", ":")) + "\n").encode())
    finally:
        os.close(fd)


def collect(root, hours=0, now=None):
    """The newest pictures, and any of the last `hours` not yet kept, for every site, each from the satellite
    most nearly overhead. Returns lines to print."""
    now = now or datetime.now(timezone.utc)
    by_sat = {}
    out = []
    for site, s in load_sites(root).items():
        sat = choose(s["lat"], s["lon"])
        if sat is None:
            out.append(f"satellite: {site}: no geostationary satellite sees it well enough")
            continue
        by_sat.setdefault(sat, []).append((site, s))
    for sat, sites in by_sat.items():
        if SATELLITES[sat]["service"] == "eumetsat":
            newest = picture_time()
            age = (now - newest).total_seconds() / 60
            if age > SATELLITES[sat]["stale_min"]:
                out.append(f"satellite: Meteosat's newest picture is {age:.0f} min old; the service has stopped, nothing kept")
                continue
            wanted = [newest - timedelta(minutes=STEP_MIN * k) for k in range(int(hours * 60 / STEP_MIN) + 1)]
        else:
            # GIBS doesn't say what it has without a 2.5 MB listing, so each run asks for every 10-minute picture of
            # the last few hours not yet kept; one not there yet comes back empty and is simply asked for again
            top = now.replace(second=0, microsecond=0, minute=now.minute - now.minute % STEP_MIN)
            wanted = [top - timedelta(minutes=STEP_MIN * k) for k in range(int(max(hours, GIBS_BEHIND_H) * 60 / STEP_MIN) + 1)]
        for site, s in sites:
            history = kept(root, site)
            have = {r["obs_time"] for _, r in history}
            for when in wanted:
                if when.strftime("%Y-%m-%dT%H:%M:%SZ") in have:
                    continue
                try:
                    row = look(sat, s["lat"], s["lon"], when, history)
                except (OSError, ValueError, zlib.error) as e:
                    out.append(f"satellite: {site} {when:%H:%M}: no picture ({e})")
                    continue
                if row is None:
                    continue                    # not published yet
                keep(root, site, {**row, "fetched": now.strftime("%Y-%m-%dT%H:%M:%SZ")})
                history.append((when, row))
                out.append(f"satellite: {site} {when:%d %b %H:%M} {SATELLITES[sat]['name']}: {row['verdict']} "
                           f"(margin {row['margin']} {row['units']})")
    return out


def main():
    ap = argparse.ArgumentParser(description="The weather satellite's rough cloud verdict for each site.")
    ap.add_argument("--data", default="data")
    ap.add_argument("--hours", type=float, default=1, help="also fetch pictures this far back not yet kept")
    ap.add_argument("--at", metavar="LAT,LON", help="one place, printed, nothing kept")
    a = ap.parse_args()
    if a.at:
        lat, lon = cell(*(float(v) for v in a.at.split(",")))
        sat = choose(lat, lon)
        if sat is None:
            sys.exit("satellite: no geostationary satellite sees that place well enough")
        if SATELLITES[sat]["service"] == "eumetsat":
            times = [picture_time()]
        else:
            now = datetime.now(timezone.utc)
            top = now.replace(second=0, microsecond=0, minute=now.minute - now.minute % STEP_MIN)
            times = [top - timedelta(minutes=STEP_MIN * k) for k in range(GIBS_BEHIND_H * 6 + 1)]
        for when in times:
            r = look(sat, lat, lon, when)
            if r:
                print(f"{when:%d %b %H:%M} UTC, {SATELLITES[sat]['name']}, cell centre {lat}, {lon}: {r['verdict']} "
                      f"(site {r['here']}, clear-sky stand-in {r['clear']}, margin {r['margin']} {r['units']})")
                return
        sys.exit(f"satellite: no picture from {SATELLITES[sat]['name']} in the last {GIBS_BEHIND_H} hours")
    lines = collect(a.data, a.hours)
    print("\n".join(lines) or "satellite: nothing new")
    if lines and all("no picture" in line or "stopped" in line for line in lines):
        sys.exit(1)


if __name__ == "__main__":
    main()
