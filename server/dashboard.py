#!/usr/bin/env python3
"""The reference-source dashboard: what each airport and ceilometer last reported, how old that is, and the
last 24 hours side by side, west to east. Observations, not predictions.

    python server/dashboard.py --data data --out www

Writes www/index.html (a static page) and www/status.json (each source's latest observation and whether it
is stale), so a source that stops is seen rather than silently missing. Run after the collectors.
Standard library only.
"""
import argparse
import html
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOME = ("Ballymoney", 55.07, -6.51)
# key, kind, name, lat, lon, minutes after which it is stale (airports close at night: Derry's silence is normal)
SOURCES = [
    ("MET-105", "ceilometer", "Belmullet", 54.2275, -10.0069, 180),
    ("MET-104", "ceilometer", "Finner", 54.4939, -8.2431, 180),
    ("MET-17", "ceilometer", "Malin Head", 55.3719, -7.3392, 180),
    ("EGAE", "metar", "City of Derry Airport", 55.043, -7.161, 90),
    ("EGAA", "metar", "Belfast International Airport", 54.654, -6.225, 90),
    ("EGAC", "metar", "Belfast City Airport", 54.614, -5.873, 90),
    ("EGPK", "metar", "Prestwick Airport", 55.509, -4.587, 90),
]
OKTAS = {"FEW": 2, "SCT": 4, "BKN": 6, "OVC": 8, "VV": 8, "OVX": 8}
CLEARISH = ("CAVOK", "NSC", "NCD", "CLR", "SKC")
HIGH_FT = 16_000
SHADE = ["#ffffff", "#eee6dc", "#ddd1c3", "#cbbba9", "#b9a58f", "#a38d76", "#8a735d", "#6f5a46", "#54412f"]


