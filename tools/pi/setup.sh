#!/usr/bin/env bash
# Run on the Pi. Installs only media tools needed by the bench applications.
set -euo pipefail
sudo apt-get update
sudo apt-get -o DPkg::Lock::Timeout=60 install -y \
  python3-gi python3-gst-1.0 gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 \
  gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libcamera v4l-utils
for element in v4l2slh265dec waylandsink x264enc rtph264pay rtph265depay; do
  gst-inspect-1.0 "$element" >/dev/null
done
printf '%s\n' 'Pi media dependencies are ready.'
