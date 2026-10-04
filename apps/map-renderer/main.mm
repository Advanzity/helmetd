#import <AppKit/AppKit.h>
#import <WebKit/WebKit.h>
#include <sys/file.h>
#include <fcntl.h>

@interface MapHost : NSObject <WKNavigationDelegate>
@property(strong) WKWebView *view;
@property(strong) NSWindow *window;
@property(strong) NSTimer *timer;
@property(strong) id activity;
@end
@implementation MapHost
- (void)webViewWebContentProcessDidTerminate:(WKWebView *)webView { [webView reload]; }
- (void)webView:(WKWebView *)webView didFailProvisionalNavigation:(WKNavigation *)navigation withError:(NSError *)error {
  NSLog(@"Map service unavailable: %@", error.localizedDescription);
}
@end
int main(int argc, char **argv) {
  @autoreleasepool {
    if (argc != 2) return 2;
    int lock = open(argv[1], O_CREAT | O_RDWR | O_NOFOLLOW, 0600);
    if (lock < 0 || flock(lock, LOCK_EX | LOCK_NB) < 0) return 3;
    [NSApplication sharedApplication];
    [NSApp setActivationPolicy:NSApplicationActivationPolicyProhibited];
    MapHost *host = [MapHost new];
    WKWebViewConfiguration *configuration = [WKWebViewConfiguration new];
    if (@available(macOS 14.0, *)) configuration.preferences.inactiveSchedulingPolicy = WKInactiveSchedulingPolicyNone;
    host.view = [[WKWebView alloc] initWithFrame:NSMakeRect(0,0,640,360) configuration:configuration];
    host.view.navigationDelegate = host;
    host.window = [[NSWindow alloc] initWithContentRect:NSMakeRect(-10000,-10000,640,360)
        styleMask:NSWindowStyleMaskBorderless backing:NSBackingStoreBuffered defer:NO];
    host.window.contentView = host.view;
    [host.window orderBack:nil];
    host.activity = [NSProcessInfo.processInfo beginActivityWithOptions:NSActivityUserInitiated reason:@"Render helmet navigation"];
    [host.view loadRequest:[NSURLRequest requestWithURL:[NSURL URLWithString:@"http://127.0.0.1:8016/assets/hud-map.html"]]];
    host.timer = [NSTimer scheduledTimerWithTimeInterval:5 repeats:YES block:^(NSTimer *timer) {
      [host.view evaluateJavaScript:@"window.helmetMapReady === true" completionHandler:^(id value, NSError *error) {
        if (error || ![value boolValue]) [host.view reload];
      }];
    }];
    [NSApp run];
  }
}