def place(lat, lon):
    """Distance in km and a compass direction from Ballymoney."""
    p1, p2, dl = math.radians(HOME[1]), math.radians(lat), math.radians(lon - HOME[2])
    km = 6371 * math.acos(min(1, math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(dl)))
    bearing = (math.degrees(math.atan2(math.sin(dl) * math.cos(p2),
                                       math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl))) + 360) % 360
    return round(km), ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((bearing + 22.5) // 45) % 8]


def load(root, key, since):
    rows = []
    folder = Path(root) / "reference" / key
    for path in sorted(folder.glob("*.jsonl")):
        if path.stem < since.strftime("%Y-%m-%d"):
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                t = datetime.fromisoformat(r["obs_time"].replace("Z", "+00:00"))
            except (ValueError, KeyError):
                continue
            if t >= since:
                rows.append((t, r))
    return sorted(rows, key=lambda x: x[0])


def latest(root, key):
    """The newest observation kept for a source, however old. A day's file isn't in time order (a backfill
    appends older reports after newer ones), so the newest time in the newest file wins, not its last line."""
    files = sorted((Path(root) / "reference" / key).glob("*.jsonl"))
    for path in reversed(files):
        best = (None, None)
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                t = datetime.fromisoformat(r["obs_time"].replace("Z", "+00:00"))
            except (ValueError, KeyError):
                continue
            if best[0] is None or t > best[0]:
                best = (t, r)
        if best[0]:
            return best
    return None, None


def oktas(kind, r):
    """How much of the sky the observation says is covered, 0 to 8, and whether any layer is high (cirrus)."""
    if kind == "metar":
        covers = [OKTAS.get(layer.get("cover"), 0) for layer in r.get("layers") or []]
        if r.get("vertical_visibility_ft") is not None or r.get("cover") == "OVX":
            covers.append(8)
        return max(covers, default=0), False
    layers = r.get("layers") or []
    covers = [8 if layer.get("vertical_visibility") else int(layer.get("oktas") or 0) for layer in layers]
    high = any((layer.get("base_ft") or 0) >= HIGH_FT for layer in layers)
    return max(covers, default=0), high


def describe(kind, r):
    """The latest observation in words, as reported: a METAR's raw text, a ceilometer's layers."""
    if kind == "metar":
        return r.get("raw", "")
    layers = r.get("layers") or []
    if not layers:
        return "no cloud base detected straight overhead"
    parts = []
    for layer in layers:
        if layer.get("vertical_visibility"):
            parts.append(f"sky hidden, vertical visibility {int(layer['base_ft'] or 0):,} ft")
        else:
            parts.append(f"{int(layer.get('oktas') or 0)}/8 at {int(layer['base_ft']):,} ft" if layer.get("base_ft") else f"{int(layer.get('oktas') or 0)}/8")
    return "; ".join(parts)


def age_text(minutes):
    if minutes < 90:
        return f"{minutes:.0f} min ago"
    if minutes < 48 * 60:
        return f"{minutes / 60:.1f} h ago"
    return f"{minutes / 1440:.0f} days ago"


def timeline(root, now):
    """24 hours, one row per source west to east, shaded by how much of the sky each observation reports
    covered; a dark tick above a row marks a layer at 16,000 ft or higher (cirrus height)."""
    W, LEFT, ROW, TOP = 1000, 215, 30, 30
    start = now - timedelta(hours=24)
    x = lambda t: LEFT + (t - start).total_seconds() / 86400 * (W - LEFT - 10)
    order = sorted(SOURCES, key=lambda s: s[4])
    H = TOP + ROW * len(order) + 40
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="The last 24 hours at each source, west to east">']
    for h in range(0, 25, 3):
        t = start + timedelta(hours=h)
        out.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{TOP - 6}" y2="{H - 34}" stroke="#e6dacb"/>'
                   f'<text x="{x(t):.1f}" y="{H - 18}" text-anchor="middle" class="tick">{t:%H:%M}</text>')
    for i, (key, kind, name, lat, lon, _) in enumerate(order):
        y = TOP + i * ROW
        km, way = place(lat, lon)
        out.append(f'<text x="{LEFT - 8}" y="{y + 17}" text-anchor="end" class="row">{html.escape(name.replace(" Airport", ""))} '
                   f'<tspan class="tick">{km} km {way}</tspan></text>')
        rows = load(root, key, start)
        gap = timedelta(minutes=75 if kind == "metar" else 5)
        for j, (t, r) in enumerate(rows):
            t2 = min(rows[j + 1][0] if j + 1 < len(rows) else t + gap, t + gap)
            n, high = oktas(kind, r)
            x1, x2 = x(t), max(x(t2), x(t) + 0.6)
            code = r.get("cover") if kind == "metar" else None
            label = r.get("raw") if kind == "metar" else f'{r["obs_time"]} {describe(kind, r)}'
            out.append(f'<rect x="{x1:.1f}" y="{y + 4}" width="{x2 - x1:.1f}" height="{ROW - 10}" fill="{SHADE[n]}"'
                       f'{" stroke=\"#8a735d\" stroke-width=\".4\"" if code in CLEARISH else ""}><title>{html.escape(label)}</title></rect>')
            if high:
                out.append(f'<rect x="{x1:.1f}" y="{y}" width="{x2 - x1:.1f}" height="3" fill="#24408f"/>')
        if not rows:
            out.append(f'<text x="{LEFT + 6}" y="{y + 17}" class="tick">no observations in the last 24 hours</text>')
    out.append(f'<text x="{LEFT}" y="{TOP - 12}" class="tick">UTC, {start:%d %b %H:%M} to {now:%d %b %H:%M}</text></svg>')
    return "\n".join(out)


def build(root, out_dir, now=None):
    now = now or datetime.now(timezone.utc)
    status, rows = [], []
    for key, kind, name, lat, lon, stale_after in sorted(SOURCES, key=lambda s: s[4]):
        km, way = place(lat, lon)
        t, r = latest(root, key)
        minutes = (now - t).total_seconds() / 60 if t else None
        stale = minutes is None or minutes > stale_after
        status.append({"source": key, "kind": kind, "name": name, "distance_km": km, "direction": way,
                       "latest": t.strftime("%Y-%m-%dT%H:%M:%SZ") if t else None,
                       "age_minutes": round(minutes) if minutes is not None else None, "stale": stale})
        if stale and kind == "metar" and minutes is not None:
            note = "no report since then (the airport may be closed)"
        elif stale:
            note = "stale: check the collector"
        else:
            note = ""
        rows.append(f'<tr class="{"stale" if stale else ""}"><th scope="row">{html.escape(name)}'
                    f'<span>{"airport report (METAR)" if kind == "metar" else "Met Éireann ceilometer"}</span></th>'
                    f'<td>{km} km {way}</td><td>{f"{t:%d %b %H:%M}" if t else "none yet"}<span>'
                    f'{age_text(minutes) if minutes is not None else ""}{" · " + note if note else ""}</span></td>'
                    f'<td class="obs">{html.escape(describe(kind, r)) if r else ""}</td></tr>')
    page = f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>cloudyoke reference data</title>
