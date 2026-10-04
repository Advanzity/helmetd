#include "hud_control.hpp"

#include <sys/file.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>
#include <fcntl.h>
#include <algorithm>
#include <cctype>
#include <cstring>
#include <filesystem>
#include <sstream>
#include <stdexcept>

namespace helmetd {
std::string handle_control(const std::string& request, HudState& state, Time now,
                           const HudOptions& options) {
  std::istringstream input(request);
  std::string id, command, value, setting, extra;
  input >> id >> command;
  if (id.empty() || id.size() > 40 || !std::all_of(id.begin(), id.end(),
      [](unsigned char c) { return std::isalnum(c); })) return "";
  auto error = [&] { return "{\"request_id\":\"" + id +
      "\",\"status\":\"error\",\"reason\":\"Unsupported HUD command\"}"; };
  if (command == "game") {
    HudState::Game game;
    int active, crashed;
    if (!(input >> active >> game.speed_mph >> game.gear >> game.rpm >> game.signal
                >> crashed >> game.warnings) || (input >> extra) ||
        active < 0 || active > 1 || crashed < 0 || crashed > 1 ||
        game.speed_mph < 0 || game.speed_mph > 336 || game.gear < -1 || game.gear > 6 ||
        game.rpm < 0 || game.rpm > 20000 || game.warnings < 0 || game.warnings > 511 ||
        (game.signal != "off" && game.signal != "left" && game.signal != "right")) return error();
    game.active = active;
    game.crashed = active && crashed;
    if (!active) { game.signal = "off"; game.warnings = 0; }
    game.received_at = now;
    state.game = game;
  } else if (command == "nav_map") {
    HudState::RouteMap map;
    int count;
    if (!(input >> map.mode >> map.x >> map.y >> count) || count < 0 || count > 32 ||
        (map.mode != "none" && map.mode != "preview" && map.mode != "active" && map.mode != "stale") ||
        map.x < -1 || map.y < -1 || map.x > 1000 || map.y > 1000 ||
        ((map.x == -1) != (map.y == -1)) ||
        (map.mode == "none" ? count != 0 : count < 2)) return error();
    for (int i = 0; i < count; ++i) {
      int x, y;
      if (!(input >> x >> y) || x < 0 || x > 1000 || y < 0 || y > 1000) return error();
      map.points.emplace_back(x, y);
    }
    if (input >> extra) return error();
    map.received_at = now;
    state.route_map = std::move(map);
  } else if (command == "nav" || command == "nav_live" || command == "game_nav") {
    HudState::Navigation nav;
    nav.from_game = command == "game_nav";
    nav.simulated = command != "nav_live";
    std::string label;
    if (!(input >> nav.state >> nav.maneuver >> nav.distance_m >> nav.remaining_m
                >> nav.remaining_s >> label) || (input >> extra)) return error();
    const auto one_of = [](const std::string& v, std::initializer_list<const char*> values) {
      return std::any_of(values.begin(), values.end(), [&](const char* item) { return v == item; });
    };
    if (!one_of(nav.state, {"idle", "navigating", "paused", "off_route", "location_lost", "arrived"}) ||
        !one_of(nav.maneuver, {"none", "straight", "left", "right", "uturn", "stop", "arrive"}) ||
        nav.distance_m < -1 || nav.distance_m > 10000000 ||
        nav.remaining_m < -1 || nav.remaining_m > 10000000 ||
        nav.remaining_s < -1 || nav.remaining_s > 604800 || label.empty() ||
        label.size() > 48 || label.size() % 2 != 0) return error();
    nav.destination.clear();
    const auto digit = [](char c) -> int {
      if (c >= '0' && c <= '9') return c - '0';
      if (c >= 'a' && c <= 'f') return c - 'a' + 10;
      return -1;
    };
    for (std::size_t i = 0; i < label.size(); i += 2) {
      const int high = digit(label[i]), low = digit(label[i + 1]);
      if (high < 0 || low < 0 || high * 16 + low < 32 || high * 16 + low > 126) return error();
      nav.destination += static_cast<char>(high * 16 + low);
    }
    if (nav.state == "idle" || nav.state == "off_route" || nav.state == "location_lost") {
      nav.maneuver = "none";
      nav.distance_m = nav.remaining_m = nav.remaining_s = -1;
    }
    nav.received_at = now;
    state.navigation = nav;
  } else {
  input >> value >> setting >> extra;
  if (!extra.empty()) return error();
  if (command == "status" && value.empty()) {
    // Read-only snapshot below.
  } else if (command == "mode" && setting.empty()) {
    if (value == "full") state.panels = 7;
    else if (value == "quiet") state.panels = navigation_panel | telemetry_panel;
    else if (value == "focus") state.panels = telemetry_panel;
    else if (value == "camera") state.panels = camera_panel | telemetry_panel;
    else if (value == "clear") state.panels = 0;
    else return error();
    state.quiet = value == "quiet";
  } else if (command == "signal" && setting.empty() &&
      (value == "left" || value == "right" || value == "off")) {
    state.set_signal(value, now);
  } else if (command == "camera" && setting.empty() &&
      (value == "front" || value == "left" || value == "right" || value == "rear" || value == "auto")) {
    state.camera_view = value;
    state.camera_view_until = now + std::chrono::seconds(8);
    state.panels |= camera_panel;
  } else if (command == "panel" && (setting == "on" || setting == "off")) {
    const unsigned bit = value == "camera" ? camera_panel : value == "nav" ? navigation_panel :
        value == "telemetry" ? telemetry_panel : 0;
    if (!bit) return error();
    if (setting == "on") state.panels |= bit;
    else state.panels &= ~bit;
  } else if (command == "diagnostics" && setting.empty() && (value == "on" || value == "off")) {
    state.diagnostics = value == "on";
  } else if (command == "preview" && setting.empty() &&
      (value == "left" || value == "right" || value == "rear" || value == "person" || value == "turn" || value == "message" || value == "pothole" || value == "debris" || value == "roadworks" || value == "slippery" || value == "off")) {
    state.alert_preview = value;
    state.alert_preview_at = now;
  } else if (command == "notification" && !value.empty() && !setting.empty() &&
      value.size() <= 20 && setting.size() <= 28) {
    const auto safe = [](const std::string& token) {
      return std::all_of(token.begin(), token.end(), [](unsigned char c) {
        return std::isalnum(c) || c == '_' || c == '-' || c == '.';
      });
    };
    if (!safe(value) || !safe(setting)) return error();
    std::replace(value.begin(), value.end(), '_', ' ');
    std::replace(setting.begin(), setting.end(), '_', ' ');
    state.notification_app = value;
    state.notification_sender = setting;
    state.notification_at = now;
  } else if (command == "notice" && setting.empty() &&
      (value == "saved" || value == "save_failed" || value == "muted")) {
    state.confirmation = value == "saved" ? "CLIP SAVED" : value == "muted" ? "AUDIO MUTED" : "SAVE UNAVAILABLE";
    state.confirmation_at = now;
  } else if (command == "phase" && setting.empty() &&
      (value == "listening" || value == "thinking" || value == "speaking" || value == "offline")) {
    state.assistant_phase = value;
    state.assistant_at = now;
  } else return error();
  }

  const bool fresh = state.detection_fresh(now);
  std::ostringstream out;
  const auto camera_detections = [&](bool valid, const std::vector<Detection>& detections) {
    out << ",\"detection_fresh\":" << valid << ",\"detections\":[";
    unsigned count = 0;
    if (valid) for (const auto& d : detections) {
      if (!valid_detection(d)) continue;
      if (count == 10) break;
      if (count++) out << ',';
      const float center = d.x + d.width / 2;
      out << "{\"label\":\"" << detection_label(d.class_id) << "\",\"confidence\":" << d.confidence
          << ",\"image_region\":\"" << (center < .33f ? "left" : center > .67f ? "right" : "center") << "\"}";
    }
    out << ']';
  };
  out << std::boolalpha << "{\"request_id\":\"" << id << "\",\"status\":\"ok\","
      << "\"panels\":" << state.panels << ",\"diagnostics\":" << state.diagnostics << ",\"quiet\":" << state.quiet
      << ",\"camera_source\":\"" << (state.game_fresh(now) ? "game" : options.camera) << "\",\"camera_fresh\":" << state.camera_fresh(now)
      << ",\"detection_enabled\":" << state.perception_enabled
      << ",\"detection_failed\":" << state.perception_failed
      << ",\"detection_fresh\":" << fresh << ",\"frame_age_ms\":";
  if (state.camera_at) out << std::max<long long>(0,
      std::chrono::duration_cast<std::chrono::milliseconds>(now - *state.camera_at).count());
  else out << "null";
  out << ",\"game_fresh\":" << state.game_fresh(now)
      << ",\"game_crashed\":" << (state.game_fresh(now) && state.game.crashed)
      << ",\"game_warning_mask\":" << (state.game_fresh(now) ? state.game.warnings : 0)
      << ",\"telemetry_source\":\"" << (state.game_fresh(now) ? "game" : state.demo ? "preview" : "unavailable") << "\"";
  out << ",\"telemetry_simulated\":" << (state.demo || state.game_fresh(now)) << ",\"navigation_simulated\":" << state.navigation.simulated << ','
      << "\"navigation_state\":\"" << (state.navigation_fresh(now) ? state.navigation.state : "unavailable")
      << "\",\"navigation_source\":\"" << (state.navigation.from_game ? "game" : "console")
      << "\",\"navigation_fresh\":" << state.navigation_fresh(now) << ",\"detections\":[";
  bool first = true;
  unsigned count = 0;
  if (fresh) for (const auto& d : state.detections) {
    if (!valid_detection(d)) continue;
    if (count++ == 10) break;
    const float center = d.x + d.width / 2;
    if (!first) out << ',';
    first = false;
    out << "{\"label\":\"" << detection_label(d.class_id) << "\",\"confidence\":" << d.confidence
        << ",\"image_region\":\"" << (center < 0.33f ? "left" : center > 0.67f ? "right" : "center") << "\"}";
  }
  out << "],\"signal\":\"" << state.active_signal(now) << "\",\"camera_view\":\"" << state.camera_view
      << "\",\"cameras\":[{\"label\":\"" << options.camera_label
      << "\",\"port\":" << options.camera_port << ",\"fresh\":" << state.camera_fresh(now)
      << ",\"visible\":" << state.camera_visible(now)
      << ",\"rtp_pushed\":" << state.camera_rtp.pushed << ",\"rtp_lost\":" << state.camera_rtp.lost
      << ",\"rtp_late\":" << state.camera_rtp.late << ",\"jitter_ms\":" << state.camera_rtp.jitter_ns / 1000000.0;
  camera_detections(fresh, state.detections);
  out << '}';
  for (std::size_t i = 0; i < options.extra_cameras.size(); ++i) {
    out << ",{\"label\":\"" << options.extra_cameras[i].label << "\",\"port\":" << options.extra_cameras[i].port
        << ",\"fresh\":" << state.extra_camera_fresh(i, now)
        << ",\"visible\":" << state.extra_camera_visible(i, now)
        << ",\"failed\":" << (i < state.extra_cameras.size() && state.extra_cameras[i].failed)
        << ",\"frames\":" << (i < state.extra_cameras.size() ? state.extra_cameras[i].frames : 0);
    const auto stats = i < state.extra_cameras.size() ? state.extra_cameras[i].rtp : HudState::RtpStats{};
    if (i < state.extra_cameras.size()) {
      const auto& camera = state.extra_cameras[i];
      out << ",\"detection_failed\":" << camera.detection_failed;
      camera_detections(!camera.detection_failed && state.extra_camera_fresh(i, now) &&
          HudState::fresh(camera.detection_at, now, std::chrono::milliseconds(500)), camera.detections);
    }
    out << ",\"rtp_pushed\":" << stats.pushed << ",\"rtp_lost\":" << stats.lost
        << ",\"rtp_late\":" << stats.late << ",\"jitter_ms\":" << stats.jitter_ns / 1000000.0 << '}';
  }
  out << "]}";
  return out.str();
}

HudControl::HudControl(const std::string& path) {
  if (path.empty()) return;
  sockaddr_un address{};
  if (path.size() >= sizeof(address.sun_path)) throw std::runtime_error("HUD control socket path too long");
  const auto parent = std::filesystem::path(path).parent_path();
  if (!parent.empty()) std::filesystem::create_directories(parent);
  lock_ = open((path + ".lock").c_str(), O_CREAT | O_RDWR | O_NOFOLLOW, 0600);
  if (lock_ < 0 || flock(lock_, LOCK_EX | LOCK_NB) < 0) {
    if (lock_ >= 0) close(lock_);
    throw std::runtime_error("Another HUD owns this control socket");
  }
  try {
    struct stat existing{};
    if (lstat(path.c_str(), &existing) == 0) {
      if (!S_ISSOCK(existing.st_mode) || existing.st_uid != getuid())
        throw std::runtime_error("Refusing to replace a non-owned control socket path");
      if (unlink(path.c_str()) < 0) throw std::runtime_error("Could not remove stale control socket");
    }
    socket_ = socket(AF_UNIX, SOCK_DGRAM, 0);
    if (socket_ < 0) throw std::runtime_error("Could not create HUD control socket");
    address.sun_family = AF_UNIX;
    std::memcpy(address.sun_path, path.c_str(), path.size() + 1);
    if (bind(socket_, reinterpret_cast<sockaddr*>(&address), sizeof(address)) < 0)
      throw std::runtime_error("Could not bind HUD control socket");
    path_ = path;
    if (chmod(path.c_str(), 0600) < 0) throw std::runtime_error("Could not protect HUD control socket");
  } catch (...) {
    if (socket_ >= 0) close(socket_);
    if (!path_.empty()) unlink(path_.c_str());
    close(lock_);
    throw;
  }
}

HudControl::~HudControl() {
  if (socket_ >= 0) close(socket_);
  if (!path_.empty()) unlink(path_.c_str());
  if (lock_ >= 0) close(lock_);
}

void HudControl::poll(HudState& state, Time now, const HudOptions& options) {
  if (socket_ < 0) return;
  // Bound per-frame work; all rendering and state mutation remain on this thread.
  for (int i = 0; i < 8; ++i) {
    char buffer[1025];
    sockaddr_un peer{};
    socklen_t length = sizeof(peer);
    const auto count = recvfrom(socket_, buffer, sizeof(buffer), MSG_DONTWAIT,
        reinterpret_cast<sockaddr*>(&peer), &length);
    if (count < 0) break;
    if (count == 0 || count > 1024) continue;
    const auto reply = handle_control(std::string(buffer, count), state, now, options);
    if (!reply.empty()) sendto(socket_, reply.data(), reply.size(), MSG_DONTWAIT,
        reinterpret_cast<const sockaddr*>(&peer), length);
  }
}
}  // namespace helmetd
