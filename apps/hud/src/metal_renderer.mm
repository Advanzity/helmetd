#include "metal_renderer.hpp"

#import <AppKit/AppKit.h>
#import <CoreText/CoreText.h>
#import <Metal/Metal.h>
#import <MetalKit/MetalKit.h>
#import <QuartzCore/CAMetalLayer.h>

#include <array>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <vector>

namespace helmetd {
namespace {
// Logical layout is 1280x720. All coordinates and text scale together.
struct Color { float r, g, b, a = 1; };
// Use the available foreground range at low glasses brightness. This changes
// only UI colors; the clear color, black masks, and camera pixels stay unchanged.
constexpr Color white{1.0f, 1.0f, 1.0f};
constexpr Color muted{0.78f, 0.79f, 0.80f};
constexpr Color cyan{0.55f, 0.94f, 0.94f};
constexpr Color amber{1.0f, 0.80f, 0.18f};
constexpr Color black{0, 0, 0};
struct Vertex { float x, y, u, v; Color color; };
static_assert(sizeof(Vertex) == 32);
struct Draw { std::size_t first, count; int texture; };
constexpr int cell_width = 80;
std::array<float, 95> glyph_advances{};
constexpr int cell_height = 80;
constexpr int atlas_width = cell_width * 16;
constexpr int atlas_height = cell_height * 6;

constexpr auto shaders = R"METAL(
#include <metal_stdlib>
using namespace metal;
struct Vertex { float2 position; float2 uv; float4 color; };
struct Raster { float4 position [[position]]; float2 uv; float4 color; };
vertex Raster hud_vertex(const device Vertex* vertices [[buffer(0)]], uint index [[vertex_id]]) {
  Vertex v = vertices[index];
  return {float4(v.position, 0, 1), v.uv, v.color};
}
fragment float4 hud_fragment(Raster in [[stage_in]], texture2d<float> image [[texture(0)]],
                             constant int& mode [[buffer(0)]]) {
  constexpr sampler sampling(coord::normalized, address::clamp_to_edge, filter::linear, mip_filter::linear);
  if (mode == 0) return in.color;
  float4 sampled = image.sample(sampling, in.uv);
  if (mode == 1) return float4(in.color.rgb, in.color.a * sampled.a);
  if (mode == 7 || mode == 8) {
    // Reject the generated sheet's low-intensity halo at runtime, not via
    // destructive image editing. Retain a soft antialiased silhouette edge.
    float peak = max(sampled.r, max(sampled.g, sampled.b));
    float mask = smoothstep(0.50, 0.82, peak);
    return float4(sampled.rgb, sampled.a * mask * in.color.a);
  }
  if (mode == 6) {
    // Suppress dark map haze on emissive glasses, retaining bright route detail.
    float3 rgb = max(sampled.rgb - float3(0.012), float3(0)) / 0.988;
    rgb = pow(rgb, float3(0.90));
    float edge = smoothstep(0.0, 0.035, in.uv.x) * smoothstep(0.0, 0.035, 1.0-in.uv.x);
    edge *= smoothstep(0.0, 0.025, in.uv.y) * smoothstep(0.0, 0.025, 1.0-in.uv.y);
    return float4(rgb * edge, in.color.a);
  }
  return float4(sampled.rgb, in.color.a);
}
)METAL";

id<MTLTexture> make_texture(id<MTLDevice> device, int width, int height,
                            MTLTextureUsage usage, MTLStorageMode storage, bool mipmapped = false) {
  auto* descriptor = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
      width:width height:height mipmapped:mipmapped];
  descriptor.usage = usage;
  descriptor.storageMode = storage;
  auto texture = [device newTextureWithDescriptor:descriptor];
  if (!texture) throw std::runtime_error("Cannot allocate Metal texture");
  return texture;
}

id<MTLTexture> make_atlas(id<MTLDevice> device) {
  constexpr int supersample = 3;
  const int width = atlas_width * supersample, height = atlas_height * supersample;
  std::vector<std::uint8_t> pixels(width * height * 4, 0);
  auto color_space = CGColorSpaceCreateDeviceRGB();
  auto context = CGBitmapContextCreate(pixels.data(), width, height, 8,
      width * 4, color_space, static_cast<CGBitmapInfo>(kCGImageAlphaPremultipliedFirst) | kCGBitmapByteOrder32Little);
  CGColorSpaceRelease(color_space);
  if (!context) throw std::runtime_error("Cannot create glyph atlas");
  CGContextScaleCTM(context, supersample, supersample);
  CGContextSetShouldAntialias(context, true);
  CGContextSetAllowsAntialiasing(context, true);
  CGContextSetShouldSmoothFonts(context, false);
  NSFont* font = [NSFont systemFontOfSize:64 weight:NSFontWeightMedium];
  NSDictionary* attributes = @{NSFontAttributeName:font, NSForegroundColorAttributeName:NSColor.whiteColor};
  for (int c = 32; c <= 126; ++c) {
    const int index = c - 32;
    NSString* character = [NSString stringWithFormat:@"%c", c];
    NSAttributedString* string = [[NSAttributedString alloc] initWithString:character attributes:attributes];
    CTLineRef line = CTLineCreateWithAttributedString((__bridge CFAttributedStringRef)string);
    glyph_advances[index] = CTLineGetTypographicBounds(line, nullptr, nullptr, nullptr);
    CGContextSetTextPosition(context, (index % 16) * cell_width + 3,
        atlas_height - (index / 16) * cell_height - 64);
    CTLineDraw(line, context);
    CFRelease(line);
  }
  CGContextRelease(context);
  auto texture = make_texture(device, width, height, MTLTextureUsageShaderRead, MTLStorageModeShared, true);
  [texture replaceRegion:MTLRegionMake2D(0, 0, width, height) mipmapLevel:0
      withBytes:pixels.data() bytesPerRow:width * 4];
  auto command = [[device newCommandQueue] commandBuffer];
  auto blit = [command blitCommandEncoder];
  [blit generateMipmapsForTexture:texture];
  [blit endEncoding];
  [command commit];
  [command waitUntilCompleted];
  return texture;
}
}  // namespace

