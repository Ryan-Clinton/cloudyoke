# cloudyoke specification

The design of the network: the station, how cloud is judged, where readings go,
hosts' privacy, the stages and their gates, and the sources. Written 9 November
2026; nothing is built yet. The sensor idea comes from the cloud sensor plan in
telescopeyoke, the telescope project cloudyoke grew out of; this document is
about the network.

Every fact below has its source in section 11. Lines marked "estimate" are
arithmetic, not measurements.

## 1. The idea in one paragraph

A small box on a wall or shed looks straight up all night and measures the sky's
temperature in infrared. A clear sky reads far colder than the air; cloud reads
close to the air's temperature. One box tells its owner whether their own sky is
clear right now, measured rather than forecast. Many boxes, sending a reading a
minute to ryanclinton.uk, make a live map of where it is clear. Because most of
our weather arrives from the west and south-west, boxes 30 to 80 km upwind
might show cloud coming before it gets here: that is the ambition, and it is
unproven.

### 1.1 Three different claims

A sensor measures the infrared from a wide cone of sky. It doesn't see a single
cloud, its height, its direction or its speed, and different layers can move in
different directions while gaps open and close in place. So the network makes
three separate claims, each only after the one before is shown to work:

| Claim | What it means | When it can be made |
|---|---|---|
| **Detection** | this box's sky is clear, partly cloudy or cloudy, now | after stage 1's pass (section 9) |
| **Agreement** | boxes near each other agree, and a change at one box is followed by the same change at the next one downwind | after stages 2 and 3 have a season of data |
| **Arrival warning** | "cloud likely here in about N minutes", with how often that has been right | experimental; only once the criteria in section 9.1 are met |

The map shows what was measured: each box's state and how old its last reading
is. It never fills the space between boxes as if it were a radar picture.

## 2. Why it doesn't exist already

As far as the research found (section 11.1), every infrared cloud sensor in use
is on its own: observatory roof-closers, AAG CloudWatchers and SkyAlerts that
share only on their owner's network, single DIY builds, one public ThingSpeak
channel. Steve Marple at Lancaster proposed "an open-access cloud-detection
network" with the same sensor in May 2013 and wrote "I am not aware of any
existing cloud detection networks"; his prototype ran for over a year, but no
shared map followed. Meteor camera networks (GMN, UKMON, AllSky7) label a camera
"cloudy" at most and publish no cloud data. Absence can't be proved, so the page
says "we couldn't find one", not "the first".

What has changed since 2013: ESP32 boards at about £3 with WiFi built in,
firmware that installs from a web page, and a server (the server) already
running the site's scheduled jobs.

## 3. The unit

Fixed, pointing straight up, on WiFi. Telescopeyoke's telescope-mounted sensor
moves and looks along the tube, so its readings can't be compared with a fixed
unit's: it is never a network unit and never sends here. No telescopeyoke code
is used by the network.

| Part | Job | AliExpress | UK, solder-free |
|---|---|---|---|
| ESP32 board | reads the sensors, sends over WiFi | about £3 (DevKit) | £9 (M5Stack AtomS3 Lite, native USB, Grove port) |
| MLX90614, 90° (BAA) | sky temperature | about £2 to £6 (GY-906) | £18.60 (M5Stack NCIR unit) |
| BME280 | air temperature, humidity, so the dew point | about £1 to £4 | £7.50 to £14.40 (Pimoroni or Adafruit, STEMMA QT) |
| Leads | | jumper wires | £3.80 (two Grove to STEMMA QT) |
| Box | weatherproof case | about £4 (IP65 100 × 100 × 50 mm) | the same |
| USB supply, 1 A | power | one in a drawer, or about £5 | the same |
| **Total (estimate)** | | **about £15 to £20** | **about £50 to £60** |

Running cost (estimate): about 0.2 to 0.5 W at the plug, a few kWh and about £1 a
year, before any heater.

Things the research turned up that the build guide must say:

- **The variant matters.** Many GY-906 listings bundle BAA, BCC and DCI under one
  title. Only the BAA (90°) suits a zenith sensor. The marking is on the can; the
  firmware can't tell. Ryan's own two (ordered 9 Nov) should be checked when they
  arrive.
- **Fake BME280s are common:** many are BMP280s with no humidity sensor. The
  firmware reads the chip ID (0x60 is a BME280, 0x58 a BMP280) and the unit
  reports which it has; a BMP280 unit still works but can't give the dew point.
