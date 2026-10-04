# Mac perception

OpenCV DNN runs the OpenCV Zoo YOLOX-S detector on the Mac. The Pi captures one
USB/CSI camera and sends baseline H.264 RTP; the native HUD decodes that stream,
submits images to a separate inference thread, draws labeled boxes, and sends
the rendered HUD back to the Pi over the existing HEVC path.

Classes: person, bicycle, car, motorcycle, bus, and truck. This is image-space
perception, separate from the still-planned world tracking and calibration.

## Setup and run

From the repository root on the Mac:

```sh
brew install cmake ninja pkgconf gstreamer opencv
python3 tools/download_detector.py
cmake --preset mac-debug
cmake --build --preset mac-debug
ctest --preset mac-debug

./build/mac-debug/bin/helmetd-hud \
  --camera udp --camera-port 5002 \
  --detect-model .local/models/object_detection_yolox_2022nov.onnx \
  --host <pi-lan-ip> --port 5000
```

Omit `--host` for a local preview. The Pi display receiver must be running to
show the returned HUD. On the Pi, use a mode actually supported by the camera:

```sh
v4l2-ctl --device /dev/video0 --list-formats-ext
python3 ~/helmetd/apps/capture/capture.py \
  --source usb --device /dev/video0 --usb-format mjpeg \
  --width 640 --height 360 --fps 30 --host <mac-lan-ip> --port 5002
```

The connected Suyin HD Camera supports this MJPEG 640x360/30 mode.
For a CSI camera use `--source csi`;
see [capture setup](../capture/README.md). One process owns the USB camera. Stop
a previous capture before starting another, and use one HUD sender per display port.

The 35.9 MB model stays in ignored `.local/models`. The downloader checks its
SHA-256 and refuses unexpected existing weights. Only the specified YOLOX-S
export is supported; other YOLO families have different preprocessing/outputs.

For capture independent of SSH, install the supplied user service on the Pi:

```sh
mkdir -p ~/.config/systemd/user ~/.config/helmetd
cp config/pi/helmetd-capture.service ~/.config/systemd/user/
printf 'HELMETD_MAC_HOST=<mac-lan-ip>\n' > ~/.config/helmetd/capture.env
systemctl --user daemon-reload
systemctl --user enable --now helmetd-capture.service
journalctl --user -u helmetd-capture.service -n 20
```

The service expects the project at `~/helmetd`, restarts on capture errors,
and uses the verified USB MJPEG mode. Update `capture.env` and restart it when
the Mac's LAN address changes. Stop it with
`systemctl --user stop helmetd-capture.service` before a manual capture test.

## Caution cues

Detection confidence is objectness times the class score, with a 0.50 threshold
and class-aware NMS at IoU 0.45. At most 32 detections are displayed. Cues require:

- Confidence at least 0.60.
- A box overlapping the central 30–70% of image width and extending below 60%
  of image height.
- Person height at least 30% of the image, or vehicle box area at least 12%.
- The same class/box matched at IoU greater than 0.30 for three consecutive
  analyzed frames spanning at least 150 ms. A gap over 500 ms resets confirmation.

The HUD then shows **PERSON IN VIEW** or **VEHICLE IN VIEW**, with
**CHECK SURROUNDINGS**. A qualifying person takes priority over a vehicle.
These are uncalibrated image-based attention cues, not measurements of distance,
collision probability, or instructions to brake/steer. A large box does not
prove danger; a missing box does not mean the road is clear. Lighting, camera
angle, occlusion, and detection mistakes affect results. Bench validation does
not establish safe use while riding. There is no LLM in the warning path and
no automatic voice connection yet.
The current Pi display receiver retains its last displayed frame if the Mac
downlink stops. Mac-side camera expiry does not protect against that separate
failure; automatic downlink blanking remains a display follow-up before road use.

## Freshness and load

Inference is submitted at most 10 times per second. The worker holds one pending
image and one result, replacing old pending input under load. Results retain
their source image and local pipeline timestamp: the camera inset and boxes
always refer to the same image. This makes the detection-enabled inset update
at inference speed; the main HUD continues at its configured render rate.

Analyzed imagery, boxes, and automatic cues expire after 500 ms of **local
pipeline age**, including inference. Unanalyzed camera preview keeps its 250 ms
budget; the worker also rejects input already older than 250 ms. The UDP receiver
uses an 80 ms jitter buffer and clock-synchronized appsink to avoid consuming
future presentation timestamps. Network/capture clock synchronization is
still missing, so this is not sensor-to-eye latency. If inference cannot meet
that budget, the HUD says detection is waiting/stale. Runtime detector failures
are logged, clear the automatic cues, and let unannotated camera preview continue.
The moving-ball test source remains synthetic and should produce no road objects.
Speed/gear and Space-key warnings remain explicitly simulated bench inputs.

## Checks

`ctest` checks detector output geometry, class-aware suppression, persistence,
confidence/region guards, stale/future timestamps, exact image association, and
the existing real Metal/media tests. It does not download weights or photos.

Check the real network on a local image:

```sh
./build/mac-debug/bin/helmetd-detect \
  .local/models/object_detection_yolox_2022nov.onnx photo.jpg result.png
```

For an opt-in full local RTP → OpenCV → Metal check, supply a JPEG with a
large central person and a new output directory. This checks both active
cautions and their removal after the sender stops:

```sh
python3 apps/hud/tests/perception_uplink.py \
  --hud build/mac-debug/bin/helmetd-hud \
  --model .local/models/object_detection_yolox_2022nov.onnx \
  --image photo.jpg --directory .local/perception-test
```

Model/preprocessing reference: [OpenCV Zoo YOLOX](https://github.com/opencv/opencv_zoo/tree/main/models/object_detection_yolox),
whose model and reference files are [Apache-2.0](https://github.com/opencv/opencv_zoo/blob/main/models/object_detection_yolox/LICENSE).
Smoke-test photos can be obtained separately from the upstream
[Ultralytics assets](https://github.com/ultralytics/assets/blob/main/im/bus.jpg)
and [YOLOX assets](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/assets/dog.jpg);
they are not bundled with this repository.

## October 3, 2026 bench results

- Apple M4, OpenCV 5.0.0, pinned YOLOX-S: sample images detected people, a car,
  bicycle, bus, and truck. Single-image inference was approximately 120 ms.
- Local H.264 RTP → OpenCV → Metal: active people/caution overlay passed;
  stopping the source removed both the old image and the caution.
- Suyin USB camera → Pi capture → Mac detection → Pi HEVC display: 450 rendered
  and encoded frames in 15 seconds, 102 inference results, no missed render ticks.
  The last analyzed frame's local pipeline age was 314 ms; this excludes unknown
  sensor/network offset and Pi presentation time. The image was current for
  433 of 450 HUD frames, including startup.
- Detector/state checks and four native HUD/media checks passed. The separate
  legacy synthetic HEVC sender loopback failed with the previously documented
  VideoToolbox `VTDecompressionSessionCreate returned -4` issue on retry.
