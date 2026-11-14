# Joining

A site joins with an infrared cloud sensor pointing straight up. There are two ways in:

| You have | You do |
|---|---|
| About £15 and an evening | Build the Nano station: an Arduino Nano, an MLX90614 (BAA) and a BME280, on USB to a computer or Raspberry Pi that's on overnight ([firmware/nano-usb](../firmware/nano-usb/README.md), [hardware/bom.md](../hardware/bom.md)) |
| An AAG CloudWatcher, Boltwood or other ASCOM ObservingConditions sensor | Help test the read-only bridge ([issue 7](https://github.com/Ryan-Clinton/cloudyoke/issues/7)) |

## Steps

1. **Join.** Open a [join issue](https://github.com/Ryan-Clinton/cloudyoke/issues/new?template=join.yml) with your
   area and which way in. If you don't use GitHub, use the form on
   [the project's page](https://ryanclinton.uk/cloudyoke/#join). Give a town or area, never an address.
2. **Build or connect.** Help with parts and wiring goes in the issue.
3. **Your site goes on the page.** On the [joined sites' page](https://ryanclinton.uk/cloudyoke/live/sites/) each
   site shows by its area's name only ([spec §6](spec.md#6-hosts-privacy)). Meteosat's verdict for the site's
   0.05° square is shown beside the sensor as a reference, as the airport reports are.
4. **Sending.** Each sensor gets its own key. Outside stations start sending once the data licence is settled
   ([issue 8](https://github.com/Ryan-Clinton/cloudyoke/issues/8)), so every host knows what they're agreeing
   to before their first reading. Until then a Nano station keeps its readings on the host's own computer, in
   the same format the server stores.

## Leaving

Say so on your issue or by email. Your site comes off the page, and its readings are deleted on request.

## For the maintainer: adding a site

On the server, add the site to `/srv/cloudyoke/data/sites.json`. The key is a short id and `as` is `station` or
`existing sensor`:

```
{"brecon": {"area": "Brecon, Wales", "lat": 51.95, "lon": -3.39, "as": "station", "joined": "2026-11-14"}}
```

The position can be the town's centre. It is snapped to its cell before anything uses it. Then backfill the
satellite reference: `sudo -u cloudyoke python3 /srv/cloudyoke/code/server/satellite.py --data /srv/cloudyoke/data --hours 12`.
