#!/usr/bin/env python3
"""The network's pages: one per site, with what the references near it last reported (airports, ceilometers),
the satellite's verdict, and the last 24 hours side by side; and an overview of every site. Observations,
not predictions.

    python server/dashboard.py --data data --out www

Each site's references are whatever the collectors have found near it (data/reference/index.json), so a new
site gets its own the first time metar.py --sites runs, and nothing about any one place is written here.
Writes www/index.html (the overview), www/sites/<site>/index.html and www/status.json (every site's sources,
their latest observation and whether it is stale, so a source that stops is seen rather than silently
missing). A site appears by its area's name only; distances are measured from its public cell
(registry.py) and rounded to 5 km, so they can't be combined to find it. Standard library only.
"""
import argparse
import html
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import registry
import satellite
import seen

E = html.escape
STALE_MIN = {"metar": 90, "ceilometer": 180}       # airports close at night, so their silence can be normal
RADIUS_KM = {"metar": 150, "ceilometer": 250}      # what a site's page shows, as far as the collectors look
OKTAS = {"FEW": 2, "SCT": 4, "BKN": 6, "OVC": 8, "VV": 8, "OVX": 8}
CLEARISH = ("CAVOK", "NSC", "NCD", "CLR", "SKC")
HIGH_FT = 16_000
SHADE = ["#ffffff", "#eee6dc", "#ddd1c3", "#cbbba9", "#b9a58f", "#a38d76", "#8a735d", "#6f5a46", "#54412f"]
VERDICT_SHADE = {"probably clear": "#ffffff", "thin or broken cloud": "#c9b7a2", "cloud": "#6f5a46"}
SEEN_SHADE = {"clear": "#ffffff", "partly": "#c9b7a2", "cloudy": "#6f5a46"}
KIND_TEXT = {"metar": "airport report (METAR)", "ceilometer": "ceilometer"}

STYLE = """
:root { --bg: #f3e9dd; --panel: #fbf5ee; --line: #dccbb6; --text: #2b231c; --dim: #6f6052; --accent: #a3242c; }
body { margin: 0; background: var(--bg); color: var(--text); font: 16px/1.55 system-ui, sans-serif; }
main { max-width: 70rem; margin: 0 auto; padding: 2rem 1rem 4rem; }
h1 { font-size: clamp(1.8rem, 5vw, 2.6rem); margin: .2rem 0; letter-spacing: -.02em; }
.label { font: .75rem/1.4 ui-monospace, monospace; letter-spacing: .08em; text-transform: uppercase; color: var(--dim); }
p { max-width: 46rem; }
.wrap { overflow-x: auto; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: .5rem; }
table { border-collapse: collapse; width: 100%; font-size: .92rem; }
th, td { text-align: left; vertical-align: top; padding: .55rem .7rem; border-bottom: 1px solid var(--line); }
th span, td span { display: block; color: var(--dim); font-weight: 400; font-size: .82rem; }
td.obs { font-family: ui-monospace, monospace; font-size: .82rem; }
tr.stale td, tr.stale th { color: var(--dim); }
svg { display: block; width: 100%; min-width: 760px; height: auto; font: 12px system-ui, sans-serif; }
svg .row { fill: var(--text); font-weight: 600; } svg .tick { fill: var(--dim); font-weight: 400; }
.verdict { font-size: 1.4rem; font-weight: 650; margin: .4rem 0 0; }
.key { font-size: .85rem; color: var(--dim); }
a { color: var(--accent); }
"""


