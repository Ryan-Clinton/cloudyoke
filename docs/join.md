# Joining

A place joins the network before any sensor does. Each joined area gets the satellite's cloud verdict every 10
minutes on the [joined sites' page](https://ryanclinton.uk/cloudyoke/live/sites/). The people there say what the
sky really did, and that is what tests the verdict. Equipment adds to it later. None is needed to start.

## Why a place without a sensor is worth adding

Meteosat's 10.5 µm infrared picture covers all of Europe every 10 minutes, day and night, for free.
[satellite.py](../server/satellite.py) turns it into a verdict for each site: probably clear, thin or broken
cloud, or cloud. Nobody knows how good that verdict is at any given place. Thin cirrus, low cloud as cold as the
ground, and hills and coasts all fool it in different ways. Every site where someone reports the real sky adds a
measured answer, site by site. The same scores later test cloudyoke's own sensors.

## Ways to take part

| You have | You do | It gives |
|---|---|---|
| A view of the sky | Say what it did on nights you're out: clear, partly or cloudy, from when to when | The satellite scored at your place |
| A telescope or camera that images | Share your subs' times, or a session log with star counts or the frames you kept and lost | Hard ground truth: a star count can't be fooled the way an eye in the dark can |
| An AAG CloudWatcher, Boltwood or other ASCOM sensor | Help test the read-only bridge ([issue 7](https://github.com/Ryan-Clinton/cloudyoke/issues/7)) | A calibrated sensor's readings beside the satellite |
| £15 and an evening | Build the Nano station ([firmware/nano-usb](../firmware/nano-usb/README.md)) on a computer that's on overnight | Your sky every minute, judged by the server |

## Steps

1. **Join.** Open a [join issue](https://github.com/Ryan-Clinton/cloudyoke/issues/new?template=join.yml) with your
   area and what you have. If you don't use GitHub, use the form on
   [the project's page](https://ryanclinton.uk/cloudyoke/#join). Give a town or area, never an address.
2. **Your area goes on the page.** The server judges your area at the centre of the 0.05° square it falls in
   (about 5 by 3 km), never at a house. The page shows the area's name only
   ([spec §6](spec.md#6-hosts-privacy)). Verdicts start within 10 minutes and run every night.
3. **Report what you see.** Comment on your join issue after a night out, for example: "21:00 to 23:30 clear,
   then cloud", in UK time or UTC (say which). Imagers can attach a capture log or a list of sub times. Each
   report is stored with [seen.py](../server/seen.py), and the page shows how the satellite scored against it.
4. **Add equipment when you like.** A sensor gets its own key and sends readings to the server. Outside stations
   start sending once the data licence is settled ([issue 8](https://github.com/Ryan-Clinton/cloudyoke/issues/8)),
   so every host knows what they're agreeing to before their first reading. Until then a Nano station keeps its
   readings on the host's own computer, in the same format the server stores.

## Leaving

Say so on your issue or by email. Your area comes off the page, and the reports you gave are deleted on request.

## For the maintainer: adding a site

On the server, add the area to `/srv/cloudyoke/data/sites.json`. The key is a short id and `as` is one of
`location`, `imager`, `existing sensor` or `station`:

```
{"brecon": {"area": "Brecon, Wales", "lat": 51.95, "lon": -3.39, "as": "imager", "joined": "2026-11-14"}}
```

The position can be the town's centre. It is snapped to its cell before anything uses it. Then backfill the
day: `sudo -u cloudyoke python3 /srv/cloudyoke/code/server/satellite.py --data /srv/cloudyoke/data --hours 12`.
Record reports with `server/seen.py add`, and see the scores with `server/seen.py scores`.
