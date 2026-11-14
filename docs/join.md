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
[network's pages](https://ryanclinton.uk/cloudyoke/live/) by its area's name only, with the airports and
ceilometers near it,
([spec §6](spec.md#6-hosts-privacy)), with the weather satellite's verdict beside it as a reference. Outside stations start
sending once the data licence is settled ([issue 8](https://github.com/Ryan-Clinton/cloudyoke/issues/8)), so every
host knows what they're agreeing to before their first reading. A host can leave at any time; their site comes off
the page and its readings are deleted on request.

## For the maintainer: adding a site

With `server/registry.py` on the server: [deploy/README.md](../deploy/README.md#adding-a-site). The site's
airports, ceilometers and satellite verdicts are found from its position, and its page appears on the next run.