struct MetalRenderer::Impl {
  HudOptions options;
  id<MTLDevice> device;
  id<MTLCommandQueue> queue;
  id<MTLRenderPipelineState> pipeline;
  id<MTLTexture> target;
  id<MTLTexture> atlas;
  id<MTLTexture> camera_texture;
  id<MTLTexture> map_texture;
  id<MTLTexture> symbol_texture;
  id<MTLTexture> notification_texture;
  double map_checked = 0;
  double map_modified = 0;
  std::vector<id<MTLTexture>> extra_textures;
  std::vector<bool> extra_uploaded;
  id<MTLBuffer> vertex_buffer;
  id<MTLBuffer> readback_buffer;
  id<NSObject> streaming_activity = nil;
  NSWindow* window = nil;
  CAMetalLayer* layer = nil;
  std::vector<Vertex> vertices;
  std::vector<Draw> draws;
  std::vector<std::uint8_t> pixels;
  bool camera_uploaded = false;
  float composition_opacity = 1;
  double camera_entered = 0, map_entered = 0, animation_time = 0;
  std::string prior_view = "auto";
  bool prior_map = false;
  bool interaction_initialized = false, prior_quiet = false;
  std::string prior_navigation, notice;
  double notice_entered = -10;
  std::array<double, 4> cue_seen{-10,-10,-10,-10};
  std::array<double, 4> cue_entered{};
  std::optional<Time> last_preview_at;
  static float ease_out(float t) {
    if (NSWorkspace.sharedWorkspace.accessibilityDisplayShouldReduceMotion) return t > 0 ? 1.f : 0.f;
    t = std::clamp(t, 0.f, 1.f);
    return 1.f - std::pow(1.f-t, 3.f);
  }
  float composition_offset = 0;
  std::size_t row_bytes = 0;

  explicit Impl(const HudOptions& o) : options(o) {
    device = MTLCreateSystemDefaultDevice();
    if (!device) throw std::runtime_error("A Metal-capable GPU is required");
    queue = [device newCommandQueue];
    NSError* error = nil;
    auto library = [device newLibraryWithSource:[NSString stringWithUTF8String:shaders] options:nil error:&error];
    if (!library) throw std::runtime_error("Metal shader compilation: " + std::string(error.localizedDescription.UTF8String));
    auto* descriptor = [MTLRenderPipelineDescriptor new];
    descriptor.vertexFunction = [library newFunctionWithName:@"hud_vertex"];
    descriptor.fragmentFunction = [library newFunctionWithName:@"hud_fragment"];
    descriptor.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
    descriptor.colorAttachments[0].blendingEnabled = YES;
    descriptor.colorAttachments[0].sourceRGBBlendFactor = MTLBlendFactorSourceAlpha;
    descriptor.colorAttachments[0].destinationRGBBlendFactor = MTLBlendFactorOneMinusSourceAlpha;
    descriptor.colorAttachments[0].sourceAlphaBlendFactor = MTLBlendFactorOne;
    descriptor.colorAttachments[0].destinationAlphaBlendFactor = MTLBlendFactorOneMinusSourceAlpha;
    pipeline = [device newRenderPipelineStateWithDescriptor:descriptor error:&error];
    if (!pipeline) throw std::runtime_error("Metal pipeline: " + std::string(error.localizedDescription.UTF8String));
    target = make_texture(device, o.width, o.height,
        MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead, MTLStorageModePrivate);
    atlas = make_atlas(device);
    MTKTextureLoader* loader = [[MTKTextureLoader alloc] initWithDevice:device];
    NSError* sprite_error = nil;
    symbol_texture = [loader newTextureWithContentsOfURL:[NSURL fileURLWithPath:@HELMETD_SPRITE_PATH]
      options:@{MTKTextureLoaderOptionSRGB:@NO, MTKTextureLoaderOptionGenerateMipmaps:@YES}
      error:&sprite_error];
    notification_texture = [loader newTextureWithContentsOfURL:[NSURL fileURLWithPath:@HELMETD_NOTIFICATION_PATH]
      options:@{MTKTextureLoaderOptionSRGB:@NO, MTKTextureLoaderOptionGenerateMipmaps:@YES} error:&sprite_error];
    if (!notification_texture) throw std::runtime_error("Notification texture could not load");
    if (!symbol_texture) throw std::runtime_error("HUD symbol atlas could not load");
    map_texture = make_texture(device, 640, 360, MTLTextureUsageShaderRead, MTLStorageModeShared);
    camera_texture = make_texture(device, CameraFrame::width, CameraFrame::height,
        MTLTextureUsageShaderRead, MTLStorageModeShared);
    for (std::size_t i = 0; i < o.extra_cameras.size(); ++i)
      extra_textures.push_back(make_texture(device, CameraFrame::width, CameraFrame::height,
          MTLTextureUsageShaderRead, MTLStorageModeShared));
    extra_uploaded.resize(o.extra_cameras.size(), false);
    vertex_buffer = [device newBufferWithLength:sizeof(Vertex) * 16000 options:MTLResourceStorageModeShared];
    row_bytes = (o.width * 4 + 255) & ~std::size_t(255);
    readback_buffer = [device newBufferWithLength:row_bytes * o.height options:MTLResourceStorageModeShared];
    if (!queue || !vertex_buffer || !readback_buffer) throw std::runtime_error("Cannot allocate Metal resources");
    if (!o.host.empty() || !o.output.empty()) {
      streaming_activity = [[NSProcessInfo processInfo]
          beginActivityWithOptions:(NSActivityUserInitiated | NSActivityLatencyCritical)
          reason:@"Streaming the helmet HUD and receiving live cameras"];
    }
    if (!o.headless) {
      [NSApplication sharedApplication];
      [NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];
      [NSApp finishLaunching];
      const auto screen = NSScreen.mainScreen.visibleFrame.size;
      const double scale = std::min({1.0, (screen.width - 80) / o.width, (screen.height - 100) / o.height});
      window = [[NSWindow alloc] initWithContentRect:NSMakeRect(0, 0, o.width * scale, o.height * scale)
          styleMask:NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable
          backing:NSBackingStoreBuffered defer:NO];
      window.releasedWhenClosed = NO;
      window.title = @"Helmetd — Front camera + HUD · Uncalibrated preview";
      window.backgroundColor = NSColor.blackColor;
      layer = [CAMetalLayer layer];
      layer.device = device;
      layer.pixelFormat = MTLPixelFormatBGRA8Unorm;
      layer.framebufferOnly = NO;
      layer.drawableSize = CGSizeMake(o.width, o.height);
      layer.maximumDrawableCount = 2;
      layer.displaySyncEnabled = NO;
      window.contentView.wantsLayer = YES;
      window.contentView.layer = layer;
      [window center];
      [window makeKeyAndOrderFront:nil];
      [NSApp activateIgnoringOtherApps:YES];
    }
  }

