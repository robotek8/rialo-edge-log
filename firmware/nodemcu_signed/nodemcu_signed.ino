#include <Arduino.h>
#include <StackThunk.h>
#include <bearssl/bearssl.h>
#include <user_interface.h>

#include "device_secrets.h"

extern "C" size_t signDigestOnSecondStack(
    const br_ec_private_key* privateKey,
    const unsigned char* digest,
    unsigned char* signature) {
  br_ecdsa_sign signer = br_ecdsa_sign_raw_get_default();
  return signer(
      br_ec_get_default(),
      &br_sha256_vtable,
      digest,
      privateKey,
      signature);
}

make_stack_thunk(signDigestOnSecondStack);

extern "C" size_t thunk_signDigestOnSecondStack(
    const br_ec_private_key* privateKey,
    const unsigned char* digest,
    unsigned char* signature);

namespace {

constexpr uint32_t kSerialBaud = 115200;
constexpr uint32_t kSampleIntervalMs = 5000;
constexpr uint32_t kWatchdogTimeoutMs = 8000;
constexpr int32_t kMinimumTemperatureMilliC = 3500;
constexpr int32_t kMaximumTemperatureMilliC = 5500;
constexpr size_t kSha256Length = 32;
constexpr size_t kRawP256SignatureLength = 64;

// Set this to a free NodeMCU pin such as D5 when a normally-closed enclosure
// switch is installed. Leave -1 to report tamper_open=false without using a pin.
constexpr int8_t kTamperPin = -1;
constexpr bool kTamperOpenWhenHigh = true;

char deviceId[24];
char resetReason[24] = "unknown";
uint32_t bootId = 0;
uint32_t sequenceNumber = 0;
uint32_t nextSampleAtMs = 0;
int32_t simulatedTemperatureMilliC = 4200;

void blinkStatusLed() {
  digitalWrite(LED_BUILTIN, LOW);
  delay(35);
  digitalWrite(LED_BUILTIN, HIGH);
}

void updateSimulatedTemperature() {
  simulatedTemperatureMilliC += random(-80, 81);
  simulatedTemperatureMilliC = constrain(
      simulatedTemperatureMilliC,
      kMinimumTemperatureMilliC,
      kMaximumTemperatureMilliC);
}

void bytesToHex(
    const unsigned char* input,
    size_t inputLength,
    char* output) {
  static const char kHexDigits[] = "0123456789abcdef";
  for (size_t index = 0; index < inputLength; ++index) {
    output[index * 2] = kHexDigits[input[index] >> 4];
    output[index * 2 + 1] = kHexDigits[input[index] & 0x0F];
  }
  output[inputLength * 2] = '\0';
}

bool signPayload(const char* payload, char* signatureHex) {
  unsigned char digest[kSha256Length];
  br_sha256_context sha256Context;
  br_sha256_init(&sha256Context);
  br_sha256_update(&sha256Context, payload, strlen(payload));
  br_sha256_out(&sha256Context, digest);

  br_ec_private_key privateKey = {
      BR_EC_secp256r1,
      DEVICE_PRIVATE_KEY,
      sizeof(DEVICE_PRIVATE_KEY)};
  unsigned char signature[kRawP256SignatureLength];
  const size_t signatureLength = thunk_signDigestOnSecondStack(
      &privateKey,
      digest,
      signature);
  if (signatureLength != kRawP256SignatureLength) {
    return false;
  }

  bytesToHex(signature, signatureLength, signatureHex);
  return true;
}

void detectResetReason() {
  const String reason = ESP.getResetReason();
  const char* code = "unknown";
  if (reason.indexOf("Power") >= 0) {
    code = "power_on";
  } else if (reason.indexOf("External") >= 0) {
    code = "external_reset";
  } else if (reason.indexOf("Watchdog") >= 0) {
    code = "watchdog_reset";
  } else if (reason.indexOf("Software") >= 0 || reason.indexOf("restart") >= 0) {
    code = "software_reset";
  } else if (reason.indexOf("Deep-Sleep") >= 0) {
    code = "deep_sleep_wake";
  } else if (reason.indexOf("Exception") >= 0) {
    code = "exception_reset";
  }
  strlcpy(resetReason, code, sizeof(resetReason));
}

bool isTamperOpen() {
  if (kTamperPin < 0) return false;
  return digitalRead(kTamperPin) == (kTamperOpenWhenHigh ? HIGH : LOW);
}

void printRegistration() {
  Serial.printf(
      "{\"message_type\":\"device_registration\","
      "\"schema_version\":1,\"device_id\":\"%s\","
      "\"signature_algorithm\":\"ecdsa-p256-sha256-raw\","
      "\"public_key_sec1\":\"%s\"}\n",
      deviceId,
      DEVICE_PUBLIC_KEY_HEX);
}

void printSignedTelemetry() {
  ++sequenceNumber;
  const uint32_t uptimeMs = millis();
  const bool tamperOpen = isTamperOpen();

  char canonicalPayload[192];
  snprintf(
      canonicalPayload,
      sizeof(canonicalPayload),
      "3|%s|%lu|%lu|%ld|1|%lu|%s|%u",
      deviceId,
      static_cast<unsigned long>(sequenceNumber),
      static_cast<unsigned long>(uptimeMs),
      static_cast<long>(simulatedTemperatureMilliC),
      static_cast<unsigned long>(bootId),
      resetReason,
      tamperOpen ? 1U : 0U);

  char signatureHex[kRawP256SignatureLength * 2 + 1];
  ESP.wdtFeed();
  if (!signPayload(canonicalPayload, signatureHex)) {
    Serial.println("SIGNING_ERROR");
    ESP.wdtFeed();
    return;
  }
  ESP.wdtFeed();

  Serial.printf(
      "{\"message_type\":\"telemetry\",\"schema_version\":3,"
      "\"device_id\":\"%s\",\"sequence\":%lu,\"uptime_ms\":%lu,"
      "\"temperature_milli_c\":%ld,\"temperature_c\":%.3f,"
      "\"simulated\":true,\"boot_id\":%lu,"
      "\"reset_reason\":\"%s\",\"tamper_open\":%s,"
      "\"signature_algorithm\":\"ecdsa-p256-sha256-raw\","
      "\"signature\":\"%s\"}\n",
      deviceId,
      static_cast<unsigned long>(sequenceNumber),
      static_cast<unsigned long>(uptimeMs),
      static_cast<long>(simulatedTemperatureMilliC),
      static_cast<double>(simulatedTemperatureMilliC) / 1000.0,
      static_cast<unsigned long>(bootId),
      resetReason,
      tamperOpen ? "true" : "false",
      signatureHex);
}

}  // namespace

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);

  Serial.begin(kSerialBaud);
  delay(150);

  stack_thunk_add_ref();
  snprintf(deviceId, sizeof(deviceId), "edge-%06X", ESP.getChipId());
  detectResetReason();
  bootId = os_random();
  if (bootId == 0) bootId = ESP.getCycleCount() ^ ESP.getChipId();
  randomSeed(bootId);
  if (kTamperPin >= 0) {
    pinMode(kTamperPin, kTamperOpenWhenHigh ? INPUT_PULLUP : INPUT);
  }

  ESP.wdtEnable(kWatchdogTimeoutMs);
  ESP.wdtFeed();

  Serial.println();
  Serial.println("Rialo Edge Log - signed NodeMCU telemetry");
  Serial.printf("Device ID: %s\n", deviceId);
  Serial.printf("Boot ID: %08lx, reset: %s\n", static_cast<unsigned long>(bootId), resetReason);
  Serial.printf("Watchdog: enabled (%lu ms)\n", static_cast<unsigned long>(kWatchdogTimeoutMs));
  printRegistration();
  nextSampleAtMs = millis();
  ESP.wdtFeed();
}

void loop() {
  ESP.wdtFeed();

  const uint32_t nowMs = millis();
  if (static_cast<int32_t>(nowMs - nextSampleAtMs) < 0) {
    delay(1);
    return;
  }

  nextSampleAtMs = nowMs + kSampleIntervalMs;
  updateSimulatedTemperature();
  printSignedTelemetry();
  blinkStatusLed();
  ESP.wdtFeed();
}
