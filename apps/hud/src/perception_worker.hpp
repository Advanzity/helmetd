#pragma once

#include "detector.hpp"
#include "media.hpp"
#include <condition_variable>
#include <mutex>
#include <thread>

namespace helmetd {
struct PerceptionResult {
  CameraFrame frame;
  std::vector<Detection> detections;
  Advisory advisory = Advisory::none;
  double inference_ms = 0;
};

// One pending image and one completed result. Inference never blocks rendering;
// overloaded inputs replace the pending image rather than building a backlog.
class PerceptionWorker {
 public:
  explicit PerceptionWorker(const std::string& model);
  ~PerceptionWorker();
  void submit(const CameraFrame& frame);
  bool poll(PerceptionResult& result);
  std::string error();
 private:
  void run();
  Detector detector_;
  std::mutex mutex_;
  std::condition_variable wake_;
  std::optional<CameraFrame> pending_;
  std::optional<PerceptionResult> completed_;
  std::string error_;
  bool stopping_ = false;
  std::thread thread_;
};
}  // namespace helmetd
