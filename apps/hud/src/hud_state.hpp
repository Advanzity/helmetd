#pragma once

#include "perception.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <optional>

namespace helmetd {
using Clock = std::chrono::steady_clock;
using Time = Clock::time_point;

// Bench inputs only. A future compute adapter must supply acquisition times and
// validity; it must not turn an old sensor value into a fresh one on every tick.
struct HudState {
  struct RtpStats {
    std::uint64_t pushed = 0, lost = 0, late = 0, jitter_ns = 0;
  } camera_rtp;
  struct ExtraCamera {
    RtpStats rtp;
    std::optional<Time> received_at;
    std::uint64_t frames = 0;
    bool failed = false;
    Advisory advisory = Advisory::none;
    std::optional<Time> detection_at;
    std::vector<Detection> detections;
    bool detection_failed = false;
    mutable Advisory displayed = Advisory::none;
    mutable std::optional<Time> displayed_at;
  };
  std::vector<ExtraCamera> extra_cameras;
  std::string notification_app, notification_sender;
  std::optional<Time> notification_at;
  std::string alert_preview;
  std::optional<Time> alert_preview_at;
  std::string confirmation;
  std::optional<Time> confirmation_at;
  struct Game {
    bool active = false, crashed = false;
    int speed_mph = 0, gear = 0, rpm = 0, warnings = 0;
    std::string signal = "off";
    std::optional<Time> received_at;
  } game;
  bool game_fresh(Time now) const {
    return game.active && fresh(game.received_at, now, std::chrono::milliseconds(1500));
  }
  std::string signal = "off";
  std::optional<Time> signal_until;
  std::string camera_view = "auto";
  std::optional<Time> camera_view_until;
  void set_signal(const std::string& value, Time now) {
    signal = value;
    signal_until = now + std::chrono::seconds(15);
    if (value != "off") panels |= 1;
  }
  std::string active_signal(Time now) const {
    if (game_fresh(now)) return game.crashed ? "off" : game.signal;
    return signal_until && now < *signal_until ? signal : "off";
  }
  bool extra_camera_fresh(std::size_t index, Time now) const {
    return index < extra_cameras.size() && camera_enabled && !extra_cameras[index].failed &&
        fresh(extra_cameras[index].received_at, now, std::chrono::milliseconds(500));
  }
  bool extra_camera_visible(std::size_t index, Time now) const {
    return index < extra_cameras.size() && camera_enabled && !extra_cameras[index].failed &&
        fresh(extra_cameras[index].received_at, now, std::chrono::milliseconds(1500));
  }
  bool camera_visible(Time now) const {
    return camera_enabled && fresh(camera_at, now, std::chrono::milliseconds(1500));
  }
  struct RouteMap {
    std::string mode = "none";
    std::vector<std::pair<int, int>> points;
    int x = -1, y = -1;
    std::optional<Time> received_at;
  } route_map;
  bool demo = false;
  struct Navigation {
    bool simulated = true;
    std::string state = "idle";
    std::string maneuver = "none";
    std::string destination = "No active route";
    int distance_m = -1;
    int remaining_m = -1;
    int remaining_s = -1;
    std::optional<Time> received_at;
  } navigation;
  unsigned panels = 7;
  bool diagnostics = false;
  bool quiet = false;
  std::string assistant_phase = "offline";
  std::optional<Time> assistant_at;
  int speed_mph = 32;
  int gear = 3;
  bool telemetry_enabled = true;
  bool camera_enabled = true;
  std::optional<Time> telemetry_at;
  std::optional<Time> camera_at;
  std::optional<Time> warning_until;
  bool perception_enabled = false;
  bool perception_failed = false;
  std::optional<Time> detection_at;
  std::vector<Detection> detections;
  Advisory advisory = Advisory::none;
  static constexpr std::chrono::milliseconds perception_budget{500};

  bool detection_fresh(Time now) const {
    return perception_enabled && !perception_failed && camera_enabled && camera_fresh(now) &&
        fresh(detection_at, now, perception_budget);
  }
  Advisory current_advisory(Time now) const {
    return detection_fresh(now) ? advisory : Advisory::none;
  }

  // Presentation debounce only: raw detections and voice observations remain unchanged.
  mutable Advisory displayed_advisory = Advisory::none;
  mutable std::optional<Time> displayed_advisory_at;
  Advisory display_advisory(Time now) const {
    if (!camera_fresh(now) || !camera_enabled || perception_failed || !perception_enabled) {
      displayed_advisory = Advisory::none;
      displayed_advisory_at.reset();
      return Advisory::none;
    }
    if (detection_fresh(now) && advisory != Advisory::none) {
      displayed_advisory = advisory;
      displayed_advisory_at = detection_at;
    }
    return fresh(displayed_advisory_at, now, std::chrono::milliseconds(2000))
        ? displayed_advisory : Advisory::none;
  }

  Advisory side_display_advisory(std::size_t index, Time now) const {
    auto& camera = extra_cameras[index];
    if (camera.detection_failed || !extra_camera_fresh(index, now)) {
      camera.displayed = Advisory::none;
      camera.displayed_at.reset();
      return Advisory::none;
    }
    if (fresh(camera.detection_at, now, perception_budget) && camera.advisory != Advisory::none) {
      camera.displayed = camera.advisory;
      camera.displayed_at = camera.detection_at;
    }
    return fresh(camera.displayed_at, now, std::chrono::milliseconds(2000))
        ? camera.displayed : Advisory::none;
  }

  void tick_simulation(Time now) {
    if (telemetry_enabled) telemetry_at = now;
  }
  void trigger_warning(Time now) { warning_until = now + std::chrono::seconds(5); }
  bool warning(Time now) const { return warning_until && now < *warning_until; }
  static bool fresh(std::optional<Time> received, Time now,
                    std::chrono::milliseconds budget) {
    return received && now >= *received && now - *received <= budget;
  }
  bool telemetry_fresh(Time now) const {
    return fresh(telemetry_at, now, std::chrono::milliseconds(1000));
  }
  bool camera_fresh(Time now) const {
    // Bound a short video hold across Wi-Fi jitter independently of inference.
    return camera_enabled && fresh(camera_at, now, std::chrono::milliseconds(500));
  }
  bool navigation_fresh(Time now) const {
    return fresh(navigation.received_at, now, std::chrono::milliseconds(3000));
  }
  void change_speed(int delta) { speed_mph = std::clamp(speed_mph + delta, 0, 160); }
  void next_gear() { gear = (gear + 1) % 7; }
};
}  // namespace helmetd