<meta name="description" content="What the airports and Met Éireann ceilometers around Ballymoney last reported, and the last 24 hours, west to east.">
<style>
:root {{ --bg: #f3e9dd; --panel: #fbf5ee; --line: #dccbb6; --text: #2b231c; --dim: #6f6052; --accent: #a3242c; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 16px/1.55 system-ui, sans-serif; }}
main {{ max-width: 70rem; margin: 0 auto; padding: 2rem 1rem 4rem; }}
h1 {{ font-size: clamp(1.8rem, 5vw, 2.6rem); margin: .2rem 0; letter-spacing: -.02em; }}
.label {{ font: .75rem/1.4 ui-monospace, monospace; letter-spacing: .08em; text-transform: uppercase; color: var(--dim); }}
p {{ max-width: 46rem; }}
.wrap {{ overflow-x: auto; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: .5rem; }}
table {{ border-collapse: collapse; width: 100%; font-size: .92rem; }}
th, td {{ text-align: left; vertical-align: top; padding: .55rem .7rem; border-bottom: 1px solid var(--line); }}
th span, td span {{ display: block; color: var(--dim); font-weight: 400; font-size: .82rem; }}
td.obs {{ font-family: ui-monospace, monospace; font-size: .82rem; }}
tr.stale td, tr.stale th {{ color: var(--dim); }}
svg {{ display: block; width: 100%; min-width: 760px; height: auto; font: 12px system-ui, sans-serif; }}
svg .row {{ fill: var(--text); font-weight: 600; }} svg .tick {{ fill: var(--dim); font-weight: 400; }}
.key {{ font-size: .85rem; color: var(--dim); }}
a {{ color: var(--accent); }}
</style></head><body><main>
<p class="label">cloudyoke · reference data · observations, not predictions</p>
<h1>What the sky around Ballymoney is reporting</h1>
<p>Updated every 30 minutes, last at {now:%d %b %Y %H:%M} UTC. These are airport weather reports and Met Éireann
ceilometers, collected as references for cloudyoke&rsquo;s own sensors, which aren&rsquo;t running yet. Each sees
something different: airport reports leave out any cloud above 5,000 ft, and a ceilometer sees only one point straight
overhead.</p>
<h2>Latest from each source</h2>
<div class="wrap"><table><thead><tr><th>Source</th><th>From Ballymoney</th><th>Latest (UTC)</th><th>As reported</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<h2>The last 24 hours, west to east</h2>
<div class="wrap">{timeline(root, now)}</div>
<p class="key">Darker means more of the sky reported covered (in eighths). White outlined: a code like CAVOK or NCD, which
is not the same as a clear sky. Blue tick above a row: a ceilometer layer at 16,000 ft or higher, cirrus height. Blank:
no observations (airports close at night). Whether a change at one source shows up later at the next is one of the
things cloudyoke is collecting this data to test.</p>
<p class="key">Sources: airport reports from the Aviation Weather Center (aviationweather.gov). Contains Met Éireann data,
CC BY 4.0. Code and method: <a href="https://github.com/Ryan-Clinton/cloudyoke">github.com/Ryan-Clinton/cloudyoke</a> ·
<a href="/cloudyoke/">about cloudyoke</a></p>
</main></body></html>
"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, text in (("index.html", page), ("status.json", json.dumps({"generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                                        "sources": status}, indent=1))):
        tmp = out / f".{name}.part"           # written whole, then moved into place, so a reader never sees half a page
        tmp.write_text(text, encoding="utf-8")
        os.chmod(tmp, 0o644)
        os.replace(tmp, out / name)
    return status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="www")
    a = ap.parse_args()
    stale = [s["name"] for s in build(a.data, a.out) if s["stale"]]
    print(f"dashboard: written; stale: {', '.join(stale) if stale else 'none'}")


if __name__ == "__main__":
    main()
