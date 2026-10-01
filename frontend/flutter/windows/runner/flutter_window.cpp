#include "flutter_window.h"

#include <flutter_windows.h>

#include <optional>

#include "flutter/generated_plugin_registrant.h"

FlutterWindow::FlutterWindow(const flutter::DartProject& project)
    : project_(project) {}

FlutterWindow::~FlutterWindow() {}

bool FlutterWindow::OnCreate() {
  if (!Win32Window::OnCreate()) {
    return false;
  }

  RECT frame = GetClientArea();

  // The size here must match the window dimensions to avoid unnecessary surface
  // creation / destruction in the startup path.
  flutter_controller_ = std::make_unique<flutter::FlutterViewController>(
      frame.right - frame.left, frame.bottom - frame.top, project_);
  // Ensure that basic setup of the controller was successful.
  if (!flutter_controller_->engine() || !flutter_controller_->view()) {
    return false;
  }
  RegisterPlugins(flutter_controller_->engine());
  SetChildContent(flutter_controller_->view()->GetNativeWindow());

  flutter_controller_->engine()->SetNextFrameCallback([&]() {
    this->Show();
  });

  // Flutter can complete the first frame before the "show window" callback is
  // registered. The following call ensures a frame is pending to ensure the
  // window is shown. It is a no-op if the first frame hasn't completed yet.
  flutter_controller_->ForceRedraw();

  return true;
}

void FlutterWindow::OnDestroy() {
  if (flutter_controller_) {
    flutter_controller_ = nullptr;
  }

  Win32Window::OnDestroy();
}

LRESULT
FlutterWindow::MessageHandler(HWND hwnd, UINT const message,
                              WPARAM const wparam,
                              LPARAM const lparam) noexcept {
  // Give Flutter, including plugins, an opportunity to handle window messages.
  if (flutter_controller_) {
    std::optional<LRESULT> result =
        flutter_controller_->HandleTopLevelWindowProc(hwnd, message, wparam,
                                                      lparam);
    if (result) {
      return *result;
    }
  }

  switch (message) {
    case WM_FONTCHANGE:
      flutter_controller_->engine()->ReloadSystemFonts();
      break;
    case WM_GETMINMAXINFO: {
      // The minimum is for the client area, where Flutter draws, but Windows
      // takes it as a whole-window size. The frame is measured from the live
      // window rather than computed, so it is right for whatever style and
      // DPI the window has now.
      HMONITOR monitor = MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST);
      double scale = FlutterDesktopGetDpiForMonitor(monitor) / 96.0;
      RECT window_rect, client_rect;
      GetWindowRect(hwnd, &window_rect);
      GetClientRect(hwnd, &client_rect);
      LONG frame_w = (window_rect.right - window_rect.left) - client_rect.right;
      LONG frame_h = (window_rect.bottom - window_rect.top) - client_rect.bottom;
      LONG min_w = static_cast<LONG>(kMinClientWidth * scale) + frame_w;
      LONG min_h = static_cast<LONG>(kMinClientHeight * scale) + frame_h;

      // Never larger than the screen's usable area. A 1366x768 laptop at 125%
      // is about 1093x576 logical after the taskbar, under the 640 minimum,
      // and a minimum it cannot satisfy would push the window off-screen
      // rather than keep it usable.
      MONITORINFO info = {sizeof(MONITORINFO)};
      if (GetMonitorInfo(monitor, &info)) {
        LONG work_w = info.rcWork.right - info.rcWork.left;
        LONG work_h = info.rcWork.bottom - info.rcWork.top;
        if (min_w > work_w) min_w = work_w;
        if (min_h > work_h) min_h = work_h;
      }

      auto* limits = reinterpret_cast<MINMAXINFO*>(lparam);
      limits->ptMinTrackSize.x = min_w;
      limits->ptMinTrackSize.y = min_h;
      return 0;
    }
  }

  return Win32Window::MessageHandler(hwnd, message, wparam, lparam);
}
