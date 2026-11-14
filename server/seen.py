#!/usr/bin/env python3
"""What a joined site's sensor said the sky did, and how the satellite's verdicts (satellite.py) score against it.

    python server/seen.py add --data data --site ballymoney --from 2026-11-14T21:00 --to 2026-11-14T23:30 \\
        --sky clear --by station
    python server/seen.py scores --data data [--site ballymoney]

A report is a span of time (UTC) and the sky's state through it: clear, partly or cloudy. --by says which
sensor: "station" for a cloudyoke station's judged state, "sensor" for an existing sensor's own verdict
(CloudWatcher, Boltwood). Entered by hand until the server judges stations itself (issue 5). Kept as given in
data/seen/<site>.jsonl; nothing is inferred between them.

Scoring pairs each satellite verdict whose picture falls inside a report with what the report says. The
satellite's "thin or broken cloud" counts as agreeing with partly; its "probably clear" under a cloudy report
is a missed cloud, its "cloud" under a clear report a false cloud. Standard library only.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SKIES = ("clear", "partly", "cloudy")
BY = ("station", "sensor")
MATCH = {"probably clear": "clear", "thin or broken cloud": "partly", "cloud": "cloudy"}


def when(text):
    t = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return t.astimezone(timezone.utc) if t.tzinfo else t.replace(tzinfo=timezone.utc)


def add(root, site, start, end, sky, by, note=""):
    if sky not in SKIES or by not in BY:
        raise ValueError(f"sky is one of {SKIES}, by one of {BY}")
    start, end = when(start), when(end)
    if end <= start:
        raise ValueError("a report ends after it starts")
    row = {"site": site, "from": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "to": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "sky": sky, "by": by, "note": note, "added": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    path = Path(root) / "seen" / f"{site}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return row


def reports(root, site):
    path = Path(root) / "seen" / f"{site}.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
            out.append((when(r["from"]), when(r["to"]), r))
        except (ValueError, KeyError):
            continue
    return out


def verdicts(root, site):
    out = []
    for path in sorted((Path(root) / "satellite" / site).glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                out.append((when(r["obs_time"]), r["verdict"]))
            except (ValueError, KeyError):
                continue
    return out


def score(root, site):
    """Counts of (what was seen, what the satellite said), and the totals that matter."""
    pairs = {}
    seen = reports(root, site)
    for t, v in verdicts(root, site):
        for start, end, r in seen:
            if start <= t < end:
                key = (r["sky"], v)
                pairs[key] = pairs.get(key, 0) + 1
                break
    n = sum(pairs.values())
    agree = sum(c for (sky, v), c in pairs.items() if MATCH[v] == sky)
    return {"pairs": pairs, "n": n, "agree": agree,
            "missed_cloud": pairs.get(("cloudy", "probably clear"), 0),
            "false_cloud": pairs.get(("clear", "cloud"), 0),
            "reports": len(seen)}


def score_lines(root, site):
    s = score(root, site)
    if not s["n"]:
        return [f"{site}: {s['reports']} reports, no satellite verdicts inside them yet"]
    lines = [f"{site}: {s['n']} verdicts inside {s['reports']} reports; agreed {s['agree']} "
             f"({100 * s['agree'] / s['n']:.0f}%), missed cloud {s['missed_cloud']}, false cloud {s['false_cloud']}"]
    for sky in SKIES:
        row = [f"{s['pairs'].get((sky, v), 0):>5}" for v in MATCH]
        lines.append(f"  seen {sky:<7} satellite said clear/thin/cloud: {' '.join(row)}")
    return lines


def main():
    ap = argparse.ArgumentParser(description="Reports of the real sky at joined sites, and the satellite's scores.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("add")
    a1.add_argument("--data", default="data")
    a1.add_argument("--site", required=True)
    a1.add_argument("--from", dest="start", required=True, help="UTC, e.g. 2026-11-14T21:00")
    a1.add_argument("--to", dest="end", required=True)
    a1.add_argument("--sky", required=True, choices=SKIES)
    a1.add_argument("--by", default="station", choices=BY)
    a1.add_argument("--note", default="")
    a2 = sub.add_parser("scores")
    a2.add_argument("--data", default="data")
    a2.add_argument("--site")
    a = ap.parse_args()
    if a.cmd == "add":
        try:
            print(json.dumps(add(a.data, a.site, a.start, a.end, a.sky, a.by, a.note)))
        except ValueError as e:
            sys.exit(f"seen: {e}")
        return
    sites = [a.site] if a.site else sorted(p.stem for p in (Path(a.data) / "seen").glob("*.jsonl"))
    for site in sites:
        print("\n".join(score_lines(a.data, site)))


if __name__ == "__main__":
    main()
