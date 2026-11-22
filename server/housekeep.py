#!/usr/bin/env python3
"""Daily housekeeping of the reference data, so it can't grow for ever.

    python server/housekeep.py --data data             says what it would do, changes nothing
    python server/housekeep.py --data data --apply     does it

- After 7 days, each day's airport files become one bundle, data/archive/airports/<UTC date>.jsonl.bz2, and each
  day's ceilometer files one bundle, data/archive/ceilometers/<UTC date>.jsonl.xz. Thousands of tiny files become one,
  about 25 times smaller for airports and 90 for ceilometers. Rows are unchanged, sorted by source and time.
- After 400 days, reference files, bundles and satellite files are deleted: a full year, so a season can be compared
  with the same season before, and a month to spare.

Only files named <UTC date>.jsonl directly inside data/reference/<source>/ or data/satellite/<site>/, and this
script's own bundles, are ever touched. Station readings (data/<unit>/), data/seen and the registry are not.
Each source's newest file is always left as it is, so a source that has gone quiet still shows as stale on its page.
A bundle replaces its files only after it has been read back and matched. A later backfill of a bundled day is merged
in on the next run, without duplicates. If the newest file anywhere is over 30 days older than today, the clock or
the collectors are wrong and nothing is done. Standard library only.
"""
import argparse
import bz2
import json
import lzma
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BUNDLE_AFTER_DAYS = 7
DELETE_AFTER_DAYS = 400
MAX_SILENCE_DAYS = 30
DATED = re.compile(r"(\d{4}-\d{2}-\d{2})\.jsonl")
CEILOMETER = re.compile(r"MET-\d+")
AIRPORT = re.compile(r"[A-Z0-9]{4}")
BUNDLES = {"airports": (".jsonl.bz2", bz2), "ceilometers": (".jsonl.xz", lzma)}   # the best of each on real files


def dated_files(folder):
    """A source's dated files as [(day, path)], oldest first. Anything else in the folder is ignored."""
    out = []
    for path in folder.iterdir():
        m = DATED.fullmatch(path.name)
        if not m or path.is_symlink() or not path.is_file():
            continue
        try:
            out.append((date.fromisoformat(m.group(1)), path))
        except ValueError:
            continue
    return sorted(out, key=lambda x: x[0])


def sources(root):
    """Every source folder that housekeeping may touch, as (folder, bundle kind or None)."""
    out = []
    for kind in ("reference", "satellite"):
        parent = Path(root) / kind
        if not parent.is_dir():
            continue
        for p in sorted(parent.iterdir()):
            if p.is_dir() and not p.is_symlink():
                bundle = None
                if kind == "reference":
                    bundle = "ceilometers" if CEILOMETER.fullmatch(p.name) else "airports" if AIRPORT.fullmatch(p.name) else None
                out.append((p, bundle))
    return out


def bundle_path(root, kind, day):
    return Path(root) / "archive" / kind / f"{day}{BUNDLES[kind][0]}"


def old_bundles(root, today):
    out = []
    for kind, (suffix, _) in BUNDLES.items():
        folder = Path(root) / "archive" / kind
        if not folder.is_dir():
            continue
        for path in folder.iterdir():
            if not path.name.endswith(suffix) or path.is_symlink():
                continue
            try:
                day = date.fromisoformat(path.name[:-len(suffix)])
            except ValueError:
                continue
            if (today - day).days > DELETE_AFTER_DAYS:
                out.append(path)
    return sorted(out)


def plan(root, today):
    """({(kind, day): [files to bundle]}, [files to delete]), or ValueError if the dates say the clock is wrong."""
    bundle, remove, newest = {}, [], None
    for folder, kind in sources(root):
        files = [f for f in dated_files(folder) if f[0] <= today]       # a future-dated file is never acted on
        if not files:
            continue
        last_day = files[-1][0]
        newest = max(newest or last_day, last_day)
        for day, path in files[:-1]:
            age = (today - day).days
            if age > DELETE_AFTER_DAYS:
                remove.append(path)
            elif age > BUNDLE_AFTER_DAYS and kind:
                bundle.setdefault((kind, day), []).append(path)
    if newest is not None and (today - newest).days > MAX_SILENCE_DAYS:
        raise ValueError(f"newest file is from {newest}, over {MAX_SILENCE_DAYS} days before {today}")
    return bundle, remove + old_bundles(root, today)


def row_key(line):
    """Sort by source then time, which is what makes the bundle compress so well. An unreadable line sorts first."""
    try:
        r = json.loads(line)
        return (str(r.get("icao") or r.get("station") or ""), str(r.get("obs_time") or ""), line)
    except (ValueError, AttributeError):
        return ("", "", line)


def make_bundle(root, kind, day, paths):
    """The day's files, plus anything already bundled for that day, as one verified file. Returns bytes saved."""
    target = bundle_path(root, kind, day)
    codec = BUNDLES[kind][1]
    target.parent.mkdir(parents=True, exist_ok=True)
    rows, before = set(), 0
    if target.exists():
        before += target.stat().st_size
        rows.update(line for line in codec.decompress(target.read_bytes()).split(b"\n") if line)
    for path in paths:
        body = path.read_bytes()
        before += len(body)
        rows.update(line for line in body.split(b"\n") if line)
    data = b"\n".join(sorted(rows, key=row_key)) + b"\n"
    packed = codec.compress(data, 9) if codec is bz2 else codec.compress(data, preset=6)
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        with os.fdopen(fd, "wb") as f:
            f.write(packed)
            f.flush()
            os.fsync(f.fileno())
        if codec.decompress(temporary.read_bytes()) != data:
            raise ValueError(f"{temporary} failed its check")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    folder = os.open(target.parent, os.O_RDONLY)
    try:
        os.fsync(folder)
    finally:
        os.close(folder)
    for path in paths:
        path.unlink()
    return before - len(packed)


def run(root, today, apply):
    """Returns (files bundled, bytes saved, files deleted, bytes deleted, problems)."""
    bundle, remove = plan(root, today)
    bundled = saved = deleted = freed = 0
    problems = []
    for (kind, day), paths in sorted(bundle.items(), key=lambda x: (x[0][0], x[0][1])):
        try:
            if apply:
                saved += make_bundle(root, kind, day, paths)
            bundled += len(paths)
        except (OSError, ValueError, EOFError, lzma.LZMAError) as e:
            problems.append(f"{kind} {day}: {e}")
    for path in remove:
        try:
            size = path.stat().st_size
            if apply:
                path.unlink()
            deleted += 1
            freed += size
        except OSError as e:
            problems.append(f"{path}: {e}")
    return bundled, saved, deleted, freed, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--apply", action="store_true", help="make the changes; without it, only say what they'd be")
    a = ap.parse_args()
    today = datetime.now(timezone.utc).date()
    try:
        bundled, saved, deleted, freed, problems = run(a.data, today, a.apply)
    except ValueError as e:
        sys.exit(f"housekeep: nothing done: {e}")
    verb = ("bundled", "deleted") if a.apply else ("would bundle", "would delete")
    print(f"housekeep: {verb[0]} {bundled} files (saved {saved / 1e6:.1f} MB), {verb[1]} {deleted} files ({freed / 1e6:.1f} MB)")
    for p in problems:
        print(f"housekeep: {p}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
