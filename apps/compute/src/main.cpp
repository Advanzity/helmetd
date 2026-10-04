#include "detector.hpp"
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <stdexcept>

int main(int argc, char** argv) {
  if (argc != 4) {
    std::cout << "helmetd-detect MODEL.onnx INPUT_IMAGE OUTPUT.png\n"
                 "Single-image detector check; live alerts run in helmetd-hud.\n";
    return argc == 2 && std::string(argv[1]) == "--help" ? 0 : 1;
  }
  try {
    if (std::filesystem::exists(argv[3])) throw std::runtime_error("Output already exists");
    cv::setNumThreads(4);
    helmetd::Detector detector(argv[1]);
    auto image = cv::imread(argv[2]);
    const auto before = std::chrono::steady_clock::now();
    const auto detections = detector.infer(image);
    std::cout << "Inference ms: " << std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - before).count() << '\n';
    for (const auto& d : detections) {
      const cv::Rect box(int(d.x * image.cols), int(d.y * image.rows),
                         int(d.width * image.cols), int(d.height * image.rows));
      cv::rectangle(image, box, {0, 200, 255}, 2);
      const std::string label = std::string(helmetd::detection_label(d.class_id)) + " " +
          std::to_string(int(d.confidence * 100)) + "%";
      cv::putText(image, label, {box.x, std::max(20, box.y - 5)},
                  cv::FONT_HERSHEY_SIMPLEX, 0.6, {0, 200, 255}, 2);
      std::cout << std::fixed << std::setprecision(3) << label << " box="
                << d.x << ',' << d.y << ',' << d.width << ',' << d.height << '\n';
    }
    if (!cv::imwrite(argv[3], image)) throw std::runtime_error("Cannot write result image");
    std::cout << "Detections: " << detections.size() << "; output: " << argv[3] << '\n';
    return 0;
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
