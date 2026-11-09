# deploy/

How cloudyoke runs on the server behind ryanclinton.uk: its own user, `/srv/cloudyoke/code` (a clone of
this repository) and `/srv/cloudyoke/data`.

| Unit | Does |
|---|---|
| `cloudyoke-metar.service` + `.timer` | Every 30 minutes, keeps City of Derry's airport reports (`server/metar.py`) |

Set up once, as root:

```
useradd --system --home /srv/cloudyoke --shell /usr/sbin/nologin cloudyoke
git clone https://github.com/Ryan-Clinton/cloudyoke.git /srv/cloudyoke/code
install -d -o cloudyoke -g cloudyoke /srv/cloudyoke/data
cp /srv/cloudyoke/code/deploy/cloudyoke-metar.* /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now cloudyoke-metar.timer
sudo -u cloudyoke python3 /srv/cloudyoke/code/server/metar.py --data /srv/cloudyoke/data --ids EGAE --hours 360
```

Update: `git -C /srv/cloudyoke/code pull`. The receiver isn't run on the server yet: it goes up once the
first station's firmware can send to it.
