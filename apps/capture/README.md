# Pi capture

`capture.py` sends one camera or an explicitly labeled test source to the native
Mac HUD. It uses system Python/GStreamer and software `x264enc` with constrained
baseline H.264, RTP payload 97, a 90000 Hz clock, 1200-byte packets, and parameter
sets with every keyframe. Defaults: 640x360 at 30 fps, 1500 kbps, one keyframe per
second. The raw-frame queue is bounded and drops older frames.

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

On the October 3, 2026 bench, no USB or CSI camera enumerated. A two-second
local test source run encoded 60 frames and exited successfully. The interrupted
full-loop run did not produce a final verified frame count. Physical camera acquisition, sustained simultaneous
uplink/downlink, capture timestamps and reconnect handling still need tests
after a camera is connected. Sensor acquisition is not implemented.
