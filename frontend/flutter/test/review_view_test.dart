// Behaviour tests for the Review queue - the screen the whole governance half
// of PIP reaches the user through.
//
// A fake ApiClient rather than a live backend: what needs pinning here is how
// the view treats what the server said, and the two places it can silently say
// something untrue (attributing PIP's own note to the user, and explaining a
// periodic check with a sentence written for a gated field) are pure rendering
// decisions. The endpoints themselves are covered by the Python suite.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/review_view.dart';

class FakeApi extends ApiClient {
  FakeApi() : super('http://127.0.0.1:8765/api/v1');

  List<dynamic> memory = [];
  List<dynamic> decisions = [];
  List<dynamic> proactive = [];

  final List<String> calls = [];
  Object? confirmError;

  @override
  Future<List<dynamic>> getPendingMemory() async => memory;

  @override
  Future<List<dynamic>> getPendingDecisions() async => decisions;

  @override
  Future<List<dynamic>> getProactive() async => proactive;

  @override
  Future<void> confirmPendingMemory(int candidateId) async {
    calls.add('confirm:$candidateId');
    if (confirmError != null) throw confirmError!;
    memory = memory.where((c) => c['id'] != candidateId).toList();
  }

  @override
  Future<void> dismissPendingMemory(int candidateId) async {
    calls.add('dismiss:$candidateId');
    memory = memory.where((c) => c['id'] != candidateId).toList();
  }

  @override
  Future<void> promotePendingDecision(int candidateId) async {
    calls.add('promote:$candidateId');
    decisions = decisions.where((c) => c['id'] != candidateId).toList();
  }

  @override
  Future<void> dismissPendingDecision(int candidateId) async {
    calls.add('decline:$candidateId');
    decisions = decisions.where((c) => c['id'] != candidateId).toList();
  }
}

Map<String, dynamic> observerCandidate() => {
      'id': 1,
      'target_table': 'active_projects',
      'field_name': 'Thesis writeup',
      'proposed_value': 'Dissertation chapters 4 and 5',
      'label': 'explicit',
      'evidence_count': 3,
      'evidence_text': 'I need to get chapters 4 and 5 done this month',
      'validation_status': 'REQUIRES_CONFIRMATION',
      'origin': 'observer',
    };

Map<String, dynamic> verificationCandidate() => {
      'id': 2,
      'target_table': 'preference_memory',
      'field_name': 'answer_style',
      'proposed_value': 'terse',
      'label': 'inferred',
      'evidence_count': 1,
      'evidence_text': 'Periodic memory check (session 30). PIP recorded this as inferred.',
      'validation_status': 'REQUIRES_CONFIRMATION',
      'origin': 'verification',
    };

Future<FakeApi> pumpReview(
  WidgetTester tester, {
  List<dynamic>? memory,
  List<dynamic>? decisions,
  List<dynamic>? proactive,
}) async {
  final api = FakeApi()
    ..memory = memory ?? []
    ..decisions = decisions ?? []
    ..proactive = proactive ?? [];
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: ReviewView(api: api, refreshToken: 0, onQueueChanged: () {}),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return api;
}

