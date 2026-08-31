// Behaviour tests for the Decision Log's state transitions.
//
// Two things here are correctness rather than polish, and both are invisible
// if they break:
//
//   * the state filter has to reach the backend. list/search take exactly one
//     state and default to 'active', so a screen that forgets to pass it shows
//     only live decisions - and retracting one through this screen would be
//     indistinguishable from deleting it.
//   * a retraction has to carry a reason. The row outlives the retraction, and
//     the reason is the only thing that later separates "this was a
//     fabrication we cleaned up" from "this was real and we changed our mind".

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/decisions_view.dart';

class FakeApi extends ApiClient {
  FakeApi() : super('http://127.0.0.1:8765/api/v1');

  Map<String, List<dynamic>> byState = {};
  final List<String> calls = [];
  Object? stateError;

  @override
  Future<List<dynamic>> searchDecisions([String query = '', String state = 'active']) async {
    calls.add('search:$state:$query');
    return byState[state] ?? [];
  }

  @override
  Future<void> updateDecisionState(
    int decisionId, {
    required String state,
    required String reason,
    int? supersededBy,
  }) async {
    calls.add('state:$decisionId=$state reason="$reason" by=$supersededBy');
    if (stateError != null) throw stateError!;
  }
}

Map<String, dynamic> decision(
  int id,
  String text, {
  String state = 'active',
  String? stateReason,
  int? supersededBy,
}) =>
    {
      'id': id,
      'decision_text': text,
      'confidence': 0.75,
      'state': state,
      'state_reason': stateReason,
      'superseded_by': supersededBy,
      'created_at': '2026-08-31T10:00:00Z',
    };

Future<FakeApi> pumpDecisions(WidgetTester tester, Map<String, List<dynamic>> byState) async {
  final api = FakeApi()..byState = byState;
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(body: DecisionsView(api: api, activeProjectId: null)),
    ),
  );
  await tester.pumpAndSettle();
  return api;
}

void main() {
  testWidgets('asks the backend for active decisions on open', (tester) async {
    final api = await pumpDecisions(tester, {
      'active': [decision(1, 'Use FastAPI')],
    });

    expect(api.calls, contains('search:active:'));
    expect(find.text('Use FastAPI'), findsOneWidget);
  });

  testWidgets('switching the filter re-queries for that state', (tester) async {
    final api = await pumpDecisions(tester, {
      'active': [decision(1, 'Use FastAPI')],
      'abandoned': [decision(2, 'Use Flask', state: 'abandoned', stateReason: 'PIP invented this')],
    });

    await tester.tap(find.text('Retracted'));
    await tester.pumpAndSettle();

    expect(api.calls, contains('search:abandoned:'));
    expect(find.text('Use Flask'), findsOneWidget);
    expect(find.text('Use FastAPI'), findsNothing);
  });

  testWidgets('a retracted decision shows the reason it was retracted', (tester) async {
    await pumpDecisions(tester, {
      'active': [],
      'abandoned': [decision(2, 'Use Flask', state: 'abandoned', stateReason: 'PIP invented this')],
    });

    await tester.tap(find.text('Retracted'));
    await tester.pumpAndSettle();

    expect(find.text('PIP invented this'), findsOneWidget);
  });

  testWidgets('an active decision with no reason recorded shows no empty reason', (tester) async {
    // state_reason is NULL for anything still active and for anything
    // retracted before the column existed. A blank quote block would suggest
    // the record is poorer than it is.
    await pumpDecisions(tester, {
      'active': [decision(1, 'Use FastAPI')],
    });

    expect(find.text('Use FastAPI'), findsOneWidget);
    expect(find.byKey(const Key('decision-state-reason')), findsNothing);
  });

  testWidgets('will not retract until a reason is given', (tester) async {
    final api = await pumpDecisions(tester, {
      'active': [decision(1, 'Use FastAPI')],
    });

    await tester.tap(find.text('Retract'));
    await tester.pumpAndSettle();

    final confirm = find.widgetWithText(FilledButton, 'Confirm');
    expect(tester.widget<FilledButton>(confirm).onPressed, isNull);

    await tester.enterText(find.byKey(const Key('state-reason-field')), 'PIP invented this');
    await tester.pumpAndSettle();
    expect(tester.widget<FilledButton>(confirm).onPressed, isNotNull);

    await tester.tap(confirm);
    await tester.pumpAndSettle();

    expect(
      api.calls,
      contains('state:1=abandoned reason="PIP invented this" by=null'),
    );
  });

  testWidgets('supersede can name the decision that replaced it', (tester) async {
    final api = await pumpDecisions(tester, {
      'active': [decision(1, 'Use Flask')],
    });

    await tester.tap(find.text('Supersede'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('state-reason-field')), 'moved to FastAPI');
    await tester.enterText(find.byKey(const Key('superseded-by-field')), '7');
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
    await tester.pumpAndSettle();

    expect(api.calls, contains('state:1=superseded reason="moved to FastAPI" by=7'));
  });

  testWidgets('a non-active decision offers reactivation instead of retraction', (tester) async {
    await pumpDecisions(tester, {
      'active': [],
      'abandoned': [decision(2, 'Use Flask', state: 'abandoned', stateReason: 'wrong')],
    });

    await tester.tap(find.text('Retracted'));
    await tester.pumpAndSettle();

    expect(find.text('Reactivate'), findsOneWidget);
    expect(find.text('Retract'), findsNothing);
  });

  testWidgets('reactivating does not demand a reason, matching the backend', (tester) async {
    await pumpDecisions(tester, {
      'active': [],
      'abandoned': [decision(2, 'Use Flask', state: 'abandoned', stateReason: 'wrong')],
    });

    await tester.tap(find.text('Retracted'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Reactivate'));
    await tester.pumpAndSettle();

    final confirm = find.widgetWithText(FilledButton, 'Reactivate');
    expect(tester.widget<FilledButton>(confirm).onPressed, isNotNull);
  });

  testWidgets("a refused transition shows the server's sentence on that row", (tester) async {
    final api = await pumpDecisions(tester, {
      'active': [decision(1, 'Use FastAPI')],
    });
    api.stateError = ApiException(422, '{"detail": "invalid decision state"}');

    await tester.tap(find.text('Retract'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('state-reason-field')), 'no longer true');
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
    await tester.pumpAndSettle();

    expect(find.text('invalid decision state'), findsOneWidget);
  });
}
