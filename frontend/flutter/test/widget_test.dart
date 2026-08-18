// Smoke test for the throwaway Flutter spike - just confirms the app builds
// and shows its initial shell, not exercising the WebSocket flow itself
// (that needs a live fake_echo_server.py, done separately).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_spike/main.dart';

void main() {
  testWidgets('Spike app builds and shows the connect bar', (WidgetTester tester) async {
    await tester.pumpWidget(const SpikeApp());

    expect(find.text('PIP Flutter Spike - fake echo WS'), findsOneWidget);
    expect(find.widgetWithText(ElevatedButton, 'Connect'), findsOneWidget);
    expect(find.widgetWithText(ElevatedButton, 'Send'), findsOneWidget);
    expect(find.text('disconnected'), findsOneWidget);
  });
}
