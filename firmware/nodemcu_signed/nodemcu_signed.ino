#include <Arduino.h>
#include <StackThunk.h>
#include <bearssl/bearssl.h>

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
constexpr int32_t kMinimumTemperatureMilliC = 3500;
constexpr int32_t kMaximumTemperatureMilliC = 5500;
constexpr size_t kSha256Length = 32;
constexpr size_t kRawP256SignatureLength = 64;

char deviceId[24];
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

  char canonicalPayload[128];
  snprintf(
      canonicalPayload,
      sizeof(canonicalPayload),
      "2|%s|%lu|%lu|%ld|1",
      deviceId,
      static_cast<unsigned long>(sequenceNumber),
      static_cast<unsigned long>(uptimeMs),
      static_cast<long>(simulatedTemperatureMilliC));

  char signatureHex[kRawP256SignatureLength * 2 + 1];
  if (!signPayload(canonicalPayload, signatureHex)) {
    Serial.println("SIGNING_ERROR");
    return;
  }

  Serial.printf(
      "{\"message_type\":\"telemetry\",\"schema_version\":2,"
      "\"device_id\":\"%s\",\"sequence\":%lu,\"uptime_ms\":%lu,"
      "\"temperature_milli_c\":%ld,\"temperature_c\":%.3f,"
      "\"simulated\":true,"
      "\"signature_algorithm\":\"ecdsa-p256-sha256-raw\","
      "\"signature\":\"%s\"}\n",
      deviceId,
      static_cast<unsigned long>(sequenceNumber),
      static_cast<unsigned long>(uptimeMs),
      static_cast<long>(simulatedTemperatureMilliC),
      static_cast<double>(simulatedTemperatureMilliC) / 1000.0,
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
  randomSeed(ESP.getCycleCount());

  Serial.println();
  Serial.println("Rialo Edge Log - signed NodeMCU telemetry");
  Serial.printf("Device ID: %s\n", deviceId);
  printRegistration();
  nextSampleAtMs = millis();
}

void loop() {
  const uint32_t nowMs = millis();
  if (static_cast<int32_t>(nowMs - nextSampleAtMs) < 0) {
    return;
  }

  nextSampleAtMs = nowMs + kSampleIntervalMs;
  updateSimulatedTemperature();
  printSignedTelemetry();
  blinkStatusLed();
}