- **The BME280 goes outside the box,** in a vented shade, or it measures the box.
- **Dew and rain on the sensor's face are the main source of error.** Two ways to
  try on the first unit: the sensor open to the sky under a short hood (as
  telescopeyoke's sensor plan has it), or behind thin polyethylene film (plastic films under
  0.25 mm pass most of 8 to 14 µm; one Cloudy Nights builder got clear readings
  about 30 °C below the air through cling film, though some cling film is PVC).
  Germanium windows cost £470 and up, so they're out. A 1 W heater resistor
  near the can, switched on near the dew point, is the fallback, with its own
  risk: Melexis warns that heat sources nearby and uneven temperature across the
  package shift the reading. Which arrangement goes in the guide is decided by
  the test in section 9.2, not now.
- **The view must be clear in a wide cone.** At 90° the sensor sees anything
  within 45° of straight up, so a roof edge, wall, tree or a hood that is too
  deep reads as warm sky. The guide gives the rule: nothing may rise above the
  box by more than its distance from the box (that keeps it below 45°
  elevation, outside the cone), and the hood stops short of the cone too. The
  install check is in section 5.4.
- **Power:** a 1 A supply, because WiFi transmit peaks reach about 260 mA.
- **The ESP32 is rated to −40 °C;** cold is not the problem, damp is.

### 3.1 Existing sensors

The ESP32 station is the project's reference design, not a condition of
joining. Many observatories already run cloud sensors that are installed,
powered and logging: the Lunatico AAG CloudWatcher and the Boltwood Cloud
Sensor among them. Their owners can send to the network without replacing
anything, through a small program on their own PC or Raspberry Pi: a
**bridge**. No bridge exists yet; the first is being designed, and is not
called working until it has run against a real sensor at a volunteer's
observatory for a few weeks.

#### 3.1.1 Two ways to reach an ASCOM sensor

ASCOM's ObservingConditions interface has properties for sky temperature,
air temperature, humidity and cloud cover. It reaches a program in two ways,
and an installed ASCOM driver does not by itself give the second:

- **Alpaca:** the device or its software serves the interface over HTTP. The
  bridge reads it directly, on the same machine or the local network.
- **A classic Windows COM driver:** the interface exists only inside Windows.
  To reach it over HTTP, the owner runs ASCOM Remote (part of the ASCOM
  project) on the observatory PC, set to listen on that machine only, and the
  bridge reads that. This is documented in the bridge's guide but supported
  only once a tester with a COM-only setup needs it.

INDI (the AAG's `indi_aagcloudwatcher_ng`) and the Boltwood one-line data file
are later bridges, built when an owner wants one and can test it.

#### 3.1.2 What a bridge may and may not do

A bridge sits next to equipment that may close an observatory roof, so its
limits are a contract, enforced in its code and tested:

- **It only reads,** from an allowlist: the ObservingConditions properties in
  3.1.3, `TimeSinceLastUpdate` for each, `Connected` (read, never written),
  and `Name`, `Description`, `DriverInfo`, `DriverVersion` and
  `InterfaceVersion`. Over Alpaca that means GET requests to those endpoints
  and nothing else.
- **It never writes.** No PUT of any kind: it never sets `Connected`,
  `AveragePeriod` or any other property, never calls `Refresh`, `Action`,
  `CommandBlind`, `CommandBool` or `CommandString`, and never connects or
  disconnects the device. If the device isn't connected (because the
  observatory's own software isn't running), the bridge reports the station
  offline and waits.
- **It is gentle.** At most one request at a time, one full read a minute, a
  5-second timeout on each request, and backing off to every 10 minutes after
  repeated failures.
- **It is not a safety device.** The network's readings are never fed back
  into an observatory's safety monitor or roof control. That would need its
  own design and the owner's explicit choice, and is out of scope.
- **Outgoing only.** It makes HTTPS connections out to the network and opens
  no ports; nothing on the internet can reach the observatory through it.

#### 3.1.3 What a station can do: capabilities, not kinds

Sensors report different things, and some report a judgement rather than a
measurement. Each station declares, at registration and in every reading,
which of these it supplies:

| Capability | Reference station | A third-party sensor, if its driver gives it |
|---|---|---|
| `sky_temperature` | always, raw | `SkyTemperature` |
| `air_temperature` | always | `Temperature` |
| `humidity` | with a BME280 | `Humidity` |
| `maker_cloud_cover` | never | `CloudCover`, from the maker's own thresholds |

The bridge works out the list by trying each property once at start-up and
again every hour: one that answers "not implemented" (ASCOM's
PropertyNotImplementedException, Alpaca error 0x400) is simply left out, and
the others carry on. A missing humidity never takes a station offline.

What follows from the list:

- **The network judges a station itself** only when it supplies sky and air
  temperature and their processing is known (3.1.4). Its judgement uses the
  method in section 4.
