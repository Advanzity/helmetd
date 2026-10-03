#include "hud_options.hpp"
#include "hud_state.hpp"
#include "media.hpp"
#include "metal_renderer.hpp"

#include <algorithm>
#include <csignal>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string_view>
#include <thread>
#include <vector>

namespace {
volatile std::sig_atomic_t interrupted = 0;
void on_signal(int) { interrupted = 1; }
}

int main(int argc, char** argv) {
  using namespace helmetd;
  if (argc == 2 && std::string_view(argv[1]) == "--help") { print_usage(); return 0; }
  try {
    const auto options = parse_options(argc, argv);
    gst_init(nullptr, nullptr);
    std::signal(SIGINT, on_signal);
    std::signal(SIGTERM, on_signal);
    MetalRenderer renderer(options);
    CameraInput camera(options);
    VideoOutput output(options);
    HudState state;
    const auto started = Clock::now();
    if (options.warning) state.trigger_warning(started);
    const auto interval = std::chrono::nanoseconds(1000000000 / options.fps);
    auto next = started;
    CameraFrame camera_frame;
    std::vector<double> render_ms;
    render_ms.reserve(1000000);
    std::uint64_t rendered = 0, missed_ticks = 0, camera_frames = 0, visible_camera_frames = 0;
    double last_camera_age_ms = 0;
    std::cout << "Metal: " << renderer.device_name() << " | " << options.width << 'x' << options.height
              << " @ " << options.fps << " fps\n"
              << "Telemetry: SIMULATED | Camera: " << options.camera << " | HUD: head-fixed\n"
              << "Space warning; arrows speed; G gear; C camera stall; T telemetry stall; Q quit.\n";
    if (!options.host.empty()) std::cout << "HEVC RTP/UDP -> " << options.host << ':' << options.port << " (receipt unconfirmed)\n";
    if (!options.output.empty()) std::cout << "HEVC recording -> " << options.output << '\n';
    std::cout << std::flush;
    while (!interrupted && (options.frames == 0 || rendered < static_cast<std::uint64_t>(options.frames))) {
      const auto now = Clock::now();
      if (!renderer.poll_events(state, now)) break;
      state.tick_simulation(now);
      // Drain even during a simulated stall, retaining no stale backlog.
      const bool updated = camera.poll(camera_frame) && state.camera_enabled;
      if (camera.failed()) state.camera_at.reset();
      if (updated) {
        state.camera_at = camera_frame.received_at;
        ++camera_frames;
        last_camera_age_ms = std::chrono::duration<double, std::milli>(Clock::now() - camera_frame.received_at).count();
      }
      const auto before_render = Clock::now();
      if (state.camera_fresh(before_render)) ++visible_camera_frames;
      const auto elapsed_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(before_render - started).count();
      const auto pixels = renderer.render(state, updated ? &camera_frame : nullptr,
          before_render, elapsed_ns / 1e9, rendered, output.enabled() || !options.snapshot.empty());
      output.push(pixels.data(), pixels.size(), elapsed_ns, rendered);
      const auto completed = Clock::now();
      if (render_ms.size() < 1000000)
        render_ms.push_back(std::chrono::duration<double, std::milli>(completed - before_render).count());
      ++rendered;
      next += interval;
      if (completed > next) {
        const auto skipped = (completed - next) / interval + 1;
        missed_ticks += skipped;
        next += interval * skipped;
      }
      std::this_thread::sleep_until(next);
    }
    output.finish();
    if (!options.snapshot.empty()) renderer.save_snapshot(options.snapshot);
    if (rendered == 0) throw std::runtime_error("No HUD frames rendered");
    std::sort(render_ms.begin(), render_ms.end());
    const auto percentile = [&](double p) { return render_ms[static_cast<std::size_t>((render_ms.size() - 1) * p)]; };
    std::cout << "Rendered " << rendered << " frames; submitted " << output.submitted()
              << "; encoded " << output.encoded() << "; missed render ticks " << missed_ticks << ".\n"
              << std::fixed << std::setprecision(2)
              << "Camera samples " << camera_frames << "; HUD frames with fresh camera " << visible_camera_frames
              << "; last sample local pipeline age " << last_camera_age_ms << " ms.\n"
              << "Render + readback + enqueue CPU wall time: p50=" << percentile(0.5)
              << " ms p95=" << percentile(0.95) << " ms (up to first 1M frames).\n"
              << "This excludes encoder completion, Wi-Fi, Pi decode and optical display latency.\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "Error: " << error.what() << '\n';
    return 1;
  }
}