  ~Impl() {
    if (streaming_activity) [[NSProcessInfo processInfo] endActivity:streaming_activity];
  }

  void quad(float x, float y, float w, float h, Color color, int texture = 0,
            float u = 0, float v = 0, float uw = 1, float vh = 1) {
    y += composition_offset;
    color.a *= composition_opacity;
    const float left = x / 640 - 1, right = (x + w) / 640 - 1;
    const float top = 1 - y / 360, bottom = 1 - (y + h) / 360;
    const auto first = vertices.size();
    vertices.insert(vertices.end(), {{left, top, u, v, color}, {left, bottom, u, v + vh, color},
        {right, top, u + uw, v, color}, {right, top, u + uw, v, color},
        {left, bottom, u, v + vh, color}, {right, bottom, u + uw, v + vh, color}});
    if (!draws.empty() && draws.back().texture == texture) draws.back().count += 6;
    else draws.push_back({first, 6, texture});
  }

  void text(const std::string& value, float x, float y, float size, Color color) {
    const float scale = size / 64;
    for (const unsigned char c : value) {
      const auto index = (c >= 32 && c <= 126 ? c : '?') - 32;
      if (c != ' ')
        quad(x, y, cell_width * scale, cell_height * scale, color, 1,
            float((index % 16) * cell_width) / atlas_width,
            float((index / 16) * cell_height) / atlas_height,
            float(cell_width) / atlas_width, float(cell_height) / atlas_height);
      x += (glyph_advances[index] + 1.5f) * scale;
    }
  }
  void symbol(int cell, float x, float y, float width, float height) {
    // Individual visible bounds in the 1536x1024 atlas. Fit uniformly rather
    // than stretching each differently shaped symbol into the destination box.
    constexpr float bounds[8][4] = {
      {78,134,208,302}, {470,132,206,304}, {784,152,318,290}, {1176,108,320,344},
      {50,566,292,318}, {422,564,290,320}, {772,618,366,246}, {1230,562,244,340}
    };
    if (cell < 0 || cell >= 8) return;
    if (cell < 4 && !NSWorkspace.sharedWorkspace.accessibilityDisplayShouldReduceMotion) {
      if (animation_time-cue_seen[cell] > .18) cue_entered[cell] = animation_time;
      cue_seen[cell] = animation_time;
      const float age = float(animation_time-cue_entered[cell]);
      // A single damped settle, never a looping warning pulse. At entry the
      // warning is already fully visible at 72% of its final size.
      const float spring = age >= .65f ? 1.f : 1.f - .28f*std::exp(-8.f*age)*std::cos(16.f*age);
      const float travel = 1.f-ease_out(age/.45f);
      if (cell == 0) x -= 20.f*travel;
      else if (cell == 1) x += 20.f*travel;
      else y += 16.f*travel;
      x += width*(1-spring)*.5f; y += height*(1-spring)*.5f;
      width *= spring; height *= spring;
    }
    const auto& box = bounds[cell];
    const float scale = std::min(width / box[2], height / box[3]);
    const float fitted_width = box[2] * scale, fitted_height = box[3] * scale;
    quad(x + (width-fitted_width)*.5f, y + (height-fitted_height)*.5f,
      fitted_width, fitted_height, white, 7,
      box[0]/1536.f, box[1]/1024.f, box[2]/1536.f, box[3]/1024.f);
  }
  void triangle(float ax, float ay, float bx, float by, float cx, float cy, Color color) {
    const auto first = vertices.size();
    vertices.insert(vertices.end(), {{ax / 640 - 1, 1 - ay / 360, 0, 0, color},
        {bx / 640 - 1, 1 - by / 360, 0, 0, color},
        {cx / 640 - 1, 1 - cy / 360, 0, 0, color}});
    if (!draws.empty() && draws.back().texture == 0) draws.back().count += 3;
    else draws.push_back({first, 3, 0});
  }
  void corners(float x, float y, float w, float h, Color color) {
    constexpr float size = 16, stroke = 2;
    for (const float dx : {0.f, w - size}) {
      quad(x + dx, y, size, stroke, color);
      quad(x + dx, y + h - stroke, size, stroke, color);
    }
    for (const float dx : {0.f, w - stroke}) {
      quad(x + dx, y, stroke, size, color);
      quad(x + dx, y + h - size, stroke, size, color);
    }
  }

  void extra_camera_view(const HudState& state, Time now, int index, const std::string& label,
                         float left, float top, float width, bool focused = false) {
    const float height = width * 9 / 16;
    const bool fresh = index >= 0 && state.extra_camera_fresh(index, now) && extra_uploaded[index];
    const auto color = focused && state.active_signal(now) != "off" ? amber : cyan;
    symbol(6, left, top-31, 26, 24);
    text(label, left+34, top - 27, 16, fresh ? color : muted);
    const bool visible = index >= 0 && state.extra_camera_visible(index, now) && extra_uploaded[index];
    if (visible) {
      quad(left, top, width, height, white, 3 + index);
      if (!fresh) {
        quad(left, top + height - 22, width, 22, black);
        text("VIDEO DELAYED", left + 8, top + height - 21, 13, amber);
      }
    }
    else {
      text(index >= 0 && state.extra_cameras[index].frames ? "RECONNECTING" : "CAMERA OFFLINE", left + 12, top + height / 2 - 16, 15, muted);
      text("WAITING FOR CAMERA", left + 22, top + height / 2 + 10, 12, muted);
    }
    corners(left - 2, top - 2, width + 4, height + 4, fresh ? color : muted);
    if (focused && state.diagnostics) text(state.active_signal(now) != "off" ? "AUTO RETURN" : "CAMERA VIEW",
        left, top + height + 15, 12, color);
  }

