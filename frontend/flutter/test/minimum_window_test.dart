// Nothing overflows at the smallest size the window can be made.
//
// The 2026-10-01 audit found no minimum window size at all: the runner opened
// at 1280x720 and Windows would let it be dragged down to a sliver. Measured
// with the real font, the sidebar ran out of height at 800x600 and four
// screens overflowed sideways at 640x480 and below.
//
// The minimum is enforced by the Windows runner (WM_GETMINMAXINFO in
// windows/runner/flutter_window.cpp), and its numbers live in exactly one
// place, flutter_window.h. This test reads them from that header rather than
// repeating them, so moving the minimum without checking the layout at the
// new size is a failing test, not a silent drift between C++ and Dart.
// tool/check_min_window.py is the other half: that the built window really
// refuses to go smaller.
//
// Text is measured in Segoe UI, the font the app actually renders in on
// Windows. flutter_test's default font draws every glyph as a full em square,
// far wider than real text; under it the chat footer "overflows" at 1280x720,
// which it does not on screen. If the font file is missing the test falls back
// to that wider font, which can only fail spuriously, never pass falsely.

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/home_shell.dart';
import 'package:pip_flutter_client/screens/sign_in_screen.dart';
import 'package:pip_flutter_client/theme.dart';

class FakeApi extends ApiClient {
  FakeApi() : super('http://127.0.0.1:1/api/v1');

  @override
  Future<Map<String, dynamic>> getStatus() async => {'pending_count': 0};

  @override
  Future<List<dynamic>> getProjects() async => [];

  @override
  Future<List<dynamic>> getConversations({String? projectId}) async => [];

  @override
  Future<Map<String, dynamic>> authProfiles() async => {
        'active': 'default',
        'profiles': [
          {'slug': 'default', 'name': 'Default', 'exists': true},
        ],
      };
}

const _tabs = ['Chat', 'Review', 'Profile', 'Decisions', 'Projects', 'Documents', 'Providers', 'Backup', 'Trace'];

/// The runner's minimum client size, in logical pixels, read from the header
/// that defines it.
Size _minimumFromRunner() {
  final header = File('windows/runner/flutter_window.h').readAsStringSync();
  int read(String name) {
    final match = RegExp('constexpr int $name = (\\d+);').firstMatch(header);
    if (match == null) fail('windows/runner/flutter_window.h does not define $name');
    return int.parse(match.group(1)!);
  }

  return Size(read('kMinClientWidth').toDouble(), read('kMinClientHeight').toDouble());
}

/// Collects overflow reports instead of letting the first one end the test,
/// so a failure lists every screen that broke, not just the first.
List<String> _collectOverflows() {
  final found = <String>[];
  FlutterError.onError = (details) {
    final text = details.exceptionAsString();
    if (!text.contains('overflowed')) {
      FlutterError.presentError(details);
      return;
    }
    final where = RegExp(r'lib/[^\s:]+\.dart:\d+').firstMatch(details.toString())?.group(0);
    found.add('${text.split('\n').first} at $where');
  };
  return found;
}

void main() {
  setUpAll(() async {
    // Registered under both names: Roboto is what the Material theme asks for
    // under flutter_test's default platform, Segoe UI is what Windows uses.
    for (final family in ['Roboto', 'Segoe UI']) {
      final loader = FontLoader(family);
      for (final face in ['segoeui', 'segoeuib', 'segoeuisl']) {
        final file = File('C:/Windows/Fonts/$face.ttf');
        if (!file.existsSync()) continue;
        final bytes = file.readAsBytesSync();
        loader.addFont(Future.value(ByteData.view(bytes.buffer)));
      }
      await loader.load();
    }
  });

  testWidgets('every tab fits the minimum window', (tester) async {
    final minimum = _minimumFromRunner();
    tester.view.physicalSize = minimum;
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final handler = FlutterError.onError;
    final overflows = _collectOverflows();
    addTearDown(() => FlutterError.onError = handler);

    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light,
      home: HomeShell(api: FakeApi(), themeMode: ThemeMode.light, onCycleTheme: () {}, onSignedOut: () {}),
    ));
    await tester.pump();

    for (final tab in _tabs) {
      final before = overflows.length;
      await tester.tap(find.text(tab).first, warnIfMissed: false);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      for (var i = before; i < overflows.length; i++) {
        overflows[i] = '$tab: ${overflows[i]}';
      }
    }

    FlutterError.onError = handler;
    expect(overflows, isEmpty, reason: 'at ${minimum.width.toInt()}x${minimum.height.toInt()}:\n${overflows.join('\n')}');
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('first-run sign-in fits the minimum window', (tester) async {
    final minimum = _minimumFromRunner();
    tester.view.physicalSize = minimum;
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final handler = FlutterError.onError;
    final overflows = _collectOverflows();
    addTearDown(() => FlutterError.onError = handler);

    // Setup rather than locked: it has the extra confirm field, so it is the
    // taller of the two.
    await tester.pumpWidget(MaterialApp(
      home: Builder(
        builder: (context) => MediaQuery(
          data: MediaQuery.of(context).copyWith(disableAnimations: true),
          child: SignInScreen(api: FakeApi(), state: AuthState.setup, onUnlocked: () {}),
        ),
      ),
    ));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    FlutterError.onError = handler;
    expect(overflows, isEmpty, reason: overflows.join('\n'));
    await tester.pumpWidget(const SizedBox());
  });
}
