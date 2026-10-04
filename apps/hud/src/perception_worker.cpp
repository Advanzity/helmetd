#include "perception_worker.hpp"
#include <opencv2/imgproc.hpp>

namespace helmetd {
PerceptionWorker::PerceptionWorker(const std::string& model) : detector_(model) {
  cv::setNumThreads(4);
  thread_ = std::thread([this] { run(); });
}
PerceptionWorker::~PerceptionWorker() {
  {
    std::lock_guard lock(mutex_);
    stopping_ = true;
  }
  wake_.notify_one();
  thread_.join();
}
void PerceptionWorker::submit(const CameraFrame& frame) {
  std::lock_guard lock(mutex_);
  if (!error_.empty()) return;
  pending_ = frame;
  wake_.notify_one();
}
bool PerceptionWorker::poll(PerceptionResult& result) {
  std::lock_guard lock(mutex_);
  if (!completed_) return false;
  result = std::move(*completed_);
  completed_.reset();
  return true;
}
std::string PerceptionWorker::error() {
  std::lock_guard lock(mutex_);
  return error_;
}
void PerceptionWorker::run() {
  AdvisoryEvaluator evaluator;
  try {
    while (true) {
      PerceptionResult result;
      {
        std::unique_lock lock(mutex_);
        wake_.wait(lock, [this] { return stopping_ || pending_.has_value(); });
        if (stopping_) return;
        result.frame = std::move(*pending_);
        pending_.reset();
      }
      const auto before = Clock::now();
      if (!HudState::fresh(result.frame.received_at, before, std::chrono::milliseconds(250)))
        continue;
      cv::Mat bgra(CameraFrame::height, CameraFrame::width, CV_8UC4, result.frame.bgra.data()), bgr;
      cv::cvtColor(bgra, bgr, cv::COLOR_BGRA2BGR);
      result.detections = detector_.infer(bgr);
      result.inference_ms = std::chrono::duration<double, std::milli>(Clock::now() - before).count();
      result.advisory = evaluator.update(result.detections, result.frame.received_at);
      // Retain the source timestamp and image; finishing inference doesn't make
      // an old observation fresh, and boxes must never move onto a newer image.
      std::lock_guard lock(mutex_);
      completed_ = std::move(result);
    }
  } catch (const std::exception& e) {
    std::lock_guard lock(mutex_);
    error_ = e.what();
    pending_.reset();
    completed_.reset();
  }
}
}  // namespace helmetd
