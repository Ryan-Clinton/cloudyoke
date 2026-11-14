# cloudyoke

An open network of low-cost infrared sky sensors.

Stations on walls and sheds measure the infrared temperature of the sky every
minute and send their raw readings to one server, which judges the cloud cover
over each station and keeps an open record for analysis. Built on ESP32
boards, MLX90614 thermopiles and BME280 sensors, at about £24 a station from
AliExpress, £21 each for ten ([build guide](hardware/build.md)).

Public page: https://ryanclinton.uk/cloudyoke/

## Status

**Early development, open to join.** The first sensor hardware is due between
13 and 18 November 2026, and the first station goes up in Ballymoney, County
Antrim, Northern Ireland. The Nano-over-USB station's firmware is written
([firmware/nano-usb](firmware/nano-usb/README.md)); the ESP32's isn't. The
server keeps references for every site, found by distance: each airport within
150 km, Met Éireann's ceilometers in Ireland, and an infrared verdict from the
weather satellite overhead (Meteosat, GOES or Himawari) every 10 minutes ([live](https://ryanclinton.uk/cloudyoke/live/)).
Next milestone:
[first observational data](https://github.com/Ryan-Clinton/cloudyoke/milestone/1).

| | |
|---|---|
| Phase | Parts arriving; joining open |
| Stations online | 0 |
| Data | Reference sources (airports, ceilometers, satellite) |

## Join

A site joins with an infrared cloud sensor: the £24 ESP32 station on the
house's WiFi (firmware in progress, issue 3), or a CloudWatcher, Boltwood or
other ASCOM sensor already running. How:
[docs/join.md](docs/join.md). Say hello and ask anything in the
[welcome thread](https://github.com/Ryan-Clinton/cloudyoke/discussions/9).

## How a station measures cloud

An MLX90614 infrared thermopile points straight up and reads the sky in the 8
to 14 µm band, over a cone 90° wide. A clear sky is cold, because the sensor
is looking out to space through dry air; cloud is water close overhead, so the
reading climbs towards the air's own temperature. A BME280 reads the air's
temperature and humidity, and the gap between sky and air, corrected for the
air's own glow with the formula the AAG CloudWatcher uses, is the
measurement. Clear sky reads anywhere from about 20 to over 35 °C below the
air, depending on the site and the humidity.

## Architecture

```
station (ESP32 + MLX90614 + BME280)
  └─ one raw reading a minute, timestamped, sequence-numbered,
     buffered for up to 6 hours through WiFi drops
        └─ HTTPS POST, per-station key in the Authorization header
              └─ server: stores every reading, learns each station's clear sky,
                 judges clear / some cloud / cloudy / wet / learning / fault / no reading
                    └─ public page, map and daily CSV downloads
```

The station does no judging. The server decides what the readings mean, so the
method can improve without any station being reflashed. A station that is
still learning, faulty or silent is never shown as clear. Full detail, with
the reading format, registration, calibration safeguards and privacy rules:
[docs/spec.md](docs/spec.md).

## Already running a cloud sensor?

The ESP32 station is the reference design, not a condition of joining.
Observatories already running an AAG CloudWatcher, a Boltwood or another ASCOM
ObservingConditions device should be able to send readings through a small
bridge on their own PC or Raspberry Pi. **No bridge exists yet:** the first,
for ASCOM Alpaca, is being designed, and owners of such sensors are invited to
help validate it ([issue 7](https://github.com/Ryan-Clinton/cloudyoke/issues/7)).
The bridge only reads, never writes to the device, opens no ports and is never
part of an observatory's safety system ([spec §3.1](docs/spec.md#31-existing-sensors)).
Each station declares what it measures; a maker's own cloud verdict is kept
beside the network's judgement, labelled as the maker's.

## Open questions

- **Thin cloud:** whether a £24 station tells thin high cloud from clear sky.
- **Self-calibration:** whether each station can learn its own clear sky
  without hand-set thresholds.
- **Agreement over distance:** two stations in one town, then 10 km apart,
  then 50.
- **Propagation:** whether cloud reaching one station predicts its arrival at
  the next one downwind, and how reliably.

## Roadmap

Each stage has a gate it must pass before the next ([spec §9](docs/spec.md#9-stages)):

1. **One station, Ballymoney.** Agreement with the sky overhead over four weeks
   including damp nights; a self-learned baseline; faults flagged; the dew
   test (open under a hood, behind thin polythene, or with a heater).
2. **Two in one town.** Neighbours agree on at least 90% of judged readings
   over four weeks. The data licence is settled before this station sends.
3. **A line upwind,** on the first station's usual nights (the north-west
   coast, near Derry, mid Ulster), and hosts anywhere who build one: nothing in
   the code is tied to one place ([spec §9](docs/spec.md#9-stages)). Arrival
   warnings are shown only after a season's test (spec §9.1).
4. **Open to anyone:** build guide, one-click web installer, parts lists by
   country, once the hardware and self-calibration have passed on at least
   three stations and the server has been load-tested.

Alongside stages 1 to 3, a second track brings in **existing sensors**: the
reading format takes bridges first, then one ASCOM Alpaca bridge proven
against a volunteer's real sensor, then a guide someone else can install it
from.

## Hardware

How to build one, every version (WiFi, wired, 4G; charger or solar; soldered or
solder-free), with shop prices and bulk prices for ten: [hardware/build.md](hardware/build.md).
Planning a ring of stations round your site: [docs/ring.md](docs/ring.md).

## Contributing

Ideas, questions and suggested station locations go in Discussions; specific
work goes in Issues. See [CONTRIBUTING.md](CONTRIBUTING.md). To add your sky,
see [docs/join.md](docs/join.md). People who would join but don't use GitHub can leave an email and a general area on
the [public page](https://ryanclinton.uk/cloudyoke/#join).

## Prior work

Infrared cloud sensors aren't new: observatories close their roofs with them,
and amateurs have built their own for years. Every one found so far works on
its own. Steve Marple at Lancaster [proposed an open cloud-detection network](https://blog.stevemarple.co.uk/2013/05/an-open-access-cloud-detection-network.html)
with the same sensor in 2013. Other networks of this kind are worth hearing
about: open a discussion.

## Licence

The code and documentation in this repository are under the [MIT licence](LICENSE).
The licence for the network's readings is not chosen yet; it is settled before
any outside station sends a reading ([issue 8](https://github.com/Ryan-Clinton/cloudyoke/issues/8)).

cloudyoke is run by Ryan Clinton (ryan@ryanclinton.uk), and grew out of
telescopeyoke, his telescope project.
