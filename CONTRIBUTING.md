# Contributing to cloudyoke

The project is at the design stage: the first station's hardware is due in
mid-November 2026, and there is no firmware or server code here yet. That
makes this the best time to question the design.

## Joining

Building a station or bringing an existing sensor: [docs/join.md](docs/join.md), and say hello in the
[welcome thread](https://github.com/Ryan-Clinton/cloudyoke/discussions/9).

## Where things go

- **Discussions:** ideas, questions, hardware suggestions, calibration
  approaches, possible station locations, and any similar network you know of.
- **Issues:** a specific piece of work or a specific problem with the design,
  with enough detail to act on.
- **Pull requests:** welcome on the docs now, and on code once the firmware
  and server folders exist. One subject per pull request.

## Useful now

- Experience with MLX90614 sky sensors outdoors: dew, rain, hoods, windows,
  heaters, calibration.
- Experience running ESP32 boards outdoors for months: power, WiFi from the
  end of a garden, enclosures.
- Checking the calibration approach in [docs/spec.md §4](docs/spec.md#4-telling-clear-from-cloud)
  against what you've seen.
- Places upwind (west and north-west coasts of Ireland) where a station could
  go.
- Owning an AAG CloudWatcher, a Boltwood or another ASCOM ObservingConditions
  sensor, and being willing to test the first bridge against it.

## Privacy

Never post a home address, exact coordinates or photos that identify a house
in an issue or discussion. A town or area is enough; registration handles the
rest privately, and the public map only ever shows a rough square
([spec §6](docs/spec.md#6-hosts-privacy)).

## Layout

One repository for everything (docs, hardware, firmware, server) until there
is a real reason to split it.

```
docs/spec.md       the design: station, judging, readings, privacy, stages, sources
hardware/bom.md    parts, prices, traps and wiring
firmware/          nano-usb: the first station, a Nano over USB; the ESP32 code is not started
bridges/           readers for existing sensors, ASCOM Alpaca first (not started)
schemas/           the reading format as JSON Schema, with examples; check with python schemas/check.py
server/            receiver and night graph for the first station; judging and the rest to come
tests/             python -m unittest discover -s tests
```
