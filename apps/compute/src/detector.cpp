#include "detector.hpp"

#include <opencv2/imgproc.hpp>
#include <stdexcept>

namespace helmetd {
Detector::Detector(const std::string& model) : net_(cv::dnn::readNetFromONNX(model)) {
  if (net_.empty()) throw std::runtime_error("Cannot load YOLOX model: " + model);
  net_.setPreferableBackend(cv::dnn::DNN_BACKEND_OPENCV);
  net_.setPreferableTarget(cv::dnn::DNN_TARGET_CPU);
}
std::vector<Detection> Detector::infer(const cv::Mat& bgr) {
  if (bgr.empty() || bgr.type() != CV_8UC3)
    throw std::runtime_error("Detector expects a nonempty BGR image");
  const double scale = std::min(640.0 / bgr.cols, 640.0 / bgr.rows);
  cv::Mat padded(640, 640, CV_8UC3, cv::Scalar::all(114)), resized;
  cv::resize(bgr, resized, cv::Size(std::max(1, int(bgr.cols * scale)),
                                  std::max(1, int(bgr.rows * scale))));
  resized.copyTo(padded(cv::Rect(0, 0, resized.cols, resized.rows)));
  net_.setInput(cv::dnn::blobFromImage(padded, 1.0, cv::Size(640, 640), {}, true, false));
  return decode(net_.forward(), bgr.cols, bgr.rows);
}
std::vector<Detection> Detector::decode(const cv::Mat& output, int width, int height) {
  if (width <= 0 || height <= 0 || output.type() != CV_32F || output.dims != 3 ||
      output.size[0] != 1 || output.size[1] != 8400 || output.size[2] != 85 ||
      !output.isContinuous())
    throw std::runtime_error("Expected YOLOX-S output [1,8400,85]; use the pinned model");
  const float scale = std::min(640.f / width, 640.f / height);
  std::vector<cv::Rect> boxes;
  std::vector<float> scores;
  std::vector<int> classes;
  const float* row = output.ptr<float>();
  for (int stride : {8, 16, 32}) {
    const int cells = 640 / stride;
    for (int gy = 0; gy < cells; ++gy) for (int gx = 0; gx < cells; ++gx, row += 85) {
      const auto best = std::max_element(row + 5, row + 85);
      const int id = static_cast<int>(best - row - 5);
      const float score = row[4] * *best;
      if (!road_class(id) || !std::isfinite(score) || score < 0.5f || score > 1) continue;
      const float cx = (row[0] + gx) * stride / scale;
      const float cy = (row[1] + gy) * stride / scale;
      const float w = std::exp(row[2]) * stride / scale;
      const float h = std::exp(row[3]) * stride / scale;
      if (!std::isfinite(cx) || !std::isfinite(cy) || !std::isfinite(w) || !std::isfinite(h)) continue;
      const int left = int(std::clamp(cx - w / 2, 0.f, float(width)));
      const int top = int(std::clamp(cy - h / 2, 0.f, float(height)));
      const int right = int(std::clamp(cx + w / 2, 0.f, float(width)));
      const int bottom = int(std::clamp(cy + h / 2, 0.f, float(height)));
      if (right <= left || bottom <= top) continue;
      boxes.emplace_back(left, top, right - left, bottom - top);
      scores.push_back(score);
      classes.push_back(id);
    }
  }
  std::vector<int> keep;
  cv::dnn::NMSBoxesBatched(boxes, scores, classes, 0.5f, 0.45f, keep);
  std::vector<Detection> detections;
  for (int i : keep) {
    const auto& b = boxes[i];
    detections.push_back({classes[i], scores[i], float(b.x) / width, float(b.y) / height,
                          float(b.width) / width, float(b.height) / height});
    if (detections.size() == 32) break;
  }
  return detections;
}
}  // namespace helmetd