- **The maker's verdict is always kept beside it,** with its origin, when the
  station gives one. It is never treated as a measured fraction of the sky (a
  Boltwood's cloud cover, for instance, comes from thresholds its owner set),
  never compared with raw readings as if alike, and never used to tune the
  network's own method. Having both is useful: the network's judgement can be
  checked against the maker's on the same sky.
- **A station that supplies only the maker's verdict** is shown with that
  verdict, labelled as the maker's.

#### 3.1.4 Provenance

A driver's sky temperature may be raw, corrected, filtered or averaged, and
the ASCOM property alone doesn't say which. So each station's setup row
(section 5.1) records the device model, the driver's name and version (read
from `DriverInfo` and `DriverVersion`), and, for each capability, what is known
of its processing: `raw`, `corrected` (with the method, if the maker documents
it), `averaged` (with the period), or `unknown`. A reading carries the same
`processing` field.

The network's calibration is applied only to sky temperatures known to be raw.
Values whose processing is `corrected`, `averaged` or `unknown` are stored and
shown as the station's own figures, but not judged by the network until their
processing is established, by the maker's documentation or by comparison with
a reference station nearby.

#### 3.1.5 Age and staleness

A driver can return the same value for many minutes while its sensor is
stuck. So each value in a bridge's reading carries its age in seconds, from
`TimeSinceLastUpdate` where the driver implements it, or `null` where it
doesn't. The reading's own time `t` is when the bridge read the driver.

- A value more than 5 minutes old, by its age, is not current.
- A station whose values have no age at all is shown as current only while
  they keep changing; ten identical readings in a row mark it stale.
- A driver that errors, times out or is disconnected produces a reading with
  no values and the flag `source_offline`, and the station shows as offline,
  never as its last known state.

## 4. Telling clear from cloud

The unit sends raw numbers (sky temperature, air temperature, humidity); the
server decides what they mean, so the method can improve without anyone
reflashing.

- **The correction.** The CloudWatcher's formula (Lunatico's manual) removes the
  part of the sky reading that comes from the air's own temperature. Its default
  is linear (K1 = 33, the rest 0); Lunatico ships a tool to fit K1 to K7 per site,
  which says what matters here: there is no universal clear-sky number.
- **Each unit learns its own clear sky.** Clear-sky gaps reported by builders
  range from about 20 °C to over 35 °C below the air, and humidity moves them.
  So the server learns each unit's clear baseline from its own corrected
  readings, and "cloudy" is measured up from that. No published method does
  exactly this (the nearest peer-reviewed one, NSKY-CD 2023, sets thresholds
  statistically from the readings' own distribution, which is the same idea), so
  it is an experiment, tested on the first units before the page claims it works.
  The safeguards, all in the server's code and tested:
  - **A low percentile, not the minimum.** The baseline is the 5th percentile of
    the corrected night-time readings in a rolling 30 nights, so one freak cold
    reading doesn't move it.
  - **Enough clear sky first.** A baseline counts only once the unit has at
    least 10 nights with at least 2 hours each, and its night readings spread
    widely (the gap between its 5th and 95th percentiles at least 10 °C). A
    month of overcast gives a narrow spread, so the unit stays unlearned rather
    than taking grey cloud for clear.
  - **Bad readings left out.** Readings flagged by the unit (section 5.2),
    readings while the sensor's face is wet or within 1 °C of the dew point,
    sky readings warmer than the air by more than 2 °C (a fault or something
    warm in view), and readings during the heater's first 10 minutes on.
  - **A drifting baseline is noticed.** If it moves more than 3 °C in a week,
    the unit drops back to "learning" and the host gets one email.
  - **States:** clear, some cloud, cloudy, wet, learning, fault, no reading. Only
    a learned unit with a fresh, unflagged reading can be clear. Learning, fault
    and no reading are never shown as clear, on the map or in the data.
- **Checking against the sky.** No one reference is right for astronomy:
  - **The person under it.** Notes of what the sky is doing, with the time, as
    telescopeyoke's sensor plan already asks. At
    stage 1 that is Ryan; later, any host who wants to.
  - **Timed sky photos.** A phone or camera pointed straight up, a few seconds'
    exposure, with the time: stars or no stars is a clear answer for thin cloud.
  - **Telescopeyoke's frames, once, by hand.** Star counts from Ryan's nights
    compared with the sensor's log during stage 1. That is an analysis done
    once, not a feed: the network never reads telescopeyoke.
  - **Airports.** METARs every 30 minutes, free from aviationweather.gov.
    Useful near Derry (EGAE), Dublin, Shannon and Cork, which are staffed. Two
    codes don't mean a clear sky: NCD (the ceilometer saw nothing directly
    overhead; Belfast International and Belfast City report "AUTO NCD" at night)
    and NSC (no cloud that matters to aviation, which can still be cloud that
    matters to a camera). Neither is counted as clear, and nor is CAVOK.
    **Derry reports in the day and evening, not all night.** Its 400 reports
    from 27 October to 9 November 2026 ran from about 05:00 to 22:00 UTC, with
    5 between 22:00 and 05:00. So it checks a station's evening and dawn, not
    the middle of the night; the hours it is silent stay silent, never filled
    in. The airports are kept as reference sources (section 5.6).
