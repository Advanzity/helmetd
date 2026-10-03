#include "metal_renderer.hpp"

#import <AppKit/AppKit.h>
#import <CoreText/CoreText.h>
#import <Metal/Metal.h>
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
constexpr Color white{0.92f, 0.97f, 1.0f};
constexpr Color muted{0.43f, 0.53f, 0.57f};
constexpr Color cyan{0.28f, 0.88f, 0.94f};
constexpr Color amber{1.0f, 0.65f, 0.22f};
constexpr Color panel{0.018f, 0.029f, 0.035f};
struct Vertex { float x, y, u, v; Color color; };
static_assert(sizeof(Vertex) == 32);
struct Draw { std::size_t first, count; int texture; };
constexpr int cell_width = 48;
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
  constexpr sampler sampling(coord::normalized, address::clamp_to_edge, filter::linear);
  if (mode == 0) return in.color;
  float4 sampled = image.sample(sampling, in.uv);
  if (mode == 1) return float4(in.color.rgb, in.color.a * sampled.a);
  return float4(sampled.rgb, 1);
}
)METAL";

id<MTLTexture> make_texture(id<MTLDevice> device, int width, int height,
                            MTLTextureUsage usage, MTLStorageMode storage) {
  auto* descriptor = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
      width:width height:height mipmapped:NO];
  descriptor.usage = usage;
  descriptor.storageMode = storage;
  auto texture = [device newTextureWithDescriptor:descriptor];
  if (!texture) throw std::runtime_error("Cannot allocate Metal texture");
  return texture;
}

