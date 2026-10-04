#include "detector.hpp"
#include <iostream>
#include <limits>
#include <stdexcept>

using namespace helmetd;
using namespace std::chrono_literals;
void require(bool value, const char* message) {
  if (!value) throw std::runtime_error(message);
}
int main() {
  try {
    const auto now = std::chrono::steady_clock::now();
    const Detection person{0, 0.9f, 0.4f, 0.2f, 0.2f, 0.6f};
    const Detection car{2, 0.9f, 0.3f, 0.4f, 0.4f, 0.4f};
    AdvisoryEvaluator rules;
    require(rules.update({person}, now) == Advisory::none, "One image must not warn");
    require(rules.update({person}, now + 100ms) == Advisory::none, "Two images must not warn");
    require(rules.update({person}, now + 200ms) == Advisory::person, "Persistent person should warn");
    require(rules.update({}, now + 300ms) == Advisory::none, "Empty observation must clear cue");
    require(rules.update({car}, now + 400ms) == Advisory::none, "New vehicle needs confirmation");
    rules.update({car}, now + 500ms);
    require(rules.update({car}, now + 600ms) == Advisory::vehicle, "Large persistent car should warn");
    require(rules.update({car}, now + 2s) == Advisory::none, "Long gap must reset confirmation");
    require(rules.update({car}, now + 1s) == Advisory::none, "Out-of-order frame must not warn");
    for (auto bad : std::vector<Detection>{
        {0, 0.55f, 0.4f, 0.2f, 0.2f, 0.6f}, // weak confidence
        {0, 0.9f, 0, 0.2f, 0.15f, 0.6f},   // outside watch zone
        {2, 0.9f, 0.4f, 0.4f, 0.1f, 0.2f}, // small vehicle
        {0, 0.9f, 0.4f, 0.2f, -1, 0.6f},   // malformed geometry
        {0, std::numeric_limits<float>::quiet_NaN(), 0.4f, 0.2f, 0.2f, 0.6f}}) {
      AdvisoryEvaluator check;
      for (int i = 0; i < 5; ++i)
        require(check.update({bad}, now + i * 100ms) == Advisory::none, "Invalid/non-caution candidate warned");
    }
    AdvisoryEvaluator switching;
    switching.update({person}, now);
    switching.update({car}, now + 100ms);
    require(switching.update({person}, now + 200ms) == Advisory::none, "Different objects must not share persistence");
    AdvisoryEvaluator relabelled;
    auto truck = car; truck.class_id = 7;
    relabelled.update({car}, now);
    relabelled.update({truck}, now + 100ms);
    require(relabelled.update({car}, now + 200ms) == Advisory::vehicle,
            "Overlapping vehicle relabel must retain confirmation");
    AdvisoryEvaluator duplicate;
    duplicate.update({person}, now);
    duplicate.update({person}, now);
    require(duplicate.update({person}, now + 200ms) == Advisory::none, "Repeated timestamp must not confirm");

    // Known YOLOX raw output: 640x360 source padded on the bottom, no centering.
    const int shape[] = {1, 8400, 85};
    cv::Mat output(3, shape, CV_32F, cv::Scalar(0));
    auto put = [&](int index, int id, float cx, float cy) {
      auto* row = output.ptr<float>() + index * 85;
      row[0] = cx / 8 - index % 80;
      row[1] = cy / 8 - index / 80;
      row[2] = std::log(160.f / 8); row[3] = std::log(120.f / 8);
      row[4] = 0.9f; row[5 + id] = 0.9f;
    };
    put(0, 0, 320, 180);
    put(1, 0, 322, 180); // same-class duplicate suppressed
    put(2, 2, 320, 180); // overlapping different class retained
    put(3, 0, 320, 580); // wholly in letterbox padding discarded
    const auto decoded = Detector::decode(output, 640, 360);
    require(decoded.size() == 2, "Class-aware NMS or padding rejection failed");
    for (const auto& d : decoded) {
      require(std::abs(d.x - 0.375f) < 0.005f && std::abs(d.y - 1.f/3) < 0.005f,
              "Incorrect letterbox coordinate mapping");
      require(std::abs(d.confidence - 0.81f) < 0.001f, "Must multiply objectness and class score");
    }
    bool rejected = false;
    try { Detector::decode(cv::Mat::zeros(10, 10, CV_32F), 640, 360); }
    catch (const std::runtime_error&) { rejected = true; }
    require(rejected, "Incompatible model output must fail clearly");
    std::cout << "PASS: persistence, reset, false cue guards, YOLOX geometry, class NMS, model shape.\n";
    return 0;
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n'; return 1;
  }
}
