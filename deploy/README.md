# deploy/

How cloudyoke runs on the server behind ryanclinton.uk: its own user, `/srv/cloudyoke/code` (a clone of
this repository) and `/srv/cloudyoke/data`.

| Unit | Does |
|---|---|
| `cloudyoke-metar.service` + `.timer` | Every 30 minutes: every airport in the collection box and within 150 km of each site (`server/metar.py --box ... --sites`), then all of Met Éireann's ceilometers (`server/met_eireann.py --all`), then every site's page in `/srv/cloudyoke/www` (`server/dashboard.py`), served at ryanclinton.uk/cloudyoke/live/ by the site's nginx |
| `cloudyoke-satellite.service` + `.timer` | Every 10 minutes, the verdict of the satellite overhead for each site (`server/satellite.py`), then the pages again |
| `cloudyoke-airports.service` + `.timer` | Every 10 minutes: the latest report from every airport in the UK, Isle of Man, Ireland, USA, Canada and Australia, from one worldwide file (`server/metar.py --countries`) |
| `cloudyoke-housekeep.service` + `.timer` | Once a day: bundles airport and ceilometer files over 7 days old into `data/archive/airports/<date>.jsonl.bz2` and `data/archive/ceilometers/<date>.jsonl.xz`, and deletes reference and satellite data over 400 days old (`server/housekeep.py`). Never touches station readings |

The collectors and housekeeping share a lock, `/srv/cloudyoke/data/.collect.lock`, so two never write the same files.

Sites come from the registry (`server/registry.py`, files in `/srv/cloudyoke/data`), and each site's page shows
the airports and ceilometers found by distance. Collection is wider than the sites: every airport reporting in
the box 50°N to 58°N, 11°W to 2°W (Ireland across to western Britain, `--box`), every airport in the countries
above (`--countries`) and all of Met Éireann's ceilometers (`--all`), with no site or page of their own. Meanwhile
on ryanclinton.uk shows the nearest sensors.

Meanwhile reads these stored files directly, so changing them means telling that project first:
`data/reference/index.json` (`kind`, `name`, `lat`, `lon`) and `data/reference/<ICAO>/<UTC date>.jsonl`
(`obs_time`, `cover`, `layers`, `vertical_visibility_ft`, `weather`, `correction`, and the raw report in `raw`).
For ceilometers it reads `data/reference/MET-<id>/<UTC date>.jsonl` (`obs_time`, `layers[].base_ft`,
`layers[].oktas`, and from 22 November 2026 `sky_status`: `layers`, `none_detected`, `hit_without_layer` or
`no_data`; older rows don't have it), today's and yesterday's plain files only, so the 7-day bundling doesn't reach it. The public page's
`/cloudyoke/#join` anchor, in the ryanclinton.uk project, is linked from every Meanwhile page.

Set up once, as root:

```
useradd --system --home /srv/cloudyoke --shell /usr/sbin/nologin cloudyoke
git clone https://github.com/Ryan-Clinton/cloudyoke.git /srv/cloudyoke/code
install -d -o cloudyoke -g cloudyoke /srv/cloudyoke/data /srv/cloudyoke/www
cp /srv/cloudyoke/code/deploy/cloudyoke-*.service /srv/cloudyoke/code/deploy/cloudyoke-*.timer /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now cloudyoke-metar.timer cloudyoke-airports.timer cloudyoke-satellite.timer cloudyoke-housekeep.timer
```

## Adding a site

```
sudo -u cloudyoke python3 /srv/cloudyoke/code/server/registry.py add-site --data /srv/cloudyoke/data \
    --id brecon --place Brecon --country GB
sudo -u cloudyoke python3 /srv/cloudyoke/code/server/metar.py --data /srv/cloudyoke/data --sites --hours 24
sudo -u cloudyoke python3 /srv/cloudyoke/code/server/satellite.py --data /srv/cloudyoke/data --hours 12
```

The place is looked up by name and country (position and population); its position is snapped to its 0.05°
cell and never published. Pages measure from the 0.05° cell for a town of 1,000 or more or 3 sites in the cell,
otherwise the 0.2° cell (spec §6); the registry decides. Without a place to look up: `--area`, `--lat`, `--lon`
and `--population`. A station at the site:
`registry.py register --site brecon --setup sensor=BAA ...` prints its unit id and key once.

Backfilling airports: one request returns at most 400 reports across the airports it covers, so a long
backfill goes one airport at a time (`metar.py --ids EGFF --hours 360`, about 8 days at an airport that reports
round the clock). The 30-minute run asks for 3 hours, far under that even where airports are dense.

Update: `git -C /srv/cloudyoke/code pull`. The receiver isn't run on the server yet: it takes keys from the
registry (`receiver.py --data /srv/cloudyoke/data`), and goes up once outside stations can send (the data
licence, issue 8).