  void camera_panel_view(const HudState& state, Time now) {
    constexpr float top = 432, width = 288, height = 162;
    auto view = state.active_signal(now);
    if (view == "off") view = state.camera_view;
    std::transform(view.begin(), view.end(), view.begin(), [](unsigned char c) { return std::toupper(c); });
    if (view == "AUTO") return;
    const float left = view == "RIGHT" ? 928.f : 64.f;
    if (view != options.camera_label) {
      int selected = -1;
      for (std::size_t i = 0; i < options.extra_cameras.size(); ++i)
        if (options.extra_cameras[i].label == view) selected = static_cast<int>(i);
      extra_camera_view(state, now, selected, view, left, top, width, true);
      return;
    }
    const bool camera_fresh = state.camera_fresh(now) && camera_uploaded;
    const Color camera_color = state.current_advisory(now) != Advisory::none || state.warning(now) ? amber : cyan;
    text(options.camera_label,
        left, 402, 16, camera_fresh ? camera_color : muted);
    if (state.diagnostics) text(options.camera == "test" ? "PREVIEW FEED" : (options.camera == "udp" ? "RTP FEED" : "DISABLED"),
        left, 610, 13, muted);
    if (state.camera_visible(now) && camera_uploaded) {
      quad(left, top, width, height, white, 2);
      if (!camera_fresh) {
        quad(left, top + height - 22, width, 22, black);
        text("VIDEO DELAYED", left + 8, top + height - 21, 13, amber);
      }
    }
    else {
      text(state.camera_at ? "RECONNECTING" : "CAMERA OFFLINE", 87, 490, 19, muted);
      text(state.camera_at ? "STALE FRAME HIDDEN" : "WAITING FOR VIDEO", 113, 526, 13, muted);
    }
    // Spatial boxes are only valid on their exact source frame. Scene advisories
    // may remain fresh while the independent live preview advances.
    if (state.detection_fresh(now) && state.detection_at == state.camera_at) {
      for (const auto& d : state.detections) {
        if (!valid_detection(d)) continue;
        const float x = left + d.x * width, y = top + d.y * height;
        const float w = d.width * width, h = d.height * height;
        const float stroke = std::min({2.f, w, h});
        quad(x, y, w, stroke, camera_color);
        quad(x, y + h - stroke, w, stroke, camera_color);
        quad(x, y, stroke, h, camera_color);
        quad(x + w - stroke, y, stroke, h, camera_color);
        const std::string label = std::string(detection_label(d.class_id)) + " " +
            std::to_string(int(d.confidence * 100)) + "%";
        const float label_width = float(label.size()) * 7.3f;
        const float label_x = std::min(x, left + width - label_width);
        const float label_y = std::clamp(y - 17, top, top + height - 17);
        quad(label_x, label_y, label_width, 17, black);
        text(label, label_x, label_y, 12, camera_color);
      }
    }
    corners(left - 2, top - 2, width + 4, height + 4, camera_fresh ? camera_color : muted);
    const char* camera_status = camera_fresh ? (options.camera == "test" ? "SYNTHETIC INPUT" : "LOCAL DECODE ACTIVE") : "WAITING FOR CAMERA";
    if (state.perception_enabled) camera_status = state.perception_failed ? "DETECTION UNAVAILABLE" :
        (state.detection_fresh(now) ? "IMAGE CUES / UNCALIBRATED" : "DETECTION WAITING / STALE");
    if (state.diagnostics) text(camera_status, left, 633, 12, muted);
  }

  void route_map_view(const HudState& state, Time now) {
    const auto& map = state.route_map;
    constexpr float x = 38, y = 420, w = 344, h = 194;
    const bool fresh = HudState::fresh(map.received_at, now, std::chrono::milliseconds(3000));
    const bool active = fresh && map.mode == "active";

    if (map.points.size() < 2 || map.mode == "none") {
      text("CHOOSE A DESTINATION", x + 30, y + 65, 14, muted);
      return;
    }
    const double clock = NSDate.date.timeIntervalSince1970;
    if (clock - map_checked > .08 && !options.control_socket.empty()) {
      map_checked = clock;
      NSString* socket = [NSString stringWithUTF8String:options.control_socket.c_str()];
      NSString* path = [socket.stringByDeletingLastPathComponent stringByAppendingPathComponent:@"hud-map.bgra"];
      NSDictionary* attrs = [[NSFileManager defaultManager] attributesOfItemAtPath:path error:nil];
      const double modified = [attrs[NSFileModificationDate] timeIntervalSince1970];
      if (modified > map_modified && clock - modified < 2) {
        NSData* bytes = [NSData dataWithContentsOfFile:path];
        if (bytes.length == 640 * 360 * 4) {
          [map_texture replaceRegion:MTLRegionMake2D(0, 0, 640, 360) mipmapLevel:0
              withBytes:bytes.bytes bytesPerRow:640 * 4];
          map_modified = modified;
        }
      }
    }
    if (clock - map_modified < 2 && fresh) {
      Color map_color = white;
      map_color.a = ease_out(float((animation_time-map_entered)/.32));
      const Color edge{1,1,1,.38f};
      quad(x-1, y-31, w+2, 1, edge);
      quad(x-1, y-31, 1, h+68, edge);
      quad(x+w, y-31, 1, h+68, edge);
      quad(x-1, y+h+36, w+2, 1, edge);
      text("ROUTE", x + 12, y - 24, 14, white);
      quad(x, y, w, h, map_color, 6);
      quad(x, y+h+1, w, 1, Color{1,1,1,.35f});
      if (active && state.navigation.remaining_m >= 0 && state.navigation.remaining_s >= 0) {
        char summary[64];
        std::snprintf(summary, sizeof(summary), "%d min  /  %.1f mi",
          (state.navigation.remaining_s+59)/60, state.navigation.remaining_m/1609.344);
        text(summary, x+12, y+h+9, 15, white);
      } else text(state.navigation.state == "paused" ? "GUIDANCE PAUSED" :
          map.mode == "preview" ? "ROUTE PREVIEW" : "POSITION UNAVAILABLE",
          x+12, y+h+10, 12, muted);
    } else {
      text("3D MAP UNAVAILABLE", x + 28, y + 70, 14, muted);
    }
  }

