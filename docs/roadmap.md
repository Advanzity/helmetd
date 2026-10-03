# Implementation roadmap

The [motorcycle feature brief](design/hud/feature-brief.md) defines the proposed
HUD states and a staged hackathon demo. UI simulation can proceed alongside the
hardware milestones below; it does not validate the spatial or transport path.

The four core project folders exist and the Mac synthetic test sender is
implemented. The Pi and glasses have not yet been tested. Follow the
[project inventory and creation order](repository-plan.md); each implementation
milestone should produce a small demonstration and a recorded result.

## 0. Prove hardware and tracking access

- Inventory the Pi, Mac, cameras/sensors, glasses firmware, and existing adapter.
- Display a Pi-generated test pattern through the adapter on the XREAL 1S.
- Record supported modes, power arrangement, and any exposed USB sensor devices.
- Determine whether glasses pose is accessible or external marker tracking is
  required. Confirm rigid camera mounting if using external tracking.

Done when: display output works and there is a demonstrated, documented route
to obtain position and orientation for the first anchor experiment. A video
connection alone does not complete the tracking requirement.

## 1. Prove the Mac-to-Pi display stream

- Render a test pattern/frame counter on the Mac and stream it over Wi-Fi.
- Decode and display it through the Pi and adapter.
- Measure latency, drops, queue growth, and reconnect behavior.
- Compare a small set of codec/transport candidates; record the working choice.

Done when: the stream is repeatable on the actual devices and bounded under
load, and disconnecting/reconnecting cannot leave an indefinitely stale image.
This validates transport; it is not yet a world-anchored HUD.

## 2. Define contracts and prove the uplink

- Select the application stacks based on milestones 0 and 1.
- Define minimal session, timing, sensor/pose, and frame-metadata contracts.
- Add one camera and the selected sensor/pose source, with acquisition timestamps.
- Display input and tracking health on the Mac; support a small replay fixture.
- Run uplink and downlink simultaneously on the same Wi-Fi connection.

Done when: the Mac receives identifiable, timestamped inputs while the Pi
continues displaying returned frames without accumulating stale work.

## 3. Demonstrate one world anchor

- Calibrate the capture-to-eye transforms and projection for the tested mode.
- Establish a known physical marker as the first world reference.
- Render one label from the current/predicted eye pose and return it to the Pi.
- Test head rotation and translation; measure static and moving alignment error.
- Test tracking loss, recovery, and world-origin resets.

Done when: the label stays aligned to the physical marker when seen through the
glasses during the agreed movement test, and invalid tracking removes the
overlay. Agree numeric error and latency limits before calling this passed.

## 4. Resolve latency and sustained operation

- Measure p50/p95 end-to-end latency, pose age, drops, temperature, and power.
- Test prediction and feasible local correction if movement exposes drift.
- Test Wi-Fi congestion, camera failure, Mac interruption, and device reconnects.
- Record whether the Mac-rendered architecture meets the agreed spatial target.

Done when: the full loop meets agreed alignment, latency, and recovery targets
during a sustained run. If it cannot, document and resolve the architectural
change before expanding features.

## 5. Expand the HUD

Add the selected sensor readouts, additional anchors, and application-specific
graphics. Add markerless tracking or anchor persistence only when required by
the intended experience. Introduce setup automation, startup services, and CI
around the working components.

## Next planning inputs

1. Is an XREAL Eye available, and which cameras/IMU are intended for the Pi?
2. Which MacBook chip and Pi configuration are available?
3. What should the first anchored label identify, and at what distance?
4. What motion, alignment error, and latency must the first demo tolerate?
