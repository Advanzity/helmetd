#pragma once

#include <string>
#include <vector>

namespace helmetd {
enum HudPanel : unsigned { camera_panel = 1, navigation_panel = 2, telemetry_panel = 4 };
struct HudOptions {
  struct ExtraCamera { std::string label; int port; };
  std::string camera_label = "CAMERA 1";
  std::vector<ExtraCamera> extra_cameras;
  std::string host;
  std::string output;
  std::string record_dir;
  std::string snapshot;
  std::string camera = "test";
  std::string detect_model;
  std::string control_socket;
  int port = 5000;
  int camera_port = 5002;
  int voice_port = 0;
  int width = 1280;
  int height = 720;
  int fps = 30;
  int bitrate = 4000;
  int frames = 0;
  bool demo = false;
  bool headless = false;
  bool warning = false;
  unsigned panels = camera_panel | navigation_panel | telemetry_panel;
  bool diagnostics = false;
};
HudOptions parse_options(int argc, char** argv);
void print_usage();
}  // namespace helmetd
