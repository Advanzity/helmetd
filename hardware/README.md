# Hardware

Planning inventory, 2026-10-03. See the [Pi bench record](pi-bench-2026-10-03.md)
for live hardware observations and verified video output.

| Item | Status |
| --- | --- |
| Raspberry Pi 5 | Connected: approximately 4 GiB, Debian 13.7 arm64; hardware HEVC/Wayland display verified. Power/cooling models TBD. |
| MacBook | Selected for processing and rendering; chip and macOS version TBD. |
| XREAL 1S | Model confirmed by the user. Firmware TBD. |
| HDMI-to-USB-C adapter | Available, confirmed by the user. Model, power, supported modes, and USB data path unverified. |
| Cameras / sensors | Available per user; no USB or CSI camera enumerated on the Pi during bring-up. Models/modes TBD. |
| XREAL Eye / companion device | Availability not confirmed. |
| Wi-Fi network | AP/hotspot arrangement and measured performance TBD. |

## Display connection

The Pi 5 uses micro-HDMI for display output and does not provide DisplayPort
video over USB-C. Validate the complete path:

```text
Pi micro-HDMI -> HDMI -> powered HDMI-to-USB-C conversion -> XREAL 1S
```

Check the existing adapter's direction, power arrangement, EDID, refresh rate,
and stereo modes on the actual hardware. A working video connection does not
establish that glasses sensor data is accessible over USB.

Sources: [Raspberry Pi display documentation](https://www.raspberrypi.com/documentation/computers/getting-started.html),
[XREAL device connections](https://tutorials.xreal.com/docs/glasses/one-series/first-use/connect-device/).

## Tracking and display constraints

The XREAL 1S provides native 3DoF tracking. XREAL offers the Eye accessory for
6DoF spatial screen anchoring. Custom graphics registered to physical objects
also require an accessible pose source and calibration; do not infer those
capabilities from screen anchoring alone.

The SDK feature table distinguishes 6DoF head tracking from plane tracking and
spatial-anchor APIs. Verify the exact 1S/firmware/runtime combination and data
connection before selecting an SDK. Linux/Pi access through the existing
adapter remains unverified.

The published 1S specification lists 3840 x 1200 binocular resolution and
refresh rates up to 120 Hz. These are device specifications, not proof that the
adapter, chosen input mode, codec, and Pi can deliver that mode together.

Sources: [XREAL 1S](https://www.xreal.com/1s),
[XREAL Eye](https://www.xreal.com/us/eye),
[SDK compatibility](https://docs.xreal.com/XREALDevices/Compatibility),
[1S specifications](https://tutorials.xreal.com/docs/glasses/one-series/spec/).

The Pi 5 specification lists a hardware HEVC decoder. Verify actual decoder
availability and simultaneous camera acquisition, uplink encoding, downlink
decoding, and display load before selecting codecs in either direction.

Source: [Raspberry Pi 5 specification](https://www.raspberrypi.com/products/raspberry-pi-5/).

## Bench record to complete

- Exact device/adapter models, firmware, OS, and connected ports.
- Display modes proven through the adapter, including eye order if stereo works.
- Which USB devices enumerate and what tracking data can actually be read.
- Camera-to-glasses mounting rigidity and available IMU data.
- Power consumption, temperature, throttling, and sustained network performance.

Record calibration details in [calibration](calibration/README.md).
