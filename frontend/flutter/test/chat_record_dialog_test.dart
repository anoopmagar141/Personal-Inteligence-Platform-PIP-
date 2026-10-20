// A chat's "where we left off" record, seen and put right in the app (BLUEPRINT #13 part 4).
//
// The record is written by PIP's Observer, a model, when a chat ends, and every later chat in the project is shown
// it - so it can be wrong in a way that keeps coming back. Before this there was no screen for it at all: the user
// could neither see what PIP would carry forward nor correct it. The dialog shows the record, says who wrote it and
// when, shows what the chat produced (its decisions, and how its candidates came out), and lets the user edit or
// clear it. The backend is the authority: a correction it refuses shows its own sentence and the form stays open.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/chat_view.dart';
import 'package:pip_flutter_client/theme.dart';
import 'package:pip_flutter_client/widgets/chat_record_dialog.dart';
import 'package:pip_flutter_client/ws_chat_client.dart';

Map<String, dynamic> _record({String source = 'observer'}) => {
      'record': {
        'topic': 'Zephyr warehouse migration',
        'open_problems': ['the cutover window'],
        'last_decisions': ['move inventory first'],
        'suggested_next_step': 'draft the cutover plan',
        'record_date': '2026-10-18T09:30:00Z',
        'source': source,
      },
      'links': {
        'decisions': [
          {'id': 1, 'decision_text': 'Move the database to Postgres before the next release.', 'state': 'active'},
        ],
        'outcomes': {'accepted': 2, 'deferred': 1, 'rejected': 3},
      },
    };

class _Calls {
  int loads = 0;
  final saved = <Map<String, dynamic>>[];
  int clears = 0;
}

Future<_Calls> _pumpDialog(
  WidgetTester tester, {
  Map<String, dynamic>? loaded,
  Future<Map<String, dynamic>> Function(Map<String, dynamic>)? onSave,
}) async {
  final calls = _Calls();
  tester.view.physicalSize = const Size(1200, 1000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light,
    home: Scaffold(
      body: ChatRecordDialog(
        load: () async {
          calls.loads++;
          return loaded ?? _record();
        },
        save: (fields) async {
          calls.saved.add(fields);
          if (onSave != null) return onSave(fields);
          return {
            'record': {...fields, 'record_date': '2026-10-18T10:00:00Z', 'source': 'user'},
          };
        },
        clear: () async => calls.clears++,
      ),
    ),
  ));
  await tester.pumpAndSettle();
  return calls;
}

class _FakeApi extends ApiClient {
  _FakeApi() : super('http://127.0.0.1:8765/api/v1');

  final recordsAskedFor = <String>[];

  @override
  Future<List<dynamic>> getConversations({String? projectId}) async => [];

  @override
  Future<Map<String, dynamic>> getChatRecord(String conversationId) async {
    recordsAskedFor.add(conversationId);
    return _record();
  }
}

class _FakeChatClient extends WsChatClient {
  _FakeChatClient() : super('ws://127.0.0.1:1/ws/chat');

  final _events = StreamController<ChatEvent>.broadcast();

  @override
  Stream<ChatEvent> get events => _events.stream;

  @override
  void connect() {}

  void push(String type, dynamic data) => _events.add(ChatEvent(type, data));

  @override
  void dispose() {
    _events.close();
    super.dispose();
  }
}

