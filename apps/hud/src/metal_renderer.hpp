#pragma once

#include "hud_options.hpp"
#include "hud_state.hpp"
#include "media.hpp"

#include <cstdint>
#include <memory>
#include <span>
#include <string>

namespace helmetd {
// Objective-C/Apple APIs stay behind this C++ interface.
class MetalRenderer {
 public:
  explicit MetalRenderer(const HudOptions& options);
  ~MetalRenderer();
  MetalRenderer(const MetalRenderer&) = delete;
  MetalRenderer& operator=(const MetalRenderer&) = delete;
  bool poll_events(HudState& state, Time now);
  std::span<const std::uint8_t> render(const HudState& state, const CameraFrame* camera,
      Time now, double elapsed, std::uint64_t frame, bool readback);
  void save_snapshot(const std::string& path);
  std::string device_name() const;
 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};
}  // namespace helmetd
