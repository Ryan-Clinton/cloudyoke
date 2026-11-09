# Bill of materials and wiring

Prototype hardware, not yet tested outdoors. Prices checked 9 November 2026;
treat them as rough. Sources for every price are in
[docs/spec.md §11.2](../docs/spec.md#112-parts-and-build).

## Two ways to build one station

| Part | Job | AliExpress | UK, plugs together |
|---|---|---|---|
| ESP32 board | Reads the sensors, sends a reading a minute over WiFi | DevKit, about £3 | M5Stack AtomS3 Lite (native USB, Grove port), £9 |
| MLX90614, 90° (BAA) | Sky temperature, 8 to 14 µm | GY-906 module, £2 to £6 | M5Stack NCIR unit (Grove), £18.60 |
| BME280 | Air temperature, humidity, pressure | module, £1 to £4 | Pimoroni or Adafruit (STEMMA QT), £7.50 to £14.40 |
| Leads | | jumper wires | two Grove to STEMMA QT cables, £3.80 |
| Weatherproof box | | IP65, about 100 × 100 × 50 mm, about £4 | the same |
| USB supply, 1 A | Power; WiFi transmit peaks reach about 260 mA | an old phone charger, or about £5 | the same |
| **Total (estimate)** | | **about £15 to £20** | **about £50 to £60** |

The AliExpress build needs the sensors' four-pin headers soldered and takes a
few weeks' post. The UK build needs no soldering.

## Traps

- **The MLX90614 variant.** Many GY-906 listings bundle BAA, BCC and DCI under
  one title. Only the BAA (90° field of view) suits a zenith sensor. The
  marking is laser-engraved on the can; check it on arrival.
- **Fake BME280s.** Many are BMP280s with no humidity sensor. Chip ID register
  0xD0 reads 0x60 on a BME280 and 0x58 on a BMP280. The firmware will read it
  and report which chip it has; a BMP280 station still works but can't give
  the dew point.
- **The BME280 goes outside the box,** in a vented shade, or it measures the
  inside of the box.
- **No glass or acrylic over the MLX90614:** both are opaque at 8 to 14 µm.
  Thin polyethylene film passes most of that band; whether a film window or an
  open sensor under a hood copes better with dew is the first station's test.
  Some cling film is PVC, not polyethylene.

## Wiring (ESP32 DevKit)

Both sensors share the I²C bus. Their addresses differ (MLX90614 0x5A,
BME280 0x76 or 0x77), so no changes are needed.

| ESP32 pin | Goes to |
|---|---|
| 3V3 | VIN or VCC of the MLX90614 and the BME280 |
| GND | GND of both |
| GPIO 21 (SDA) | SDA of both |
| GPIO 22 (SCL) | SCL of both |

On the M5Stack build the Grove and STEMMA QT cables carry the same four
lines; the BME280 board has two ports, so it sits between the AtomS3 and the
NCIR unit in a chain.

## Placement

The sensor sees everything within 45° of straight up, so any chimney, flue,
wall or tree must be further from the station than it rises above it. Keep
away from boiler flues and vents: warm air rising past the sensor reads as
cloud. Cable glands face down.