  void navigation_panel_view(const HudState& state, Time now) {
    const bool camera_open = (state.panels & camera_panel) &&
        (state.active_signal(now) != "off" || state.camera_view != "auto" ||
         ((state.alert_preview == "left" || state.alert_preview == "right") &&
          HudState::fresh(state.alert_preview_at, now, std::chrono::milliseconds(5000))));
    if (!state.demo && !state.quiet && !camera_open) route_map_view(state, now);
    const auto& nav = state.navigation;
    const bool fresh = state.navigation_fresh(now);
    const bool guiding = fresh && nav.state == "navigating";
    if (!guiding && (state.demo || nav.state != "idle")) {
      const std::string status = !fresh ? "NAV UNAVAILABLE" : nav.state == "location_lost" ? "LOCATION LOST" :
          nav.state == "off_route" ? "OFF ROUTE" : nav.state == "paused" ? "NAV PAUSED" :
          nav.state == "arrived" ? "ARRIVED" : "READY TO NAVIGATE";
      text(status, 548, 44, 18, fresh && nav.state == "arrived" ? cyan : muted);
    } else if (guiding && (nav.maneuver == "left" || nav.maneuver == "right")) {
      const bool left = nav.maneuver == "left";
      symbol(left ? 4 : 5, 548, 35, 66, 70);
    } else if (guiding && nav.maneuver == "straight") {
      triangle(580, 38, 560, 63, 600, 63, cyan);
      quad(576, 60, 8, 40, cyan);
    } else if (guiding) {
      text(nav.maneuver == "uturn" ? "U-TURN" : nav.maneuver == "stop" ? "STOP" : "ARRIVE",
          548, 55, 22, cyan);
    }
    if (guiding && nav.distance_m >= 0) {
      text(std::to_string(nav.distance_m) + " M", 640, 36, 30, white);
    }
    if (fresh && nav.state != "idle") text(nav.destination, 640, 76, 16, muted);
    if (nav.simulated) text("ROUTE PREVIEW", 640, 103, 12, muted);
  }

  void telemetry_panel_view(const HudState& state, Time now) {
    const auto advisory = state.display_advisory(now);
    const bool caution = advisory != Advisory::none;
    if (caution || state.warning(now)) {
      const float prior_opacity = composition_opacity;
      if (caution && state.displayed_advisory_at) {
        const float age = std::chrono::duration<float>(now-*state.displayed_advisory_at).count();
        composition_opacity *= std::clamp((2.f-age)/.25f, 0.f, 1.f);
      }
      text("!", 942, 395, 29, amber);
      text(caution ? advisory_title(advisory) : "REAR APPROACH", 972, 398, 22, amber);
      text(caution ? "CHECK SURROUNDINGS" : "PREVIEW ALERT", 973, 432, 13, amber);
      composition_opacity = prior_opacity;
    }
    if (state.quiet) return;
    const bool telemetry_fresh = state.demo && state.telemetry_fresh(now);
    const std::string speed = telemetry_fresh ? std::to_string(state.speed_mph) : "--";
    text(speed, 530, 606, 54, telemetry_fresh ? white : muted);
    text("mph", 610, 642, 16, muted);
    quad(658, 613, 1, 42, muted);
    text(telemetry_fresh ? (state.gear == 0 ? "N" : std::to_string(state.gear)) : "-",
        688, 606, 54, telemetry_fresh ? white : muted);
    text("GEAR", 744, 642, 14, muted);
    if (state.demo) text("PREVIEW DATA", 566, 679, 11, muted);
  }

  void ride_chrome(const HudState& state, Time now, double elapsed) {
    text("helmetd", 36, 28, 24, white);
    bool connected = state.camera_fresh(now);
    for (std::size_t i = 0; i < state.extra_cameras.size(); ++i)
      connected = connected || state.extra_camera_fresh(i, now);
    const Color link_color = connected ? cyan : muted;
    // These bars describe incoming video availability, not Wi-Fi signal strength.
    for (int i = 0; i < 3; ++i) quad(1040 + i * 6, 48 - i * 5, 3, 6 + i * 5, link_color);
    text(connected ? "LINK" : "NO VIDEO", 1064, 34, 12, link_color);
    corners(1180, 34, 28, 16, muted);
    quad(1209, 39, 3, 6, muted);
    text("--", 1220, 33, 13, muted);
    for (const auto& label : {std::string("LEFT"), std::string("RIGHT")}) {
      bool fresh = false;
      for (std::size_t i = 0; i < options.extra_cameras.size(); ++i)
        if (options.extra_cameras[i].label == label) fresh = state.extra_camera_fresh(i, now);
      const float x = label == "LEFT" ? 36 : 1212;
      auto color = state.active_signal(now) == (label == "LEFT" ? "left" : "right") ? amber :
          fresh ? white : muted;
      if (state.active_signal(now) == (label == "LEFT" ? "left" : "right"))
        color.a = .7f + .3f * std::sin(elapsed * 6.283);
      corners(x, 545, 24, 17, color);
      if (label == "LEFT") triangle(x-12, 553, x-6, 548, x-6, 558, color);
      else triangle(x+36, 553, x+30, 548, x+30, 558, color);
    }
    if (state.assistant_phase == "offline" ||
        !HudState::fresh(state.assistant_at, now, std::chrono::milliseconds(3000)))
      text("VOICE OFF", 1090, 667, 13, muted);
  }

