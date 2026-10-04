#include "hud_options.hpp"

#include <charconv>
#include <algorithm>
#include <cctype>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string_view>

namespace helmetd {
namespace {
int number(std::string_view value, int low, int high, std::string_view name) {
  int result = 0;
  const auto [end, error] = std::from_chars(value.data(), value.data() + value.size(), result);
  if (error != std::errc{} || end != value.data() + value.size() || result < low || result > high)
    throw std::runtime_error(std::string(name) + " must be " + std::to_string(low) + ".." + std::to_string(high));
  return result;
}
void check_path(const std::string& path, std::string_view extension) {
  if (path.empty()) return;
  if (std::filesystem::path(path).extension() != extension)
    throw std::runtime_error("Expected " + std::string(extension) + " output: " + path);
  if (std::filesystem::exists(path)) throw std::runtime_error("Output already exists: " + path);
  const auto parent = std::filesystem::path(path).parent_path();
  if (!parent.empty() && !std::filesystem::is_directory(parent))
    throw std::runtime_error("Output directory does not exist: " + parent.string());
}
unsigned panels(std::string_view value) {
  if (value == "all") return camera_panel | navigation_panel | telemetry_panel;
  if (value == "none") return 0;
  unsigned result = 0;
  for (;;) {
    const auto comma = value.find(',');
    const auto name = value.substr(0, comma);
    unsigned panel = 0;
    if (name == "camera") panel = camera_panel;
    else if (name == "nav") panel = navigation_panel;
    else if (name == "telemetry") panel = telemetry_panel;
    else throw std::runtime_error("--panels must be all, none, or a comma-separated list of camera,nav,telemetry");
    if (result & panel) throw std::runtime_error("Duplicate --panels entry: " + std::string(name));
    result |= panel;
    if (comma == std::string_view::npos) return result;
    value.remove_prefix(comma + 1);
  }
}
bool valid_label(std::string_view label) {
  return !label.empty() && label.size() <= 16 &&
      std::all_of(label.begin(), label.end(), [](unsigned char c) {
        return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
            (c >= '0' && c <= '9') || c == ' ' || c == '-';
      });
}
}  // namespace

HudOptions parse_options(int argc, char** argv) {
  HudOptions o;
  bool frames_set = false;
  for (int i = 1; i < argc; ++i) {
    const std::string_view key(argv[i]);
    if (key == "--demo") { o.demo = true; continue; }
    if (key == "--headless") { o.headless = true; continue; }
    if (key == "--warning") { o.warning = true; continue; }
    if (key == "--diagnostics") { o.diagnostics = true; continue; }
    if (i + 1 == argc) throw std::runtime_error("Missing value for " + std::string(key));
    const std::string_view value(argv[++i]);
    if (key == "--host") o.host = value;
    else if (key == "--output") o.output = value;
    else if (key == "--snapshot") o.snapshot = value;
    else if (key == "--camera") o.camera = value;
    else if (key == "--detect-model") o.detect_model = value;
    else if (key == "--control-socket") o.control_socket = value;
    else if (key == "--panels") o.panels = panels(value);
    else if (key == "--port") o.port = number(value, 1, 65535, key);
    else if (key == "--camera-port") o.camera_port = number(value, 1, 65535, key);
    else if (key == "--camera-label") {
      if (!valid_label(value)) throw std::runtime_error("Camera label must contain 1..16 letters, digits, spaces or hyphens");
      o.camera_label = value;
    }
    else if (key == "--extra-camera") {
      const auto colon = value.find(':');
      if (colon == std::string_view::npos || !valid_label(value.substr(0, colon)) || o.extra_cameras.size() == 3)
        throw std::runtime_error("--extra-camera expects LABEL:PORT; at most three extra cameras");
      o.extra_cameras.push_back({std::string(value.substr(0, colon)), number(value.substr(colon + 1), 1, 65535, key)});
    }
    else if (key == "--voice-port") o.voice_port = number(value, 1, 65535, key);
    else if (key == "--width") o.width = number(value, 640, 1920, key);
    else if (key == "--height") o.height = number(value, 360, 1080, key);
    else if (key == "--fps") o.fps = number(value, 1, 60, key);
    else if (key == "--bitrate") o.bitrate = number(value, 100, 100000, key);
    else if (key == "--record-dir") o.record_dir = value;
    else if (key == "--frames") { o.frames = number(value, 0, 1000000, key); frames_set = true; }
    else throw std::runtime_error("Unknown option: " + std::string(key));
  }
  if (!o.host.empty() && !o.output.empty()) throw std::runtime_error("Choose --host or --output, not both");
  if (o.width % 2 || o.height % 2) throw std::runtime_error("Video dimensions must be even");
  if (o.width * 9 != o.height * 16) throw std::runtime_error("This HUD layout requires a 16:9 frame");
  if (o.camera != "test" && o.camera != "udp" && o.camera != "none")
    throw std::runtime_error("--camera must be test, udp, or none");
  if (!o.detect_model.empty() && (o.camera == "none" || !std::filesystem::is_regular_file(o.detect_model)))
    throw std::runtime_error("--detect-model needs an existing YOLOX ONNX file and an enabled camera");
  if (!o.output.empty() && !frames_set) o.frames = 150;
  if (o.voice_port && o.detect_model.empty())
    throw std::runtime_error("--voice-port requires --detect-model");
  if (!o.output.empty() && o.frames == 0) throw std::runtime_error("Recordings require a finite --frames value");
  if (o.headless && o.host.empty() && o.output.empty() && o.frames == 0)
    throw std::runtime_error("Headless preview requires a finite --frames value");
  if (o.camera == "udp" && !o.host.empty() && o.port == o.camera_port)
    throw std::runtime_error("Camera uplink and HUD downlink must use separate ports");
  check_path(o.output, ".mp4");
  auto upper = [](std::string& label) {
    std::transform(label.begin(), label.end(), label.begin(), [](unsigned char c) { return std::toupper(c); });
  };
  upper(o.camera_label);
  for (auto& camera : o.extra_cameras) upper(camera.label);
  for (std::size_t i = 0; i < o.extra_cameras.size(); ++i) {
    const auto& camera = o.extra_cameras[i];
    if ((o.camera == "udp" && camera.port == o.camera_port) ||
        (!o.host.empty() && camera.port == o.port))
      throw std::runtime_error("Every camera and HUD downlink must use separate ports");
    for (std::size_t j = 0; j < i; ++j)
      if (camera.port == o.extra_cameras[j].port || camera.label == o.extra_cameras[j].label)
        throw std::runtime_error("Extra camera ports and labels must be unique");
    if (camera.label == o.camera_label) throw std::runtime_error("Camera labels must be unique");
  }
  check_path(o.snapshot, ".png");
  return o;
}

void print_usage() {
  std::cout <<
      "helmetd-hud [options]\n"
      "Native Metal HUD. Speed/gear are simulated; visual alerts require --detect-model.\n"
      "  --host HOST        Send rendered HUD via HEVC RTP/UDP (payload 96)\n"
      "  --port N           Downlink UDP port (default 5000)\n"
      "  --output FILE.mp4  Record rendered HUD; default 150 frames\n"
      "  --snapshot FILE.png Save the final rendered frame\n"
      "  --record-dir DIR    Keep bounded rolling H.264 clips per camera\n"
      "  --camera MODE      test (default), udp (baseline H.264 RTP), or none\n"
      "  --camera-port N    Uplink UDP port (default 5002, payload 97)\n"
      "  --camera-label NAME Primary camera label (default CAMERA 1)\n"
      "  --extra-camera LABEL:PORT Add an independent UDP feed; repeat up to three times\n"
      "  --detect-model FILE Enable OpenCV YOLOX boxes and image-based caution cues\n"
      "  --voice-port N     Publish fresh caution cues to localhost UDP (e.g. 8014)\n"
      "  --control-socket FILE Local Unix socket for voice controls and status\n"
      "  --panels LIST      all (default), none, or camera,nav,telemetry\n"
      "  --diagnostics      Show header, transport label, and frame counter\n"
      "  --demo             Enable simulated speed/gear and warning controls\n"
      "  --headless         Render offscreen without opening a window\n"
      "  --warning          Trigger a simulated five-second rear warning\n"
      "  --frames N         Stop after N frames; 0 = unlimited preview/UDP\n"
      "  --width/--height N Even 16:9 dimensions, 640x360..1920x1080\n"
      "  --fps N            1..60 (default 30)\n"
      "  --bitrate N        HEVC target kbps (default 4000)\n"
      "Keys: 1 camera panel; 2 demo navigation; 3 speed/gear/alerts; D diagnostics;\n"
      "      Space warning/clear; arrows speed; G gear; C camera stall;\n"
      "      L/R demo signal; B rear view; X clear; T telemetry stall; Esc/Q quit.\n"
      "Default navigation is simulated; the local console can supply live guidance.\n"
      "Black pixels are the optical background; no world anchoring yet.\n";
}
}  // namespace helmetd
