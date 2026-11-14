# Building a station

A first version, to be refined after the first station's tests (dew, hood or film: [issue 2](https://github.com/Ryan-Clinton/cloudyoke/issues/2)).
**The firmware isn't written yet** ([issue 3](https://github.com/Ryan-Clinton/cloudyoke/issues/3)), so a station
can be bought and built now and flashed when it is ready. Questions go in
[Discussions](https://github.com/Ryan-Clinton/cloudyoke/discussions/9). Planning several stations round your site:
[docs/ring.md](../docs/ring.md).

Prices were read from the shops' own pages on 14 November 2026, in GBP with VAT, one listing per part
([prices-2026-11-14.json](prices-2026-11-14.json) has every listing). They change daily on AliExpress. AliExpress
delivery is £1.99 an item, free once an order reaches £8, so order a station's parts together.

## Choose your version

Three choices, mixed freely:

| Choice | Options |
|---|---|
| **Connection** | **WiFi** (the usual one), **wired Ethernet** (where WiFi doesn't reach; power and data on one cable) or **4G** (no internet nearby; a data SIM) |
| **Power** | **Phone charger** (a socket within reach of a USB cable) or **solar panel and battery** (no socket) |
| **Assembly** | **Soldered** (cheapest: eight pins to solder) or **solder-free** (modules with pins fitted, push-on wires) |

| Version | Parts, one station | Each, buying 10 | Notes |
|---|---|---|---|
| WiFi, charger, soldered (AliExpress) | **about £24** | **about £21** | The standard build |
| WiFi, charger, solder-free (Amazon UK) | about £55 | about £34 | Pre-soldered modules, next-day delivery |
| WiFi, charger, solder-free (UK shops, M5Stack) | about £48 | about £48 | Plug-together cables, no loose wires |
| WiFi, solar, soldered | about £38 (LOLIN D32) to £45 (FireBeetle) | about £35 to £42 | Low-power board, 18650 cell, two panels |
| Wired Ethernet with PoE, soldered | about £30 (WT32-ETH01) to £35 (Olimex), plus a PoE injector | a little less | One cable up to 100 m |
| 4G, solar, soldered | about £69 plus a data SIM | a little less | Firmware comes after the others |

All need a USB charger (one from a drawer, or £2.75 each in a 4-pack) except solar and 4G, and the PoE version
needs an injector or a PoE switch at the router end (not priced yet).

## Parts

### The core: every version

| Part | Job | AliExpress | Amazon UK |
|---|---|---|---|
| MLX90614, **BAA** (GY-906) | Sky temperature, 8 to 14 µm, 90° view | [£5.37](https://www.aliexpress.com/item/1005005995826372.html), pins loose; pick BAA from the options | [£15](https://www.amazon.co.uk/dp/B0CNM72R4L) pre-soldered (£11.37 each in a 2-pack) |
| BME280, 3.3 V | Air temperature, humidity, pressure | [£6.80](https://www.aliexpress.com/item/1005010813117971.html) (£6.46 each for 5) | [£10.50](https://www.amazon.co.uk/dp/B0BQFV883T) pre-soldered (£9.15 each in a 2-pack) |
| IP65 box, about 100 × 100 × 70 mm | The case | [£4.75](https://www.aliexpress.com/item/1005012037311684.html) (option D) | [£7.45](https://www.amazon.co.uk/dp/B09SP4PH41) (£4.36 each in a 4-pack) |
| PG7 cable glands | Cables in, water out | [£1.79 for 10](https://www.aliexpress.com/item/1005006063567574.html) | [£6.99 for 50](https://www.amazon.co.uk/dp/B07JH2LPZF) |
| Female-to-female jumper wires | Joining the boards | [about £1](https://www.aliexpress.com/item/1005007046465880.html) a strip | [£6.99](https://www.amazon.co.uk/dp/B01EV70C78) kit (40 female-female) |

### The board, by version

| Version | Board | Price |
|---|---|---|
| WiFi, charger | ESP32 DevKit (WROOM-32) | AliExpress [£4.10](https://www.aliexpress.com/item/1005006176546785.html) (£3.69 each for 5); Amazon [£7.99](https://www.amazon.co.uk/dp/B0CJHR8SMK), or £6.66 each in ELEGOO's 3-pack |
| WiFi, longer range | ESP32 DevKitC with **WROOM-32U** (u.FL socket) and a 2.4 GHz antenna | AliExpress [£11.85](https://www.aliexpress.com/item/1005010530406237.html) with antenna; spare antenna and lead [£1.65](https://www.aliexpress.com/item/1005005670189033.html) |
| WiFi, solder-free, plug-together | M5Stack AtomS3 Lite, NCIR unit, Adafruit BME280 (STEMMA QT), two Grove to STEMMA QT cables | The Pi Hut: [£7.80](https://thepihut.com/products/atoms3-lite-esp32s3-dev-kit), [£18.60](https://thepihut.com/products/ncir-sensor-unit), [£13.40](https://thepihut.com/products/adafruit-bme280-i2c-or-spi-temperature-humidity-pressure-sensor), cables about £3.80 |
| Solar | **FireBeetle 2 ESP32-E** (genuine DFRobot, built for deep sleep) or LOLIN D32 (cheaper, a clone, untested) | The Pi Hut [£9.90](https://thepihut.com/products/firebeetle-esp32-e-iot-microcontroller-supports-wi-fi-bluetooth); AliExpress [£3.09](https://www.aliexpress.com/item/1005006233798203.html) |
| Wired, PoE | **Olimex ESP32-POE** (power over the Ethernet cable) or WT32-ETH01 with a PoE splitter | Olimex [€17.95](https://www.olimex.com/Products/IoT/ESP32/ESP32-POE/open-source-hardware) (€16.16 each for 10); AliExpress [£5.12](https://www.aliexpress.com/item/1005009734802525.html) and splitter [£4.79](https://www.aliexpress.com/item/1005005523161215.html) |
| 4G | LilyGO T-SIM7000G (ESP32, LTE-M modem, 18650 holder, solar input) | AliExpress [£36.91](https://www.aliexpress.com/item/4000542688096.html); pick the modem variant for your region |

### Power, by version

| Version | Parts | Price |
|---|---|---|
| Charger | 1 A USB charger and a USB cable long enough to reach | Charger from a drawer, or Amazon [£2.75 each in a 4-pack](https://www.amazon.co.uk/dp/B0HKTDQQ2M); 5 m micro-USB cable [£6.99](https://www.amazon.co.uk/dp/B0D4Q2X94J) (not outdoor-rated: run it through a gland, keep the plug end indoors) |
| Solar | 6 V solar panel, CN3791 solar charger (6 V version), 18650 cell and holder | Panel [£1.70](https://www.aliexpress.com/item/1005008240317081.html) (use two: these 80 mm panels give about 70 mA in full sun, about 0.4 W, whatever the title says); charger [£2.00](https://www.aliexpress.com/item/1005008909011290.html); holder [£0.90](https://www.aliexpress.com/item/32825161070.html); cell: Vapcell K30 3000 mAh, [£9 each in a 2-pack](https://www.amazon.co.uk/s?k=Samsung+30Q+18650) on Amazon (buy branded cells from a named seller: cheap 18650s often hold a fraction of their label) |
| PoE | A PoE injector, or a PoE switch, at the router end | Not priced yet |
| 4G | A UK data SIM for IoT (a few MB a day) | Not priced yet |

A soldering iron, if you have none: Amazon [£15.97](https://www.amazon.co.uk/dp/B07SLRRYMC) (HANDSKIT 90 W kit).

## Check the parts when they arrive

- **The MLX90614 must be BAA.** The marking is engraved on the metal can. BCC and DCI have narrower views and
  are no use pointing at the sky. Listings mix them up.
- **The BME280 might be a BMP280,** with no humidity sensor. The firmware will read the chip and say which you
  have. A BMP280 station works but can't give the dew point.
- **Nothing gets 5 V except the board's USB socket.** Both sensors run on 3.3 V from the board.

## Soldering (the AliExpress modules)

Each sensor comes with a strip of header pins loose in the bag: four on the GY-906, four or six on the BME280.
Push the short ends through the board from the side without the chip, stand it in a breadboard or blu-tack to
hold it square, and solder each pin: iron on the pin and the pad together for two seconds, feed a little solder
in, take the solder away, then the iron. Eight joints in all, each a small shiny cone. If you've never soldered,
practise on the spare pins first.

## Wiring

Both sensors share one I²C bus: four wires each, the same four pins on the board. Their addresses differ
(MLX90614 0x5A, BME280 0x76 or 0x77), so nothing needs setting.

**ESP32 DevKit** (WiFi, and WiFi with the WROOM-32U):

| ESP32 pin | MLX90614 (GY-906) | BME280 |
|---|---|---|
| 3V3 | VIN | VIN or VCC |
| GND | GND | GND |
| GPIO 21 | SDA | SDA |
| GPIO 22 | SCL | SCL |

The board's 3V3 and GND pins take two wires each: use a female-female jumper from each sensor, and join pairs
with a short 3-way jumper or a small solder splice. On a six-pin BME280, leave CSB and SDO unconnected.

**M5Stack** (plug-together): AtomS3 Lite, then the BME280, then the NCIR unit, in a chain of Grove to STEMMA QT
cables. The BME280 board has two ports, so it sits in the middle.

**FireBeetle 2 ESP32-E** (solar): SDA and SCL as the DevKit (GPIO 21 and 22). The sensors' power comes from a spare
GPIO pin, not 3V3, so they are switched off while the board sleeps; the pin is fixed with the firmware (issue 3).
Battery: 18650 holder to the CN3791's BAT terminals, panel (or two in parallel) to its solar input, and the CN3791's
battery output to the FireBeetle's battery connector (a JST PH 2.0 plug).

**Olimex ESP32-POE** (wired): the sensors go on its UEXT connector (pin 1 3.3 V, pin 2 GND, pin 5 SCL, pin 6 SDA;
check against Olimex's schematic). The Ethernet cable from a PoE injector or switch powers it.

**WT32-ETH01** (wired, cheaper): needs 5 V from a PoE splitter; its I²C pins are fixed with the firmware.

**LilyGO T-SIM7000G** (4G): SDA and SCL pins are fixed with the firmware. The board has its own 18650 holder and
solar input.

## Power

| | Draws | Lasts | Cost |
|---|---|---|---|
| Charger | about 0.5 W, sending every minute | for ever | about £1 a year |
| Solar, low-power board | about 20 mAh a day: wakes each minute to read, sends every 10 minutes | a full 18650 about four months with no sun; two small panels keep it topped up | nothing |
| Solar, ESP32 DevKit | about 250 mAh a day: its regulator and USB chip never sleep | about ten days | don't |

A solar station can't run a dew heater (about 1 W, more than its whole budget). If the first station's tests show
that a heater is needed, solar stations get the polythene-film window instead.

Mount the panel facing south, tilted steeply (about 60°) for the winter sun, below the box or far enough to the
side that it stays out of the sensor's view (the rule below).

## The box

- **The MLX90614 looks straight up through a hole in the lid,** its can flush with the outside, sealed round with
  neutral-cure silicone. Nothing over it: glass and acrylic block 8 to 14 µm. Whether it stays open under a short
  hood or behind thin polythene film is the first station's test (issue 2); until then, a hood no taller than
  its own width (so it stays out of the 45° cone).
- **The BME280 goes outside the box,** in a small shaded, ventilated spot under it, on its four wires through a
  gland. Inside, it measures the box.
- **Cable glands face down,** and a drip loop in every cable outside.
- **Conformal coating** on the boards (not the sensors' faces) helps with damp.

## Where it goes

- **A clear view straight up:** the sensor sees everything within 45° of the zenith, so any chimney, wall, tree
  or roof edge must be further from the box than it rises above it.
- **Away from boiler flues, vents and extractor fans:** warm air rising past the sensor reads as cloud.
- **Height:** a shed roof, a fence post or a wall bracket a metre or two up is fine. Out of reach of children and
  livestock.
- **WiFi:** check the signal where the box will go with a phone before mounting. If it's weak, use the WROOM-32U
  board with its external antenna.

## Buying for a ring

Most astronomers who build one will want 5 to 10, in a ring 10 to 15 km round their site
([docs/ring.md](../docs/ring.md)). Buying for 10 WiFi stations on chargers:

| Basket | Per station | 10 stations | What's in it |
|---|---|---|---|
| **AliExpress, soldered** | about £21.40 | **about £214** | ESP32 DevKit 5-packs (£3.69 each), GY-906-BAA (£5.37), BME280 5-packs (£6.46), boxes (£4.51), two packs of 10 glands, jumper strips; free delivery |
| **Amazon UK, solder-free** | about £33.60 | **about £336** | ELEGOO ESP32 3-packs (£6.66), pre-soldered GY-906-BAA 2-packs (£11.37), pre-soldered BME280 2-packs (£9.15), box 4-packs (£4.36), 50 glands, two jumper kits |
| Chargers for 10 | about £2.75 | about £28 | three 4-packs from Amazon, if the hosts haven't spare ones |

Tips for a ring:

- **Order one or two spare sensors.** Some MLX90614s arrive as the wrong variant whatever the listing says, and a
  spare built station lets you swap a faulty one without a gap.
- **Mix the versions to fit the hosts:** chargers where there's a socket, solar where there isn't, the external
  antenna board at the end of long gardens.
- **Order AliExpress parts in one go,** a month before you need them: post takes two to three weeks.
- **Build them all at one sitting,** the same way, and label each box with its unit id, what it is, and your phone
  number.
