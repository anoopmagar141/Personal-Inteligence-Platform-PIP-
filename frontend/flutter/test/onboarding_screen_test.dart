// Behaviour tests for the first screen anybody sees.
//
// Two things here are easy to get wrong in a way nothing else catches. The
// calling name is optional, so the payload must be able to omit it rather than
// send an empty string the backend then has to interpret. And the project
// field creates a real project from whatever is typed into it - including the
// word somebody types when they mean "none".

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/onboarding_screen.dart';
import 'package:pip_flutter_client/theme.dart';

class FakeApi extends ApiClient {
  FakeApi() : super('http://127.0.0.1:8765/api/v1');

  Map<String, dynamic>? submitted;

  @override
  Future<void> completeOnboarding(Map<String, dynamic> payload) async {
    submitted = payload;
  }
}

Future<void> _pump(WidgetTester tester, FakeApi api, {VoidCallback? onComplete}) async {
  // The form is nine fields tall and the default 800x600 test surface is not,
  // so the dropdown overflows and the submit button lands off screen - which
  // fails as "the tap did nothing" rather than as a layout complaint. Same
  // treatment chat_scope_test and providers_view_test already give their own
  // wide screens.
  tester.view.physicalSize = const Size(1200, 2000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  // AppTheme.light, not a bare MaterialApp. The screen is built against this
  // theme's type scale, and Material's larger defaults make the interaction-
  // style dropdown wider than the 440px card - which surfaces as a layout
  // overflow that fails every test in this file for a reason that has nothing
  // to do with what any of them assert.
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light,
    home: OnboardingScreen(api: api, onComplete: onComplete ?? () {}),
  ));
  await tester.pumpAndSettle();
}

Future<void> _fillRequired(WidgetTester tester) async {
  await tester.enterText(find.widgetWithText(TextFormField, 'Full name *'), 'Anup Magar');
}

void main() {
  testWidgets('sends the calling name alongside the full one', (tester) async {
    final api = FakeApi();
    await _pump(tester, api);

    await _fillRequired(tester);
    await tester.enterText(
      find.widgetWithText(TextFormField, 'What should PIP call you?'),
      'saru',
    );
    await tester.tap(find.text('Complete setup'));
    await tester.pumpAndSettle();

    expect(api.submitted!['name'], 'Anup Magar');
    expect(api.submitted!['preferred_name'], 'saru');
  });

  testWidgets('omits the calling name entirely when it is left blank', (tester) async {
    // Absent, not "". The backend stores a blank as NULL either way, but a key
    // that is present and empty is a claim that somebody answered the
    // question, and every later reader has to know to disbelieve it.
    final api = FakeApi();
    await _pump(tester, api);

    await _fillRequired(tester);
    await tester.tap(find.text('Complete setup'));
    await tester.pumpAndSettle();

    expect(api.submitted!.containsKey('preferred_name'), isFalse);
  });

  testWidgets('a full name is still required', (tester) async {
    final api = FakeApi();
    await _pump(tester, api);

    await tester.tap(find.text('Complete setup'));
    await tester.pumpAndSettle();

    expect(api.submitted, isNull);
    expect(find.text('Required'), findsOneWidget);
  });

  testWidgets('creates no project when the project field is left blank', (tester) async {
    final api = FakeApi();
    await _pump(tester, api);

    await _fillRequired(tester);
    await tester.tap(find.text('Complete setup'));
    await tester.pumpAndSettle();

    expect(api.submitted!.containsKey('current_project'), isFalse);
  });

  testWidgets('does not promise that anything is locked once set', (tester) async {
    // It said name, language and timezone were permanent. They are editable
    // from the profile screen, and had been for a while - the copy was simply
    // never updated, which is the same class of defect as a docstring
    // describing a code path nobody wired.
    await _pump(tester, FakeApi());

    expect(find.textContaining('locked once set'), findsNothing);
    expect(find.textContaining('change any of this later'), findsOneWidget);
  });
}
