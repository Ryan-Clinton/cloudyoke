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
| `metar.py` | Airport weather reports as a reference source (City of Derry, EGAE, first): fetched from the Aviation Weather Center's API, each kept once with its raw text and real observation time in `data/reference/<ICAO>/`; codes like CAVOK and NCD kept as given, never turned into "clear" ([spec §5.3.1](../docs/spec.md#531-reference-sources-airport-reports)). Run every 30 minutes |
| `metar_graph.py` | An airport's days as SVG: cloud layers by height, the codes, fog and visibility, closed hours left blank |

`night_graph.py --reference EGAE` adds a strip of the airport's reports under a station's night.

Try it:

```
echo '{"cy-0001": "trial-key"}' > keys.json
python server/receiver.py --listen 127.0.0.1:8095 --data data --keys keys.json &
python server/pretend_station.py --key trial-key --night 2026-11-20
python server/night_graph.py --data data --unit cy-0001 --night 2026-11-20 > night.svg
python server/metar.py --data data --ids EGAE --hours 360
python server/metar_graph.py --data data --icao EGAE --from 2026-11-03 --days 7 > egae.svg
```

Tests: `python -m unittest discover -s tests`.

Not here yet: per-station clear-sky baselines and states (§4), registration and revocation (§5.1),
gzipping finished days, the load test (issue 6). The receiver goes on the server behind
ryanclinton.uk once the first station's firmware can send to it.