- **Thin high cloud is where the sensor earns its place.** Satellite cloud masks
  at night miss thin cirrus and raise false alarms on 8 to 20% of clear pixels;
  thin cirrus is also what spoils astrophotography frames. The sensor sees some
  of it but not all (Kitt Peak notes its own misses cirrus), and the page says so.

## 5. Where the readings go

On the server behind ryanclinton.uk.

### 5.1 Registering a unit

- A host registers on the site and gets a unit id (`cy-0001`) and a secret key,
  shown once. The installer page (stage 4) writes both into the unit over the
  USB cable, with the WiFi details; until then Ryan does it by hand.
- Registration records the setup, because different setups read differently
  (for a bridged sensor, also its device model, driver name and version, and
  each capability's processing, section 3.1.4):
  sensor variant (BAA, read off the can), BME280 or BMP280, board, hardware
  revision, hood, film or open, heater or none, mounting (wall, pole, shed
  roof), and the height above ground. A change of any of these is a new setup
  row with its date, so readings are always judged against the setup they were
  taken with.
- **Revoking.** Ryan can revoke a key; the server answers 401 and keeps
  nothing. A lost or stolen unit is revoked and a new key issued.
- **Replacing.** A replacement board keeps the unit id (the place's history
  carries on) with a new key and a new setup row; readings from the old key
  after that are refused.

### 5.2 One reading

Each unit POSTs JSON to `ryanclinton.uk/cloudyoke/send` over HTTPS. The key goes
in the `Authorization: Bearer` header, never in the body, so a body saved while
debugging never holds it; nginx's access log doesn't record that header. nginx
rate-limits the route, as it does `/forms/send`.

```json
{"schema": 1, "unit": "cy-0001", "hw": "esp32-devkit/bme280/baa/r1", "fw": "0.1.0",
 "boot": 7, "seq": 40213, "t": "2026-11-20T23:14:00Z", "t_ok": true,
 "readings": {"sky_c": -18.4, "air_c": 6.1, "humidity": 81, "pressure_hpa": 1012.3},
 "flags": [], "rssi": -71, "uptime_s": 40213}
```

- **Required:** `schema`, `unit`, `fw`, `boot`, `seq`, `t`, `t_ok`, `readings.sky_c`,
  `readings.air_c`. **Optional:** everything else; a unit without humidity
  (a BMP280) leaves it out, never sends 0.
- **Station types and capabilities.** Every reading says what sent it and
  what it carries, and the server checks the rest against that:
  - `"source"`: `"cloudyoke-esp32"` for a reference station, or the bridge's
    kind (`"ascom-alpaca"`, later `"indi"`, `"boltwood-file"`).
  - `"capabilities"`: the list from section 3.1.3.
  - each value in `readings` is required if its capability is declared and
    absent otherwise; a reference station always declares `sky_temperature`
    and `air_temperature`.
  - from a bridge, each value is an object, `{"value": -18.4, "age_s": 42,
    "processing": "raw"}` (section 3.1.4 and 3.1.5); a reference station sends
    plain numbers, which are raw and fresh by definition.
  - `"maker"`: `{"cloud_cover": 50, "age_s": 30, "by": "Boltwood III"}`, only if
    `maker_cloud_cover` is declared.
  - the machine-readable version is `schemas/reading.schema.json`, and the
    server validates every reading against it; examples in `schemas/examples/`
    are checked by `schemas/check.py`.
- **Restarts and order, for a bridge.** A bridge keeps its `boot` counter in a
  small file beside it, adds one on every start (including after a crash, so a
  crash can never reuse numbers), and counts `seq` from 1 within each run, as a
  reference station does. A reinstall that loses the file is registered as a
  replacement (section 5.1), so the server never confuses old and new numbers.
- **Times.** `t` is when the unit took the reading, from NTP. `t_ok` is false
  until the clock has synced since boot; such readings are stored but never
  judged. The server adds its own receipt time on arrival.
- **Order and duplicates.** `boot` counts restarts (kept in flash), `seq`
  counts readings since boot. The server keeps one reading per (unit, boot,
  seq): a repeat is answered 200 and dropped, so a unit can resend safely.
- **Flags:** `sensor_read_failed`, `sky_out_of_range` (outside −70 to +60 °C),
  `air_out_of_range`, `wet`, `heater_on`, `bmp280` (no humidity), `brownout`, and, from a
  bridge, `source_offline` (the driver errored, timed out or isn't connected; no values are sent).
  Flagged readings are kept but never judged clear.
- **When WiFi drops.** The unit keeps up to 6 hours of readings (360, a few
  KB) in memory and sends them oldest first with their own `t` once it's back,
  several to a POST. The server files each under its own time, so old readings
  never stand in for "now": a state is shown as current only if its reading is
  under 3 minutes old.

### 5.3 Storing and judging

- **Storing.** A small standard-library Python service checks
  each POST, puts the readings on a bounded queue (dropped with a 503 if full,
  so the unit retries later) and a single writer appends them to one file per
  unit per day, flushed every few seconds; finished days are gzipped by a
  timer. Size, estimated: about 1,440 readings a unit a day, about 150 KB, so
  about 55 MB a unit a year before gzip. Raw readings are kept indefinitely,
  states and baselines are recomputable from them, and the folder is in the
  server's backup.
- **Judging.** A timer works out each unit's baseline and state every few
  minutes, from the files, and fetches METARs for the check.
- **How many units the server takes is not claimed** until a load test with
  simulated units (say 100, 1,000 and 5,000 posting once a minute, with
  reconnect bursts) has been run on the server. If it falls short, the first
  steps are readings every 2 minutes, or several per POST, not a new system.

### 5.3.1 Reference sources: airport reports

Airport weather reports (METARs) are collected alongside the stations from the
start as a check on the stations (section 4): City of Derry (EGAE), Belfast
International (EGAA), Belfast City (EGAC) and Prestwick (EGPK) since 10
November 2026. The two Belfast airports report AUTO NCD at night, kept as NCD. A
reference source is not a station: it is never on the map as one, never
judged, and is stored apart, in `data/reference/<ICAO>/<UTC date>.jsonl`.

- **Fetched every 30 minutes** from the Aviation Weather Center's free JSON
  API (`server/metar.py`). One request returns at most 400 reports, about 13
  days at Derry, so history not collected in time is lost.
- **Each report is kept once,** by its observation time and raw text, so a
  correction (COR) is kept beside the original. The time kept is the API's
  `obsTime`, the real observation time; its `reportTime` is rounded (the 22:50
  report is labelled 23:00).
- **The raw report is always kept,** with the decoded values as the report
  states them: the overall code, each layer's cover and base, vertical
  visibility, visibility (from the API's statute miles, with "or more" kept),
  weather such as fog, temperature, dew point, wind and pressure.
- **Nothing is turned into clear or cloudy.** CAVOK, NSC, NCD, CLR, SKC and
  the API's OVX (sky hidden, as by fog) are kept as given. The code is read from
  the report's own text, not the API's `cover` field, which rewrites NCD as
  CLR (seen on Belfast International's and Belfast City's AUTO reports, 9
  November 2026); the API's version is kept beside it as `api_cover`.
- **Graphs:** `server/metar_graph.py` draws an airport's days (layers by
  height, the codes, fog, visibility, and closed hours left blank), and
  `server/night_graph.py --reference EGAE` lines the airport's reports up
  under a station's night, for the comparison stage 1 needs (section 9.2).

**Met Éireann's ceilometers** (since 10 November 2026): Malin Head (about 70
km north-west, upwind in the usual weather), Finner and Belmullet, from Met
Éireann's open-data EDR API (`server/met_eireann.py`, CC BY 4.0, "Contains Met
Éireann data"). Each reading gives up to five cloud layers with base in feet and
cover in oktas, 9 meaning the sky is hidden. The service is marked
experimental: it keeps about 26 hours, runs about an hour behind, and answers
at most 154 readings a request, so it is fetched in 30-minute steps every 30
minutes, every 15-second reading kept. Each fetch reaches back to the newest
reading already stored, up to 26 hours: on 10 to 11 November the feed published
nothing after 14:30 for almost a day, then the whole backlog at once, and a
fixed 3-hour window missed it (recovered by hand; `docs/nights/2026-11-10.md`
compares that night's sources with a telescope's view). Like the airports' ceilometers it
sees only straight up, so nothing it reports is turned into "clear".

**The reference dashboard** (`server/dashboard.py`, ryanclinton.uk/cloudyoke/live/),
rebuilt after each collection: every source's distance and direction from
Ballymoney, its latest report as reported and how old it is, and the last 24
hours side by side, west to east, shaded by reported cover with a mark for
ceilometer layers at 16,000 ft or higher. A source past its expected interval
(90 minutes for an airport, 3 hours for a ceilometer) is shown stale and listed
in `status.json`, so one that stops is seen, not silently missing. Labelled
observations, not predictions.

**Looked for and not found** (10 November 2026): the Wild Geese / Skydive
Ireland airfield at Movenis, near Garvagh, publishes no METAR, weather station
or webcam; Armagh Observatory's live weather pages show no cloud sensor; the
only other aviation station nearby is Campbeltown (EGEC). Public infrared
sky-temperature feeds exist (a ThingSpeak channel at a star party in Gujarat,
India) but none near Ireland was found.

### 5.3.2 Joined sites: the satellite, scored on the ground

A place can join before it has a sensor (14 November 2026, [join.md](join.md)).
Every 10 minutes `server/satellite.py` judges each joined site from Meteosat's
10.5 µm infrared picture, with telescopeyoke's method: the site's brightness
against the darkest tenth of a box 3.4° of latitude by 7.4° of longitude round
it. More than 20 brighter is "cloud", under 10 "probably clear", and between is
"thin or broken cloud". The site is judged at its 0.05° cell's centre only
(section 6). The verdict is a reference, never a station's state: it is
uncalibrated and the picture is kilometres across. What people at the site saw
(`server/seen.py`: clear, partly or cloudy, from when to when, by a host's eye,
an imager's frames or a station) scores it. The joined sites' page shows each
site by its area's name, its verdicts and its score. A site that later gets a
station keeps its history, so the satellite's score there becomes a check on
the station as well.

### 5.4 The install check

When a unit is first up, the site shows its first night's readings beside the
nearest staffed airport's and asks the host for one photo straight up from
beside the box by day. A sky reading that never gets colder than about 10 °C
below the air on a night the airport calls clear, or the photo showing a roof
edge or branch inside the cone, puts the unit in "fault: check the view".

### 5.5 Showing and giving away

- **Showing.** The network's page (section 7) and later Meanwhile's "clear here
  now" beside the forecast. Each unit shows its state and its last reading's
  age; nothing is drawn between units.
- **Giving it away.** Every day's readings downloadable as CSV, with the unit's
  published cell (section 6) and nothing finer.
- **The licence is decided before anyone but Ryan sends data.** Proposed: **CC
  BY 4.0** (credit the network; commercial use allowed), as STARS4ALL's
  sky-brightness data uses. The alternative is Blitzortung's model (raw data
  only for contributors, no commercial use), which gives hosts a reason to join
  but stops a farmer or a council using it. Not yet decided. Whatever it is, hosts
  agree to it when they register, before their first reading, and keep the
  right to stop and have their unit's future readings stop being published.
  Until he decides, the proposal page says "open data" and nothing narrower.

## 6. Hosts' privacy

- A host gives a town or village and a postcode district, never an address.
- The server keeps the position the host gave privately, and publishes only a
  cell: the 0.05° square it falls in (about 5 km by 3 km here), which is still
  fine for warnings at 30 to 80 km. In a small village with one unit a 0.05°
  cell can still point at a house, so a cell is published only when it holds
  at least 3 units, or covers a town of at least 1,000 people; otherwise the
  unit is shown at the 0.2° cell (about 20 km by 13 km) or just by its area's
  name. Others do similar: RIPE Atlas rounds to about 1 km, Raspberry Shake
  moves each station up to a mile at random, Tempest blurs locations for the
  public.
- The CSV, the map and the page's code all use the published cell only; the
  private position never leaves the server.
- Names are shown only if the host asks; the default is the town.
- Sign-up emails are kept on the server, read over ssh, used only to reply,
  and deleted on request. The page says so in one sentence.
- This matches spec section 11: the town is fine, a house is not.

## 7. The public page

The project's public page is https://ryanclinton.uk/cloudyoke/. It introduces
the project, shows its status, and links here for development. Its own layout
and wording rules live with the site's code.

## 8. Hosting interest

People who would host a station but don't use GitHub can leave an email and a
general area through a small form on the public page. Developers and builders
come here instead.

## 9. Stages

| Stage | What | Shows the world | Gate to the next stage |
|---|---|---|---|
| 0 | Proposal page and sign-up | the idea, the cost, a form | none: it can go up now |
| 1 | Ryan's first fixed unit, in Ballymoney | its readings, its state, and the reference checks | stage 1's pass (9.2) |
| 2 | A friend's unit in the same town | two sensors close together should agree; a disagreement is a fault (dew, power, a bird) | the licence decided (5.5); the two agree on at least 90% of judged readings over 4 weeks |
| 3 | Upwind hosts: the north-west coast, near City of Derry Airport, mid Ulster | each box's state, and how changes at one line up with the next in time | none for showing states; arrival warnings only after 9.1 |
| 4 | Open doors: build guide, web installer (ESP Web Tools: plug in, click Install, give the WiFi over the same cable), parts lists by country | anyone can add a unit | the hardware and self-calibration have passed on at least 3 units in different places, and the load test (5.3) is done |
| 5 | Regions run themselves: a group (a society, a county) looks after its own hosts, the server stays one | the map past Ireland | an aspiration, not a plan |

The page at stage 0 promises only stage 1. Stages 2 to 5 are "what I hope".

**A second track, alongside stages 1 to 3: existing sensors (section 3.1).**

| Step | What | Gate |
|---|---|---|
| E1 | The reading format takes bridges: capabilities, provenance, ages, restarts (sections 3.1 and 5.2, `schemas/reading.schema.json`) | done in the design; the ingest service validates against the schema |
| E2 | One ASCOM Alpaca bridge, keeping to the contract in 3.1.2, run against a volunteer's real sensor for a few weeks | its capabilities are found correctly, unimplemented properties are skipped, values carry ages, errors and reconnects are recorded, and a driver failure shows as offline, never as the last known state |
| E3 | A short install guide for that bridge | someone other than its author installs it from the guide alone |

Existing sensors may give the network spread-out readings sooner than new
stations would, but only if owners take part; nothing is assumed about how
many will. Further bridges (INDI, the Boltwood file) come only when an owner
asks for one and can test it.

### 9.1 Before any arrival warning is shown

An arrival warning is a prediction, so it has to have been tested before it is
shown, and shown with its record:

- **The test.** For every change from clear to cloudy at a downwind box, look
  back at the boxes upwind (by that night's wind at cloud height, from the
  forecast models Meanwhile already fetches) and see whether one changed first,
  and by how long.
- **The bar.** Over at least one autumn-to-spring season with at least 30 such
  events: the warning time predicted from distance and wind falls within ±30
  minutes of what happened in at least 60% of them, and false warnings (an
  upwind change that never arrives) are counted and published alongside.
- **What is shown if it passes.** "Cloud likely here in about 1 hour; this kind
  of warning has been right 7 times in 10 this season", never a bare time. If
  it fails, the network still does detection and agreement, and the page says
  the warnings didn't work.

### 9.2 Stage 1's pass

Stage 1 isn't done when the unit posts temperatures: it is done when all of
these are shown, over at least 4 weeks including some damp nights:

- **It tells clear from cloudy, checked independently.** On nights with a
  reference (Ryan's notes, a timed straight-up photo, or Derry's staffed
  METAR, with NCD and NSC not counted), its state agrees with the reference at
  least 85% of the time, judged hour by hour.
- **The self-learned baseline settles** (section 4) without hand-set numbers,
  and doesn't drift more than 3 °C in a week once learned.
- **It flags its own bad readings.** A wet or faulty sensor shows as wet or
  fault, never as clear: checked by wetting the face and by unplugging the
  sensor on purpose.
- **It survives outside:** 4 weeks on the wall with no hand fixes, and it
  recovers by itself from a WiFi or power cut, sending the readings it kept.
- **The dew test (below) has picked an arrangement.**

**The dew test.** The arrangements (open under a hood, behind thin PE film,
and either with a heater) are compared on dry clear nights, humid clear
nights, after rain, and on nights when the temperature falls fast. Best done
with two sensors side by side on the wall, one open and one with film, so they
see the same sky at the same time; on alternate nights if only one is free,
which is weaker because no two nights are the same. Each is scored on: the gap
between clear and overcast readings, how often dew or rain made a reading
unusable, how quickly it recovers after rain, and, for the heater, how far the
reading moves in the minutes after it switches on. The guide takes the
arrangement with the fewest unusable hours that keeps the clear-to-overcast
gap within 3 °C of the open sensor's.

## 10. What could stop it spreading

- **Support load on one person.** Blitzortung and sensor.community grew because
  the design was open and groups ran workshops; the guide and installer must
  answer the common questions (charge-only USB cables, Windows drivers, the BOOT
  button; boards with native USB avoid two of the three).
- **The self-calibration not working.** If each unit needs hand-set thresholds,
  strangers won't manage it. Stage 1 tests this before stage 4.
- **Hosts drifting away.** Units that stop sending are marked, and the host gets
  one email.
- **The server's capacity.** Not yet known: the load test in section 5.3 comes
  before stage 4 opens the doors.
- **The arrival warnings not working.** Sparse boxes with wide views may not
  time cloud well enough. If section 9.1's bar isn't met, the network is still
  a measured "clear here now" map, and that is what the stage 0 page promises.

## 11. Sources

### 11.1 Existing networks
- Steve Marple, "An open-access cloud-detection network" (May 2013) and progress
  review (Oct 2013): blog.stevemarple.co.uk/2013/05/an-open-access-cloud-detection-network.html,
  blog.stevemarple.co.uk/2013/10/cloud-detector-review-of-progress-so-far.html
- AAG CloudWatcher sharing (LAN only): lunaticoastro.com/aag-cloud-watcher/;
  cloudynights.com/forums/topic/524738-weather-sensorsroof-closers/
- Single DIY sensors: github.com/dokeeffe/cloud-rain-monitor (Ballyhoura
  Observatory); thingspeak.mathworks.com/channels/111706
- Professional single sites: arxiv.org/pdf/2004.12128 (Lijiang);
  rct.wku.edu/kittpeak/Devices/cloud.html (Kitt Peak, misses cirrus)
- NSKY-CD, Remote Sensing 15(12):3063, 2023: doi.org/10.3390/rs15123063
- Global Meteor Network: arxiv.org/abs/2107.12335
- Blitzortung: en.wikipedia.org/wiki/Blitzortung; blitzortung.org/en/compendium.php
- sensor.community: hackaday.com/2017/04/08/getting-a-measure-on-particulates-in-stuttgart;
  zenodo.org/communities/cs-sensor-community/about
- STARS4ALL TESS: guaix.fis.ucm.es/tess/
- Met Office WOW retiring in 2026: weather.metoffice.gov.uk (Met Office for Schools, "Are you obsessed with the weather")
- Location blurring: community.raspberryshake.org/t/long-lat-question/449;
  lists.ripe.net (mat-wg, May 2011); community.tempest.earth/t/station-privacy-and-pii-concerns/175

### 11.2 Parts and build
- Prices (9 Nov 2026): aliexpress.com search pages for ESP32 DevKit, GY-906, BME280;
  thepihut.com (AtomS3 Lite, NCIR unit, Adafruit BME280, Grove to STEMMA QT cable);
  shop.pimoroni.com/products/bme280-breakout; wmestore.co.uk (Haydon IP65 box)
- MLX90614 datasheet (variants, ±0.5 °C): melexis.com
- BME280 vs BMP280 chip ID: jmargolin.com/newprojects/mytx4/difference_bme-280_bmp280.htm
- Plastic film at 8 to 14 µm: Optris/Micro-Epsilon datasheet on globalspec;
  US patent 6441956; cloudynights.com/forums/topic/810945-a-raspberry-pi-cloud-and-rain-sensor/
- Germanium window prices: edmundoptics.co.uk
- ESP Web Tools and Improv: esphome.github.io/esp-web-tools/
- ESP32 power: docs.espressif.com (low-power mode, WiFi); ESP32-WROOM-32E datasheet (−40 to 85 °C)

### 11.3 Weather and calibration
- Prevailing wind between south and west (Met Éireann text): discoveringireland.com/wind-over-ireland
- Fronts form over the Atlantic and move west to east: metoffice.gov.uk/blog/2025/what-are-weather-fronts
- Front speeds (warm 16 to 40 km/h, cold 40 to 48 km/h): atmos.northernvermont.edu (MET130 notes)
- Radiation fog forms in place: avmet.navcanada.ca/en/radiation-fog.aspx
- CloudWatcher correction and K-factor tool: lunaticoastro.com/aagcw/enhelp/topics/idh-topic180.htm;
  lunaticoastro.com/cloudwatcher-k-factor-optimisation-tool/
- METAR every 30 minutes (CAA CAP 746); free API: aviationweather.gov/data/api/
- NCD means nothing seen overhead, not clear: aviation.govt.nz automatic weather stations PDF
- NSC means no cloud of operational significance to aviation: CAA CAP 746 (METAR codes)
- Heat sources and package temperature gradients shift MLX90614 readings: Melexis MLX90614 datasheet
- Night cloud mask false alarms: arxiv.org/pdf/1204.5065
- Frost and overcast skies: search.library.wisc.edu (frost protection text);
  road weather 1 to 3 h cloud forecasts: sirwec.org (Bingen)
- Aurora dark-sky nowcasting: aurora.unis.no/doc/BACC.pdf

Not found, so not claimed anywhere: an official share of westerly winds; how much
night cloud arrives on the wind versus forms in place; a published self-calibration
from each night's coldest readings; a measured PE-film transmission for a household
bag; whether meteor networks want a cloud feed.
