#include "media.hpp"

#include <gst/video/video.h>

#include <cstring>
#include <filesystem>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

namespace helmetd {
namespace {
GstElement* make_pipeline(const std::string& description) {
  GError* error = nullptr;
  GstElement* pipeline = gst_parse_launch(description.c_str(), &error);
  if (error || !pipeline) {
    const std::string message = error ? error->message : "No pipeline";
    if (error) g_error_free(error);
    if (pipeline) gst_object_unref(pipeline);
    throw std::runtime_error(message);
  }
  return pipeline;
}

// Returns true on EOS. Errors carry their element name and are never swallowed.
bool check_bus(GstBus* bus, GstClockTime timeout = 0) {
  bool eos = false;
  while (auto* message = gst_bus_timed_pop_filtered(bus, timeout,
             static_cast<GstMessageType>(GST_MESSAGE_ERROR | GST_MESSAGE_WARNING | GST_MESSAGE_EOS))) {
    timeout = 0;
    if (GST_MESSAGE_TYPE(message) == GST_MESSAGE_EOS) eos = true;
    else {
      const bool fatal = GST_MESSAGE_TYPE(message) == GST_MESSAGE_ERROR;
      GError* error = nullptr;
      gchar* debug = nullptr;
      if (fatal) gst_message_parse_error(message, &error, &debug);
      else gst_message_parse_warning(message, &error, &debug);
      const std::string description = std::string(GST_OBJECT_NAME(GST_MESSAGE_SRC(message))) + ": " + error->message;
      g_error_free(error);
      g_free(debug);
      gst_message_unref(message);
      if (fatal) throw std::runtime_error(description);
      std::cerr << "Media warning: " << description << '\n';
      continue;
    }
    gst_message_unref(message);
  }
  return eos;
}
void start(GstElement* pipeline, GstBus* bus) {
  if (gst_element_set_state(pipeline, GST_STATE_PLAYING) == GST_STATE_CHANGE_FAILURE) {
    check_bus(bus, GST_SECOND);
    throw std::runtime_error("Media pipeline failed to start");
  }
}
}  // namespace

CameraInput::CameraInput(const HudOptions& options) {
  if (options.camera == "none") return;
  std::ostringstream pipeline;
  if (options.camera == "test") {
    pipeline << "videotestsrc is-live=true pattern=ball ! video/x-raw,width=640,height=360,framerate=30/1 ";
  } else {
    pipeline << "udpsrc port=" << options.camera_port
             << " caps=\"application/x-rtp,media=video,encoding-name=H264,payload=97,clock-rate=90000\""
                " ! rtpjitterbuffer name=rtp_jitter latency=80 drop-on-latency=true"
                " ! rtph264depay ! h264parse"
                " ! video/x-h264,profile=(string){baseline,constrained-baseline}"
                " ! tee name=encoded_camera ! queue max-size-buffers=2 leaky=downstream"
                " ! vtdec_hw ! video/x-raw,format=NV12 ";
  }
  pipeline << "! queue max-size-buffers=1 max-size-bytes=0 max-size-time=0 leaky=downstream"
              " ! videoconvert ! videoscale ! video/x-raw,format=BGRA,width=640,height=360,pixel-aspect-ratio=1/1"
              " ! appsink name=camera sync=" << (options.camera == "udp" ? "true" : "false")
           << " max-buffers=1 drop=true enable-last-sample=false";
  // RTP clock recovery can assign presentation times slightly in the future.
  // Honor that clock at the sink instead of continuously replacing the latest
  // sample with a future-dated image that the freshness guard must reject.
  const bool recording = options.camera == "udp" && !options.record_dir.empty();
  std::string recording_pattern;
  if (recording) {
    const auto directory = std::filesystem::path(options.record_dir) / std::to_string(options.camera_port);
    std::filesystem::create_directories(directory);
    recording_pattern = (directory / "segment-%05d.mp4").string();
    pipeline << " encoded_camera. ! queue max-size-buffers=0 max-size-bytes=0 max-size-time=2000000000 leaky=downstream"
        " ! h264parse ! splitmuxsink name=rolling muxer-factory=mp4mux async-finalize=true"
        " max-size-time=5000000000 max-files=8";
  }
  pipeline_ = make_pipeline(pipeline.str());
  if (recording) {
    auto* rolling = gst_bin_get_by_name(GST_BIN(pipeline_), "rolling");
    g_object_set(rolling, "location", recording_pattern.c_str(), nullptr);
    gst_object_unref(rolling);
  }
  sink_ = GST_APP_SINK(gst_bin_get_by_name(GST_BIN(pipeline_), "camera"));
  bus_ = gst_element_get_bus(pipeline_);
  try { start(pipeline_, bus_); }
  catch (...) {
    gst_element_set_state(pipeline_, GST_STATE_NULL);
    gst_object_unref(bus_); gst_object_unref(sink_); gst_object_unref(pipeline_);
    throw;
  }
}
HudState::RtpStats CameraInput::stats() const {
  HudState::RtpStats result;
  if (!pipeline_) return result;
  auto* jitter = gst_bin_get_by_name(GST_BIN(pipeline_), "rtp_jitter");
  if (!jitter) return result;
  GstStructure* stats = nullptr;
  g_object_get(jitter, "stats", &stats, nullptr);
  if (stats) {
    guint64 value = 0;
    if (gst_structure_get_uint64(stats, "num-pushed", &value)) result.pushed = value;
    if (gst_structure_get_uint64(stats, "num-lost", &value)) result.lost = value;
    if (gst_structure_get_uint64(stats, "num-late", &value)) result.late = value;
    if (gst_structure_get_uint64(stats, "avg-jitter", &value)) result.jitter_ns = value;
    gst_structure_free(stats);
  }
  gst_object_unref(jitter);
  return result;
}
CameraInput::~CameraInput() {
  if (!pipeline_) return;
  gst_element_set_state(pipeline_, GST_STATE_NULL);
  gst_object_unref(bus_); gst_object_unref(sink_); gst_object_unref(pipeline_);
}
bool CameraInput::poll(CameraFrame& frame) {
  if (!pipeline_) return false;
  const auto now = Clock::now();
  if (failed_) {
    if (now < retry_at_) return false;
    gst_element_set_state(pipeline_, GST_STATE_NULL);
    // Drain old errors before bringing this receiver back up.
    while (auto* message = gst_bus_pop(bus_)) gst_message_unref(message);
    try { start(pipeline_, bus_); failed_ = false; last_sample_at_ = Time{}; }
    catch (...) { retry_at_ = now + std::chrono::seconds(2); }
    return false;
  }
  try {
    if (check_bus(bus_)) throw std::runtime_error("Camera stream ended");
  } catch (const std::runtime_error& error) {
    // A camera failure must not stop the rest of the HUD or freeze the downlink.
    std::cerr << "Camera unavailable: " << error.what() << ". Retrying receiver in 2 seconds.\n";
    retry_at_ = now + std::chrono::seconds(2);
    failed_ = true;
    gst_element_set_state(pipeline_, GST_STATE_NULL);
    return false;
  }
  GstSample* sample = gst_app_sink_try_pull_sample(sink_, 0);
  if (!sample) {
    if (last_sample_at_ != Time{} && now - last_sample_at_ > std::chrono::seconds(3)) {
      failed_ = true;
      retry_at_ = now;
    }
    return false;
  }
  last_sample_at_ = now;
  GstVideoInfo info;
  gst_video_info_init(&info);
  GstVideoFrame mapped;
  if (!gst_video_info_from_caps(&info, gst_sample_get_caps(sample)) ||
      !gst_video_frame_map(&mapped, &info, gst_sample_get_buffer(sample), GST_MAP_READ)) {
    gst_sample_unref(sample);
    throw std::runtime_error("Cannot map camera frame");
  }
  // Translate PTS age to this process's monotonic clock. Pulling an old sample
  // from appsink after a stall must not make it look newly acquired.
  GstClock* clock = gst_element_get_clock(pipeline_);
  const bool have_clock = clock != nullptr;
  const auto running = clock ? gst_clock_get_time(clock) - gst_element_get_base_time(pipeline_) : 0;
  if (clock) gst_object_unref(clock);
  const auto pts = GST_BUFFER_PTS(gst_sample_get_buffer(sample));
  frame.received_at = Time{};
  if (have_clock && GST_CLOCK_TIME_IS_VALID(pts)) {
    const auto age = static_cast<std::int64_t>(running) - static_cast<std::int64_t>(pts);
    frame.received_at = Clock::now() - std::chrono::nanoseconds(age);
  }
  frame.bgra.resize(CameraFrame::width * CameraFrame::height * 4);
  const auto* data = static_cast<const std::uint8_t*>(GST_VIDEO_FRAME_PLANE_DATA(&mapped, 0));
  const auto stride = GST_VIDEO_FRAME_PLANE_STRIDE(&mapped, 0);
  for (int y = 0; y < CameraFrame::height; ++y)
    std::memcpy(frame.bgra.data() + y * CameraFrame::width * 4, data + y * stride, CameraFrame::width * 4);
  gst_video_frame_unmap(&mapped);
  gst_sample_unref(sample);
  return true;
}

VideoOutput::VideoOutput(const HudOptions& o) : fps_(o.fps) {
  if (o.host.empty() && o.output.empty()) return;
  std::ostringstream description;
  description << "appsrc name=render format=time is-live=true block=false max-buffers=2 max-bytes=0 max-time=0 leaky-type=downstream"
                 " ! videoconvert ! video/x-raw,format=NV12"
                 " ! vtenc_h265_hw name=encoder realtime=true allow-frame-reordering=false bitrate=" << o.bitrate
              << " max-keyframe-interval=" << o.fps << " ! h265parse ";
  if (o.output.empty())
    description << "! rtph265pay pt=96 mtu=1200 config-interval=-1 aggregate-mode=none ! udpsink name=destination sync=false async=false";
  else description << "! mp4mux faststart=true ! filesink name=destination";
  pipeline_ = make_pipeline(description.str());
  source_ = GST_APP_SRC(gst_bin_get_by_name(GST_BIN(pipeline_), "render"));
  bus_ = gst_element_get_bus(pipeline_);
  auto* caps = gst_caps_new_simple("video/x-raw", "format", G_TYPE_STRING, "BGRA",
      "width", G_TYPE_INT, o.width, "height", G_TYPE_INT, o.height,
      "framerate", GST_TYPE_FRACTION, o.fps, 1, "pixel-aspect-ratio", GST_TYPE_FRACTION, 1, 1, nullptr);
  gst_app_src_set_caps(source_, caps);
  gst_caps_unref(caps);
  auto* destination = gst_bin_get_by_name(GST_BIN(pipeline_), "destination");
  if (o.output.empty()) g_object_set(destination, "host", o.host.c_str(), "port", o.port, nullptr);
  else g_object_set(destination, "location", o.output.c_str(), nullptr);
  gst_object_unref(destination);
  auto* encoder = gst_bin_get_by_name(GST_BIN(pipeline_), "encoder");
  auto* pad = gst_element_get_static_pad(encoder, "src");
  gst_pad_add_probe(pad, GST_PAD_PROBE_TYPE_BUFFER,
      [](GstPad*, GstPadProbeInfo*, gpointer data) {
        static_cast<std::atomic<unsigned>*>(data)->fetch_add(1, std::memory_order_relaxed);
        return GST_PAD_PROBE_OK;
      }, &encoded_, nullptr);
  gst_object_unref(pad); gst_object_unref(encoder);
  try { start(pipeline_, bus_); }
  catch (...) {
    gst_element_set_state(pipeline_, GST_STATE_NULL);
    gst_object_unref(bus_); gst_object_unref(source_); gst_object_unref(pipeline_);
    throw;
  }
}
VideoOutput::~VideoOutput() {
  if (!pipeline_) return;
  gst_element_set_state(pipeline_, GST_STATE_NULL);
  gst_object_unref(bus_); gst_object_unref(source_); gst_object_unref(pipeline_);
}
void VideoOutput::push(const void* bgra, std::size_t bytes, std::uint64_t timestamp_ns,
                       std::uint64_t frame_id) {
  if (!pipeline_ || finished_) return;
  check_bus(bus_);
  auto* buffer = gst_buffer_new_allocate(nullptr, bytes, nullptr);
  if (!buffer) throw std::runtime_error("Cannot allocate video buffer");
  gst_buffer_fill(buffer, 0, bgra, bytes);
  GST_BUFFER_PTS(buffer) = timestamp_ns;
  GST_BUFFER_DURATION(buffer) = GST_SECOND / fps_;
  GST_BUFFER_OFFSET(buffer) = frame_id;
  if (gst_app_src_push_buffer(source_, buffer) != GST_FLOW_OK)
    throw std::runtime_error("Encoder rejected HUD frame");
  ++submitted_;
}
void VideoOutput::finish() {
  if (!pipeline_ || finished_) return;
  finished_ = true;
  if (gst_app_src_end_of_stream(source_) != GST_FLOW_OK)
    throw std::runtime_error("Could not finalize video stream");
  const auto deadline = Clock::now() + std::chrono::seconds(5);
  while (!check_bus(bus_, 100 * GST_MSECOND)) {
    if (Clock::now() >= deadline) throw std::runtime_error("Timed out finalizing video stream");
  }
  if (encoded_ == 0) throw std::runtime_error("No HUD frames encoded");
}
}  // namespace helmetd
