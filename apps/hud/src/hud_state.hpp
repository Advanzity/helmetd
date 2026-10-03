#pragma once

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
  int speed_mph = 32;
  int gear = 3;
  bool telemetry_enabled = true;
  bool camera_enabled = true;
  std::optional<Time> telemetry_at;
  std::optional<Time> camera_at;
  std::optional<Time> warning_until;

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
    return fresh(camera_at, now, std::chrono::milliseconds(250));
  }
  void change_speed(int delta) { speed_mph = std::clamp(speed_mph + delta, 0, 160); }
  void next_gear() { gear = (gear + 1) % 7; }
};
}  // namespace helmetd
