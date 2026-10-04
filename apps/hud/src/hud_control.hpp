#pragma once

#include "hud_options.hpp"
#include "hud_state.hpp"
#include <string>

namespace helmetd {
std::string handle_control(const std::string& request, HudState& state, Time now,
                           const HudOptions& options);

class HudControl {
 public:
  explicit HudControl(const std::string& path);
  ~HudControl();
  HudControl(const HudControl&) = delete;
  HudControl& operator=(const HudControl&) = delete;
  void poll(HudState& state, Time now, const HudOptions& options);
 private:
  int socket_ = -1, lock_ = -1;
  std::string path_;
};
}  // namespace helmetd
