# NodeMCU Telemetry Simulator

This starter firmware produces a simulated temperature reading every five
seconds, so the serial data path can be tested without a physical sensor.

## Flash with Arduino IDE

1. Open `nodemcu_simulator.ino`.
2. Select **NodeMCU 1.0 (ESP-12E Module)** as the board.
3. Select the COM port belonging to the NodeMCU V3.
4. Upload the sketch.
5. Open Serial Monitor at **115200 baud**.

Expected output:

```json
{"schema_version":1,"device_id":"edge-A1B2C3","sequence":1,"uptime_ms":153,"temperature_c":4.24,"simulated":true}
```

The built-in LED flashes whenever a reading is emitted. The signed firmware in
[`../nodemcu_signed`](../nodemcu_signed) is used by the full demo. A DS18B20 will
eventually replace the simulated value while keeping the same JSON structure.
