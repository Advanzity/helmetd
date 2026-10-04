#include "hud_options.hpp"
#include "hud_state.hpp"

#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace helmetd;
using namespace std::chrono_literals;
void require(bool value, const char* description) {
  if (!value) throw std::runtime_error(description);
}
HudOptions options(std::vector<std::string> args) {
  std::vector<char*> argv;
  for (auto& arg : args) argv.push_back(arg.data());
  return parse_options(static_cast<int>(argv.size()), argv.data());
}
void rejects(std::vector<std::string> args) {
  bool rejected = false;
  try { options(std::move(args)); }
  catch (const std::runtime_error&) { rejected = true; }
  require(rejected, "Invalid options accepted");
}
int main() {
  try {
    const auto now = Clock::now();
    HudState state;
    require(!state.telemetry_fresh(now) && !state.camera_fresh(now), "Missing data must be unavailable");
    state.tick_simulation(now);
    state.telemetry_enabled = false;
    state.tick_simulation(now + 2s);
    require(!state.telemetry_fresh(now + 2s), "Disabled telemetry must expire");
    state.camera_at = now;
    require(state.camera_fresh(now + 200ms), "Recent camera frame should be visible");
    require(!state.camera_fresh(now + 501ms), "Delayed camera must not be reported live");
    require(state.camera_visible(now + 1000ms), "Short outage retains a labeled delayed image");
    require(!state.camera_visible(now + 1501ms), "Long outage must clear the held image");
    require(!state.camera_fresh(now - 1ms), "Future timestamps must not be fresh");
    state.perception_enabled = true;
    state.detection_at = now;
    state.advisory = Advisory::person;
    require(state.current_advisory(now + 200ms) == Advisory::person, "Fresh matched detection should show");
    require(state.current_advisory(now + 400ms) == Advisory::person, "Inference has a bounded 500ms budget");
    require(state.current_advisory(now + 501ms) == Advisory::none, "Old inference must not warn");
    require(state.current_advisory(now - 1ms) == Advisory::none, "Future inference must not warn");
    state.camera_at = now + 1ms;
    require(state.current_advisory(now + 200ms) == Advisory::person, "Fresh scene advisory survives a newer preview frame");
    state.camera_at = now;
    state.perception_failed = true;
    require(state.current_advisory(now) == Advisory::none, "Failed inference must not warn");
    state.perception_failed = false;
    state.camera_enabled = false;
    require(state.current_advisory(now) == Advisory::none, "Disabled camera must not warn");
    state.camera_enabled = true;
    state.trigger_warning(now);
    require(state.warning(now + 4999ms), "Triggered warning should be visible");
    require(!state.warning(now + 5s), "Warning must expire without further input");
    state.trigger_warning(now + 6s);
    state.warning_until.reset();
    require(!state.warning(now + 6s), "Warning should clear on operator input");
    state.change_speed(-1000);
    require(state.speed_mph == 0, "Simulated speed must not go negative");
    state.change_speed(1000);
    require(state.speed_mph == 160, "Simulated speed must be bounded");
    rejects({"hud", "--headless"});
    rejects({"hud", "--output", "test.mp4", "--frames", "0"});
    rejects({"hud", "--host", "127.0.0.1", "--output", "test.mp4"});
    rejects({"hud", "--fps", "0"});
    rejects({"hud", "--width", "641"});
    rejects({"hud", "--camera", "webcam"});
    rejects({"hud", "--camera", "udp", "--extra-camera", "LEFT:5002"});
    rejects({"hud", "--host", "127.0.0.1", "--extra-camera", "LEFT:5000"});
    rejects({"hud", "--extra-camera", "LEFT:5004", "--extra-camera", "RIGHT:5004"});
    rejects({"hud", "--extra-camera", "left:5004", "--extra-camera", "LEFT:5006"});
    rejects({"hud", "--extra-camera", "LEFT:0"});
    rejects({"hud", "--extra-camera", "L\"EFT:5004"});
    rejects({"hud", "--extra-camera", "A:5004", "--extra-camera", "B:5006", "--extra-camera", "C:5008", "--extra-camera", "D:5010"});
    const auto multi = options({"hud", "--camera-label", "front", "--extra-camera", "left:5004"});
    require(multi.camera_label == "FRONT" && multi.extra_cameras[0].label == "LEFT", "Camera role labels normalize");
    state.extra_cameras.resize(2);
    state.extra_cameras[0].received_at = now;
    state.extra_cameras[1].received_at = now + 400ms;
    require(!state.extra_camera_fresh(0, now + 600ms) && state.extra_camera_fresh(1, now + 600ms), "Each feed expires independently");
    state.extra_cameras[1].failed = true;
    require(!state.extra_camera_fresh(1, now + 200ms), "Failed side feed must disappear");
    state.set_signal("left", now);
    require(state.active_signal(now + 14s) == "left" && state.active_signal(now + 15s) == "off", "Demo signal auto-cancels");
    rejects({"hud", "--detect-model", "/nonexistent/helmetd-model.onnx"});
    rejects({"hud", "--panels", "camera,unknown"});
    rejects({"hud", "--panels", "camera,"});
    rejects({"hud", "--panels", "camera,camera"});
    rejects({"hud", "--panels", "none,nav"});
    require(options({"hud"}).panels == (camera_panel | navigation_panel | telemetry_panel),
        "All three panels should be visible by default");
    require(options({"hud", "--panels", "nav,telemetry"}).panels == (navigation_panel | telemetry_panel),
        "Panel selection must not enable the camera");
    const auto empty = options({"hud", "--panels", "none"});
    require(empty.panels == 0 && !empty.diagnostics, "Empty layout must have no diagnostics");
    require(options({"hud", "--diagnostics"}).diagnostics, "Diagnostics can be enabled explicitly");
    std::cout << "PASS: stale/invalid data, warning expiry, controls, and option guards.\n";
    return 0;
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
