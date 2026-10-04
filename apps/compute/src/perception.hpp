#pragma once

#include <algorithm>
#include <chrono>
#include <cmath>
#include <optional>
#include <string>
#include <vector>

namespace helmetd {
using PerceptionTime = std::chrono::steady_clock::time_point;

// Image coordinates normalized to [0,1]. These are not world positions or distances.
struct Detection {
  int class_id = 0;
  float confidence = 0;
  float x = 0, y = 0, width = 0, height = 0;
};
inline const char* detection_label(int id) {
  switch (id) {
    case 0: return "PERSON";
    case 1: return "BICYCLE";
    case 2: return "CAR";
    case 3: return "MOTORCYCLE";
    case 5: return "BUS";
    case 7: return "TRUCK";
    default: return "OBJECT";
  }
}
inline bool road_class(int id) {
  return id == 0 || id == 1 || id == 2 || id == 3 || id == 5 || id == 7;
}
inline bool valid_detection(const Detection& d) {
  return road_class(d.class_id) && std::isfinite(d.confidence) &&
      d.confidence >= 0.5f && d.confidence <= 1 &&
      std::isfinite(d.x) && std::isfinite(d.y) &&
      std::isfinite(d.width) && std::isfinite(d.height) &&
      d.x >= 0 && d.y >= 0 && d.width > 0 && d.height > 0 &&
      d.x + d.width <= 1.00001f && d.y + d.height <= 1.00001f;
}
inline float overlap(const Detection& a, const Detection& b) {
  const auto w = std::max(0.f, std::min(a.x + a.width, b.x + b.width) - std::max(a.x, b.x));
  const auto h = std::max(0.f, std::min(a.y + a.height, b.y + b.height) - std::max(a.y, b.y));
  const float intersection = w * h;
  const float total = a.width * a.height + b.width * b.height - intersection;
  return total > 0 ? intersection / total : 0;
}

enum class Advisory { none, person, vehicle };
inline const char* advisory_title(Advisory value) {
  switch (value) {
    case Advisory::person: return "PERSON IN VIEW";
    case Advisory::vehicle: return "VEHICLE IN VIEW";
    default: return "";
  }
}

// A deliberately simple bench heuristic: a persistent, substantial object in
// the lower central image. Never infer metric range, closing speed, or road safety.
class AdvisoryEvaluator {
 public:
  Advisory update(const std::vector<Detection>& detections, PerceptionTime at) {
    using namespace std::chrono_literals;
    if (previous_at_ && at <= *previous_at_) return Advisory::none;
    if (!previous_at_ || at - *previous_at_ > 500ms) tracks_.clear();
    previous_at_ = at;
    std::vector<Track> next;
    std::vector<bool> used(tracks_.size(), false);
    Advisory result = Advisory::none;
    for (const auto& d : detections) {
      if (!valid_detection(d) || d.confidence < 0.6f) continue;
      const bool central = d.x < 0.7f && d.x + d.width > 0.3f;
      const bool lower = d.y + d.height > 0.6f;
      const bool substantial = d.class_id == 0 ? d.height >= 0.3f : d.width * d.height >= 0.12f;
      if (!central || !lower || !substantial) continue;
      Track track{d, 1, at};
      float best = 0.3f;
      std::optional<std::size_t> match;
      for (std::size_t i = 0; i < tracks_.size(); ++i) {
        if (used[i] || (tracks_[i].d.class_id == 0) != (d.class_id == 0)) continue;
        const auto iou = overlap(d, tracks_[i].d);
        if (iou > best) { best = iou; match = i; }
      }
      if (match) {
        used[*match] = true;
        track.hits = std::min(3, tracks_[*match].hits + 1);
        track.first = tracks_[*match].first;
      }
      if (track.hits >= 3 && at - track.first >= 150ms) {
        if (d.class_id == 0) result = Advisory::person;
        else if (result == Advisory::none) result = Advisory::vehicle;
      }
      next.push_back(track);
    }
    tracks_ = std::move(next);
    return result;
  }
 private:
  struct Track { Detection d; int hits; PerceptionTime first; };
  std::vector<Track> tracks_;
  std::optional<PerceptionTime> previous_at_;
};
}  // namespace helmetd
