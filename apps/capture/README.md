# Pi capture

`capture.py` sends one camera or an explicitly labeled test source to the native
Mac HUD. It uses system Python/GStreamer and software `x264enc` with constrained
baseline H.264, RTP payload 97, a 90000 Hz clock, 1200-byte packets, and parameter
sets with every keyframe. Defaults: 640x360 at 30 fps, 1500 kbps, roughly three keyframes per
second for faster recovery after packet loss. The raw-frame queue is bounded and drops older frames.

Install [Pi dependencies](../../tools/pi/setup.sh), then start the Mac HUD with
`--camera udp --camera-port 5002`. On the Pi:

```sh
# Transport check; PI TEST SOURCE is burned into the image.
python3 apps/capture/capture.py --source test --host <mac-lan-ip>

# USB: select a mode actually listed by this camera.
v4l2-ctl --device /dev/video0 --list-formats-ext
python3 apps/capture/capture.py --source usb --device /dev/video0 \
  --usb-format mjpeg --width 640 --height 480 --host <mac-lan-ip>

# CSI/libcamera; --camera-name selects a particular camera if needed.
rpicam-hello --list-cameras
python3 apps/capture/capture.py --source csi --host <mac-lan-ip>
```

Use `--seconds 15` for a bounded test; Ctrl-C stops an interactive run. Exit
output reports encoded frames, which alone does not prove Mac receipt. Real
sources never silently fall back to the test pattern. The Mac resizes camera
input to its 640x360 inset.

On the October 3, 2026 bench, the subsequently connected Suyin HD USB Camera
enumerated at `/dev/video0`. MJPEG 640x360 at 30 fps was verified through this
sender and the Mac receiver. The OpenCV-enabled full loop rendered/encoded 450
HUD frames over 15 seconds; see [perception results](../compute/README.md).
Long-duration uplink/downlink stability, capture clock synchronization, and
reconnect handling still need validation. Sensor acquisition is not implemented.

The optional [capture service](../../config/pi/helmetd-capture.service) keeps
the USB uplink running independently of SSH; installation and the Mac-address
configuration are documented in [perception setup](../compute/README.md).

## Additional USB cameras

Install `config/pi/helmetd-camera@.service` into `~/.config/systemd/user/`.
For each extra camera, create `~/.config/helmetd/cameras/<role>.env`:

```ini
HELMETD_MAC_HOST=<mac-lan-ip>
HELMETD_CAMERA_DEVICE=/dev/v4l/by-path/<verified-usb-path>-video-index0
HELMETD_CAMERA_PORT=5004
HELMETD_CAMERA_FPS=15
HELMETD_CAMERA_BITRATE=900
```

Then `systemctl --user daemon-reload` and
`systemctl --user enable --now helmetd-camera@left`. Use ports 5004/5006/5008
for left/right/rear. Enable rear only after identifying the fourth device.
Front continues to use `helmetd-capture.service` on 5002.

The two HD cameras on the October 4 bench have identical USB serial numbers,
so their by-id links collide. Use by-path links, keep their USB ports stable,
and verify the image after remounting. After the physical-side correction, LEFT uses
`platform-xhci-hcd.0-usb-0:2:1.0-video-index0`; RIGHT uses
`platform-xhci-hcd.1-usb-0:1:1.0-video-index0`. FRONT is the Innomaker.
Update the Mac host in both `capture.env` and every camera env file when the
network changes; restart the corresponding services.

The MVP service profile uses 640x360: front 30 fps / 900 kbps (the Innomaker requires 30 fps), sides 15 fps / 600 kbps.
The shorter GOP limits the wait for a clean image after packet loss.
