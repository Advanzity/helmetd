#pragma once

#include "hud_options.hpp"
#include "hud_state.hpp"

#include <gst/app/gstappsrc.h>
#include <gst/app/gstappsink.h>

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace helmetd {
struct CameraFrame {
  static constexpr int width = 640;
  static constexpr int height = 360;
  std::vector<std::uint8_t> bgra;
  Time received_at{};
};

// All calls are on the render thread; GStreamer owns its media worker threads.
class CameraInput {
 public:
  explicit CameraInput(const HudOptions& options);
  ~CameraInput();
  CameraInput(const CameraInput&) = delete;
  CameraInput& operator=(const CameraInput&) = delete;
  bool poll(CameraFrame& frame);
  bool failed() const { return failed_; }
  HudState::RtpStats stats() const;
 private:
  GstElement* pipeline_ = nullptr;
  GstAppSink* sink_ = nullptr;
  GstBus* bus_ = nullptr;
  bool failed_ = false;
  Time retry_at_{};
  Time last_sample_at_{};
};

class VideoOutput {
 public:
  explicit VideoOutput(const HudOptions& options);
  ~VideoOutput();
  VideoOutput(const VideoOutput&) = delete;
  VideoOutput& operator=(const VideoOutput&) = delete;
  bool enabled() const { return pipeline_ != nullptr; }
  void push(const void* bgra, std::size_t bytes, std::uint64_t timestamp_ns,
            std::uint64_t frame_id);
  void finish();
  unsigned encoded() const { return encoded_.load(); }
  unsigned submitted() const { return submitted_; }
 private:
  GstElement* pipeline_ = nullptr;
  GstAppSrc* source_ = nullptr;
  GstBus* bus_ = nullptr;
  std::atomic<unsigned> encoded_{0};
  unsigned submitted_ = 0;
  int fps_ = 30;
  bool finished_ = false;
};
}  // namespace helmetd
