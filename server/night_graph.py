#!/usr/bin/env python3
"""Draw one station's night as an SVG: sky temperature, air temperature, and the gap between them.

    python server/night_graph.py --data data --unit cy-0001 --night 2026-11-20 > night.svg

A night runs from 12:00 UTC on the given date to 12:00 UTC the next day. Lines break wherever readings
are more than 3 minutes apart, so a gap in the data shows as a gap, never as a line drawn across it.
Readings flagged by the station are drawn as small marks below the chart. Standard library only.
"""
import argparse
import html
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

W, H = 960, 420
LEFT, RIGHT, TOP, BOTTOM = 56, 16, 28, 64
GAP_S = 180


def value(v):
    """A reading's number, whether a reference station's plain number or a bridge's {"value": ...}."""
    if isinstance(v, dict):
        v = v.get("value")
    # Booleans are ints in Python, and NaN or infinity would wreck the scale: neither is a reading
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return v


def load(root, unit, night):
    start = datetime.combine(night, datetime.min.time(), timezone.utc) + timedelta(hours=12)
    end = start + timedelta(days=1)
    rows = []
    for day in (night, night + timedelta(days=1)):
        path = Path(root) / unit / f"{day.isoformat()}.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                t = datetime.fromisoformat(r["t"].replace("Z", "+00:00"))
            except (ValueError, KeyError):
                continue
            if start <= t < end and r.get("t_ok"):
                rows.append((t, r))
    rows.sort(key=lambda x: x[0])
    return start, end, rows


def series(rows, pick):
    """Runs of (time, value) with no gap longer than GAP_S inside a run."""
    runs, run, last = [], [], None
    for t, r in rows:
        v = pick(r)
        if v is None:
            continue
        if last is not None and (t - last).total_seconds() > GAP_S and run:
            runs.append(run)
            run = []
        run.append((t, v))
        last = t
    if run:
        runs.append(run)
    return runs


def draw(unit, start, end, rows):
    readings = lambda r: r.get("readings") or {}
    sky = series(rows, lambda r: value(readings(r).get("sky_c")))
    air = series(rows, lambda r: value(readings(r).get("air_c")))
    gap = series(rows, lambda r: (value(readings(r).get("sky_c")) - value(readings(r).get("air_c")))
                 if value(readings(r).get("sky_c")) is not None and value(readings(r).get("air_c")) is not None else None)
    values = [v for s in (sky, air, gap) for run in s for _, v in run]
    # The scale is clamped to -100..100 °C, wider than any sky or air reading, so a wild value can't stretch the
    # chart or make the gridline loop below run for ever; anything beyond is drawn at the edge
    lo = max(-100.0, min(values + [-40.0]) // 10 * 10)
    hi = min(100.0, -(-max(values + [20.0]) // 10) * 10)
    span = (end - start).total_seconds()
    x = lambda t: LEFT + (t - start).total_seconds() / span * (W - LEFT - RIGHT)
    y = lambda v: TOP + (hi - min(max(v, lo), hi)) / (hi - lo) * (H - TOP - BOTTOM)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="12">',
           f'<rect width="{W}" height="{H}" fill="#fbf5ee"/>',
           f'<text x="{LEFT}" y="18" font-weight="bold">{html.escape(unit)} · night of {start.date().isoformat()} (UTC) · '
           f'{len(rows)} readings</text>']
    pretend = sum(1 for _, r in rows if r.get("hw") == "pretend")
    if pretend:                       # made-up readings from pretend_station.py must never pass for real ones
        out.append(f'<text x="{W - RIGHT}" y="18" text-anchor="end" font-weight="bold" fill="#a3242c">'
                   f'MADE-UP DATA from pretend_station.py ({pretend} readings)</text>')
    v = lo
    while v <= hi:
        out.append(f'<line x1="{LEFT}" x2="{W - RIGHT}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#dccbb6" stroke-width="1"/>'
                   f'<text x="{LEFT - 6}" y="{y(v) + 4:.1f}" text-anchor="end" fill="#6f6052">{int(v)}°C</text>')
        v += 10
    for h in range(0, 25, 3):
        t = start + timedelta(hours=h)
        out.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{H - BOTTOM}" y2="{H - BOTTOM + 5}" stroke="#6f6052"/>'
                   f'<text x="{x(t):.1f}" y="{H - BOTTOM + 18}" text-anchor="middle" fill="#6f6052">{t:%H:%M}</text>')
    for runs, colour, width in ((air, "#b8400f", 1.5), (sky, "#24408f", 1.5), (gap, "#a3242c", 2.5)):
        for run in runs:
            pts = " ".join(f"{x(t):.1f},{y(v):.1f}" for t, v in run)
            out.append(f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="{width}" stroke-linejoin="round"/>')
    flagged = [(t, r) for t, r in rows if r.get("flags")]
    for t, r in flagged:
        out.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{H - BOTTOM + 26}" y2="{H - BOTTOM + 34}" stroke="#6f6052">'
                   f'<title>{html.escape(", ".join(r["flags"]))}</title></line>')
    key_y = H - 14
    for i, (label, colour) in enumerate((("sky minus air", "#a3242c"), ("sky", "#24408f"), ("air", "#b8400f"))):
        out.append(f'<line x1="{LEFT + i * 150}" x2="{LEFT + i * 150 + 24}" y1="{key_y - 4}" y2="{key_y - 4}" stroke="{colour}" '
                   f'stroke-width="2.5"/><text x="{LEFT + i * 150 + 30}" y="{key_y}">{label}</text>')
    if flagged:
        out.append(f'<text x="{W - RIGHT}" y="{key_y}" text-anchor="end" fill="#6f6052">ticks below: {len(flagged)} flagged readings</text>')
    if not rows:
        out.append(f'<text x="{W / 2}" y="{H / 2}" text-anchor="middle" fill="#6f6052">No readings this night</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--unit", required=True)
    ap.add_argument("--night", required=True, help="the evening's date, YYYY-MM-DD")
    a = ap.parse_args()
    start, end, rows = load(a.data, a.unit, datetime.strptime(a.night, "%Y-%m-%d").date())
    print(draw(a.unit, start, end, rows))


if __name__ == "__main__":
    main()