void main() {
  testWidgets('asks a different question depending on where a candidate came from',
      (tester) async {
    await pumpReview(tester, memory: [observerCandidate(), verificationCandidate()]);

    expect(find.text('Should I remember this?'), findsOneWidget);
    expect(find.text('Do I still have this right?'), findsOneWidget);
  });

  testWidgets('does not explain a periodic check with the sentence written for a gated field',
      (tester) async {
    // The two are both REQUIRES_CONFIRMATION for different reasons, so keying
    // the explanation on status alone produced a flat contradiction: "Do I
    // still have this right?" answered by "PIP is not allowed to record this
    // without asking", about something already recorded.
    await pumpReview(tester, memory: [verificationCandidate()]);

    expect(find.textContaining('not allowed to record'), findsNothing);
    expect(find.textContaining('Periodic memory check'), findsOneWidget);
  });

  // evidence_text is the user's own words for an Observer candidate and a
  // backend-written note for a periodic check. These are two tests rather than
  // one because a second pumpWidget of the same widget type reuses the existing
  // State - initState does not run again - which is the very reason ReviewView
  // takes a refreshToken.
  testWidgets('an observer candidate is quoted back and given a reason', (tester) async {
    await pumpReview(tester, memory: [observerCandidate()]);

    expect(find.text('I need to get chapters 4 and 5 done this month'), findsOneWidget);
    expect(find.textContaining('not allowed to record'), findsOneWidget);
  });

  testWidgets('a periodic check shows its own note once, and is not quoted', (tester) async {
    // Rendering the backend's note as a quote as well would duplicate it and
    // put PIP's own words in the user's mouth.
    await pumpReview(tester, memory: [verificationCandidate()]);

    expect(find.textContaining('Periodic memory check'), findsOneWidget);
  });

  testWidgets('confirming a candidate calls the backend and drops it from the queue',
      (tester) async {
    final api = await pumpReview(tester, memory: [observerCandidate()]);

    await tester.tap(find.text('Yes, keep it'));
    await tester.pumpAndSettle();

    expect(api.calls, ['confirm:1']);
    expect(find.text('Nothing waiting'), findsOneWidget);
  });

  testWidgets('dismissing a candidate calls the backend and writes nothing', (tester) async {
    final api = await pumpReview(tester, memory: [observerCandidate()]);

    await tester.tap(find.text('No'));
    await tester.pumpAndSettle();

    expect(api.calls, ['dismiss:1']);
  });

  testWidgets('a refused confirmation shows the reason and leaves the candidate in place',
      (tester) async {
    // A confirmation can legitimately fail: the candidate exists but cannot be
    // applied (422). Leaving the row looking unchanged would tell the user
    // nothing about why their click did nothing.
    final api = await pumpReview(tester, memory: [observerCandidate()]);
    api.confirmError = ApiException(422, '{"detail":"immutable identity fields cannot be edited"}');

    await tester.tap(find.text('Yes, keep it'));
    await tester.pumpAndSettle();

    expect(find.text('immutable identity fields cannot be edited'), findsOneWidget);
    expect(find.text('Should I remember this?'), findsOneWidget, reason: 'candidate must stay in the queue');
    expect(find.text('Yes, keep it'), findsOneWidget, reason: 'buttons must come back');
  });

  testWidgets('promotes a decision candidate', (tester) async {
    final api = await pumpReview(tester, decisions: [
      {
        'id': 7,
        'decision_text': 'Use SQLCipher rather than encrypting fields individually',
        'raw_quote': 'we just encrypt the whole database instead',
        'confidence': 0.4,
        'signals_found': ['commitment_language'],
      }
    ]);

    expect(find.text('Was this a decision you made?'), findsOneWidget);
    // The decisions section sits below Memory, past the bottom of the default
    // 800x600 test surface - without this the tap silently hits nothing.
    await tester.ensureVisible(find.text('Log it'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Log it'));
    await tester.pumpAndSettle();

    expect(api.calls, ['promote:7']);
  });

  testWidgets('renders proactive triggers as plain sentences', (tester) async {
    await pumpReview(tester, proactive: [
      {'trigger': 'session_gap_exceeds_48h', 'hours_elapsed': 72, 'threshold_hours': 48},
      {'trigger': 'goal_inactive_14_days', 'threshold_days': 14, 'goal_text': 'Learn Rust properly'},
    ]);

    expect(find.textContaining('3 day(s) since your last session'), findsOneWidget);
    expect(find.textContaining('Learn Rust properly'), findsOneWidget);
  });

  testWidgets('says so when there is nothing waiting', (tester) async {
    await pumpReview(tester);

    expect(find.text('Nothing waiting'), findsOneWidget);
    expect(find.text('No decision candidates waiting'), findsOneWidget);
    expect(find.text('Nothing to raise'), findsOneWidget);
  });

  testWidgets('ApiException surfaces the server sentence, not the JSON envelope', (tester) async {
    final wrapped = ApiException(422, '{"detail":"no such candidate"}');
    expect(wrapped.detail, 'no such candidate');
    expect(wrapped.toString(), 'no such candidate');

    final plain = ApiException(500, 'Internal Server Error');
    expect(plain.detail, 'Internal Server Error');
  });
}
