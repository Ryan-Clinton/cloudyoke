// cloudyoke: the first station on an Arduino Nano over USB (no WiFi). One line a minute on the serial port,
// read by server/serial_station.py on the computer it's plugged into, which timestamps and stores it.
//
// Wiring (hardware/bom.md, "Nano over USB"):
//   GY-906 MLX90614 BAA: VIN -> 5V (the board has its own 3.3 V regulator), GND -> GND, SDA -> A4, SCL -> A5
//   BME280 (3.3 V board): VCC -> 3V3, GND -> GND, SDA -> A4, SCL -> A5
// The 3.3 V BME280 must not see 5 V on its data lines, so the Nano's own 5 V pull-ups are switched off
// after Wire.begin(); the GY-906's pull-ups (to its 3.3 V) hold the bus instead.
//
// Libraries (Arduino Library Manager): "Adafruit MLX90614 Library" and "Adafruit BME280 Library".
//
// Line format, one per minute, 115200 baud:
//   CY v=1 sky=-18.41 amb=5.20 air=6.10 hum=81.0 pres=1012.3 chip=60
// A value the sensor didn't give is left out; chip is the BME280's ID register (60 = BME280, 58 = BMP280,
// which has no humidity sensor; 0 = nothing answered). err=... names a sensor that didn't answer.

#include <Wire.h>
#include <Adafruit_MLX90614.h>
#include <Adafruit_BME280.h>

const unsigned long PERIOD_MS = 60000UL;
Adafruit_MLX90614 mlx;
Adafruit_BME280 bme;
bool mlxOk = false, bmeOk = false;
uint8_t bmeAddr = 0, chip = 0;
unsigned long last = 0;

uint8_t readChipId(uint8_t addr) {
  Wire.beginTransmission(addr);
  Wire.write(0xD0);
  if (Wire.endTransmission() != 0) return 0;
  if (Wire.requestFrom(addr, (uint8_t)1) != 1) return 0;
  return Wire.read();
}

void startSensors() {
  mlxOk = mlx.begin();
  const uint8_t addrs[] = {0x76, 0x77};          // the BME280's two possible addresses
  chip = 0;
  for (uint8_t i = 0; i < 2; i++) {
    uint8_t id = readChipId(addrs[i]);
    if (id) { bmeAddr = addrs[i]; chip = id; break; }
  }
  bmeOk = chip && bme.begin(bmeAddr);            // the library refuses a BMP280, which is reported by chip=58
}

void printValue(const char *name, float v, uint8_t places) {
  if (isnan(v)) return;
  Serial.print(' '); Serial.print(name); Serial.print('='); Serial.print(v, places);
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  digitalWrite(SDA, LOW);                        // switch off the internal 5 V pull-ups (see above)
  digitalWrite(SCL, LOW);
  startSensors();
  Serial.println(F("CY hello v=1 nano-usb"));
}

void loop() {
  if (last && millis() - last < PERIOD_MS) return;
  last = millis();
  if (!mlxOk || !bmeOk) startSensors();          // try again each minute, so a loose wire recovers by itself
  Serial.print(F("CY v=1"));
  if (mlxOk) {
    printValue("sky", mlx.readObjectTempC(), 2);
    printValue("amb", mlx.readAmbientTempC(), 2);
  }
  if (bmeOk) {
    printValue("air", bme.readTemperature(), 2);
    if (chip == 0x60) printValue("hum", bme.readHumidity(), 1);
    printValue("pres", bme.readPressure() / 100.0F, 1);
  }
  Serial.print(F(" chip=")); Serial.print(chip, HEX);
  if (!mlxOk) Serial.print(F(" err=mlx"));
  if (!bmeOk) Serial.print(F(" err=bme"));
  Serial.println();
}
