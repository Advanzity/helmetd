#include "hud_options.hpp"
#include "hud_control.hpp"
#include "hud_state.hpp"
#include "media.hpp"
#include "metal_renderer.hpp"
#include "perception_worker.hpp"
#include "voice_events.hpp"

#include <algorithm>
#include <csignal>
#include <iomanip>
#include <iostream>
#include <memory>
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
    std::vector<std::unique_ptr<CameraInput>> extra_inputs;
    for (const auto& config : options.extra_cameras) {
      auto input_options = options;
      input_options.camera = "udp";
      input_options.camera_port = config.port;
      extra_inputs.push_back(std::make_unique<CameraInput>(input_options));
    }
    VideoOutput output(options);
    HudState state;
    state.extra_cameras.resize(extra_inputs.size());
    state.demo = options.demo;
    state.panels = options.panels;
    state.diagnostics = options.diagnostics;
    HudControl control(options.control_socket);
    VoiceEvents voice_events(options.voice_port);
    std::unique_ptr<PerceptionWorker> detector;
    if (!options.detect_model.empty()) {
      detector = std::make_unique<PerceptionWorker>(options.detect_model);
      state.perception_enabled = true;
      std::cout << "OpenCV YOLOX: person/road vehicles; image-based caution cues; uncalibrated.\n";
    }
    std::vector<std::unique_ptr<PerceptionWorker>> side_detectors(options.extra_cameras.size());
    std::vector<Time> side_next(options.extra_cameras.size());
    if (!options.detect_model.empty()) {
      for (std::size_t i = 0; i < options.extra_cameras.size(); ++i)
        if (options.extra_cameras[i].label == "LEFT" || options.extra_cameras[i].label == "RIGHT" || options.extra_cameras[i].label == "REAR")
          side_detectors[i] = std::make_unique<PerceptionWorker>(options.detect_model);
    }
    const auto started = Clock::now();
    if (options.warning) state.trigger_warning(started);
    const auto interval = std::chrono::nanoseconds(1000000000 / options.fps);
    auto next = started;
    CameraFrame camera_frame;
    CameraFrame input_frame;
    auto next_detection = started;
    auto next_stats = started;
    unsigned detection_results = 0, caution_results = 0;
    double last_inference_ms = 0;
    std::vector<double> render_ms;
    render_ms.reserve(1000000);
    std::uint64_t rendered = 0, missed_ticks = 0, camera_frames = 0, visible_camera_frames = 0;
    double last_camera_age_ms = 0;
    std::cout << "Metal: " << renderer.device_name() << " | " << options.width << 'x' << options.height
              << " @ " << options.fps << " fps\n"
              << "Telemetry: " << (options.demo ? "SIMULATED" : "NOT CONNECTED") << " | Camera: " << options.camera << " | HUD: head-fixed\n"
              << "1 camera; 2 demo nav; 3 speed/alerts; D diagnostics; Space warning;\n"
              << "arrows speed; G gear; C camera stall; T telemetry stall; Q quit.\n";
    if (!options.host.empty()) std::cout << "HEVC RTP/UDP -> " << options.host << ':' << options.port << " (receipt unconfirmed)\n";
    if (!options.output.empty()) std::cout << "HEVC recording -> " << options.output << '\n';
    std::cout << std::flush;
    while (!interrupted && (options.frames == 0 || rendered < static_cast<std::uint64_t>(options.frames))) {
      const auto now = Clock::now();
      if (state.camera_view_until && now >= *state.camera_view_until) {
        state.camera_view = "auto";
        state.camera_view_until.reset();
      }
      if (!renderer.poll_events(state, now)) break;
      state.tick_simulation(now);
      for (std::size_t i = 0; i < extra_inputs.size(); ++i) {
        CameraFrame frame;
        auto& status = state.extra_cameras[i];
        if (extra_inputs[i]->poll(frame) && state.camera_enabled) {
          status.received_at = frame.received_at;
          ++status.frames;
          renderer.update_extra_camera(i, frame);
          if (side_detectors[i] && now >= side_next[i] && side_detectors[i]->error().empty()) {
            side_detectors[i]->submit(frame);
            side_next[i] = now + std::chrono::milliseconds(200);
          }
        }
        if (side_detectors[i]) {
          PerceptionResult result;
          if (side_detectors[i]->poll(result)) {
            status.advisory = result.advisory;
            status.detections = std::move(result.detections);
            status.detection_at = result.frame.received_at;
          }
          status.detection_failed = !side_detectors[i]->error().empty();
          if (status.detection_failed) status.detection_at.reset();
        }
        status.failed = extra_inputs[i]->failed();
        if (status.failed) status.received_at.reset();
      }
      // Drain even during a simulated stall, retaining no stale backlog.
      bool updated = camera.poll(input_frame) && state.camera_enabled;
      if (detector && !state.perception_failed) {
        if (updated && now >= next_detection) {
          detector->submit(input_frame);
          next_detection = now + std::chrono::milliseconds(200);
        }
        PerceptionResult result;
        if (detector->poll(result) && state.camera_enabled) {
          state.detection_at = result.frame.received_at;
          state.detections = std::move(result.detections);
          state.advisory = result.advisory;
          last_inference_ms = result.inference_ms;
          ++detection_results;
        }
        const auto error = detector->error();
        if (!error.empty()) {
          state.perception_failed = true;
          state.detections.clear();
          state.advisory = Advisory::none;
          state.detection_at.reset();
          std::cerr << "Detection unavailable: " << error << ". Camera preview continues.\n";
        }
      }
      // Video never waits for inference. Detection retains its own source time.
      if (updated) camera_frame = std::move(input_frame);
      if (camera.failed()) {
        state.camera_at.reset();
        state.detection_at.reset();
        updated = false;
      }
      if (updated) {
        state.camera_at = camera_frame.received_at;
        ++camera_frames;
        last_camera_age_ms = std::chrono::duration<double, std::milli>(Clock::now() - camera_frame.received_at).count();
        if (state.current_advisory(Clock::now()) != Advisory::none) ++caution_results;
      }
      if (now >= next_stats) {
        state.camera_rtp = camera.stats();
        for (std::size_t i = 0; i < extra_inputs.size(); ++i)
          state.extra_cameras[i].rtp = extra_inputs[i]->stats();
        next_stats = now + std::chrono::seconds(1);
      }
      const auto before_render = Clock::now();
      control.poll(state, before_render, options);
      voice_events.publish(state, before_render);
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
    if (detector) std::cout << "Detection results " << detection_results << "; caution results "
        << caution_results << "; last inference " << last_inference_ms << " ms.\n";
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
