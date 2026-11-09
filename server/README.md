# server/

The minimum needed for the first station: receive its readings, store them reliably, and draw a night.
No judging, no map, no registration yet ([docs/spec.md §5](../docs/spec.md#5-where-the-readings-go)).
Standard library Python; if the `jsonschema` package is installed, every reading is also checked against
[schemas/reading.schema.json](../schemas/reading.schema.json).

| File | Does |
|---|---|
| `receiver.py` | Takes POSTs at `/cloudyoke/send` with `Authorization: Bearer <key>`, one reading or a list; refuses a whole send if any reading is malformed or claims another station; answers a resend as duplicates without storing it twice; one writer appends to `data/<unit>/<UTC date>.jsonl`; a full queue answers 503 so the station resends |
| `night_graph.py` | One station's night (12:00 to 12:00 UTC) as SVG: sky, air and sky minus air, with gaps left as gaps and flagged readings ticked |
| `pretend_station.py` | A made-up night for trying it all before hardware exists; its graph is stamped MADE-UP DATA |

Try it:

```
echo '{"cy-0001": "trial-key"}' > keys.json
python server/receiver.py --listen 127.0.0.1:8095 --data data --keys keys.json &
python server/pretend_station.py --key trial-key --night 2026-11-20
python server/night_graph.py --data data --unit cy-0001 --night 2026-11-20 > night.svg
```

Tests: `python -m unittest discover -s tests`.

Not here yet: per-station clear-sky baselines and states (§4), registration and revocation (§5.1),
gzipping finished days, the load test (issue 6). The receiver goes on the server behind
ryanclinton.uk once the first station's firmware can send to it.