def when(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def load(root, key, since, folder="reference"):
    rows = []
    for path in sorted((Path(root) / folder / key).glob("*.jsonl")):
        if path.stem < since.strftime("%Y-%m-%d"):
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                t = when(r["obs_time"])
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
                t = when(r["obs_time"])
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


def bins(rows, minutes=5):
    """Ceilometer readings grouped into bins: the most cloud seen in each, and whether any layer was high.
    Returns rows shaped like single readings, so the drawing code needn't care."""
    out = {}
    for t, r in rows:
        start = t.replace(second=0, microsecond=0, minute=t.minute - t.minute % minutes)
        n, high = oktas("ceilometer", r)
        b = out.setdefault(start, {"n": 0, "high": False, "count": 0, "top": 0})
        b["n"], b["high"], b["count"] = max(b["n"], n), b["high"] or high, b["count"] + 1
        b["top"] = max([b["top"]] + [layer.get("base_ft") or 0 for layer in r.get("layers") or []])
    result = []
    for start, b in sorted(out.items()):
        layers = [{"oktas": b["n"], "base_ft": b["top"] if b["high"] else None}] if b["n"] else []
        if b["high"] and not b["n"]:
            layers = [{"oktas": 0, "base_ft": b["top"]}]
        result.append((start, {"obs_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "layers": layers,
                               "summary": f"{b['count']} readings; most cover {b['n']}/8; highest base {int(b['top']):,} ft"}))
    return result


def sources(root, site):
    """A site's references, nearest first: (key, kind, name, km from its public cell rounded to 5, compass)."""
    # Which sources, their order and their distances all come from the public cell only: choosing them by the
    # private cell would leak, through who is just inside the radius, what the public cell hides
    public = {**site, "lat": site["public"][0], "lon": site["public"][1]}
    out = []
    for key, r, km, way in registry.references_near(root, public, max(RADIUS_KM.values())):
        if km <= RADIUS_KM.get(r["kind"], 0):
            out.append((key, r["kind"], r["name"], int(5 * round(km / 5)), way))
    return out


def timeline(root, now, srcs, sat_rows=None):
    """24 hours, one row per source, nearest first, shaded by how much of the sky each observation reports
    covered; a dark tick above a row marks a layer at 16,000 ft or higher (cirrus height). The satellite's
    verdicts for the site, when there are any, are the first row."""
    W, LEFT, ROW, TOP = 1000, 215, 30, 30
    start = now - timedelta(hours=24)
    x = lambda t: LEFT + max(0.0, min(1.0, (t - start).total_seconds() / 86400)) * (W - LEFT - 10)
    n_rows = len(srcs) + (1 if sat_rows is not None else 0)
    H = TOP + ROW * max(n_rows, 1) + 40
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="The last 24 hours at each source, nearest first">']
    for h in range(0, 25, 3):
        t = start + timedelta(hours=h)
        out.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{TOP - 6}" y2="{H - 34}" stroke="#e6dacb"/>'
                   f'<text x="{x(t):.1f}" y="{H - 18}" text-anchor="middle" class="tick">{t:%H:%M}</text>')
    i = 0
    if sat_rows is not None:
        y = TOP
        out.append(f'<text x="{LEFT - 8}" y="{y + 17}" text-anchor="end" class="row">Meteosat <tspan class="tick">overhead</tspan></text>')
        for t, r in sat_rows:
            x1, x2 = x(t), x(t + timedelta(minutes=satellite.STEP_MIN))
            out.append(f'<rect x="{x1:.1f}" y="{y + 4}" width="{x2 - x1:.1f}" height="{ROW - 10}" fill="{VERDICT_SHADE.get(r["verdict"], "#fff")}">'
                       f'<title>{t:%H:%M} UTC: {E(r["verdict"])} (margin {r["margin"]})</title></rect>')
        if not sat_rows:
            out.append(f'<text x="{LEFT + 6}" y="{y + 17}" class="tick">no satellite verdicts in the last 24 hours</text>')
        i = 1
    for key, kind, name, km, way in srcs:
        y = TOP + i * ROW
        i += 1
        out.append(f'<text x="{LEFT - 8}" y="{y + 17}" text-anchor="end" class="row">{E(name.replace(" Airport", ""))} '
                   f'<tspan class="tick">{km} km {way}</tspan></text>')
        rows = load(root, key, start)
        if kind == "ceilometer":
            rows = bins(rows)                  # 15-second readings drawn as 5-minute bins, or the page weighs megabytes
        gap = timedelta(minutes=75 if kind == "metar" else 5)
        for j, (t, r) in enumerate(rows):
            t2 = min(rows[j + 1][0] if j + 1 < len(rows) else t + gap, t + gap)
            n, high = oktas(kind, r)
            x1, x2 = x(t), max(x(t2), x(t) + 0.6)
            code = r.get("cover") if kind == "metar" else None
            label = r.get("raw") if kind == "metar" else f'{r["obs_time"]}, 5 minutes: {r.get("summary", describe(kind, r))}'
            out.append(f'<rect x="{x1:.1f}" y="{y + 4}" width="{x2 - x1:.1f}" height="{ROW - 10}" fill="{SHADE[n]}"'
                       f'{" stroke=\"#8a735d\" stroke-width=\".4\"" if code in CLEARISH else ""}><title>{E(label)}</title></rect>')
            if high:
                out.append(f'<rect x="{x1:.1f}" y="{y}" width="{x2 - x1:.1f}" height="3" fill="#24408f"/>')
        if not rows:
            out.append(f'<text x="{LEFT + 6}" y="{y + 17}" class="tick">no observations in the last 24 hours</text>')
    out.append(f'<text x="{LEFT}" y="{TOP - 12}" class="tick">UTC, {start:%d %b %H:%M} to {now:%d %b %H:%M}</text></svg>')
    return "\n".join(out)


