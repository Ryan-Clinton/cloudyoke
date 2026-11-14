#!/usr/bin/env python3
"""The joined sites' page: for each site, the satellite's newest verdict, the last 24 hours of verdicts with the
host's own reports under them, and how the verdicts have scored so far.

    python server/sites_page.py --data data --out www

Writes www/sites/index.html and www/sites/status.json. Each site appears by its area's name only, never a
position (docs/spec.md 6). Run after satellite.py. Standard library only.
"""
import argparse
import html
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import satellite
import seen

E = html.escape
SHADE = {"probably clear": "#ffffff", "thin or broken cloud": "#c9b7a2", "cloud": "#6f5a46"}
SEEN_SHADE = {"clear": "#ffffff", "partly": "#c9b7a2", "cloudy": "#6f5a46"}


def rows_since(root, site, since):
    out = []
    for path in sorted((Path(root) / "satellite" / site).glob("*.jsonl")):
        if path.stem < since.strftime("%Y-%m-%d"):
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                t = seen.when(r["obs_time"])
            except (ValueError, KeyError):
                continue
            if t >= since:
                out.append((t, r))
    return sorted(out, key=lambda x: x[0])


def strip(root, site, now):
    """24 hours: the satellite's verdicts on top, the host's reports underneath."""
    W, LEFT, H = 1000, 70, 74
    start = now - timedelta(hours=24)
    x = lambda t: LEFT + max(0.0, min(1.0, (t - start).total_seconds() / 86400)) * (W - LEFT - 10)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="The last 24 hours: the satellite above, reports below">',
           f'<text x="{LEFT - 8}" y="20" text-anchor="end" class="tick">satellite</text>',
           f'<text x="{LEFT - 8}" y="44" text-anchor="end" class="tick">seen</text>']
    for h in range(0, 25, 3):
        t = start + timedelta(hours=h)
        out.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="4" y2="54" stroke="#e6dacb"/>'
                   f'<text x="{x(t):.1f}" y="68" text-anchor="middle" class="tick">{t:%H:%M}</text>')
    rows = rows_since(root, site, start)
    for t, r in rows:
        x1, x2 = x(t), x(t + timedelta(minutes=satellite.STEP_MIN))
        out.append(f'<rect x="{x1:.1f}" y="6" width="{x2 - x1:.1f}" height="20" fill="{SHADE.get(r["verdict"], "#fff")}">'
                   f'<title>{t:%H:%M} UTC: {E(r["verdict"])} (margin {r["margin"]})</title></rect>')
    for s0, s1, r in seen.reports(root, site):
        if s1 < start or s0 > now:
            continue
        out.append(f'<rect x="{x(s0):.1f}" y="32" width="{x(s1) - x(s0):.1f}" height="16" fill="{SEEN_SHADE[r["sky"]]}" '
                   f'stroke="#a3242c" stroke-width=".6"><title>{s0:%H:%M} to {s1:%H:%M} UTC: {E(r["sky"])}, '
                   f'seen by the {E(r["by"])}{": " + E(r["note"]) if r.get("note") else ""}</title></rect>')
    if not rows:
        out.append(f'<text x="{LEFT + 6}" y="20" class="tick">no satellite verdicts in the last 24 hours</text>')
    out.append("</svg>")
    return "\n".join(out)


def build(root, out_dir, now=None):
    now = now or datetime.now(timezone.utc)
    status, cards = [], []
    for site, s in sorted(satellite.load_sites(root).items(), key=lambda kv: kv[1]["area"]):
        rows = rows_since(root, site, now - timedelta(hours=24))
        t, r = rows[-1] if rows else (None, None)
        minutes = (now - t).total_seconds() / 60 if t else None
        stale = minutes is None or minutes > satellite.STALE_MIN
        before = next((rr for tt, rr in reversed(rows) if t and tt <= t - timedelta(minutes=30)), None)
        sc = seen.score(root, site)
        status.append({"site": site, "area": s["area"], "joined_as": s.get("as", "location"),
                       "latest": r["obs_time"] if r else None, "verdict": r["verdict"] if r else None,
                       "margin": r["margin"] if r else None, "age_minutes": round(minutes) if minutes is not None else None,
                       "stale": stale, "scored": sc["n"], "agreed": sc["agree"]})
        if r:
            was = f"; 30 min before: {E(before['verdict'])}" if before else ""
            now_text = (f'<p class="verdict">{E(r["verdict"])}</p><p class="small">Picture of {t:%d %b %H:%M} UTC, '
                        f'{minutes:.0f} min ago{" · stale: check the collector" if stale else ""}; margin {r["margin"]} '
                        f'(over 20 is cloud, under 10 probably clear){was}</p>')
        else:
            now_text = '<p class="verdict">no verdict yet</p>'
        score_text = (f"{sc['n']} verdicts checked against {sc['reports']} reports: agreed {sc['agree']} "
                      f"({100 * sc['agree'] / sc['n']:.0f}%), missed cloud {sc['missed_cloud']}, false cloud {sc['false_cloud']}."
                      if sc["n"] else f"Not scored yet: {sc['reports']} reports of the real sky so far.")
        cards.append(f'<section class="site"><h2>{E(s["area"])}</h2><p class="label">joined as: {E(s.get("as", "location"))}</p>'
                     f'{now_text}<div class="wrap">{strip(root, site, now)}</div><p class="small">{E(score_text)}</p></section>')
    page = f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>cloudyoke joined sites</title>
