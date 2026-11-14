#!/usr/bin/env python3
"""Sites and stations (docs/spec.md 5.1 and 6), kept on the server only.

    python server/registry.py add-site --data data --id brecon --area "Brecon, Wales" --lat 51.95 --lon -3.39 \\
        [--public-cell 0.05] [--as station|existing sensor]
    python server/registry.py register --data data --site brecon [--setup sensor=BAA --setup mounting=wall]
    python server/registry.py setup --data data --unit cy-0002 --setup hood=printed
    python server/registry.py revoke --data data --unit cy-0002
    python server/registry.py list --data data

data/sites.json holds each site: its area's name (all the public ever sees), the position it was given (never
published, never used finer than its 0.05° cell) and the cell size its pages may show: 0.2° unless a 0.05° cell
is safe (spec 6: a town of 1,000 or more, or 3 stations in the cell). data/stations.json holds each station:
its site, a SHA-256 of its key (the key itself is printed once, at registration, and kept nowhere), its setups
with the date each began, and when it was revoked. The receiver re-reads stations.json whenever it changes, so
registering or revoking needs no restart.

Anything that needs a site's position (its references, its night, the satellite) gets it from here, so nothing
about one place is written into the code. Standard library only.
"""
import argparse
import hashlib
import json
import math
import os
import re
import secrets
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

CELL = 0.05
PUBLIC_CELLS = (0.05, 0.2)
ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")


def cell(lat, lon, size=CELL):
    """The centre of the cell of `size` degrees a position falls in."""
    return (round((math.floor(lat / size) + 0.5) * size, 3), round((math.floor(lon / size) + 0.5) * size, 3))


