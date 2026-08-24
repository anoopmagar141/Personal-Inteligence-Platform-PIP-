// Basic smoke test - confirms the app boots and shows the loading state
// while it checks onboarding status. Real REST/WS behavior against a live
// backend is covered separately (see docs/PIP_MASTER_REFERENCE.md's Flutter
// client section for how this was live-validated against the real server).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/main.dart';

void main() {
  testWidgets('shows a loading indicator immediately on launch', (WidgetTester tester) async {
    await tester.pumpWidget(const PipApp());
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.text('PIP'), findsOneWidget);
  });
}
