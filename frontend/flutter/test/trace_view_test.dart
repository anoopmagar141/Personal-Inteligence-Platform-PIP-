// Behaviour tests for the Trace screen.
//
// A fake ApiClient, for the same reason review_view_test.dart uses one: the
// endpoints are covered by the Python suite, and what needs pinning here is
// what the screen does with what the server said. Two things in particular,
// because both are ways a diagnostic screen can quietly lie:
//
//   * an unfamiliar stage key must survive being displayed. "pipeline" and
//     "response_cache" are logged as stages alongside stage_NN_name, and a
//     formatter that assumed the numbered shape would mangle exactly the rows
//     present when something unusual happened.
//   * error_detail must be shown. It is the only field that says what actually
//     went wrong, and it is the reason this screen exists.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/trace_view.dart';

class FakeApi extends ApiClient {
  FakeApi() : super('http://127.0.0.1:8765/api/v1');

  List<dynamic> runs = [];
  Map<String, List<dynamic>> entries = {};
  final List<String> calls = [];
  Object? traceError;

  @override
  Future<List<dynamic>> listTraces({int limit = 20}) async {
    calls.add('list');
    return runs;
  }

  @override
  Future<List<dynamic>> getTrace(String traceId) async {
    calls.add('get:$traceId');
    if (traceError != null) throw traceError!;
    return entries[traceId] ?? [];
  }
}

Map<String, dynamic> run(String id, {int entries = 2, int errors = 0}) => {
      'trace_id': id,
      'started_at': '2026-08-31T10:00:00Z',
      'entries': entries,
      'errors': errors,
    };

Map<String, dynamic> entry(
  String stage, {
  String status = 'ok',
  String message = '',
  String errorDetail = '',
}) =>
    {
      'id': 1,
      'trace_id': 'trace-a',
      'timestamp': '2026-08-31T10:00:00Z',
      'stage': stage,
      'status': status,
      'message': message,
      'error_detail': errorDetail,
    };

Future<FakeApi> pumpTrace(
  WidgetTester tester, {
  List<dynamic>? runs,
  Map<String, List<dynamic>>? entries,
  Object? traceError,
}) async {
  final api = FakeApi()
    ..runs = runs ?? []
    ..entries = entries ?? {}
    ..traceError = traceError;
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(body: TraceView(api: api, refreshToken: 0)),
    ),
  );
  await tester.pumpAndSettle();
  return api;
}

void main() {
  group('splitStageKey', () {
    test('splits a numbered stage into its step and its words', () {
      final parts = splitStageKey('stage_09_llm_streaming');
      expect(parts.step, '09');
      expect(parts.label, 'Llm streaming');
    });

    test('keeps a stage key that carries no name', () {
      // stage_01 and stage_09 are both logged bare in places.
      final parts = splitStageKey('stage_01');
      expect(parts.step, '01');
      expect(parts.label, 'Stage 01');
    });

    test('passes through a key that is not a numbered stage at all', () {
      // "pipeline" and "response_cache" are real stage values. Losing them
      // would blank rows on precisely the paths worth reading.
      expect(splitStageKey('pipeline').step, isNull);
      expect(splitStageKey('pipeline').label, 'Pipeline');
      expect(splitStageKey('response_cache').label, 'Response cache');
    });
  });

  testWidgets('says so when nothing has been traced yet', (tester) async {
    await pumpTrace(tester);

    expect(find.text('No runs traced yet'), findsOneWidget);
  });

  testWidgets('opens the newest run without being asked', (tester) async {
    // The person who just got a puzzling answer wants the run that produced
    // it, and the backend already returns newest first.
    final api = await pumpTrace(
      tester,
      runs: [run('trace-a'), run('trace-b')],
      entries: {
        'trace-a': [entry('stage_01_intent_classifier', message: 'classified as general_knowledge')],
        'trace-b': [entry('stage_01_intent_classifier', message: 'older run')],
      },
    );

    expect(api.calls, contains('get:trace-a'));
    expect(find.textContaining('classified as general_knowledge'), findsOneWidget);
    expect(find.textContaining('older run'), findsNothing);
  });

  testWidgets('shows what went wrong, not just that something did', (tester) async {
    await pumpTrace(
      tester,
      runs: [run('trace-a', errors: 1)],
      entries: {
        'trace-a': [
          entry(
            'stage_09_llm_streaming',
            status: 'error',
            message: 'generation failed',
            errorDetail: 'ollama connection refused',
          ),
        ],
      },
    );

    expect(find.text('1 error'), findsOneWidget);
    expect(find.textContaining('ollama connection refused'), findsOneWidget);
  });

  testWidgets('renders an unfamiliar stage key rather than dropping the row', (tester) async {
    await pumpTrace(
      tester,
      runs: [run('trace-a')],
      entries: {
        'trace-a': [entry('response_cache', message: 'hit, 24h ttl')],
      },
    );

    expect(find.text('Response cache'), findsOneWidget);
    expect(find.textContaining('hit, 24h ttl'), findsOneWidget);
  });

  testWidgets('keeps the run list usable when one run cannot be read', (tester) async {
    // Retention is real (trace.hard_delete_after_days), so a run can be purged
    // between the listing and the click. That is a normal outcome and must not
    // blank the screen.
    await pumpTrace(
      tester,
      runs: [run('trace-a')],
      traceError: ApiException(404, '{"detail": "no trace with id trace-a"}'),
    );

    expect(find.textContaining('no trace with id'), findsOneWidget);
    expect(find.textContaining('2 stages'), findsOneWidget);
  });
}
