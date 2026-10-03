# Development tools

Add executable utilities as their milestones are implemented:

- Display test pattern and frame counter.
- Hardware capability and connection diagnostics.
- Synthetic sensor/pose input and recorded-session replay.
- Stream latency, dropped-frame, bandwidth, and thermal measurements.
- Calibration capture and validation.
- Device setup and application launch scripts once the stack is selected.

Keep utilities small and document their dependencies. Generated reports and
captures belong in the ignored root `artifacts/` and `recordings/` directories.
