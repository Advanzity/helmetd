#pragma once

#include "hud_state.hpp"

#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>
#include <cstdio>
#include <stdexcept>

namespace helmetd {
// Local, lossy notifications: never block rendering or send images to voice services.
class VoiceEvents {
 public:
  explicit VoiceEvents(int port) {
    if (!port) return;
    socket_ = socket(AF_INET, SOCK_DGRAM, 0);
    if (socket_ < 0) throw std::runtime_error("Could not open voice event socket");
    destination_.sin_family = AF_INET;
    destination_.sin_port = htons(port);
    destination_.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    session_ = epoch_ms();
  }
  ~VoiceEvents() { if (socket_ >= 0) close(socket_); }
  VoiceEvents(const VoiceEvents&) = delete;
  VoiceEvents& operator=(const VoiceEvents&) = delete;

  void publish(const HudState& state, Time now) {
    if (socket_ < 0 || now < next_) return;
    next_ = now + std::chrono::milliseconds(100);
    const auto cue = state.current_advisory(now);
    const char* kind = cue == Advisory::person ? "person" :
        cue == Advisory::vehicle ? "vehicle" : "none";
    const auto sent = epoch_ms();
    const auto remaining = cue == Advisory::none ? 0 : std::max<std::int64_t>(0,
        (HudState::perception_budget -
         std::chrono::duration_cast<std::chrono::milliseconds>(now - *state.detection_at)).count());
    char message[320];
    const int size = std::snprintf(message, sizeof(message),
        "{\"version\":1,\"session\":\"%d-%lld\",\"seq\":%llu,\"kind\":\"%s\","
        "\"sent_at_ms\":%lld,\"expires_at_ms\":%lld}", getpid(), session_, ++sequence_,
        kind, sent, sent + remaining);
    if (size > 0 && size < static_cast<int>(sizeof(message)))
      sendto(socket_, message, size, MSG_DONTWAIT,
          reinterpret_cast<const sockaddr*>(&destination_), sizeof(destination_));
  }

 private:
  static long long epoch_ms() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
  }
  int socket_ = -1;
  sockaddr_in destination_{};
  Time next_{};
  long long session_ = 0;
  unsigned long long sequence_ = 0;
};
}  // namespace helmetd