id<MTLTexture> make_atlas(id<MTLDevice> device) {
  std::vector<std::uint8_t> pixels(atlas_width * atlas_height * 4, 0);
  auto color_space = CGColorSpaceCreateDeviceRGB();
  auto context = CGBitmapContextCreate(pixels.data(), atlas_width, atlas_height, 8,
      atlas_width * 4, color_space, static_cast<CGBitmapInfo>(kCGImageAlphaPremultipliedFirst) | kCGBitmapByteOrder32Little);
  CGColorSpaceRelease(color_space);
  if (!context) throw std::runtime_error("Cannot create glyph atlas");
  NSFont* font = [NSFont monospacedSystemFontOfSize:64 weight:NSFontWeightMedium];
  NSDictionary* attributes = @{NSFontAttributeName:font, NSForegroundColorAttributeName:NSColor.whiteColor};
  for (int c = 32; c <= 126; ++c) {
    const int index = c - 32;
    NSString* character = [NSString stringWithFormat:@"%c", c];
    NSAttributedString* string = [[NSAttributedString alloc] initWithString:character attributes:attributes];
    CTLineRef line = CTLineCreateWithAttributedString((__bridge CFAttributedStringRef)string);
    CGContextSetTextPosition(context, (index % 16) * cell_width + 3,
        atlas_height - (index / 16) * cell_height - 64);
    CTLineDraw(line, context);
    CFRelease(line);
  }
  CGContextRelease(context);
  auto texture = make_texture(device, atlas_width, atlas_height, MTLTextureUsageShaderRead, MTLStorageModeShared);
  [texture replaceRegion:MTLRegionMake2D(0, 0, atlas_width, atlas_height) mipmapLevel:0
      withBytes:pixels.data() bytesPerRow:atlas_width * 4];
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
  id<MTLBuffer> vertex_buffer;
  id<MTLBuffer> readback_buffer;
  NSWindow* window = nil;
  CAMetalLayer* layer = nil;
  std::vector<Vertex> vertices;
  std::vector<Draw> draws;
  std::vector<std::uint8_t> pixels;
  bool camera_uploaded = false;
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
    camera_texture = make_texture(device, CameraFrame::width, CameraFrame::height,
        MTLTextureUsageShaderRead, MTLStorageModeShared);
    vertex_buffer = [device newBufferWithLength:sizeof(Vertex) * 16000 options:MTLResourceStorageModeShared];
    row_bytes = (o.width * 4 + 255) & ~std::size_t(255);
    readback_buffer = [device newBufferWithLength:row_bytes * o.height options:MTLResourceStorageModeShared];
    if (!queue || !vertex_buffer || !readback_buffer) throw std::runtime_error("Cannot allocate Metal resources");
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
      window.title = @"helmetd | Space: warning   Arrows: speed   G: gear   C: camera stall   T: telemetry stall   Q: quit";
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

  void quad(float x, float y, float w, float h, Color color, int texture = 0,
            float u = 0, float v = 0, float uw = 1, float vh = 1) {
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
      x += 38.5f * scale;
    }
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

  void compose(const HudState& state, Time now, double elapsed, std::uint64_t frame) {
    vertices.clear(); draws.clear();
    text("helmetd", 52, 38, 26, white);
    quad(52, 78, 28, 2, cyan);
    text("BENCH / SIMULATED TELEMETRY", 96, 66, 14, muted);
    text(options.host.empty() ? (options.output.empty() ? "LOCAL PREVIEW" : "RECORDING") : "UDP SEND / UNCONFIRMED",
        894, 42, 16, muted);

    // Leave the center of the wearer's view clear; warnings use one focal area.
    if (state.warning(now)) {
      quad(420, 144, 440, 89, {0.065f, 0.035f, 0.007f});
      quad(420, 144, 4, 89, amber);
      text("!", 440, 158, 39, amber);
      text("REAR APPROACH", 488, 157, 28, amber);
      text("SIMULATED WARNING", 489, 198, 14, amber);
    }

    const bool camera_fresh = state.camera_fresh(now) && camera_uploaded;
    const Color camera_color = state.warning(now) ? amber : cyan;
    text("REAR CAMERA", 884, 380, 18, camera_fresh ? camera_color : muted);
    text(options.camera == "test" ? "TEST FEED" : (options.camera == "udp" ? "RTP FEED" : "DISABLED"),
        1112, 382, 13, muted);
    quad(884, 416, 344, 193.5f, panel);
    if (camera_fresh) quad(884, 416, 344, 193.5f, white, 2);
    else {
      text("CAMERA UNAVAILABLE", 919, 477, 22, muted);
      text(state.camera_at ? "STALE FRAME HIDDEN" : "WAITING FOR VIDEO", 945, 517, 15, muted);
    }
    corners(882, 414, 348, 197.5f, camera_fresh ? camera_color : muted);
    text(camera_fresh ? (options.camera == "test" ? "SYNTHETIC INPUT" : "LOCAL DECODE ACTIVE") : "NO CURRENT IMAGE",
        884, 627, 13, muted);

    const bool telemetry_fresh = state.telemetry_fresh(now);
    const std::string speed = telemetry_fresh ? std::to_string(state.speed_mph) : "--";
    text(speed, 635 - static_cast<float>(speed.size()) * 55.35f, 524, 92, white);
    text("mph", 645, 597, 21, muted);
    quad(721, 555, 1, 76, muted);
    text("GEAR", 749, 545, 15, muted);
    text(telemetry_fresh ? (state.gear == 0 ? "N" : std::to_string(state.gear)) : "-",
        756, 570, 45, telemetry_fresh ? cyan : muted);
    if (!telemetry_fresh) text("TELEMETRY LOST", 528, 641, 16, amber);
    else text("SIMULATED", 533, 650, 13, muted);

    char counter[64];
    std::snprintf(counter, sizeof(counter), "F%06llu  %07.2fs", static_cast<unsigned long long>(frame), elapsed);
    text(counter, 52, 650, 16, muted);
    text("HEAD-FIXED", 52, 620, 13, muted);
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
            if (state.warning(now)) state.warning_until.reset();
            else state.trigger_warning(now);
            break;
          case 126: case 124: state.change_speed(1); break;
          case 125: case 123: state.change_speed(-1); break;
          case 5: if (!event.isARepeat) state.next_gear(); break;
          case 8: if (!event.isARepeat) state.camera_enabled = !state.camera_enabled; break;
          case 17: if (!event.isARepeat) state.telemetry_enabled = !state.telemetry_enabled; break;
          default: [NSApp sendEvent:event]; break;
        }
      } else [NSApp sendEvent:event];
    }
  }
  return impl_->window.isVisible;
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
    std::memcpy(r.vertex_buffer.contents, r.vertices.data(), size);
    auto command = [r.queue commandBuffer];
    auto* pass = [MTLRenderPassDescriptor renderPassDescriptor];
    pass.colorAttachments[0].texture = r.target;
    pass.colorAttachments[0].loadAction = MTLLoadActionClear;
    pass.colorAttachments[0].storeAction = MTLStoreActionStore;
    pass.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
    auto encoder = [command renderCommandEncoderWithDescriptor:pass];
    [encoder setRenderPipelineState:r.pipeline];
    [encoder setVertexBuffer:r.vertex_buffer offset:0 atIndex:0];
    for (const auto& draw : r.draws) {
      [encoder setFragmentBytes:&draw.texture length:sizeof(draw.texture) atIndex:0];
      [encoder setFragmentTexture:draw.texture == 2 ? r.camera_texture : r.atlas atIndex:0];
      [encoder drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:draw.first vertexCount:draw.count];
    }
    [encoder endEncoding];
    auto blit = [command blitCommandEncoder];
    if (readback) {
      [blit copyFromTexture:r.target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0, 0, 0)
          sourceSize:MTLSizeMake(r.options.width, r.options.height, 1) toBuffer:r.readback_buffer
          destinationOffset:0 destinationBytesPerRow:r.row_bytes destinationBytesPerImage:r.row_bytes * r.options.height];
    }
    id<CAMetalDrawable> drawable = nil;
    if (r.layer && !r.window.isMiniaturized) {
      drawable = [r.layer nextDrawable];
      if (drawable) [blit copyFromTexture:r.target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0, 0, 0)
          sourceSize:MTLSizeMake(r.options.width, r.options.height, 1) toTexture:drawable.texture
          destinationSlice:0 destinationLevel:0 destinationOrigin:MTLOriginMake(0, 0, 0)];
    }
    [blit endEncoding];
    if (drawable) [command presentDrawable:drawable];
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
