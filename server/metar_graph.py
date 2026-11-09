#!/usr/bin/env python3
"""An airport's reports over a span of days as an SVG: cloud layers by height, the report's cloud code, and
visibility. A reference source, labelled as one: these are airport weather reports, not cloudyoke readings.

    python server/metar_graph.py --data data --icao EGAE --from 2026-11-03 --days 7 > egae.svg

Each layer is drawn at its base height (up to 12,000 ft; higher ones at the top edge), filled by how much
of the sky the report says it covers. The report's own code is written along the top (CAVOK, NSC, NCD and
the rest kept exactly as reported, never turned into "clear"), fog is marked, and the hours with no reports
are left empty: an airport that is closed says nothing about the sky. Standard library only.
"""
import argparse
import html
import math
from datetime import datetime, timedelta, timezone

import metar

W, H = 1100, 384
LEFT, RIGHT, TOP = 64, 16, 64
CLOUD_H, VIS_TOP, VIS_H = 170, 274, 60
MAX_FT = 12_000
# How much each code fills, in eighths of the sky, by the METAR definitions (FEW 1-2, SCT 3-4, BKN 5-7, OVC 8)
OKTAS = {"FEW": 2, "SCT": 4, "BKN": 6, "OVC": 8, "VV": 8, "OVX": 8}
SHADE = {"FEW": "#d8cdbf", "SCT": "#b9a995", "BKN": "#8f7c68", "OVC": "#5c4c3d", "VV": "#3a2f26", "OVX": "#3a2f26"}
GAP = timedelta(minutes=75)     # longer than this between reports is a gap, drawn as one


def draw(icao, start, end, rows):
    span = (end - start).total_seconds()
    x = lambda t: LEFT + (t - start).total_seconds() / span * (W - LEFT - RIGHT)
    y = lambda ft: TOP + CLOUD_H - min(ft, MAX_FT) / MAX_FT * CLOUD_H
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="11">',
           f'<rect width="{W}" height="{H}" fill="#fbf5ee"/>',
           f'<text x="{LEFT}" y="16" font-weight="bold" font-size="12">{html.escape(icao)} airport weather reports (METAR), '
           f'{start:%d %b} to {(end - timedelta(seconds=1)):%d %b %Y}, UTC · {len(rows)} reports</text>',
           f'<text x="{W - RIGHT}" y="16" text-anchor="end" fill="#6f6052">a reference source, not a cloudyoke station</text>']
    for ft in range(0, MAX_FT + 1, 3000):
        out.append(f'<line x1="{LEFT}" x2="{W - RIGHT}" y1="{y(ft):.1f}" y2="{y(ft):.1f}" stroke="#ece0d2"/>'
                   f'<text x="{LEFT - 6}" y="{y(ft) + 4:.1f}" text-anchor="end" fill="#6f6052">{ft:,} ft</text>')
    days = int(span // 86400)
    for d in range(days + 1):
        t = start + timedelta(days=d)
        out.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{TOP}" y2="{VIS_TOP + VIS_H}" stroke="#dccbb6"/>')
        if d < days:
            out.append(f'<text x="{x(t) + 4:.1f}" y="{VIS_TOP + VIS_H + 16}" fill="#6f6052">{t:%a %d}</text>')
    for i, (t, r) in enumerate(rows):
        nxt = rows[i + 1][0] if i + 1 < len(rows) else t + timedelta(minutes=30)
        t2 = min(nxt, t + GAP)
        x1, x2 = x(t), max(x(t2), x(t) + 1)
        layers = list(r.get("layers") or [])
        if r.get("vertical_visibility_ft") is not None:
            layers.append({"cover": "VV", "base_ft": r["vertical_visibility_ft"]})
        for layer in layers:
            cover, base = layer.get("cover"), layer.get("base_ft")
            if cover in OKTAS and isinstance(base, (int, float)) and math.isfinite(base):
                h = 4 + OKTAS[cover] * 1.5
                out.append(f'<rect x="{x1:.1f}" y="{y(base) - h:.1f}" width="{x2 - x1:.1f}" height="{h:.1f}" fill="{SHADE[cover]}">'
                           f'<title>{html.escape(r["raw"])}</title></rect>')
        code = r.get("cover") or ""
        if code in ("CAVOK", "NSC", "NCD", "CLR", "SKC"):
            out.append(f'<rect x="{x1:.1f}" y="{TOP - 10}" width="{x2 - x1:.1f}" height="6" fill="#ffffff" stroke="#8f7c68" stroke-width=".5">'
                       f'<title>{html.escape(code)}: {html.escape(r["raw"])}</title></rect>')
        if r.get("weather") and "FG" in r["weather"]:
            out.append(f'<rect x="{x1:.1f}" y="{TOP + CLOUD_H + 6}" width="{x2 - x1:.1f}" height="6" fill="#9b8bb0">'
                       f'<title>{html.escape(r["weather"])}: {html.escape(r["raw"])}</title></rect>')
        km = r.get("visibility_km")
        if isinstance(km, (int, float)) and math.isfinite(km):
            vy = VIS_TOP + VIS_H - min(km, 10) / 10 * VIS_H
            out.append(f'<line x1="{x1:.1f}" x2="{x2:.1f}" y1="{vy:.1f}" y2="{vy:.1f}" stroke="#24408f" stroke-width="2"/>')
    out.append(f'<text x="{LEFT - 6}" y="{VIS_TOP + 4}" text-anchor="end" fill="#6f6052">10 km+</text>'
               f'<text x="{LEFT - 6}" y="{VIS_TOP + VIS_H + 4}" text-anchor="end" fill="#6f6052">0</text>'
               f'<text x="{LEFT}" y="{VIS_TOP - 6}" fill="#24408f">visibility</text>'
               f'<text x="{LEFT}" y="34" fill="#6f6052">white ticks: the report said CAVOK, NSC, NCD, CLR or SKC, '
               f'which is not the same as a clear sky · purple band: fog reported · blank stretches: no reports (airport closed)</text>')
    key = " · ".join(f"{c} {OKTAS[c]}/8" if c in ("FEW", "SCT", "BKN") else c for c in ("FEW", "SCT", "BKN", "OVC"))
    out.append(f'<text x="{W - RIGHT}" y="{VIS_TOP - 6}" text-anchor="end" fill="#6f6052">layer thickness by cover, up to: {key}</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--icao", default="EGAE")
    ap.add_argument("--from", dest="start", required=True, help="first day, YYYY-MM-DD")
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    start = datetime.strptime(a.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = start + timedelta(days=max(1, min(a.days, 31)))
    print(draw(a.icao.upper(), start, end, metar.load(a.data, a.icao.upper(), start, end)))


if __name__ == "__main__":
    main()