  // Camera-relative cues, deliberately not world-position or collision estimates.
  bool directional_cues(const HudState& state, Time now) {
    bool alert = false;
    for (std::size_t i = 0; i < state.extra_cameras.size(); ++i) {
      const auto cue = state.side_display_advisory(i, now);
      if (cue == Advisory::none) continue;
      const auto& label = options.extra_cameras[i].label;
      alert = true;
      if (label == "REAR") {
        symbol(2, 600, 548, 46, 42);
        text(cue == Advisory::person ? "PERSON BEHIND" : "VEHICLE BEHIND", 540, 593, 14, amber);
      } else {
        const bool left = label == "LEFT";
        const float x = left ? 34 : 1246;
        symbol(left ? 0 : 1, x-12, 316, 28, 42);
        text(cue == Advisory::person ? "PERSON" : "VEHICLE", left ? 54 : 1152, 331, 13, amber);
      }
    }
    const auto front = state.display_advisory(now);
    if (front != Advisory::none) {
      alert = true;
      symbol(3, 613, 526, 34, 36);
      text(front == Advisory::person ? "PERSON AHEAD" : "VEHICLE AHEAD", 550, 568, 14, amber);
    }
    return alert;
  }

  void compact_navigation(const HudState& state, Time now) {
    const auto& nav = state.navigation;
    if (!state.navigation_fresh(now) || nav.state != "navigating") return;
    if (nav.maneuver == "left" || nav.maneuver == "right") {
      const bool left = nav.maneuver == "left";
      triangle(left ? 554 : 594, 652, 574, 640, 574, 664, cyan);
      quad(565, 649, 24, 5, cyan);
    } else if (nav.maneuver == "straight") {
      triangle(574, 636, 562, 650, 586, 650, cyan);
      quad(572, 648, 5, 20, cyan);
    } else text(nav.maneuver == "uturn" ? "U-TURN" : nav.maneuver == "stop" ? "STOP" : "ARRIVE", 510, 644, 16, cyan);
    if (nav.distance_m >= 0) text(std::to_string(nav.distance_m)+" M", 612, 641, 23, cyan);
  }

  void compose(const HudState& state, Time now, double elapsed, std::uint64_t frame) {
    vertices.clear(); draws.clear();
    animation_time = elapsed;
    const auto signal = state.active_signal(now);
    const auto view = signal == "off" ? state.camera_view : signal;
    if (interaction_initialized) {
      if (view != prior_view) {
        notice = view == "auto" ? "RIDE VIEW" : view == "left" ? "LEFT CAMERA" :
          view == "right" ? "RIGHT CAMERA" : view == "rear" ? "REAR CAMERA" : "FRONT CAMERA";
        notice_entered = elapsed;
      }
      if (state.quiet != prior_quiet) {
        notice = state.quiet ? "QUIET MODE / ALERTS ON" : "RIDE VIEW";
        notice_entered = elapsed;
      }
      if (state.navigation.state != prior_navigation) {
        const auto& phase = state.navigation.state;
        notice = phase == "paused" ? "GUIDANCE PAUSED" : phase == "navigating" ? "GUIDANCE RESUMED" :
          phase == "arrived" ? "DESTINATION REACHED" : phase == "location_lost" ? "LOCATION LOST" : "";
        notice_entered = elapsed;
      }
    }
    interaction_initialized = true;
    prior_quiet = state.quiet;
    prior_navigation = state.navigation.state;
    if (view != prior_view) { camera_entered = elapsed; prior_view = view; }
    const bool map_visible = view == "auto" && state.route_map.points.size() >= 2;
    if (map_visible && !prior_map) map_entered = elapsed;
    prior_map = map_visible;
    if (state.panels & camera_panel) {
      composition_opacity = std::clamp(float((elapsed-camera_entered)/.22), 0.f, 1.f);
      composition_opacity = ease_out(composition_opacity);
      composition_offset = 8 * (1-composition_opacity);
      camera_panel_view(state, now);
      composition_offset = 0;
      composition_opacity = 1;

    }
    if (state.alert_preview_at != last_preview_at) {
      last_preview_at = state.alert_preview_at;
      const int cell = state.alert_preview == "left" ? 0 : state.alert_preview == "right" ? 1 :
        state.alert_preview == "rear" ? 2 : 3;
      cue_entered[cell] = elapsed;
      cue_seen[cell] = elapsed;
    }
    const bool directional_alert = state.panels && directional_cues(state, now);
    if (state.panels && !directional_alert && state.alert_preview != "off" &&
        !state.alert_preview.empty() && HudState::fresh(state.alert_preview_at, now, std::chrono::milliseconds(5000))) {
      const auto& cue = state.alert_preview;
      const bool left = cue == "left", right = cue == "right";
      if (left || right) {
        HudState preview = state;
        preview.camera_view = cue;
        preview.signal = "off";
        preview.signal_until.reset();
        camera_panel_view(preview, now);
      }
      if (cue == "turn") {
        symbol(4, 548, 35, 66, 70);
        text("800 FT", 640, 36, 30, white);
        text("Oak Street", 640, 76, 16, white);
      } else if (cue == "message") {
        quad(935, 225, 32, 32, white, 8);
        text("MESSAGES", 978, 222, 12, muted);
        text("Alex", 978, 244, 18, white);
      } else if (left || right) {
        symbol(left ? 0 : 1, left ? 22 : 1234, 316, 28, 42);
        text("VEHICLE", left ? 54 : 1152, 331, 13, amber);
      } else {
        symbol(cue == "rear" ? 2 : 3, 604, 526, 42, 42);
        text(cue == "rear" ? "VEHICLE BEHIND" : "PERSON AHEAD", 550, 572, 14, amber);
      }
      // Preview identity stays in the operator controls, outside the glasses.
    }
    if (state.diagnostics || state.demo) {
      if (state.panels & navigation_panel) navigation_panel_view(state, now);
      if (state.panels & telemetry_panel) telemetry_panel_view(state, now);
    } else if (state.panels) {
      if (state.panels & navigation_panel) navigation_panel_view(state, now);
      if (!state.quiet) {
        text("helmetd", 32, 22, 24, white);
        // Reference edge affordances; no fabricated Wi-Fi or battery values.
        symbol(6, 1198, 530, 36, 28);
        triangle(1241, 545, 1236, 540, 1236, 550, white);
        if (state.route_map.points.size() < 2) {
          symbol(6, 46, 534, 28, 22);
          triangle(34, 545, 39, 540, 39, 550, white);
        }
        if (state.assistant_phase == "offline" ||
            !HudState::fresh(state.assistant_at, now, std::chrono::milliseconds(3000)))
          symbol(7, 1208, 638, 28, 38);
      }
      bool problem = options.camera != "none" && !state.camera_fresh(now);
      for (std::size_t i=0; i<state.extra_cameras.size(); ++i)
        if (state.extra_cameras[i].frames) problem |= !state.extra_camera_fresh(i, now);
      if (problem) { text("!", 1212, 32, 18, amber); }
    }
    if (state.diagnostics) {
      text("HELMETD / SYSTEM", 64, 42, 16, muted);
      text(options.host.empty() ? (options.output.empty() ? "LOCAL PREVIEW" : "RECORDING") : "UDP SEND / UNCONFIRMED",
          960, 42, 13, muted);
      char counter[64];
      std::snprintf(counter, sizeof(counter), "F%06llu  %07.2fs", static_cast<unsigned long long>(frame), elapsed);
      text(counter, 64, 668, 13, muted);
    }
    if (state.panels && !state.quiet && !directional_alert &&
        state.notification_at && HudState::fresh(state.notification_at, now, std::chrono::milliseconds(3000)) &&
        elapsed-notice_entered >= 2) {
      const float age = std::chrono::duration<float>(now-*state.notification_at).count();
      composition_opacity = std::min(ease_out(age/.22f), ease_out((3-age)/.35f));
      quad(935, 225, 32, 32, white, 8);
      text(state.notification_app, 978, 222, 12, muted);
      float sender_width = 0;
      for (unsigned char c : state.notification_sender)
        sender_width += (glyph_advances[(c >= 32 && c <= 126 ? c : '?')-32]+1.5f)/64.f;
      text(state.notification_sender, 978, 244, std::min(16.f, 260.f/std::max(1.f,sender_width)), white);
      composition_opacity = 1;
    }
    if (state.confirmation_at && HudState::fresh(state.confirmation_at, now, std::chrono::milliseconds(2000))) {
      notice = state.confirmation;
      notice_entered = elapsed - std::chrono::duration<double>(now-*state.confirmation_at).count();
    }
    if (state.panels && !directional_alert && !notice.empty() && elapsed-notice_entered < 2) {
      const float age = elapsed-notice_entered;
      composition_opacity = std::min(ease_out(age/.2f), ease_out((2-age)/.35f));
      composition_offset = 4*(1-composition_opacity);
      text(notice, 460, 552, 16, white);
      composition_offset = 0;
      composition_opacity = 1;
    }
    if (state.panels && state.assistant_phase != "offline" &&
        HudState::fresh(state.assistant_at, now, std::chrono::milliseconds(3000))) {
      symbol(7, 1026, 660, 22, 28);
      const bool speaking = state.assistant_phase == "speaking";
      for (int i = 0; i < 4; ++i) {
        const float height = 4 + (speaking ? 7 : 3) * (0.5 + 0.5 * std::sin(elapsed * (speaking ? 12 : 4) + i));
        quad(1056 + i * 5, 680 - height, 2, height, cyan);
      }
      const std::string label = speaking ? "SPEAKING" : state.assistant_phase == "thinking" ? "PROCESSING" : "LISTENING";
      text(label, 1090, 667, 13, white);
    }
  }
};

