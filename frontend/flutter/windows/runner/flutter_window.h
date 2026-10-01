#ifndef RUNNER_FLUTTER_WINDOW_H_
#define RUNNER_FLUTTER_WINDOW_H_

#include <flutter/dart_project.h>
#include <flutter/flutter_view_controller.h>

#include <memory>

#include "win32_window.h"

// The smallest client area the window can be dragged to, in logical pixels.
// Measured, not chosen: with the real font, the sidebar needs about 615px of
// height (it overflowed at 600) and four screens overflow sideways below
// 800px. test/minimum_window_test.dart reads these two lines and lays out
// every tab at exactly this size, so change them only together with that
// test passing. tool/check_min_window.py checks the built window enforces it.
constexpr int kMinClientWidth = 800;
constexpr int kMinClientHeight = 640;

// A window that does nothing but host a Flutter view.
class FlutterWindow : public Win32Window {
 public:
  // Creates a new FlutterWindow hosting a Flutter view running |project|.
  explicit FlutterWindow(const flutter::DartProject& project);
  virtual ~FlutterWindow();

 protected:
  // Win32Window:
  bool OnCreate() override;
  void OnDestroy() override;
  LRESULT MessageHandler(HWND window, UINT const message, WPARAM const wparam,
                         LPARAM const lparam) noexcept override;

 private:
  // The project to run.
  flutter::DartProject project_;

  // The Flutter instance hosted by this window.
  std::unique_ptr<flutter::FlutterViewController> flutter_controller_;
};

#endif  // RUNNER_FLUTTER_WINDOW_H_
