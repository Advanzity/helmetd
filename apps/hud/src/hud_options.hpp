#pragma once

#include <string>

namespace helmetd {
struct HudOptions {
  std::string host;
  std::string output;
  std::string snapshot;
  std::string camera = "test";
  int port = 5000;
  int camera_port = 5002;
  int width = 1280;
  int height = 720;
  int fps = 30;
  int bitrate = 4000;
  int frames = 0;
  bool headless = false;
  bool warning = false;
};
HudOptions parse_options(int argc, char** argv);
void print_usage();
}  // namespace helmetd
