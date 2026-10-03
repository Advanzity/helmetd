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
void rejects(std::vector<std::string> args) {
  std::vector<char*> argv;
  for (auto& arg : args) argv.push_back(arg.data());
  bool rejected = false;
  try { parse_options(static_cast<int>(argv.size()), argv.data()); }
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
    require(!state.camera_fresh(now + 251ms), "Stale camera frame must be hidden");
    require(!state.camera_fresh(now - 1ms), "Future timestamps must not be fresh");
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
    std::cout << "PASS: stale/invalid data, warning expiry, controls, and option guards.\n";
    return 0;
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
