// A turn that ends in an error ends: the message is shown, Stop turns back
// into Send, and the next message goes out.
//
// The client half of D-16 (docs/FREEZE_LIST.md §7.23). The defect was on the
// server - a turn with no provider allowed to answer sent no done, error or
// stopped at all - and this screen was already right about the error it never
// received. Pinned here because the fix rests on it: the server now sends that
// error, and it is only worth sending if receiving it unlocks the composer.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
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
  final sent = <String>[];

  @override
  Stream<ChatEvent> get events => _events.stream;

  @override
  void connect() {}

  @override
  void sendMessage(String text, {String? projectId}) => sent.add(text);

  void push(String type, dynamic data) => _events.add(ChatEvent(type, data));

  @override
  void dispose() {
    _events.close();
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
  testWidgets('an error ends the turn and the next message can be sent', (tester) async {
    final chat = await _pumpChat(tester);

    await _send(tester, 'explain how a hash map works');
    expect(chat.sent, ['explain how a hash map works']);
    expect(find.byTooltip('Stop'), findsOneWidget);

    chat.push('stage', {
      'stage': 'documents',
      'label': 'Searching your documents',
      'detail': 'nothing close enough',
      'status': 'empty',
    });
    chat.push('error', 'No consented provider available');
    await tester.pump();

    expect(find.textContaining('No consented provider available'), findsOneWidget);
    expect(find.byTooltip('Stop'), findsNothing);
    expect(find.byTooltip('Send'), findsOneWidget);

    await _send(tester, 'explain how a linked list works');
    expect(chat.sent, ['explain how a hash map works', 'explain how a linked list works']);
  });

  testWidgets('control: without an ending event the composer stays locked', (tester) async {
    // What the server's old behaviour looked like from here: stage lines, then
    // nothing. The second message is refused because the first never ended.
    final chat = await _pumpChat(tester);

    await _send(tester, 'explain how a hash map works');
    chat.push('stage', {
      'stage': 'documents',
      'label': 'Searching your documents',
      'detail': 'nothing close enough',
      'status': 'empty',
    });
    await tester.pump();

    expect(find.byTooltip('Stop'), findsOneWidget);
    await tester.enterText(find.byType(TextField), 'explain how a linked list works');
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pump();
    expect(chat.sent, ['explain how a hash map works']);
  });
}