def page(title, description, body):
    return f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(description, quote=True)}">
<style>{STYLE}</style></head><body><main>
{body}
<p class="key">Sources: airport reports from the Aviation Weather Center (aviationweather.gov). Contains Met Éireann data,
CC BY 4.0. Contains EUMETSAT data, © EUMETSAT. Code and method:
<a href="https://github.com/Ryan-Clinton/cloudyoke">github.com/Ryan-Clinton/cloudyoke</a> ·
<a href="/cloudyoke/">about cloudyoke</a></p>
</main></body></html>
"""


def site_status(root, sid, site, now):
    srcs, rows = [], []
    found = sources(root, site)
    for key, kind, name, km, way in found:
        t, r = latest(root, key)
        minutes = (now - t).total_seconds() / 60 if t else None
        stale = minutes is None or minutes > STALE_MIN.get(kind, 90)
        srcs.append({"source": key, "kind": kind, "name": name, "distance_km": km, "direction": way,
                     "latest": t.strftime("%Y-%m-%dT%H:%M:%SZ") if t else None,
                     "age_minutes": round(minutes) if minutes is not None else None, "stale": stale})
        note = ("no report since then (the airport may be closed)" if stale and kind == "metar" and minutes is not None
                else "stale: check the collector" if stale else "")
        rows.append(f'<tr class="{"stale" if stale else ""}"><th scope="row">{E(name)}<span>{KIND_TEXT.get(kind, kind)}</span></th>'
                    f'<td>{km} km {way}</td><td>{f"{t:%d %b %H:%M}" if t else "none yet"}<span>'
                    f'{age_text(minutes) if minutes is not None else ""}{" · " + note if note else ""}</span></td>'
                    f'<td class="obs">{E(describe(kind, r)) if r else ""}</td></tr>')
    sat_rows = load(root, sid, now - timedelta(hours=24), folder="satellite")
    t, r = sat_rows[-1] if sat_rows else (None, None)
    minutes = (now - t).total_seconds() / 60 if t else None
    sat = {"latest": r["obs_time"] if r else None, "verdict": r["verdict"] if r else None,
           "margin": r["margin"] if r else None, "age_minutes": round(minutes) if minutes is not None else None,
           "stale": minutes is None or minutes > satellite.STALE_MIN}
    return found, srcs, rows, sat_rows, sat


def site_page(root, sid, site, now):
    found, srcs, rows, sat_rows, sat = site_status(root, sid, site, now)
    sc = seen.score(root, sid)
    if sat["verdict"]:
        sat_html = (f'<p class="verdict">{E(sat["verdict"])}</p><p class="key">Meteosat&rsquo;s 10.5 µm picture of '
                    f'{sat["latest"][11:16]} UTC, {sat["age_minutes"]} min ago{" · stale" if sat["stale"] else ""}; margin '
                    f'{sat["margin"]} (over 20 is cloud, under 10 probably clear). A rough, uncalibrated reference: the '
                    f'site&rsquo;s brightness against the darkest tenth of the 400 km round it.'
                    + (f" Scored against the site&rsquo;s sensor: agreed {sc['agree']} of {sc['n']}." if sc["n"] else "") + "</p>")
    else:
        sat_html = '<p class="key">No satellite verdict yet (Meteosat sees Europe and Africa only).</p>'
    table = (f'<div class="wrap"><table><thead><tr><th>Source</th><th>Distance</th><th>Latest (UTC)</th><th>As reported</th>'
             f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>' if rows
             else '<p>No airports or ceilometers found nearby yet: they appear after the next collection.</p>')
    body = f"""<p class="label">cloudyoke · {E(site["area"])} · observations, not predictions</p>
