# Shared protocol

Language-neutral contracts between the Pi and Mac. `schemas/` and `examples/`
are reserved for the first agreed schema format and small validation fixtures.
No wire format or transport has been selected.

Define these contracts before integrating both applications:

| Contract | Required information |
| --- | --- |
| Session / capabilities | Protocol version, session identity, codecs, display modes, tracking capabilities. |
| Sensor sample | Sensor identity, units, sequence number, acquisition timestamp, validity. |
| Camera frame metadata | Stream/frame identity, capture timestamp, camera and calibration identity. |
| Pose | Timestamp, coordinate frame, position, orientation, tracking state, uncertainty if available. |
| Anchor | Anchor identity, map/session identity, transform, tracking state. |
| Rendered frame metadata | Frame identity, source pose/time, intended display time, view/projection data, calibration version. |
| Health / control | Heartbeat, stream configuration, errors, clock exchange, acknowledgements where needed. |

Video payloads belong in a media transport. Carry small telemetry/control
messages separately so large frames cannot block current pose and health data.
Metadata must associate with its exact media frame even if channels arrive out
of order.

Before defining numeric schemas, agree on:

- Coordinate handedness, axes, units, quaternion order, and transform direction.
- Camera, IMU, head, left-eye, right-eye, marker, and world frame definitions.
- Monotonic clock domains and clock-offset/drift estimation across computers.
- Sequence resets, tracking origin resets, map identity, and reconnect behavior.
- Version negotiation, stale-message rejection, and invalid-pose handling.

Share schemas across language boundaries; generate bindings only if the selected
stacks benefit from them. Do not import one app's internal models into the other.
