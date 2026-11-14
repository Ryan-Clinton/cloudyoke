#!/usr/bin/env python3
"""Meteosat's view of each joined site: a rough cloud verdict from the satellite's 10.5 µm infrared picture,
for anyone who has joined, before they have a sensor.

    python server/satellite.py --data data                 every site in data/sites.json, the newest picture
    python server/satellite.py --data data --hours 6       and any picture of the last 6 hours not yet kept
    python server/satellite.py --at 55.07,-6.51            one place, printed, nothing kept

The method is telescopeyoke's clouds.py (github.com/Ryan-Clinton/telescopeyoke), copied rather than imported so
this repository stands alone. EUMETSAT's public map service (view.eumetsat.int) draws the Meteosat Third
Generation 10.5 µm picture, a new one every 10 minutes, day and night: cloud tops are cold and drawn bright,
clear land and sea are warm and drawn dark. For each site the service draws the same box telescopeyoke's
verdicts use (1.7° of latitude either side, 3.7° of longitude, 1110 by 510 pixels), and the verdict is the
site's brightness (a 9 by 9 pixel patch, about 3 km) against the darkest tenth of the box, which stands in for
clear sky:

    more than 20 brighter: "cloud";  less than 10: "probably clear";  between: "thin or broken cloud"

It is a rough measure, not calibrated against anything at the site. That is what joined sites are for: each
host's reports of the real sky (seen.py), an imager's frames, and later a station's readings score it, site by
site.

Privacy (docs/spec.md 6): a site is judged at the centre of its 0.05° cell, never at a position someone gave,
so nothing here or in what it keeps is finer than the cell. Keeps one line per site and picture in
data/satellite/<site>/<UTC date>.jsonl. Contains EUMETSAT data, © EUMETSAT. Standard library only.
"""
import argparse
import json
import math
import os
import struct
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

WMS = "https://view.eumetsat.int/geoserver/wms"
CAPABILITIES = "https://view.eumetsat.int/geoserver/mtg_fd/ir105_hrfi/ows"
LAYER = "mtg_fd:ir105_hrfi"
AGENT = "cloudyoke (github.com/Ryan-Clinton/cloudyoke)"
WEST_EAST, SPAN = 3.7, 1.7          # degrees of longitude each way and latitude either side: telescopeyoke's close view
WIDTH, HEIGHT = 1110, 510
PATCH = 4                           # the site's patch: this many pixels each side of its own, so 9 by 9
CLEAR_PERCENTILE = 10
CLOUD_ABOVE, CLEAR_BELOW = 20, 10
CELL = 0.05
STEP_MIN = 10                       # a new picture every 10 minutes
STALE_MIN = 40                      # a newest picture older than this means the service has stopped


def cell(lat, lon):
    """The centre of the 0.05° cell a position falls in (spec 6): the only position a site is judged at."""
    return (round((math.floor(lat / CELL) + 0.5) * CELL, 3), round((math.floor(lon / CELL) + 0.5) * CELL, 3))


def verdict(margin):
    if margin > CLOUD_ABOVE:
        return "cloud"
    return "probably clear" if margin < CLEAR_BELOW else "thin or broken cloud"


def luma(r, g, b):
    """Pillow's RGB to grey (ITU-R 601, rounded)."""
    return (r * 19595 + g * 38470 + b * 7471 + 0x8000) >> 16


def png_grey(data):
    """An 8-bit PNG as (width, height, rows of grey levels 0-255), grey as Pillow's convert("L") gives it, so
    the numbers match telescopeyoke's. Palette, grey and RGB(A) pictures; not interlaced ones."""
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
        if colour == 3:
            lut = [luma(*p) for p in palette]
            rows.append([lut[v] for v in line])
        elif colour in (0, 4):
            rows.append(list(line[::channels]))
        else:
            rows.append([luma(line[x], line[x + 1], line[x + 2]) for x in range(0, stride, channels)])
    return w, h, rows


def percentile(values, q):
    """numpy's default (linear) percentile."""
    s = sorted(values)
    k = (len(s) - 1) * q / 100
    lo = math.floor(k)
    return s[lo] + (s[min(lo + 1, len(s) - 1)] - s[lo]) * (k - lo)


def judge(w, h, rows):
    """(the site's brightness, the clear-sky stand-in), with the site at the picture's centre."""
    x, y = round(w * WEST_EAST / (2 * WEST_EAST)), h // 2
    patch = [rows[j][i] for j in range(y - PATCH, y + PATCH + 1) for i in range(x - PATCH, x + PATCH + 1)]
    return sum(patch) / len(patch), percentile([v for row in rows for v in row], CLEAR_PERCENTILE)