MetalRenderer::MetalRenderer(const HudOptions& options) {
  @autoreleasepool { impl_ = std::make_unique<Impl>(options); }
}
MetalRenderer::~MetalRenderer() { if (impl_->window) [impl_->window close]; }
std::string MetalRenderer::device_name() const { return impl_->device.name.UTF8String; }

bool MetalRenderer::poll_events(HudState& state, Time now) {
  if (!impl_->window) return true;
  @autoreleasepool {
    while (auto* event = [NSApp nextEventMatchingMask:NSEventMaskAny untilDate:NSDate.distantPast
                             inMode:NSDefaultRunLoopMode dequeue:YES]) {
      if (event.type == NSEventTypeKeyDown) {
        switch (event.keyCode) {
          case 53: case 12: return false;  // Esc / Q
          case 49:
            if (!state.demo) break;
            if (state.warning(now)) state.warning_until.reset();
            else state.trigger_warning(now);
            break;
          case 126: case 124: if (state.demo) state.change_speed(1); break;
          case 125: case 123: if (state.demo) state.change_speed(-1); break;
          case 5: if (state.demo && !event.isARepeat) state.next_gear(); break;
          case 37: if (!event.isARepeat) state.set_signal(state.active_signal(now) == "left" ? "off" : "left", now); break;
          case 15: if (!event.isARepeat) state.set_signal(state.active_signal(now) == "right" ? "off" : "right", now); break;
          case 11: if (!event.isARepeat) { state.camera_view = state.camera_view == "rear" ? "auto" : "rear"; state.panels |= camera_panel; } break;
          case 7: if (!event.isARepeat) { state.set_signal("off", now); state.camera_view = "auto"; } break;
          case 8: if (state.demo && !event.isARepeat) state.camera_enabled = !state.camera_enabled; break;
          case 17: if (state.demo && !event.isARepeat) state.telemetry_enabled = !state.telemetry_enabled; break;
          case 18: if (!event.isARepeat) state.panels ^= camera_panel; break;  // 1
          case 19: if (!event.isARepeat) state.panels ^= navigation_panel; break;  // 2
          case 20: if (!event.isARepeat) state.panels ^= telemetry_panel; break;  // 3
          case 2: if (!event.isARepeat) state.diagnostics = !state.diagnostics; break;  // D
          default: [NSApp sendEvent:event]; break;
        }
      } else [NSApp sendEvent:event];
    }
  }
  // Minimizing/hiding the preview is not a request to stop the helmet stream.
  return impl_->window.isVisible || impl_->window.isMiniaturized || NSApp.isHidden;
}

void MetalRenderer::update_extra_camera(std::size_t index, const CameraFrame& frame) {
  auto& r = *impl_;
  if (index >= r.extra_textures.size()) throw std::runtime_error("Invalid extra camera index");
  [r.extra_textures[index] replaceRegion:MTLRegionMake2D(0, 0, CameraFrame::width, CameraFrame::height)
      mipmapLevel:0 withBytes:frame.bgra.data() bytesPerRow:CameraFrame::width * 4];
  r.extra_uploaded[index] = true;
}