<meta name="description" content="Meteosat's rough cloud verdict for each place that has joined cloudyoke, and how it scores against what people there saw.">
<style>
:root {{ --bg: #f3e9dd; --panel: #fbf5ee; --line: #dccbb6; --text: #2b231c; --dim: #6f6052; --accent: #a3242c; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 16px/1.55 system-ui, sans-serif; }}
main {{ max-width: 70rem; margin: 0 auto; padding: 2rem 1rem 4rem; }}
h1 {{ font-size: clamp(1.8rem, 5vw, 2.6rem); margin: .2rem 0; letter-spacing: -.02em; }}
h2 {{ margin: 0; }}
.label {{ font: .75rem/1.4 ui-monospace, monospace; letter-spacing: .08em; text-transform: uppercase; color: var(--dim); margin: .2rem 0; }}
p {{ max-width: 46rem; }}
.site {{ border-top: 1px solid var(--line); padding: 1.2rem 0; }}
.verdict {{ font-size: 1.4rem; font-weight: 650; margin: .4rem 0 0; }}
.small {{ font-size: .85rem; color: var(--dim); }}
.wrap {{ overflow-x: auto; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: .5rem; }}
svg {{ display: block; width: 100%; min-width: 640px; height: auto; font: 12px system-ui, sans-serif; }}
svg .tick {{ fill: var(--dim); }}
a {{ color: var(--accent); }}
</style></head><body><main>
<p class="label">cloudyoke · joined sites · the satellite&rsquo;s view, scored against the ground</p>
<h1>The sky over each joined site</h1>
<p>Updated every 10 minutes, last at {now:%d %b %Y %H:%M} UTC. Each verdict comes from Meteosat&rsquo;s 10.5 µm infrared
picture: the site&rsquo;s brightness against the darkest tenth of the surrounding 400 km, where cold cloud tops are bright and
clear ground is dark. It is a rough measure, not yet calibrated anywhere. Reports of the real sky from people at each site,
their telescopes&rsquo; frames and later cloudyoke&rsquo;s own sensors are what score it. A site is shown by its area only.</p>
{"".join(cards) or "<p>No sites yet.</p>"}
<p class="small">White: probably clear. Mid: thin or broken cloud. Dark: cloud. Outlined in red, underneath: what was seen
at the site. Contains EUMETSAT data, © EUMETSAT {now:%Y}. Method: <a href="https://github.com/Ryan-Clinton/cloudyoke/blob/main/server/satellite.py">satellite.py</a>.
To join: <a href="https://github.com/Ryan-Clinton/cloudyoke/blob/main/docs/join.md">docs/join.md</a> ·
<a href="../">reference data</a> · <a href="/cloudyoke/">about cloudyoke</a></p>
</main></body></html>
"""
    out = Path(out_dir) / "sites"
    out.mkdir(parents=True, exist_ok=True)
    for name, text in (("index.html", page), ("status.json", json.dumps(
            {"generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "sites": status}, indent=1))):
        tmp = out / f".{name}.part"
        tmp.write_text(text, encoding="utf-8")
        os.chmod(tmp, 0o644)
        os.replace(tmp, out / name)
    return status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="www")
    a = ap.parse_args()
    status = build(a.data, a.out)
    print(f"sites_page: {len(status)} sites; stale: {', '.join(s['site'] for s in status if s['stale']) or 'none'}")


if __name__ == "__main__":
    main()