void main() {
  testWidgets('shows the record, who wrote it and when, and what the chat produced', (tester) async {
    await _pumpDialog(tester);

    expect(find.text('Zephyr warehouse migration'), findsOneWidget);
    expect(find.textContaining('the cutover window'), findsOneWidget);
    expect(find.textContaining('move inventory first'), findsOneWidget);
    expect(find.textContaining('draft the cutover plan'), findsOneWidget);
    expect(find.textContaining('Written by PIP when this chat ended, 2026-10-18'), findsOneWidget);
    expect(find.textContaining('it may be wrong'), findsOneWidget);
    expect(find.textContaining('Move the database to Postgres'), findsOneWidget);
    expect(find.textContaining('2 kept, 1 asked about, 3 not kept'), findsOneWidget);
  });

  testWidgets('a record the user corrected says so', (tester) async {
    await _pumpDialog(tester, loaded: _record(source: 'user'));

    expect(find.textContaining('Corrected by you'), findsOneWidget);
    expect(find.textContaining('it may be wrong'), findsNothing);
  });

  testWidgets('a chat with no record yet says so and offers to write one', (tester) async {
    await _pumpDialog(tester, loaded: {'record': null, 'links': {'decisions': [], 'outcomes': {}}});

    expect(find.textContaining('No record of this chat yet'), findsOneWidget);
    expect(find.widgetWithText(TextButton, 'Write it'), findsOneWidget);
    expect(find.widgetWithText(TextButton, 'Clear'), findsNothing);
  });

  testWidgets("editing saves the user's version and shows it as theirs", (tester) async {
    final calls = await _pumpDialog(tester);

    await tester.tap(find.widgetWithText(TextButton, 'Edit'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Topic'), 'Zephyr cutover rehearsal');
    await tester.enterText(find.widgetWithText(TextField, 'Open problems (one per line)'), 'who signs off\n\nthe rollback');
    await tester.tap(find.widgetWithText(FilledButton, 'Save'));
    await tester.pumpAndSettle();

    expect(calls.saved, [
      {
        'topic': 'Zephyr cutover rehearsal',
        'open_problems': ['who signs off', 'the rollback'],
        'last_decisions': ['move inventory first'],
        'suggested_next_step': 'draft the cutover plan',
      }
    ]);
    expect(find.text('Zephyr cutover rehearsal'), findsOneWidget);
    expect(find.textContaining('Corrected by you'), findsOneWidget);
  });

  testWidgets("a refused correction shows the server's sentence and keeps the form", (tester) async {
    await _pumpDialog(tester, onSave: (_) async => throw ApiException(422, '{"detail": "A chat record needs a topic."}'));

    await tester.tap(find.widgetWithText(TextButton, 'Edit'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Topic'), '');
    await tester.tap(find.widgetWithText(FilledButton, 'Save'));
    await tester.pumpAndSettle();

    expect(find.text('A chat record needs a topic.'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Save'), findsOneWidget);
  });

  testWidgets('clearing asks first, then clears', (tester) async {
    final calls = await _pumpDialog(tester);

    await tester.tap(find.widgetWithText(TextButton, 'Clear'));
    await tester.pumpAndSettle();
    expect(calls.clears, 0, reason: 'nothing is cleared before the user confirms');
    await tester.tap(find.widgetWithText(FilledButton, 'Clear record'));
    await tester.pumpAndSettle();

    expect(calls.clears, 1);
    expect(find.textContaining('No record of this chat yet'), findsOneWidget);
  });

  testWidgets('cancelling the question keeps the record', (tester) async {
    final calls = await _pumpDialog(tester);

    await tester.tap(find.widgetWithText(TextButton, 'Clear'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, 'Cancel'));
    await tester.pumpAndSettle();

    expect(calls.clears, 0);
    expect(find.text('Zephyr warehouse migration'), findsOneWidget);
  });

  testWidgets("the chat's footer opens the open chat's record, and only when a chat is open", (tester) async {
    final api = _FakeApi();
    final chat = _FakeChatClient();
    addTearDown(chat.dispose);
    tester.view.physicalSize = const Size(1400, 1000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light,
      home: Scaffold(body: ChatView(api: api, chatClient: chat, activeProjectId: null)),
    ));
    await tester.pump();
    expect(find.byTooltip('Where we left off'), findsNothing, reason: 'a new chat has no record to show');

    chat.push('session_info', {'conversation_id': 'c1', 'title': 'Zephyr', 'messages': []});
    await tester.pump();
    await tester.tap(find.byTooltip('Where we left off'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(api.recordsAskedFor, ['c1']);
    expect(find.text('Zephyr warehouse migration'), findsOneWidget);
  });
}