std::span<const std::uint8_t> MetalRenderer::render(const HudState& state, const CameraFrame* camera,
    Time now, double elapsed, std::uint64_t frame, bool readback) {
  auto& r = *impl_;
  @autoreleasepool {
    if (camera) {
      [r.camera_texture replaceRegion:MTLRegionMake2D(0, 0, CameraFrame::width, CameraFrame::height)
          mipmapLevel:0 withBytes:camera->bgra.data() bytesPerRow:CameraFrame::width * 4];
      r.camera_uploaded = true;
    }
    r.compose(state, now, elapsed, frame);
    const auto size = r.vertices.size() * sizeof(Vertex);
    if (size > r.vertex_buffer.length) throw std::runtime_error("HUD geometry exceeds frame budget");
    if (size) std::memcpy(r.vertex_buffer.contents, r.vertices.data(), size);
    auto command = [r.queue commandBuffer];
    auto* pass = [MTLRenderPassDescriptor renderPassDescriptor];
    pass.colorAttachments[0].texture = r.target;
    pass.colorAttachments[0].loadAction = MTLLoadActionClear;
    pass.colorAttachments[0].storeAction = MTLStoreActionStore;
    pass.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
    auto encoder = [command renderCommandEncoderWithDescriptor:pass];
    [encoder setRenderPipelineState:r.pipeline];
    [encoder setVertexBuffer:r.vertex_buffer offset:0 atIndex:0];
    auto draw_hud = [&](id<MTLRenderCommandEncoder> encoder) {
    for (const auto& draw : r.draws) {
      [encoder setFragmentBytes:&draw.texture length:sizeof(draw.texture) atIndex:0];
      const auto texture = draw.texture == 8 ? r.notification_texture : draw.texture == 7 ? r.symbol_texture : draw.texture == 6 ? r.map_texture : draw.texture >= 3 ? r.extra_textures[draw.texture - 3] :
          draw.texture == 2 ? r.camera_texture : r.atlas;
      [encoder setFragmentTexture:texture atIndex:0];
      [encoder drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:draw.first vertexCount:draw.count];
    }
    };
    draw_hud(encoder);
    [encoder endEncoding];
    auto blit = [command blitCommandEncoder];
    if (readback) {
      [blit copyFromTexture:r.target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0, 0, 0)
          sourceSize:MTLSizeMake(r.options.width, r.options.height, 1) toBuffer:r.readback_buffer
          destinationOffset:0 destinationBytesPerRow:r.row_bytes destinationBytesPerImage:r.row_bytes * r.options.height];
    }
    id<CAMetalDrawable> drawable = nil;
    // An occluded preview can exhaust its drawable pool and block nextDrawable
    // for a second. The Pi stream must keep rendering offscreen regardless.
    if (r.layer && !r.window.isMiniaturized &&
        (r.window.occlusionState & NSWindowOcclusionStateVisible)) {
      drawable = [r.layer nextDrawable];

    }
    [blit endEncoding];
    if (drawable) {
      // Desktop-only composition. The streamed/readback target remains black-backed.
      auto* preview = [MTLRenderPassDescriptor renderPassDescriptor];
      preview.colorAttachments[0].texture = drawable.texture;
      preview.colorAttachments[0].loadAction = MTLLoadActionClear;
      preview.colorAttachments[0].storeAction = MTLStoreActionStore;
      preview.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
      auto screen = [command renderCommandEncoderWithDescriptor:preview];
      [screen setRenderPipelineState:r.pipeline];
      if (state.camera_fresh(now) && r.camera_uploaded) {
        const Color background{1, 1, 1, .85f};
        const Vertex full[] = {{-1,1,0,0,background},{-1,-1,0,1,background},
          {1,1,1,0,background},{1,1,1,0,background},{-1,-1,0,1,background},{1,-1,1,1,background}};
        const int mode = 2;
        [screen setVertexBytes:full length:sizeof(full) atIndex:0];
        [screen setFragmentBytes:&mode length:sizeof(mode) atIndex:0];
        [screen setFragmentTexture:r.camera_texture atIndex:0];
        [screen drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:6];
      }
      [screen setVertexBuffer:r.vertex_buffer offset:0 atIndex:0];
      draw_hud(screen);
      [screen endEncoding];
      [command presentDrawable:drawable];
    }
    [command commit];
    // First bridge deliberately serializes one GPU frame before CPU readback.
    // No texture/buffer is reused until GPU completion. Profile before optimizing.
    [command waitUntilCompleted];
    if (command.status == MTLCommandBufferStatusError)
      throw std::runtime_error("Metal frame failed: " + std::string(command.error.localizedDescription.UTF8String));
    if (readback) {
      r.pixels.resize(r.options.width * r.options.height * 4);
      const auto* source = static_cast<const std::uint8_t*>(r.readback_buffer.contents);
      for (int y = 0; y < r.options.height; ++y)
        std::memcpy(r.pixels.data() + y * r.options.width * 4, source + y * r.row_bytes, r.options.width * 4);
    }
  }
  return r.pixels;
}

void MetalRenderer::save_snapshot(const std::string& path) {
  auto& r = *impl_;
  if (r.pixels.empty()) throw std::runtime_error("No frame available for snapshot");
  auto color_space = CGColorSpaceCreateDeviceRGB();
  auto context = CGBitmapContextCreate(r.pixels.data(), r.options.width, r.options.height, 8,
      r.options.width * 4, color_space, static_cast<CGBitmapInfo>(kCGImageAlphaPremultipliedFirst) | kCGBitmapByteOrder32Little);
  CGColorSpaceRelease(color_space);
  if (!context) throw std::runtime_error("Cannot create snapshot");
  auto image = CGBitmapContextCreateImage(context);
  NSBitmapImageRep* bitmap = [[NSBitmapImageRep alloc] initWithCGImage:image];
  NSData* png = [bitmap representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
  CGImageRelease(image);
  CGContextRelease(context);
  NSError* error = nil;
  if (![png writeToFile:[NSString stringWithUTF8String:path.c_str()] options:NSDataWritingWithoutOverwriting error:&error])
    throw std::runtime_error("Snapshot: " + std::string(error.localizedDescription.UTF8String));
}
}  // namespace helmetd
