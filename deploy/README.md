# deploy/

How cloudyoke runs on the server behind ryanclinton.uk: its own user, `/srv/cloudyoke/code` (a clone of
this repository) and `/srv/cloudyoke/data`.

| Unit | Does |
|---|---|
| `cloudyoke-metar.service` + `.timer` | Every 30 minutes, keeps the reports of City of Derry, Belfast International, Belfast City and Prestwick (`server/metar.py`) |

Set up once, as root:

```
useradd --system --home /srv/cloudyoke --shell /usr/sbin/nologin cloudyoke
git clone https://github.com/Ryan-Clinton/cloudyoke.git /srv/cloudyoke/code
install -d -o cloudyoke -g cloudyoke /srv/cloudyoke/data
cp /srv/cloudyoke/code/deploy/cloudyoke-metar.* /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now cloudyoke-metar.timer
for a in EGAE EGAA EGAC EGPK; do sudo -u cloudyoke python3 /srv/cloudyoke/code/server/metar.py --data /srv/cloudyoke/data --ids $a --hours 360; done
```

Backfill one airport at a time: one request returns at most 400 reports across all the airports it names
(about 13 days at Derry, which closes at night, and about 8 at the others, which report round the clock).
The 30-minute run asks for 6 hours, far under that.

Update: `git -C /srv/cloudyoke/code pull`. The receiver isn't run on the server yet: it goes up once the
first station's firmware can send to it.
