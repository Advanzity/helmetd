# Calibration

Reserve this directory for calibration procedures, profile schemas, and small
approved reference profiles. Store raw images and personal/device-specific
measurements in the ignored root `.local/` or `recordings/` directories.

A world-anchored overlay needs:

- Camera intrinsics and lens distortion at the actual capture mode.
- Known marker dimensions for the first metric-scale tracking experiment.
- Rigid transforms between cameras, IMU, glasses/head, and each eye.
- Per-eye projection/display alignment, eye spacing, and verified eye order.
- Timestamp offsets between acquisition devices and their host clock.
- A defined world origin plus tracking reset/relocalization behavior.

Each profile should identify its devices, capture/display modes, version,
measurement procedure, and alignment error. Recalibrate after mount movement,
fit changes, or relevant mode changes. A helmet-mounted camera cannot be assumed
to maintain an exact transform to glasses that can move independently.
