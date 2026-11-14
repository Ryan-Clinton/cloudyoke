# Building a ring round your site

Most astronomers who build one station will want more: a ring of 5 to 10 stations, 10 to 15 km out, so cloud
is seen coming before it arrives. This is how to plan one. Parts and wiring are in
[hardware/build.md](../hardware/build.md); bulk prices are in [its last section](../hardware/build.md#buying-for-a-ring).

Whether a station upwind really gives warning is the network's main open question
([spec §9.1](spec.md#91-before-any-arrival-warning-is-shown)). A ring is how it gets answered at your site. Until
it is, the ring's first job is showing what each station's sky is doing now.

## The shape

- **One station at home, in the middle.** It's your sky, and every other station is compared with it.
- **The ring 10 to 15 km out.** Cloud moves at about 20 to 60 km/h, so a ring at 12 km gives roughly 12 to 35
  minutes' notice: enough to open the roof, start cooling a camera or decide not to bother.
- **Spacing.** At 12 km the ring is about 75 km round: 6 stations put one every 12 km, 8 every 9 km, 10 every
  7.5 km. Cloud cells are often smaller than the gaps between 6 stations; 8 is a good aim.
- **Weight it upwind.** Put more stations on the side your weather usually comes from (over Ireland and Britain,
  west and south-west), but keep at least one on every side. The wind changes, and the server works out upwind
  each night from the wind at cloud height, not from a fixed direction
  ([spec §1](spec.md#1-the-idea-in-one-paragraph)).
- **A second ring later.** If the first one works, a few stations at 30 to 40 km on the upwind side give an
  hour's notice.
- **Hills and coasts.** Cloud that forms over a hill or comes in off the sea gives no warning to a ring on the
  other side. A station on the hill or the coast shows it forming.

## Finding hosts

Each station needs a host with a view straight up, a socket (or sunshine) and, for the WiFi version, a signal
where the box goes. Places to ask:

- friends, family and other members of your astronomy club;
- farms (big clear skies, outbuildings with power) and sports clubs (pavilions, open ground);
- community halls, churches, schools and village shops with outdoor WiFi;
- businesses on industrial estates: flat roofs, outdoor sockets, and often a guest network.

What to tell a host:

- **What it is:** a small box that measures the sky's temperature to tell clear from cloud. No camera, no
  microphone, nothing that sees the ground.
- **What it needs:** a spot with open sky above, a socket within reach of a USB cable (or none, with the solar
  version), and their WiFi password, ideally for a guest network.
- **What it costs them:** about £1 a year of electricity on a charger, and 1 to 3 MB of data a day, under 100 MB
  a month, which no broadband plan notices.
- **Privacy:** the network shows their station by its town or area only, never an address or a house
  ([spec §6](spec.md#6-hosts-privacy)). The exact spot stays on the server.
- **Leaving:** they can ask for it to be removed at any time.

Put a label on every box: what it is, the project's web address and your phone number. A box nobody recognises
gets taken for a camera or a bomb.

## Where WiFi doesn't reach

In order of preference:

1. **The WiFi version with an external antenna** (the ESP32-WROOM-32U board and a 2.4 GHz antenna, a few pounds
   more). It reaches much further than the board's printed antenna, and is the first thing to try at the end of a
   garden or on a shed.
2. **The wired version:** an Ethernet board powered over the same cable (PoE), up to 100 m from the router or a
   switch. One cable carries power and data.
3. **A WiFi extender** in an outbuilding, if the host has one or wants one.
4. **The 4G version** (an ESP32 with a cellular modem, a solar panel and a battery) for a field or a hilltop with
   nothing nearby. It needs a data SIM, a pound or two a month, and its firmware comes after the others.

## Power without a socket

The solar version runs on one 18650 cell and a small panel. A low-power board asleep between readings uses about
20 mAh a day, so a full cell lasts around four months without any sun; the panel only keeps it topped up. Use a
2 W panel facing south, tilted steeply (about 60°) for the low winter sun, and mount it lower than the box or
far enough to the side that it stays out of the sensor's view (the 45° rule in the guide).

## Registering a ring

Each station is its own site, under its host's area name. Tell the maintainer the town or area of each, never an
address. Stations close together count towards the 0.05° cell rule, which lets their pages show finer squares.

## Looking after it

- Visit each box after its first week, then every few months: spiders, dew marks on the sensor, the BME280's shade.
- The server shows each station's last reading and its age, so a box that has gone quiet is easy to spot.
- Keep one spare built station, to swap in while a faulty one comes home for a look.
