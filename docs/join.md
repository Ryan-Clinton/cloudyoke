# Joining

A site joins with an infrared cloud sensor pointing straight up:

| You have | You do |
|---|---|
| About £15 and an evening | Build the station: an ESP32, an MLX90614 (BAA) and a BME280 in a weatherproof box, on your WiFi and an old phone charger, no computer ([hardware/bom.md](../hardware/bom.md)). Its firmware is being written ([issue 3](https://github.com/Ryan-Clinton/cloudyoke/issues/3)); parts can be ordered now |
| An AAG CloudWatcher, Boltwood or other ASCOM ObservingConditions sensor | Help test the read-only bridge ([issue 7](https://github.com/Ryan-Clinton/cloudyoke/issues/7)) |

## Talk

Everything happens in [Discussions](https://github.com/Ryan-Clinton/cloudyoke/discussions). Say hello in the
[welcome thread](https://github.com/Ryan-Clinton/cloudyoke/discussions/9) with roughly where you are (a town or
area, never an address). Ask about parts and wiring in Q&A, and post your build in Show and tell. People without a
GitHub account can use the form on [the project's page](https://ryanclinton.uk/cloudyoke/#join).

## Once a station works

Each station gets its own key, and its site goes on the
[joined sites' page](https://ryanclinton.uk/cloudyoke/live/sites/) by its area's name only
([spec §6](spec.md#6-hosts-privacy)), with Meteosat's verdict beside it as a reference. Outside stations start
sending once the data licence is settled ([issue 8](https://github.com/Ryan-Clinton/cloudyoke/issues/8)), so every
host knows what they're agreeing to before their first reading. A host can leave at any time; their site comes off
the page and its readings are deleted on request.

## For the maintainer: adding a site

On the server, add the site to `/srv/cloudyoke/data/sites.json`. The key is a short id and `as` is `station` or
`existing sensor`:

```
{"brecon": {"area": "Brecon, Wales", "lat": 51.95, "lon": -3.39, "as": "station", "joined": "2026-11-14"}}
```

The position can be the town's centre. It is snapped to its cell before anything uses it. Then backfill the
satellite reference: `sudo -u cloudyoke python3 /srv/cloudyoke/code/server/satellite.py --data /srv/cloudyoke/data --hours 12`.
