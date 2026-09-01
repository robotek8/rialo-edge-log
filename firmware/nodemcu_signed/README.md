# Signed NodeMCU Firmware

This firmware signs every telemetry reading with a device-specific ECDSA P-256
private key. The gateway enrolls the public key on first contact and rejects
readings whose signatures do not verify.

Telemetry schema 3 also signs a per-boot ID, the ESP8266 reset reason, and the
enclosure tamper state. Old schema-2 batches remain verifiable.

## Optional enclosure switch

The firmware defaults to `kTamperPin = -1`, so no GPIO is used. When a
normally-closed switch between GPIO and GND is installed, set `kTamperPin` in
`nodemcu_signed.ino` to a free pin such as `D5`. The internal pull-up keeps a
closed circuit at LOW; opening the enclosure raises the input and produces
`tamper_open: true` in every signed reading.

## Generate the Device Key

From the repository root on Windows:

```powershell
py -m pip install -r gateway\requirements.txt
py -m gateway.device_keys --output firmware\nodemcu_signed\device_secrets.h
```

`device_secrets.h` is intentionally ignored by Git. Do not send it to anyone,
commit it, or reuse its private key on another device.

## Flash

1. Open `nodemcu_signed.ino` in Arduino IDE.
2. Select **NodeMCU 1.0 (ESP-12E Module)**.
3. Upload the sketch.
4. Close Serial Monitor before starting the gateway.

The gateway stores the public key locally using trust on first use. If the same
device ID later presents another key, collection stops with a security warning.
Key registration on Rialo is not implemented; the local registry is currently
the source of truth for device identity.
