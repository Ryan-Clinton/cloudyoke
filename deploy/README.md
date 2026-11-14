# deploy/

How cloudyoke runs on the server behind ryanclinton.uk: its own user, `/srv/cloudyoke/code` (a clone of
this repository) and `/srv/cloudyoke/data`.

| Unit | Does |
|---|---|
| `cloudyoke-metar.service` + `.timer` | Every 30 minutes, for every site in the registry: the reports of each airport within 150 km (`server/metar.py --sites`), then Met Éireann's ceilometers within 250 km (`server/met_eireann.py --sites`), then every site's page in `/srv/cloudyoke/www` (`server/dashboard.py`), served at ryanclinton.uk/cloudyoke/live/ by the site's nginx |
| `cloudyoke-satellite.service` + `.timer` | Every 10 minutes, the verdict of the satellite overhead for each site (`server/satellite.py`), then the pages again |

Nothing in either unit names a place: sites come from the registry (`server/registry.py`, files in
`/srv/cloudyoke/data`), and each site's airports and ceilometers are found by distance.

Set up once, as root:

```
useradd --system --home /srv/cloudyoke --shell /usr/sbin/nologin cloudyoke
git clone https://github.com/Ryan-Clinton/cloudyoke.git /srv/cloudyoke/code
install -d -o cloudyoke -g cloudyoke /srv/cloudyoke/data /srv/cloudyoke/www
cp /srv/cloudyoke/code/deploy/cloudyoke-metar.* /srv/cloudyoke/code/deploy/cloudyoke-satellite.* /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now cloudyoke-metar.timer cloudyoke-satellite.timer
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