<h1>The sky around {E(site["area"])}</h1>
<p>Updated every 10 to 30 minutes, last at {now:%d %b %Y %H:%M} UTC. Every airport within {RADIUS_KM["metar"]} km and
ceilometer within {RADIUS_KM["ceilometer"]} km, found by distance, and the satellite overhead: references for the
site&rsquo;s own sensor. Each sees something different: airport reports leave out cloud above 5,000 ft (CAVOK) or
12,000 ft (NCD), a ceilometer sees one point straight overhead, and the satellite sees kilometres at once.</p>
<h2>The satellite overhead</h2>
{sat_html}
<h2>Latest from each source</h2>
{table}
<h2>The last 24 hours, nearest first</h2>
<div class="wrap">{timeline(root, now, found, sat_rows)}</div>
<p class="key">Darker means more of the sky reported covered (in eighths). White outlined: a code like CAVOK or NCD, which
is not the same as a clear sky. Blue tick above a row: a ceilometer layer at 16,000 ft or higher, cirrus height. Blank: no
observations (airports close at night). Distances are from the site&rsquo;s area, to the nearest 5 km.
<a href="../../">All sites</a></p>"""
    return page(f"cloudyoke: {site['area']}", f"What the airports, ceilometers and satellite around {site['area']} last reported.", body), \
        {"site": sid, "area": site["area"], "joined_as": site.get("as", "station"), "satellite": sat, "sources": srcs}


def build(root, out_dir, now=None):
    now = now or datetime.now(timezone.utc)
    out = Path(out_dir)
    status, cards = [], []
    files = {}
    for sid, site in sorted(registry.sites(root).items(), key=lambda kv: kv[1]["area"]):
        html_text, st = site_page(root, sid, site, now)
        files[f"sites/{sid}/index.html"] = html_text
        status.append(st)
        sat = st["satellite"]
        fresh = sum(1 for s in st["sources"] if not s["stale"])
        cards.append(f'<tr><th scope="row"><a href="sites/{E(sid)}/">{E(st["area"])}</a><span>{E(st["joined_as"])}</span></th>'
                     f'<td>{E(sat["verdict"] or "no verdict yet")}<span>{"stale" if sat["stale"] else (str(sat["age_minutes"]) + " min ago") if sat["latest"] else ""}</span></td>'
                     f'<td>{len(st["sources"])} nearby<span>{fresh} reporting now</span></td></tr>')
    body = f"""<p class="label">cloudyoke · the network · observations, not predictions</p>
<h1>Every site&rsquo;s sky</h1>
<p>Updated every 10 to 30 minutes, last at {now:%d %b %Y %H:%M} UTC. Each site has its own page: the satellite&rsquo;s
rough verdict overhead and every airport and ceilometer near it, found by distance. Sites are shown by their
area&rsquo;s name only. To join: <a href="https://github.com/Ryan-Clinton/cloudyoke/blob/main/docs/join.md">docs/join.md</a>.</p>
<div class="wrap"><table><thead><tr><th>Site</th><th>Satellite overhead</th><th>References</th></tr></thead>
<tbody>{"".join(cards) or '<tr><td colspan="3">No sites yet.</td></tr>'}</tbody></table></div>"""
    files["index.html"] = page("cloudyoke live", "Every cloudyoke site: the satellite overhead and the airports and ceilometers near it.", body)
    files["sites/index.html"] = '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=../"><a href="../">All sites</a>'
    files["status.json"] = json.dumps({"generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "sites": status}, indent=1)
    for name, text in files.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.part")      # written whole, then moved into place, so a reader never sees half a page
        tmp.write_text(text, encoding="utf-8")
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    return status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="www")
    a = ap.parse_args()
    status = build(a.data, a.out)
    stale = [f"{s['site']}/{x['source']}" for s in status for x in s["sources"] if x["stale"]]
    print(f"dashboard: {len(status)} sites; stale: {', '.join(stale) if stale else 'none'}")


if __name__ == "__main__":
    main()
