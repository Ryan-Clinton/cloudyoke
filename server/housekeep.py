#!/usr/bin/env python3
"""Daily housekeeping of the reference data, so it can't grow for ever.

    python server/housekeep.py --data data             says what it would do, changes nothing
    python server/housekeep.py --data data --apply     does it

- Met Éireann's 15-second ceilometer files are gzipped after 14 days (about 50 times smaller; read them with zcat).
- Reference and satellite files are deleted after 400 days: a full year, so a season can be compared with the same
  season before, and a month to spare.

Only files named <UTC date>.jsonl or <UTC date>.jsonl.gz, directly inside data/reference/<source>/ or
data/satellite/<site>/, are ever touched. Station readings (data/<unit>/), data/seen and the registry are not.
Each source's newest file is always left as it is, so a source that has gone quiet still shows as stale on its page.
If the newest file anywhere is over 30 days older than today, the clock or the collectors are wrong and nothing is
done. Standard library only.
"""
import argparse
import gzip
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

COMPRESS_AFTER_DAYS = 14
DELETE_AFTER_DAYS = 400
MAX_SILENCE_DAYS = 30
DATED = re.compile(r"(\d{4}-\d{2}-\d{2})\.jsonl(\.gz)?")
CEILOMETER = re.compile(r"MET-\d+")


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
    return sorted(out, key=lambda x: (x[0], x[1].name))


def sources(root):
    """Every source folder that housekeeping may touch."""
    out = []
    for kind in ("reference", "satellite"):
        parent = Path(root) / kind
        if parent.is_dir():
            out += [p for p in sorted(parent.iterdir()) if p.is_dir() and not p.is_symlink()]
    return out


def plan(root, today):
    """(files to compress, files to delete), or ValueError if the dates say the clock can't be trusted."""
    squeeze, remove, newest = [], [], None
    for folder in sources(root):
        files = [f for f in dated_files(folder) if f[0] <= today]       # a future-dated file is never acted on
        if not files:
            continue
        newest = max(newest or files[-1][0], files[-1][0])
        last_day = files[-1][0]
        for day, path in files:
            if day == last_day:
                continue
            age = (today - day).days
            if age > DELETE_AFTER_DAYS:
                remove.append(path)
            elif age > COMPRESS_AFTER_DAYS and path.suffix == ".jsonl" and CEILOMETER.fullmatch(folder.name):
                squeeze.append(path)
    if newest is not None and (today - newest).days > MAX_SILENCE_DAYS:
        raise ValueError(f"newest file is from {newest}, over {MAX_SILENCE_DAYS} days before {today}")
    return squeeze, remove


def compress(path):
    """path to path.gz, checked against the original before the original goes. A leftover .gz from a run that
    stopped part-way is accepted only if it holds exactly the same bytes."""
    data = path.read_bytes()
    target = path.with_name(path.name + ".gz")
    if target.exists():
        if gzip.decompress(target.read_bytes()) != data:
            raise ValueError(f"{target} exists and differs from {path.name}")
    else:
        temporary = path.with_name(f".{path.name}.gz.tmp")
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
            with os.fdopen(fd, "wb") as f:
                f.write(gzip.compress(data, mtime=0))
                f.flush()
                os.fsync(f.fileno())
            if gzip.decompress(temporary.read_bytes()) != data:
                raise ValueError(f"{temporary} failed its check")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    before, after = len(data), target.stat().st_size
    path.unlink()
    return before, after


def run(root, today, apply):
    """Returns (files compressed, bytes saved by that, files deleted, bytes deleted, problems)."""
    squeeze, remove = plan(root, today)
    squeezed = saved = deleted = freed = 0
    problems = []
    for path in squeeze:
        try:
            if apply:
                before, after = compress(path)
                saved += before - after
            squeezed += 1
        except (OSError, ValueError, EOFError) as e:
            problems.append(f"{path}: {e}")
    for path in remove:
        try:
            size = path.stat().st_size
            if apply:
                path.unlink()
            deleted += 1
            freed += size
        except OSError as e:
            problems.append(f"{path}: {e}")
    return squeezed, saved, deleted, freed, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--apply", action="store_true", help="make the changes; without it, only say what they'd be")
    a = ap.parse_args()
    today = datetime.now(timezone.utc).date()
    try:
        squeezed, saved, deleted, freed, problems = run(a.data, today, a.apply)
    except ValueError as e:
        sys.exit(f"housekeep: nothing done: {e}")
    verb = ("compressed", "deleted") if a.apply else ("would compress", "would delete")
    print(f"housekeep: {verb[0]} {squeezed} files (saved {saved / 1e6:.1f} MB), {verb[1]} {deleted} files ({freed / 1e6:.1f} MB)")
    for p in problems:
        print(f"housekeep: {p}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