def distance(lat1, lon1, lat2, lon2):
    """Kilometres and compass point from the first position to the second."""
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    km = 6371 * math.acos(max(-1, min(1, math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(dl))))
    bearing = (math.degrees(math.atan2(math.sin(dl) * math.cos(p2),
                                       math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl))) + 360) % 360
    return km, ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((bearing + 22.5) // 45) % 8]


def now_text():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _write(path, data, mode=0o640):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.part")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def sites(root):
    """Every site, with "lat" and "lon" snapped to its 0.05° cell (what the server works with) and "public"
    the centre of the cell its pages may show. The position as given stays in the file only."""
    out = {}
    for sid, s in _read(Path(root) / "sites.json").items():
        size = s.get("public_cell", 0.2) if s.get("public_cell", 0.2) in PUBLIC_CELLS else 0.2
        lat, lon = cell(s["lat"], s["lon"])
        out[sid] = {**s, "lat": lat, "lon": lon, "public": cell(s["lat"], s["lon"], size), "public_cell": size}
    return out


def stations(root):
    return _read(Path(root) / "stations.json")


def site_of(root, unit):
    """The site a station belongs to, or None."""
    st = stations(root).get(unit)
    return sites(root).get(st["site"]) if st else None


def add_site(root, sid, area, lat, lon, public_cell=0.2, kind="station"):
    if not ID.match(sid):
        raise ValueError("a site id is 2 to 40 lower-case letters, digits and hyphens")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("that isn't a position on Earth")
    if public_cell not in PUBLIC_CELLS:
        raise ValueError(f"the public cell is one of {PUBLIC_CELLS}")
    path = Path(root) / "sites.json"
    data = _read(path)
    if sid in data:
        raise ValueError(f"site {sid} already exists")
    data[sid] = {"area": area, "lat": lat, "lon": lon, "public_cell": public_cell, "as": kind, "joined": now_text()[:10]}
    _write(path, data)
    return data[sid]


def references(root):
    """data/reference/index.json: every reference source kept, {key: {kind, name, lat, lon}}, written by the
    collectors as they find sources. Public positions: airports and weather stations, never hosts."""
    return _read(Path(root) / "reference" / "index.json")


def note_references(root, entries):
    if not entries:
        return
    path = Path(root) / "reference" / "index.json"
    data = _read(path)
    if all(data.get(k) == v for k, v in entries.items()):
        return
    data.update(entries)
    _write(path, data, 0o644)


def references_near(root, site, radius_km):
    """The reference sources within radius_km of a site's cell, nearest first, as (key, entry, km, compass)."""
    out = []
    for key, r in references(root).items():
        km, way = distance(site["lat"], site["lon"], r["lat"], r["lon"])
        if km <= radius_km:
            out.append((key, r, km, way))
    return sorted(out, key=lambda x: x[2])


def _hash(key):
    return hashlib.sha256(key.encode()).hexdigest()


def _setup(pairs):
    out = {}
    for p in pairs or []:
        k, sep, v = p.partition("=")
        if not sep or not k:
            raise ValueError(f"a setup is key=value, not {p!r}")
        out[k] = v
    return out


def register(root, site, setup=None):
    """A new station at a site: returns (unit id, key). The key is shown this once and only its hash is kept."""
    if site not in _read(Path(root) / "sites.json"):
        raise ValueError(f"no site {site}: add it first")
    path = Path(root) / "stations.json"
    data = _read(path)
    n = max((int(u[3:]) for u in data if re.fullmatch(r"cy-\d+", u)), default=0) + 1
    unit, key = f"cy-{n:04d}", secrets.token_urlsafe(32)
    data[unit] = {"site": site, "key_sha256": _hash(key), "registered": now_text(), "revoked": None,
                  "setups": [{"from": now_text(), **_setup(setup)}]}
    _write(path, data, 0o600)
    return unit, key


def new_setup(root, unit, setup):
    """A change to a station's setup is a new row with its date, so readings are judged against the right one."""
    path = Path(root) / "stations.json"
    data = _read(path)
    if unit not in data:
        raise ValueError(f"no station {unit}")
    data[unit]["setups"].append({"from": now_text(), **_setup(setup)})
    _write(path, data, 0o600)


def revoke(root, unit):
    path = Path(root) / "stations.json"
    data = _read(path)
    if unit not in data:
        raise ValueError(f"no station {unit}")
    data[unit]["revoked"] = now_text()
    _write(path, data, 0o600)


class Keys:
    """The receiver's view of stations.json: which unit a key belongs to, re-read whenever the file changes.
    Revoked stations' keys are not known at all."""

    def __init__(self, root):
        self.path = Path(root) / "stations.json"
        self.stamp, self.by_hash = None, {}
        self.lock = threading.Lock()

    def unit_for(self, key):
        # Every write replaces the file (a new inode), so (inode, size, mtime) changes on every write even within
        # the clock's resolution; the new list is built before it and its stamp are swapped in together, under a
        # lock, so no thread ever pairs a new stamp with an old list (a revoked key that keeps working)
        with self.lock:
            try:
                st = self.path.stat()
                stamp = (st.st_ino, st.st_size, st.st_mtime_ns)
            except OSError:
                stamp = None
            if stamp != self.stamp:
                by_hash = {s["key_sha256"]: u for u, s in _read(self.path).items() if not s.get("revoked")} if stamp else {}
                self.by_hash, self.stamp = by_hash, stamp
            by_hash = self.by_hash
        return by_hash.get(_hash(key)) if key else None


def main():
    ap = argparse.ArgumentParser(description="cloudyoke's sites and stations.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("add-site", "register", "setup", "revoke", "list"):
        p = sub.add_parser(name)
        p.add_argument("--data", default="data")
        if name == "add-site":
            p.add_argument("--id", required=True)
            p.add_argument("--area", required=True, help="the name the pages show, e.g. \"Brecon, Wales\"")
            p.add_argument("--lat", type=float, required=True)
            p.add_argument("--lon", type=float, required=True)
            p.add_argument("--public-cell", type=float, default=0.2, choices=PUBLIC_CELLS)
            p.add_argument("--as", dest="kind", default="station", choices=("station", "existing sensor"))
        if name == "register":
            p.add_argument("--site", required=True)
        if name in ("setup", "revoke"):
            p.add_argument("--unit", required=True)
        if name in ("register", "setup"):
            p.add_argument("--setup", action="append", metavar="KEY=VALUE")
    a = ap.parse_args()
    try:
        if a.cmd == "add-site":
            add_site(a.data, a.id, a.area, a.lat, a.lon, a.public_cell, a.kind)
            print(f"registry: site {a.id} added")
        elif a.cmd == "register":
            unit, key = register(a.data, a.site, a.setup)
            print(f"registry: {unit} at {a.site}\nkey (shown once, give it to the host): {key}")
        elif a.cmd == "setup":
            new_setup(a.data, a.unit, a.setup)
            print(f"registry: new setup for {a.unit}")
        elif a.cmd == "revoke":
            revoke(a.data, a.unit)
            print(f"registry: {a.unit} revoked")
        else:
            st = stations(a.data)
            for sid, s in sorted(sites(a.data).items()):
                units = [u + (" (revoked)" if v.get("revoked") else "") for u, v in st.items() if v["site"] == sid]
                print(f"{sid}: {s['area']}, as {s['as']}, public cell {s['public_cell']}°; stations: {', '.join(units) or 'none'}")
    except ValueError as e:
        sys.exit(f"registry: {e}")


if __name__ == "__main__":
    main()
