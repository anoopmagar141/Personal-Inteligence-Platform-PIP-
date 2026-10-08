// A connection that drops mid-reply ends the turn (docs/FREEZE_LIST.md D-23).
//
// Found by reading the code while fixing D-22, which made the SERVER end a turn whose
// pipeline raised. This is the half no server change can reach: when the backend
// process dies or restarts in the middle of a reply, the socket just closes. Only the
// sidebar's connection pill listened to WsChatClient.status; the chat screen did not,
// so the reply stayed "writing", the composer stayed locked on Stop, and the
// reconnect that followed did not end the turn either. Nothing the person could do
// short of leaving the screen.
//
// Two halves, both held here:
//   - the screen ends the turn on a drop, says so, and lets the next message go out;
//   - the client remembers which conversation it was in, so the reconnect resumes it
//     instead of starting a second one while the screen still shows one transcript.

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/chat_view.dart';
import 'package:pip_flutter_client/theme.dart';
import 'package:pip_flutter_client/ws_chat_client.dart';

class FakeApi extends ApiClient {
  FakeApi() : super('http://127.0.0.1:8765/api/v1');

  @override
  Future<List<dynamic>> getConversations({String? projectId}) async => [];
}

/// Delivers whatever the test pushes, and records what the screen sends.
class FakeChatClient extends WsChatClient {
  FakeChatClient() : super('ws://127.0.0.1:1/ws/chat');

  final _events = StreamController<ChatEvent>.broadcast();
  final _status = StreamController<String>.broadcast();
  final sent = <String>[];

  @override
  Stream<ChatEvent> get events => _events.stream;

  @override
  Stream<String> get status => _status.stream;

  @override
  void connect() {}

  @override
  void sendMessage(String text, {String? projectId}) => sent.add(text);

  void push(String type, dynamic data) => _events.add(ChatEvent(type, data));
  void pushStatus(String value) => _status.add(value);

  @override
  void dispose() {
    _events.close();
    _status.close();
    super.dispose();
  }
}

Future<FakeChatClient> _pumpChat(WidgetTester tester) async {
  final chatClient = FakeChatClient();
  addTearDown(chatClient.dispose);

  tester.view.physicalSize = const Size(1400, 1000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light,
    home: Scaffold(
      body: ChatView(api: FakeApi(), chatClient: chatClient, activeProjectId: null),
    ),
  ));
  await tester.pump();
  return chatClient;
}

Future<void> _send(WidgetTester tester, String text) async {
  await tester.enterText(find.byType(TextField), text);
  await tester.tap(find.byTooltip('Send'));
  await tester.pump();
}

void main() {
  group('the screen', () {
    testWidgets('a drop mid-reply ends the turn, says so, and unlocks the composer', (tester) async {
      final chat = await _pumpChat(tester);
      await _send(tester, 'first question');
      chat.push('token', 'Half an ans');
      await tester.pump();
      expect(find.byTooltip('Stop'), findsOneWidget, reason: 'the turn should be in flight');

      chat.pushStatus('disconnected');
      await tester.pump();

      expect(find.byTooltip('Stop'), findsNothing, reason: 'the composer stayed locked on Stop');
      expect(find.byTooltip('Send'), findsOneWidget);
      expect(find.textContaining('connection to PIP was lost'), findsOneWidget);
    });

    testWidgets('the next message goes out after a drop', (tester) async {
      final chat = await _pumpChat(tester);
      await _send(tester, 'first question');
      chat.pushStatus('disconnected');
      await tester.pump();
      chat.pushStatus('connected');
      await tester.pump();

      await _send(tester, 'second question');

      expect(chat.sent, ['first question', 'second question']);
    });

    testWidgets('a drop while nothing is being answered says nothing', (tester) async {
      final chat = await _pumpChat(tester);

      chat.pushStatus('disconnected');
      chat.pushStatus('connected');
      await tester.pump();

      expect(find.textContaining('connection to PIP was lost'), findsNothing);
      expect(find.byTooltip('Send'), findsOneWidget);
    });

    testWidgets('a reply that finished before the drop is not turned into an error', (tester) async {
      final chat = await _pumpChat(tester);
      await _send(tester, 'first question');
      chat.push('token', 'A whole answer.');
      chat.push('done', null);
      await tester.pump();

      chat.pushStatus('disconnected');
      await tester.pump();

      expect(find.textContaining('connection to PIP was lost'), findsNothing);
      expect(find.textContaining('A whole answer.'), findsOneWidget);
    });
  });

  group('the client', () {
    String sessionInfo(String? id) => jsonEncode({
          'type': 'session_info',
          'data': {'conversation_id': id, 'messages': []},
        });

    test('a reconnect resumes the conversation the server last named', () {
      final client = WsChatClient('ws://127.0.0.1:1/ws/chat', apiToken: 't');
      addTearDown(client.dispose);
      expect(client.connectUri.queryParameters.containsKey('conversation_id'), isFalse);

      client.handleRaw(sessionInfo('abc-123'));

      expect(client.connectUri.queryParameters['conversation_id'], 'abc-123');
    });

    test('a session_info with no id does not forget the one it has', () {
      final client = WsChatClient('ws://127.0.0.1:1/ws/chat', apiToken: 't', conversationId: 'abc-123');
      addTearDown(client.dispose);

      client.handleRaw(sessionInfo(null));

      expect(client.connectUri.queryParameters['conversation_id'], 'abc-123');
    });

    test('events other than session_info leave the conversation alone', () {
      final client = WsChatClient('ws://127.0.0.1:1/ws/chat', apiToken: 't', conversationId: 'abc-123');
      addTearDown(client.dispose);

      client.handleRaw(jsonEncode({'type': 'token', 'data': 'hello'}));

      expect(client.connectUri.queryParameters['conversation_id'], 'abc-123');
    });

    test('the token still travels with it', () {
      final client = WsChatClient('ws://127.0.0.1:1/ws/chat', apiToken: 'secret-token');
      addTearDown(client.dispose);

      client.handleRaw(sessionInfo('abc-123'));

      expect(client.connectUri.queryParameters['token'], 'secret-token');
    });
  });
}
