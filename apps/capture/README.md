# Capture application

Planned C++20 application on the Raspberry Pi 5. No runtime implemented yet.

Planned modules:

| Module | Responsibility |
| --- | --- |
| Capture | Acquire camera frames and preserve capture timestamps. |
| Sensors | Read attached sensors and any accessible glasses tracking data. |
| Streaming | Send camera/sensor data to the Mac. |
| Runtime | Configuration, clock exchange, connection health, and reconnects. |

Use bounded queues and preserve acquisition timestamps. Camera APIs and sensor
drivers depend on the selected hardware. Display reception belongs to the
separate [display project](../display/README.md).

Read the shared [protocol plan](../../packages/protocol/README.md) before adding
device messages. Setup and run commands will be documented after implementation.
