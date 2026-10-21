// No click, no search (BLUEPRINT card D-45, the owner's choice of 2026-10-21).
//
// With web search consented, PIP used to search on its own whenever a message had a word like "today", so "I feel
// tired today" went to the search provider. The backend now answers without the web and sends an offer of the exact
// words it would search for; this screen shows them under that answer, and only a tap sends the search.

import 'dart:async';

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

class FakeChatClient extends WsChatClient {
  FakeChatClient() : super('ws://127.0.0.1:1/ws/chat');

  final _events = StreamController<ChatEvent>.broadcast();
  final sent = <String>[];
  final approved = <String>[];

  @override
  Stream<ChatEvent> get events => _events.stream;

  @override
  void connect() {}

  @override
  void sendMessage(String text, {String? projectId}) => sent.add(text);

  @override
  void approveWebSearch(String offerId) => approved.add(offerId);

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
    home: Scaffold(body: ChatView(api: FakeApi(), chatClient: chatClient, activeProjectId: null)),
  ));
  await tester.pump();
  return chatClient;
}

Future<void> _turn(WidgetTester tester, FakeChatClient chat, String message, String answer) async {
  await tester.enterText(find.byType(TextField), message);
  await tester.tap(find.byTooltip('Send'));
  await tester.pump();
  chat.push('token', answer);
  chat.push('done', null);
  await tester.pump();
}

void main() {
  testWidgets('an offer shows the exact words under the answer, and nothing is sent', (tester) async {
    final chat = await _pumpChat(tester);
    await _turn(tester, chat, 'I feel tired today', 'Rest helps.');

    chat.push('web_search_offer', {'offer_id': 'o1', 'query': 'I feel tired today'});
    await tester.pump();

    expect(find.text('Search the web for: "I feel tired today"'), findsOneWidget);
    expect(find.text('Only these words are sent to the search provider.'), findsOneWidget);
    expect(chat.approved, isEmpty);
  });

  testWidgets('a tap sends that search, removes the button and adds the answer with no new user bubble',
      (tester) async {
    final chat = await _pumpChat(tester);
    await _turn(tester, chat, 'what is the weather in Kathmandu today?', 'I cannot see the weather.');
    chat.push('web_search_offer', {'offer_id': 'o1', 'query': 'what is the weather in Kathmandu today?'});
    await tester.pump();

    await tester.tap(find.text('Search the web for: "what is the weather in Kathmandu today?"'));
    await tester.pump();

    expect(chat.approved, ['o1']);
    expect(chat.sent, ['what is the weather in Kathmandu today?'], reason: 'the question is not sent again');
    expect(find.textContaining('Search the web for'), findsNothing);
    expect(find.byTooltip('Stop'), findsOneWidget, reason: 'the searched answer is on its way');

    chat.push('token', 'Light rain in Kathmandu.');
    chat.push('done', null);
    await tester.pump();

    expect(find.text('Light rain in Kathmandu.'), findsOneWidget);
    expect(find.text('I cannot see the weather.'), findsOneWidget, reason: 'the first answer stays');
    expect(find.text('what is the weather in Kathmandu today?'), findsOneWidget, reason: 'one user bubble');
    expect(find.byTooltip('Send'), findsOneWidget);
  });

  testWidgets('control: a turn with no offer shows no button', (tester) async {
    final chat = await _pumpChat(tester);
    await _turn(tester, chat, 'explain how a hash map works', 'It hashes keys.');

    expect(find.textContaining('Search the web for'), findsNothing);
  });

  test('the consent text says PIP asks before each search', () {
    final text = ApiClient.consentScopes['web_search_only']!;
    expect(text, contains('asks you before each search'));
    expect(text, contains('first 12 words'));
  });
}