def _get(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get("Content-Type", "")


def picture_time(timeout=15):
    """When the newest picture was taken (UTC), from the service's own capabilities."""
    body, _ = _get(f"{CAPABILITIES}?service=WMS&version=1.3.0&request=GetCapabilities", timeout)
    for node in ET.fromstring(body).iter():
        if node.tag.rsplit("}", 1)[-1] == "Dimension" and node.get("name") == "time" and node.get("default"):
            return datetime.fromisoformat(node.get("default").replace("Z", "+00:00"))
    raise ValueError("the service didn't say when its newest picture was taken")


def picture(lat, lon, when, timeout=60):
    params = {"service": "WMS", "version": "1.3.0", "request": "GetMap", "layers": LAYER, "styles": "",
              "crs": "EPSG:4326", "bbox": f"{lat - SPAN:.3f},{lon - WEST_EAST:.3f},{lat + SPAN:.3f},{lon + WEST_EAST:.3f}",
              "width": WIDTH, "height": HEIGHT, "format": "image/png", "time": when.strftime("%Y-%m-%dT%H:%M:00Z")}
    body, kind = _get(f"{WMS}?{urllib.parse.urlencode(params)}", timeout)
    if not kind.startswith("image/png"):
        # The service sometimes answers with an error page instead of a picture
        raise ValueError(f"the service sent {kind or 'something unnamed'}, not a picture")
    return png_grey(body)


def look(lat, lon, when):
    here, clear = judge(*picture(lat, lon, when))
    margin = here - clear
    return {"obs_time": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "here": round(here, 1), "clear": round(clear, 1),
            "margin": round(margin, 1), "verdict": verdict(margin)}


def load_sites(root):
    """data/sites.json: {"<id>": {"area": "Ballymoney, County Antrim", "lat": .., "lon": .., ...}}, kept on the
    server only. Each site's position is snapped to its cell here, whatever the file holds."""
    path = Path(root) / "sites.json"
    if not path.exists():
        return {}
    sites = json.loads(path.read_text(encoding="utf-8"))
    for s in sites.values():
        s["lat"], s["lon"] = cell(s["lat"], s["lon"])
    return sites


def kept_times(root, site):
    times = set()
    for path in (Path(root) / "satellite" / site).glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                times.add(json.loads(line)["obs_time"])
            except (ValueError, KeyError):
                continue
    return times


def keep(root, site, row):
    folder = Path(root) / "satellite" / site
    folder.mkdir(parents=True, exist_ok=True)
    fd = os.open(folder / f"{row['obs_time'][:10]}.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, (json.dumps(row, separators=(",", ":")) + "\n").encode())
    finally:
        os.close(fd)


def collect(root, hours=0, now=None):
    """The newest picture, and any of the last `hours` not yet kept, for every site. Returns lines to print."""
    now = now or datetime.now(timezone.utc)
    newest = picture_time()
    age = (now - newest).total_seconds() / 60
    if age > STALE_MIN:
        return [f"satellite: the newest picture is {age:.0f} min old; the service has stopped, nothing kept"]
    wanted = [newest - timedelta(minutes=STEP_MIN * k) for k in range(int(hours * 60 / STEP_MIN) + 1)]
    out = []
    for site, s in load_sites(root).items():
        have = kept_times(root, site)
        for when in wanted:
            if when.strftime("%Y-%m-%dT%H:%M:%SZ") in have:
                continue
            try:
                row = look(s["lat"], s["lon"], when)
            except (OSError, ValueError, zlib.error) as e:
                out.append(f"satellite: {site} {when:%H:%M}: no picture ({e})")
                continue
            keep(root, site, {**row, "fetched": now.strftime("%Y-%m-%dT%H:%M:%SZ")})
            out.append(f"satellite: {site} {when:%d %b %H:%M}: {row['verdict']} (margin {row['margin']})")
    return out


def main():
    ap = argparse.ArgumentParser(description="Meteosat's rough cloud verdict for each joined site.")
    ap.add_argument("--data", default="data")
    ap.add_argument("--hours", type=float, default=1, help="also fetch pictures this far back not yet kept")
    ap.add_argument("--at", metavar="LAT,LON", help="one place, printed, nothing kept")
    a = ap.parse_args()
    if a.at:
        lat, lon = cell(*(float(v) for v in a.at.split(",")))
        when = picture_time()
        r = look(lat, lon, when)
        print(f"{when:%d %b %H:%M} UTC, cell centre {lat}, {lon}: {r['verdict']} "
              f"(site {r['here']}, clear-sky stand-in {r['clear']}, margin {r['margin']})")
        return
    lines = collect(a.data, a.hours)
    print("\n".join(lines) or "satellite: nothing new")
    if lines and all("no picture" in line or "stopped" in line for line in lines):
        sys.exit(1)


if __name__ == "__main__":
    main()
