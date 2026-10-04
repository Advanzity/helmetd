#pragma once

#include "perception.hpp"
#include <opencv2/core.hpp>
#include <opencv2/dnn.hpp>

namespace helmetd {
// OpenCV Zoo YOLOX-S 2022nov: RGB, unscaled 0..255, top-left 640x640 letterbox.
class Detector {
 public:
  explicit Detector(const std::string& model);
  std::vector<Detection> infer(const cv::Mat& bgr);
  static std::vector<Detection> decode(const cv::Mat& output, int width, int height);
 private:
  cv::dnn::Net net_;
};
}  // namespace helmetd
