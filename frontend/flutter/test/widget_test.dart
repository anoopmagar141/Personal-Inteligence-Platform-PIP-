// Basic smoke test - confirms the app boots and shows the loading state
// while it checks onboarding status.
//
// Behaviour against real payloads is covered per screen (review_view_test,
// trace_view_test, profile_view_test, decisions_view_test,
// projects_view_test) with a fake ApiClient; the endpoints those screens call
// are covered by the Python suite. tool/validate_live.dart is the one that
// runs against a real server.

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
