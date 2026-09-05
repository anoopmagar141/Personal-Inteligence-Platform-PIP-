// Behaviour test for the sign-out control in the sidebar.
//
// The backend half of this is covered in test_sign_in.py. What is only
// checkable here is the wiring, which is the half that has historically gone
// missing in this project: session_key.lock() worked for months while nothing
// called it. A button that looks right and calls nothing would pass every
// other test in this repository.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/home_shell.dart';
import 'package:pip_flutter_client/theme.dart';

class FakeApi extends ApiClient {
  FakeApi() : super('http://127.0.0.1:1/api/v1');

  int lockCalls = 0;
  Object? lockError;

  @override
  Future<void> lock() async {
    lockCalls++;
    if (lockError != null) throw lockError!;
  }

  // Everything the shell asks for on the way up. Answered rather than left to
  // throw, so a failure in this file is about signing out and not about a
  // screen that could not finish building.
  @override
  Future<Map<String, dynamic>> getStatus() async => {'pending_count': 0};

  @override
  Future<List<dynamic>> getProjects() async => [];

  @override
  Future<List<dynamic>> getConversations({String? projectId}) async => [];
}

/// pump, never pumpAndSettle.
///
/// WsChatClient reschedules its own reconnect on every failed attempt, and
/// this shell points at a port with nothing behind it, so there is always
/// another frame pending and "settled" is a state this tree never reaches.
/// Fixed durations advance past the dialog transition instead of waiting for
/// a quiet that will not come.
Future<void> _tick(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 400));
}

/// Records that the shell asked to be dismissed.
///
/// A mutable holder rather than a returned int: the count is read AFTER the
/// taps, and a plain `int` return would be captured at pump time and forever
/// read 0 - a test that appears to check the callback while asserting a
/// constant.
class SignOutSpy {
  int count = 0;
}

Future<SignOutSpy> _pumpShell(WidgetTester tester, FakeApi api) async {
  final spy = SignOutSpy();
  tester.view.physicalSize = const Size(1600, 1200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light,
    home: HomeShell(
      api: api,
      themeMode: ThemeMode.light,
      onCycleTheme: () {},
      onSignedOut: () => spy.count++,
    ),
  ));
  await tester.pump();
  return spy;
}

void main() {
  testWidgets('asks before signing out, and does nothing if declined', (tester) async {
    final api = FakeApi();
    final spy = await _pumpShell(tester, api);

    await tester.tap(find.text('Sign out'));
    await _tick(tester);
    expect(find.text('Sign out?'), findsOneWidget);

    await tester.tap(find.text('Cancel'));
    await _tick(tester);

    expect(api.lockCalls, 0);
    expect(spy.count, 0);
  });

  testWidgets('locks the backend when confirmed', (tester) async {
    final api = FakeApi();
    final spy = await _pumpShell(tester, api);

    await tester.tap(find.text('Sign out'));
    await _tick(tester);
    // The dialog's own button, not the sidebar item behind it.
    await tester.tap(find.widgetWithText(FilledButton, 'Sign out'));
    await _tick(tester);

    expect(api.lockCalls, 1);
    // The half that only this file can check: the backend being locked is
    // useless if the app stays on the screen it was already showing.
    expect(spy.count, 1);
  });

  testWidgets('stays put when the lock fails', (tester) async {
    // The one outcome worse than the error is leaving somebody on a sign-in
    // screen over a database that is still open. If the lock did not happen,
    // the screen must not pretend it did.
    final api = FakeApi()..lockError = Exception('backend said no');
    final spy = await _pumpShell(tester, api);

    await tester.tap(find.text('Sign out'));
    await _tick(tester);
    await tester.tap(find.widgetWithText(FilledButton, 'Sign out'));
    await _tick(tester);

    expect(api.lockCalls, 1);
    expect(spy.count, 0);
    expect(find.textContaining('Could not sign out'), findsOneWidget);
  });
}
