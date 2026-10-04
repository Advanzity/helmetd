#include "hud_control.hpp"
#include <iostream>
#include <stdexcept>

int main() {
  using namespace helmetd;
  using namespace std::chrono_literals;
  try {
    HudState state;
    HudOptions options;
    const auto now = Clock::now();
    auto require = [](bool ok) { if (!ok) throw std::runtime_error("Control assertion failed"); };
    require(handle_control("map nav_map active 100 200 3 0 0 500 500 1000 1000", state, now, options).find("error") == std::string::npos);
    require(state.route_map.points.size() == 3 && state.route_map.x == 100);
    for (const auto& invalid : {"map nav_map active 0 0 33", "map nav_map active -1 0 2 0 0 1 1",
         "map nav_map active 0 0 2 0 0 1001 1", "map nav_map none -1 -1 2 0 0 1 1",
         "map nav_map active 0 0 2 0 0 1 1 extra"}) {
      require(handle_control(invalid, state, now, options).find("error") != std::string::npos);
      require(state.route_map.points.size() == 3);
    }
    handle_control("ack notice saved", state, now, options);
    require(state.confirmation == "CLIP SAVED" && state.confirmation_at == now);
    require(handle_control("ack notice arbitrary", state, now, options).find("error") != std::string::npos);
    handle_control("sig signal left", state, now, options);
    require(state.active_signal(now) == "left");
    require(handle_control("sig signal hazard", state, now, options).find("error") != std::string::npos);
    handle_control("sig signal right", state, now, options);
    require(state.active_signal(now) == "right");
    handle_control("sig signal off", state, now, options);
    require(state.active_signal(now) == "off");
    handle_control("cam camera rear", state, now, options);
    require(state.camera_view == "rear");
    require(state.camera_view_until == now + 8s);
    handle_control("n notification Messages Alex_Smith", state, now, options);
    require(state.notification_app == "Messages" && state.notification_sender == "Alex Smith");
    require(HudState::fresh(state.notification_at, now + 2s, 3000ms));
    require(!HudState::fresh(state.notification_at, now + 4s, 3000ms));
    require(handle_control("n notification Messages Alex body", state, now, options).find("error") != std::string::npos);
    require(state.notification_sender == "Alex Smith");
    require(handle_control("cam camera roof", state, now, options).find("error") != std::string::npos);
    handle_control("cam camera auto", state, now, options);
    require(handle_control("abc mode focus", state, now, options).find("\"status\":\"ok\"") != std::string::npos);
    require(state.panels == telemetry_panel && state.camera_enabled);
    handle_control("abc panel camera on", state, now, options);
    handle_control("abc panel camera on", state, now, options);
    require(state.panels == (camera_panel | telemetry_panel));
    require(handle_control("abc panel camera on extra", state, now, options).find("error") != std::string::npos);
    require(state.panels == (camera_panel | telemetry_panel));
    require(handle_control("bad\"id mode clear", state, now, options).empty());
    state.perception_enabled = true;
    state.camera_at = state.detection_at = now;
    state.detections = {{0, .9f, .1f, .1f, .3f, .7f}};
    require(handle_control("abc status", state, now, options).find("PERSON") != std::string::npos);
    const auto stale = handle_control("abc status", state, now + 501ms, options);
    require(stale.find("PERSON") == std::string::npos);
    require(stale.find("\"detection_fresh\":false") != std::string::npos);
    handle_control("abc phase speaking", state, now, options);
    require(state.assistant_phase == "speaking" && state.assistant_at == now);
    handle_control("abc mode quiet", state, now, options);
    require(state.quiet && state.panels == (navigation_panel | telemetry_panel));
    require(handle_control("abc status", state, now, options).find("\"quiet\":true") != std::string::npos);
    handle_control("abc mode full", state, now, options);
    require(!state.quiet);
    handle_control("abc mode clear", state, now, options);
    require(state.panels == 0 && state.camera_enabled && state.perception_enabled);
    require(handle_control("abc nav navigating left 120 2000 240 5269646765", state, now, options)
                .find("\"navigation_state\":\"navigating\"") != std::string::npos);
    require(state.navigation.destination == "Ridge" && state.navigation.distance_m == 120);
    require(state.navigation_fresh(now + 2999ms) && !state.navigation_fresh(now + 3001ms));
    for (const auto& invalid : {"abc nav navigating left -2 100 20 41",
         "abc nav navigating left 5 10 20 zz", "abc nav navigating left 5 10 20 0a",
         "abc nav navigating left 5 10 20 41 extra", "abc nav flying left 5 10 20 41"}) {
      require(handle_control(invalid, state, now, options).find("error") != std::string::npos);
      require(state.navigation.destination == "Ridge" && state.navigation.distance_m == 120);
    }
    handle_control("abc nav location_lost left 120 2000 240 5269646765", state, now, options);
    require(state.navigation.maneuver == "none" && state.navigation.distance_m == -1);
    require(handle_control("abc nav_live navigating right 80 1000 120 43616665", state, now, options)
                .find("\"navigation_simulated\":false") != std::string::npos);
    require(!state.navigation.simulated && state.navigation.destination == "Cafe");
    require(handle_control("abc status", state, now + 3001ms, options)
                .find("\"navigation_state\":\"unavailable\"") != std::string::npos);
    options.extra_cameras.push_back({"LEFT", 5004});
    state.extra_cameras.resize(1);
    state.extra_cameras[0].received_at = now;
    state.extra_cameras[0].detection_at = now;
    state.extra_cameras[0].detections = {{2, .9f, .1f, .1f, .3f, .7f}};
    require(handle_control("side status", state, now, options).find("CAR") != std::string::npos);
    require(handle_control("side status", state, now + 501ms, options).find("CAR") == std::string::npos);
    state.camera_enabled = state.perception_enabled = true;
    state.perception_failed = false;
    state.camera_at = state.detection_at = now;
    state.advisory = Advisory::person;
    require(state.display_advisory(now) == Advisory::person);
    state.advisory = Advisory::none;
    state.camera_at = state.detection_at = now + 400ms;
    require(state.current_advisory(now + 400ms) == Advisory::none);
    require(state.display_advisory(now + 400ms) == Advisory::person);
    require(state.display_advisory(now + 651ms) == Advisory::person);
    state.camera_at = state.detection_at = now + 2001ms;
    require(state.display_advisory(now + 2001ms) == Advisory::none);
    state.camera_at = state.detection_at = now + 400ms;
    state.advisory = Advisory::person;
    require(state.display_advisory(now + 400ms) == Advisory::person);
    require(state.display_advisory(now + 901ms) == Advisory::none);
    HudState gap;
    gap.perception_enabled = true;
    gap.camera_at = gap.detection_at = now;
    gap.advisory = Advisory::person;
    require(gap.display_advisory(now) == Advisory::person);
    gap.camera_at = now + 700ms;
    require(!gap.detection_fresh(now + 700ms));
    require(gap.display_advisory(now + 700ms) == Advisory::person);
    gap.camera_at = now + 2001ms;
    require(gap.display_advisory(now + 2001ms) == Advisory::none);
    std::cout << "PASS: allowlisted controls, idempotence, phase and scene freshness.\n";
    return 0;
  } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
