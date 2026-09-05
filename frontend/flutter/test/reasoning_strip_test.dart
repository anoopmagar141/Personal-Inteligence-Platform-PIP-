// The live "what PIP is doing" strip.
//
// Every assertion here is about honesty rather than looks: that a stage which
// found nothing says so, that the strip reports what the backend sent instead
// of a sentence this widget composed, and that it does not claim to be working
// once the answer has arrived.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/theme.dart';
import 'package:pip_flutter_client/widgets/reasoning_strip.dart';
import 'package:pip_flutter_client/widgets/thinking_orb.dart';

ReasoningStep _step(String stage, String label, String detail, [String status = 'ok']) =>
    ReasoningStep(stage: stage, label: label, detail: detail, status: status);

Future<void> _pump(WidgetTester tester, List<ReasoningStep> steps, {bool active = true}) async {
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light,
    home: Scaffold(body: ReasoningStrip(steps: steps, active: active)),
  ));
  // pump, not pumpAndSettle: the orb animates forever by design, so there is
  // no settled frame to wait for.
  await tester.pump();
}

void main() {
  testWidgets('says only "Thinking" before any stage has reported', (tester) async {
    // The window between sending and the first event. Naming a stage here
    // would be asserting one that may not have run.
    await _pump(tester, const []);

    expect(find.text('Thinking'), findsOneWidget);
  });

  testWidgets('shows the latest stage as the current one', (tester) async {
    await _pump(tester, [
      _step('decisions', 'Checking your decisions', '2 recorded'),
      _step('documents', 'Searching your documents', '3 passages from 2 documents'),
    ]);

    expect(find.text('Searching your documents'), findsOneWidget);
    expect(find.text('3 passages from 2 documents'), findsOneWidget);
    // The earlier one is still visible, as a finished line.
    expect(find.textContaining('Checking your decisions'), findsOneWidget);
  });

  testWidgets('a stage that found nothing still says what it found', (tester) async {
    // The distinction the whole feature exists for. An empty document search
    // and a document search that was never run are identical downstream, and
    // telling them apart is the entire diagnosis when an answer is wrong.
    await _pump(tester, [
      _step('documents', 'Searching your documents', 'nothing close enough', 'empty'),
      _step('writing', 'Writing', 'llama3.1:8b'),
    ]);

    expect(find.textContaining('nothing close enough'), findsOneWidget);
  });

  testWidgets('renders the backend sentence rather than one of its own', (tester) async {
    // If this widget ever starts mapping stage ids to its own copy, it will
    // drift from what the backend actually did - and it has no way to know a
    // lookup found three passages.
    await _pump(tester, [_step('documents', 'Rummaging about', 'seventeen things')]);

    expect(find.text('Rummaging about'), findsOneWidget);
    expect(find.text('seventeen things'), findsOneWidget);
  });

  testWidgets('stops animating once the answer has arrived', (tester) async {
    await _pump(
      tester,
      [_step('writing', 'Writing', 'llama3.1:8b')],
      active: false,
    );

    final orb = tester.widget<ThinkingOrb>(find.byType(ThinkingOrb));
    expect(orb.state, OrbState.idle);
  });

  testWidgets('the orb reflects which stage is running', (tester) async {
    await _pump(tester, [_step('documents', 'Searching your documents', '1 passage')]);
    expect(tester.widget<ThinkingOrb>(find.byType(ThinkingOrb)).state, OrbState.searching);

    await _pump(tester, [_step('writing', 'Writing', 'llama3.1:8b')]);
    expect(tester.widget<ThinkingOrb>(find.byType(ThinkingOrb)).state, OrbState.writing);
  });

  test('an unknown stage falls back to idle rather than guessing', () {
    // A backend that adds a stage this build has never heard of should leave
    // the orb calm, not pick an animation at random.
    expect(orbStateForStage('something_new'), OrbState.idle);
    expect(orbStateForStage(null), OrbState.idle);
  });
}
