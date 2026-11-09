# The first station: an Arduino Nano over USB

No WiFi: the Nano prints one reading a minute over its USB cable, and `server/serial_station.py`, on the
computer it's plugged into, timestamps each one and stores it in the receiver's format. The night graph
and the City of Derry comparison then work on it unchanged, with no server needed on the night.

## Parts

The Nano, a GY-906 MLX90614 **BAA** (check the marking on the can, issue 1), a 3.3 V BME280, jumper wires,
and a USB cable long enough to reach outside.

## Wiring

| Nano pin | Goes to |
|---|---|
| 5V | GY-906 VIN (the GY-906 has its own 3.3 V regulator) |
| 3V3 | BME280 VCC |
| GND | GND of both |
| A4 (SDA) | SDA of both |
| A5 (SCL) | SCL of both |

- **The 3.3 V BME280 must never see 5 V.** It is powered from 3V3, and the sketch switches off the Nano's
  own 5 V pull-ups on A4 and A5 straight after starting the bus, so the GY-906's pull-ups (to its own
  3.3 V) hold the lines.
- **Check the Nano's 3V3 pin with the multimeter first,** with the Nano on USB and nothing else connected.
  On many clone Nanos it comes from the USB chip; it should read about 3.3 V. If it reads 0 or far off,
  don't connect the BME280 to it.
- **Before trusting the bus,** with everything wired and on USB, the multimeter should read about 3.3 V
  (not 5 V) from A4 to GND and from A5 to GND.

## Flashing

1. In the Arduino IDE, Library Manager: install **Adafruit MLX90614 Library** and **Adafruit BME280
   Library** (say yes to their dependencies).
2. Open `nano-usb.ino`, board **Arduino Nano**. Most clone Nanos need **Processor: ATmega328P (Old
   Bootloader)**; if the upload fails, switch between that and the plain ATmega328P.
3. Upload, then open the Serial Monitor at **115200** baud. Within a minute:

   ```
   CY hello v=1 nano-usb
   CY v=1 sky=21.04 amb=20.90 air=20.65 hum=48.3 pres=1012.3 chip=60
   ```

   Indoors the sky value is just the ceiling's temperature. `chip=60` is a real BME280; `chip=58` a BMP280
   (no humidity); `err=mlx` or `err=bme` names a sensor that isn't answering. Close the Serial Monitor
   before the next step: only one program can have the port.

## The night

- **The sensor must be outside, looking straight up.** Glass and plastic windows are opaque to it, so a
  sensor behind a window measures the window. Run the USB cable through a door or window gap (USB 2.0
  cables work to about 5 m).
- **On the computer** (Python and `pip install pyserial`), from the cloudyoke folder:

  ```
  python server/serial_station.py --port COM5 --unit cy-0001 --data data          (Windows; the port is in the IDE's Tools > Port)
  python server/serial_station.py --port /dev/ttyUSB0 --unit cy-0001 --data data  (Linux)
  ```

  It prints each reading as it stores it. Leave it running; Ctrl+C stops it.
- **Notes of the sky**, with the time, at least each time it changes (clear, thin cloud, cloud, rain), and
  a photo straight up now and then. These are the check the sensor is judged against (spec §9.2).
- **Next day:**

  ```
  python server/metar.py --data data --ids EGAE --hours 48
  python server/night_graph.py --data data --unit cy-0001 --night 2026-11-20 --reference EGAE > night.svg
  ```

  The graph shows sky, air and sky minus air through the night, with Derry's reports underneath.
