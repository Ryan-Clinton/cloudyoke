#!/usr/bin/env python3
"""The minimum receiver for the first station: takes readings, checks them, stores them. No judging, no map.

    python server/receiver.py --listen 127.0.0.1:8095 --data data --keys keys.json

keys.json maps each station to its secret: {"cy-0001": "long-random-string"}. A station POSTs to
/cloudyoke/send with "Authorization: Bearer <secret>" and a body of one reading or a list of them
(docs/spec.md 5.2). Each reading is checked (against schemas/reading.schema.json too, when the
jsonschema package is installed), duplicates by (unit, boot, seq) are answered but not stored again,
and the rest go on a bounded queue that one writer thread appends to data/<unit>/<UTC date>.jsonl,
one reading per line with the server's receipt time added. A full queue answers 503, so the station
keeps its readings and tries again. Standard library only.
"""
import argparse
import hmac
import json
import logging
import os
import queue
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_BODY = 256 * 1024                 # a WiFi drop's worth of buffered readings (360) fits easily
MAX_READINGS = 400
QUEUE_SIZE = 10_000

log = logging.getLogger("receiver")

try:                                  # full schema checks when available; the basic checks below always run
    from jsonschema import Draft202012Validator
    SCHEMA = Draft202012Validator(json.loads((Path(__file__).parent.parent / "schemas" / "reading.schema.json").read_text()))
except ImportError:
    SCHEMA = None


def basic_problem(r):
    """Why a reading can't be stored, or None. Enough to keep junk out without the jsonschema package."""
    if not isinstance(r, dict):
        return "not an object"
    for k, kind in (("schema", int), ("unit", str), ("source", str), ("fw", str), ("boot", int), ("seq", int),
                    ("t", str), ("t_ok", bool), ("flags", list), ("capabilities", list)):
        if not isinstance(r.get(k), kind) or (kind is int and isinstance(r.get(k), bool)):
            return f"{k} missing or wrong type"
    if r["schema"] != 1:
        return "unknown schema version"
    try:
        datetime.fromisoformat(r["t"].replace("Z", "+00:00"))
    except ValueError:
        return "t is not a time"
    if "source_offline" not in r["flags"] and r["source"] == "cloudyoke-esp32":
        readings = r.get("readings")
        if not isinstance(readings, dict) or not all(isinstance(readings.get(k), (int, float)) for k in ("sky_c", "air_c")):
            return "a reference station needs readings.sky_c and readings.air_c"
    return None


class Store:
    """Remembers what has been stored, so a resend is answered without being written twice, and owns the
    one writer thread."""

    def __init__(self, root):
        self.root = Path(root)
        self.seen = {}                # unit -> set of (boot, seq), loaded from disk the first time a unit sends
        self.lock = threading.Lock()
        self.queue = queue.Queue(QUEUE_SIZE)
        threading.Thread(target=self._writer, daemon=True).start()

    def _load(self, unit):
        keys = set()
        for path in (self.root / unit).glob("*.jsonl"):
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line)
                    keys.add((r["boot"], r["seq"]))
                except (ValueError, KeyError):
                    continue          # a torn last line after a crash is skipped, never fatal
        return keys

    def claim(self, unit, boot, seq):
        """True if this reading is new (and marks it taken), False if it was stored before."""
        with self.lock:
            if unit not in self.seen:
                self.seen[unit] = self._load(unit)
            if (boot, seq) in self.seen[unit]:
                return False
            self.seen[unit].add((boot, seq))
            return True

    def release(self, unit, boot, seq):
        with self.lock:
            self.seen.get(unit, set()).discard((boot, seq))

    def _writer(self):
        while True:
            r = self.queue.get()
            day = r["t"][:10]
            folder = self.root / r["unit"]
            folder.mkdir(parents=True, exist_ok=True)
            line = (json.dumps(r, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
            # One write per line with O_APPEND, so a crash can tear at most the last line, never mix two
            fd = os.open(folder / f"{day}.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            try:
                os.write(fd, line)
            finally:
                os.close(fd)
            self.queue.task_done()


class Handler(BaseHTTPRequestHandler):
    store = None
    keys = {}

    def reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/cloudyoke/send":
            return self.reply(404, {"ok": False})
        auth = self.headers.get("Authorization", "")
        secret = auth[7:] if auth.startswith("Bearer ") else ""
        unit = next((u for u, k in self.keys.items() if secret and hmac.compare_digest(k, secret)), None)
        if unit is None:
            return self.reply(401, {"ok": False, "why": "unknown or revoked key"})
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self.reply(411, {"ok": False})
        if not 0 < length <= MAX_BODY:
            return self.reply(413, {"ok": False})
        try:
            body = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            return self.reply(400, {"ok": False, "why": "not JSON"})
        readings = body if isinstance(body, list) else [body]
        if not 0 < len(readings) <= MAX_READINGS:
            return self.reply(400, {"ok": False, "why": "no readings, or too many in one send"})
        # Check the whole send first: one bad reading refuses it all, so nothing is half-stored
        for r in readings:
            why = basic_problem(r)
            if why is None and SCHEMA is not None:
                err = next(SCHEMA.iter_errors(r), None)
                why = err.message if err else None
            if why is None and r["unit"] != unit:
                why = "unit doesn't match the key"
            if why:
                log.warning("%s: refused a send: %s", unit, why)
                return self.reply(400, {"ok": False, "why": why})
        stored = duplicates = 0
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for r in readings:
            if not self.store.claim(unit, r["boot"], r["seq"]):
                duplicates += 1
                continue
            try:
                self.store.queue.put_nowait({**r, "received": now})
            except queue.Full:
                self.store.release(unit, r["boot"], r["seq"])
                log.warning("queue full: asked %s to resend", unit)
                return self.reply(503, {"ok": False, "stored": stored, "why": "busy, send again later"})
            stored += 1
        self.reply(200, {"ok": True, "stored": stored, "duplicates": duplicates})

    def log_message(self, *args):
        pass


def serve(listen, data, keys):
    Handler.store = Store(data)
    Handler.keys = keys
    host, port = listen.rsplit(":", 1)
    return ThreadingHTTPServer((host, int(port)), Handler)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", default="127.0.0.1:8095")
    ap.add_argument("--data", default="data")
    ap.add_argument("--keys", default="keys.json")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    keys = json.loads(Path(a.keys).read_text())
    log.info("listening on %s, %d station keys, schema checks %s", a.listen, len(keys), "on" if SCHEMA else "basic only")
    serve(a.listen, a.data, keys).serve_forever()


if __name__ == "__main__":
    main()
