# deploy/

How cloudyoke runs on the server behind ryanclinton.uk: its own user, `/srv/cloudyoke/code` (a clone of
this repository) and `/srv/cloudyoke/data`.

| Unit | Does |
|---|---|
| `cloudyoke-metar.service` + `.timer` | Every 30 minutes, keeps the reports of City of Derry, Belfast International, Belfast City and Prestwick (`server/metar.py`), then Met Éireann's ceilometers at Malin Head, Finner and Belmullet (`server/met_eireann.py`), then rebuilds the dashboard in `/srv/cloudyoke/www` (`server/dashboard.py`), served at ryanclinton.uk/cloudyoke/live/ by the site's nginx |
| `cloudyoke-satellite.service` + `.timer` | Every 10 minutes, Meteosat's verdict for each joined site in `/srv/cloudyoke/data/sites.json` (`server/satellite.py`), then the joined sites' page at ryanclinton.uk/cloudyoke/live/sites/ (`server/sites_page.py`). Adding a site: [docs/join.md](../docs/join.md#for-the-maintainer-adding-a-site) |

Set up once, as root:

```
useradd --system --home /srv/cloudyoke --shell /usr/sbin/nologin cloudyoke
git clone https://github.com/Ryan-Clinton/cloudyoke.git /srv/cloudyoke/code
install -d -o cloudyoke -g cloudyoke /srv/cloudyoke/data /srv/cloudyoke/www
cp /srv/cloudyoke/code/deploy/cloudyoke-metar.* /srv/cloudyoke/code/deploy/cloudyoke-satellite.* /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now cloudyoke-metar.timer cloudyoke-satellite.timer
sudo -u cloudyoke python3 /srv/cloudyoke/code/server/met_eireann.py --data /srv/cloudyoke/data --hours 27
for a in EGAE EGAA EGAC EGPK; do sudo -u cloudyoke python3 /srv/cloudyoke/code/server/metar.py --data /srv/cloudyoke/data --ids $a --hours 360; done
```

Backfill one airport at a time: one request returns at most 400 reports across all the airports it names
(about 13 days at Derry, which closes at night, and about 8 at the others, which report round the clock).
The 30-minute run asks for 6 hours, far under that.

Update: `git -C /srv/cloudyoke/code pull`. The receiver isn't run on the server yet: it goes up once the
first station's firmware can send to it.
