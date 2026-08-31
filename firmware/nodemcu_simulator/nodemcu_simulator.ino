#include <Arduino.h>

namespace {

constexpr uint32_t kSerialBaud = 115200;
constexpr uint32_t kSampleIntervalMs = 5000;
constexpr float kMinimumTemperatureC = 3.50F;
constexpr float kMaximumTemperatureC = 5.50F;

char deviceId[24];
uint32_t sequenceNumber = 0;
uint32_t nextSampleAtMs = 0;
float simulatedTemperatureC = 4.20F;

void blinkStatusLed() {
  // The NodeMCU V3 built-in LED is active-low.
  digitalWrite(LED_BUILTIN, LOW);
  delay(35);
  digitalWrite(LED_BUILTIN, HIGH);
}

void updateSimulatedTemperature() {
  const long changeInHundredths = random(-8, 9);
  simulatedTemperatureC += static_cast<float>(changeInHundredths) / 100.0F;
  simulatedTemperatureC = constrain(
      simulatedTemperatureC,
      kMinimumTemperatureC,
      kMaximumTemperatureC);
}

void printTelemetry() {
  ++sequenceNumber;

  Serial.printf(
      "{\"schema_version\":1,\"device_id\":\"%s\","
      "\"sequence\":%lu,\"uptime_ms\":%lu,"
      "\"temperature_c\":%.2f,\"simulated\":true}\n",
      deviceId,
      static_cast<unsigned long>(sequenceNumber),
      static_cast<unsigned long>(millis()),
      simulatedTemperatureC);
}

}  // namespace

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);

  Serial.begin(kSerialBaud);
  delay(150);

  snprintf(
      deviceId,
      sizeof(deviceId),
      "edge-%06X",
      ESP.getChipId());

  randomSeed(ESP.getCycleCount());

  Serial.println();
  Serial.println("Rialo Edge Log - NodeMCU telemetry simulator");
  Serial.printf("Device ID: %s\n", deviceId);
  Serial.println("Emitting one JSON reading every five seconds.");

  nextSampleAtMs = millis();
}

void loop() {
  const uint32_t nowMs = millis();
  if (static_cast<int32_t>(nowMs - nextSampleAtMs) < 0) {
    return;
  }

  nextSampleAtMs = nowMs + kSampleIntervalMs;
  updateSimulatedTemperature();
  printTelemetry();
  blinkStatusLed();
}

