#include "hud_options.hpp"

#include <charconv>
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
}  // namespace

HudOptions parse_options(int argc, char** argv) {
  HudOptions o;
  bool frames_set = false;
  for (int i = 1; i < argc; ++i) {
    const std::string_view key(argv[i]);
    if (key == "--headless") { o.headless = true; continue; }
    if (key == "--warning") { o.warning = true; continue; }
    if (i + 1 == argc) throw std::runtime_error("Missing value for " + std::string(key));
    const std::string_view value(argv[++i]);
    if (key == "--host") o.host = value;
    else if (key == "--output") o.output = value;
    else if (key == "--snapshot") o.snapshot = value;
    else if (key == "--camera") o.camera = value;
    else if (key == "--port") o.port = number(value, 1, 65535, key);
    else if (key == "--camera-port") o.camera_port = number(value, 1, 65535, key);
    else if (key == "--width") o.width = number(value, 640, 1920, key);
    else if (key == "--height") o.height = number(value, 360, 1080, key);
    else if (key == "--fps") o.fps = number(value, 1, 60, key);
    else if (key == "--bitrate") o.bitrate = number(value, 100, 100000, key);
    else if (key == "--frames") { o.frames = number(value, 0, 1000000, key); frames_set = true; }
    else throw std::runtime_error("Unknown option: " + std::string(key));
  }
  if (!o.host.empty() && !o.output.empty()) throw std::runtime_error("Choose --host or --output, not both");
  if (o.width % 2 || o.height % 2) throw std::runtime_error("Video dimensions must be even");
  if (o.width * 9 != o.height * 16) throw std::runtime_error("This HUD layout requires a 16:9 frame");
  if (o.camera != "test" && o.camera != "udp" && o.camera != "none")
    throw std::runtime_error("--camera must be test, udp, or none");
  if (!o.output.empty() && !frames_set) o.frames = 150;
  if (!o.output.empty() && o.frames == 0) throw std::runtime_error("Recordings require a finite --frames value");
  if (o.headless && o.host.empty() && o.output.empty() && o.frames == 0)
    throw std::runtime_error("Headless preview requires a finite --frames value");
  if (o.camera == "udp" && !o.host.empty() && o.port == o.camera_port)
    throw std::runtime_error("Camera uplink and HUD downlink must use separate ports");
  check_path(o.output, ".mp4");
  check_path(o.snapshot, ".png");
  return o;
}

void print_usage() {
  std::cout <<
      "helmetd-hud [options]\n"
      "Native Metal HUD. Speed/gear and warnings are simulated bench inputs.\n"
      "  --host HOST        Send rendered HUD via HEVC RTP/UDP (payload 96)\n"
      "  --port N           Downlink UDP port (default 5000)\n"
      "  --output FILE.mp4  Record rendered HUD; default 150 frames\n"
      "  --snapshot FILE.png Save the final rendered frame\n"
      "  --camera MODE      test (default), udp (baseline H.264 RTP), or none\n"
      "  --camera-port N    Uplink UDP port (default 5002, payload 97)\n"
      "  --headless         Render offscreen without opening a window\n"
      "  --warning          Trigger a simulated five-second rear warning\n"
      "  --frames N         Stop after N frames; 0 = unlimited preview/UDP\n"
      "  --width/--height N Even 16:9 dimensions, 640x360..1920x1080\n"
      "  --fps N            1..60 (default 30)\n"
      "  --bitrate N        HEVC target kbps (default 4000)\n"
      "Keys: Space warning/clear; arrows speed; G gear; C camera stall;\n"
      "      T telemetry stall; Esc/Q quit. Ctrl-C finalizes output.\n"
      "Black pixels are the optical background; no world anchoring yet.\n";
}
}  // namespace helmetd
