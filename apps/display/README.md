# Display application

Planned C++20/GStreamer receiver on the Pi. No runtime implemented yet; Pi
decoder and adapter compatibility are still unverified.

The [Mac sender](../hud/README.md) emits H.265 RTP/UDP with payload type 96 and
a 90000 Hz clock. The initial receiver must depayload, parse, hardware-decode,
and display through DRM/KMS to HDMI. Verify the actual decoder and supported
display mode before implementing the startup service.

Responsibilities include bounded buffering, stream timeout/stale-image clearing,
reconnect recovery, and local connection status. Display-side pose correction
remains a separate experiment requiring verified tracking and calibration.
