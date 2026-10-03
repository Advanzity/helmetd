#include <gst/gst.h>

#include <atomic>
#include <charconv>
#include <chrono>
#include <csignal>
#include <filesystem>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>

namespace {
volatile std::sig_atomic_t interrupted = 0;
void on_signal(int) { interrupted = 1; }

struct Options {
  std::string host;
  std::string output;
  int port = 5000;
  int width = 1280;
  int height = 720;
  int fps = 30;
  int bitrate = 4000;
  int frames = -1;
};

void usage() {
  std::cout << "helmetd-test-sender --host HOST | --output FILE.mp4 [options]\n"
               "  --host HOST       Send H.265 RTP/UDP to a receiver (payload 96)\n"
               "  --output FILE     Record a local MP4; existing files are refused\n"
               "  --port N          UDP destination port (default 5000)\n"
               "  --width N         Even frame width, 64..3840 (default 1280)\n"
               "  --height N        Even frame height, 64..2160 (default 720)\n"
               "  --fps N           Frame rate, 1..120 (default 30)\n"
               "  --bitrate N       Target kbps, 100..100000 (default 4000)\n"
               "  --frames N        Frame limit; 0 means unlimited for UDP only\n"
               "                    Default: 150 for files, unlimited for UDP\n"
               "  --help            Show this help\n"
               "Ctrl-C stops streaming and finalizes a recording.\n";
}

int number(std::string_view value, int minimum, int maximum, std::string_view name) {
  int parsed = 0;
  const auto [end, error] = std::from_chars(value.data(), value.data() + value.size(), parsed);
  if (error != std::errc{} || end != value.data() + value.size() ||
      parsed < minimum || parsed > maximum) {
    throw std::runtime_error(std::string(name) + " must be an integer between " +
                             std::to_string(minimum) + " and " + std::to_string(maximum));
  }
  return parsed;
}

Options parse(int argc, char** argv) {
  Options options;
  for (int i = 1; i < argc; ++i) {
    const std::string_view argument(argv[i]);
    if (i + 1 == argc) throw std::runtime_error("Missing value for " + std::string(argument));
    const std::string_view value(argv[++i]);
    if (argument == "--host") options.host = value;
    else if (argument == "--output") options.output = value;
    else if (argument == "--port") options.port = number(value, 1, 65535, argument);
    else if (argument == "--width") options.width = number(value, 64, 3840, argument);
    else if (argument == "--height") options.height = number(value, 64, 2160, argument);
    else if (argument == "--fps") options.fps = number(value, 1, 120, argument);
    else if (argument == "--bitrate") options.bitrate = number(value, 100, 100000, argument);
    else if (argument == "--frames") options.frames = number(value, 0, 1000000, argument);
    else throw std::runtime_error("Unknown option: " + std::string(argument));
  }
  if (options.host.empty() == options.output.empty())
    throw std::runtime_error("Choose exactly one of --host or --output");
  if (options.width % 2 != 0 || options.height % 2 != 0)
    throw std::runtime_error("Width and height must be even for NV12 video");
  if (options.frames == -1) options.frames = options.output.empty() ? 0 : 150;
  if (!options.output.empty()) {
    if (options.frames == 0) throw std::runtime_error("File recordings require a finite --frames value");
    if (std::filesystem::path(options.output).extension() != ".mp4")
      throw std::runtime_error("Output must have an .mp4 extension");
    if (std::filesystem::exists(options.output))
      throw std::runtime_error("Output already exists: " + options.output);
  }
  return options;
}

GstPadProbeReturn count_frame(GstPad*, GstPadProbeInfo*, gpointer data) {
  static_cast<std::atomic<unsigned>*>(data)->fetch_add(1, std::memory_order_relaxed);
  return GST_PAD_PROBE_OK;
}

int run(const Options& options) {
  // Only validated numbers enter this description. User-supplied paths and
  // hosts are set as properties below, never interpreted as pipeline syntax.
  std::ostringstream description;
  description << "videotestsrc is-live=true pattern=ball num-buffers="
              << (options.frames == 0 ? -1 : options.frames)
              << " ! video/x-raw,width=" << options.width << ",height=" << options.height
              << ",framerate=" << options.fps << "/1"
                 " ! timeoverlay time-mode=buffer-count text=\"helmetd | frame \""
                 " font-desc=\"Monospace 24\" shaded-background=true"
                 " ! timeoverlay time-mode=stream-time valignment=bottom"
                 " text=\"stream time | \" font-desc=\"Monospace 24\" shaded-background=true"
                 " ! videoconvert ! video/x-raw,format=NV12"
                 " ! queue max-size-buffers=2 max-size-bytes=0 max-size-time=0 leaky=downstream"
                 " ! vtenc_h265_hw name=encoder realtime=true allow-frame-reordering=false"
                 " bitrate=" << options.bitrate << " max-keyframe-interval=" << options.fps
              << " ! h265parse ";
  if (options.output.empty()) {
    description << "! rtph265pay pt=96 mtu=1200 config-interval=-1 aggregate-mode=none"
                   " ! udpsink name=destination sync=false async=false";
  } else {
    description << "! mp4mux faststart=true ! filesink name=destination";
  }

  GError* parse_error = nullptr;
  GstElement* pipeline = gst_parse_launch(description.str().c_str(), &parse_error);
  if (parse_error != nullptr) {
    const std::string message(parse_error->message);
    g_error_free(parse_error);
    if (pipeline != nullptr) gst_object_unref(pipeline);
    throw std::runtime_error("Cannot create pipeline: " + message);
  }
  if (pipeline == nullptr) throw std::runtime_error("Cannot create pipeline");

  GstElement* destination = gst_bin_get_by_name(GST_BIN(pipeline), "destination");
  if (options.output.empty()) {
    g_object_set(destination, "host", options.host.c_str(), "port", options.port, nullptr);
  } else {
    g_object_set(destination, "location", options.output.c_str(), nullptr);
  }
  gst_object_unref(destination);

  std::atomic<unsigned> encoded_frames{0};
  GstElement* encoder = gst_bin_get_by_name(GST_BIN(pipeline), "encoder");
  GstPad* encoded_pad = gst_element_get_static_pad(encoder, "src");
  gst_pad_add_probe(encoded_pad, GST_PAD_PROBE_TYPE_BUFFER, count_frame, &encoded_frames, nullptr);
  gst_object_unref(encoded_pad);
  gst_object_unref(encoder);
  GstBus* bus = gst_element_get_bus(pipeline);

  std::cout << "VideoToolbox hardware HEVC | " << options.width << 'x' << options.height
            << " @ " << options.fps << " fps | " << options.bitrate << " kbps\n";
  if (options.output.empty()) {
    std::cout << "RTP/UDP -> " << options.host << ':' << options.port
              << " (payload=96, clock-rate=90000)\n";
  } else {
    std::cout << "Recording -> " << options.output << '\n';
  }
  std::cout << std::flush;

  int result = 0;
  bool finished = false;
  bool stopping = false;
  auto stop_started = std::chrono::steady_clock::now();
  if (gst_element_set_state(pipeline, GST_STATE_PLAYING) == GST_STATE_CHANGE_FAILURE) {
    std::cerr << "Pipeline failed to start; checking for a GStreamer error.\n";
    result = 1;
  }

  while (!finished) {
    if (interrupted && !stopping) {
      stopping = true;
      stop_started = std::chrono::steady_clock::now();
      gst_element_send_event(pipeline, gst_event_new_eos());
    }
    GstMessage* message = gst_bus_timed_pop_filtered(
        bus, 100 * GST_MSECOND,
        static_cast<GstMessageType>(GST_MESSAGE_ERROR | GST_MESSAGE_EOS | GST_MESSAGE_WARNING));
    if (message != nullptr) {
      if (GST_MESSAGE_TYPE(message) == GST_MESSAGE_EOS) {
        finished = true;
      } else {
        GError* error = nullptr;
        gchar* debug = nullptr;
        const bool fatal = GST_MESSAGE_TYPE(message) == GST_MESSAGE_ERROR;
        if (fatal) gst_message_parse_error(message, &error, &debug);
        else gst_message_parse_warning(message, &error, &debug);
        std::cerr << (fatal ? "Error" : "Warning") << " from "
                  << GST_OBJECT_NAME(GST_MESSAGE_SRC(message)) << ": " << error->message << '\n';
        if (debug != nullptr) std::cerr << debug << '\n';
        g_error_free(error);
        g_free(debug);
        if (fatal) { result = 1; finished = true; }
      }
      gst_message_unref(message);
    }
    if (result != 0) finished = true;
    if (stopping && std::chrono::steady_clock::now() - stop_started > std::chrono::seconds(5)) {
      std::cerr << "Timed out finalizing the stream; recording may be incomplete.\n";
      result = 1;
      finished = true;
    }
  }

  gst_element_set_state(pipeline, GST_STATE_NULL);
  gst_object_unref(bus);
  gst_object_unref(pipeline);
  const auto count = encoded_frames.load();
  std::cout << "Encoded " << count << " frames.\n";
  if (count == 0) {
    std::cerr << "No encoded frames were produced.\n";
    return 1;
  }
  return result;
}
}  // namespace

int main(int argc, char** argv) {
  if (argc == 1 || (argc == 2 && std::string_view(argv[1]) == "--help")) {
    usage();
    return argc == 1 ? 2 : 0;
  }
  try {
    const auto options = parse(argc, argv);
    gst_init(nullptr, nullptr);
    std::signal(SIGINT, on_signal);
    std::signal(SIGTERM, on_signal);
    return run(options);
  } catch (const std::exception& error) {
    std::cerr << "Error: " << error.what() << '\n';
    return 1;
  }
}
