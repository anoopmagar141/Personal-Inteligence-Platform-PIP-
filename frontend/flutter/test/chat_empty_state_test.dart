// The empty chat screen and its starters.
//
// A blank column is the one screen every new installation opens on, and it
// used to say nothing at all. The starters are not decoration: each one points
// at a part of PIP a newcomer has no way to discover - the decision log, the
// document index, the warm-start gap - and tapping one fills the composer
// rather than sending, because the useful version of "what did I decide
// about" always has something after it.

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

Future<void> _pumpChat(WidgetTester tester) async {
  final chatClient = WsChatClient('ws://127.0.0.1:1/ws/chat');
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
  // pump rather than pumpAndSettle - the client retries its connection against
  // a dead port forever, so this tree never settles.
  await tester.pump();
}

void main() {
  testWidgets('an empty conversation offers somewhere to start', (tester) async {
    await _pumpChat(tester);

    expect(find.text('What are you working on?'), findsOneWidget);
    expect(find.text('A past decision'), findsOneWidget);
    expect(find.text('My documents'), findsOneWidget);
  });

  testWidgets('a starter fills the composer instead of sending it', (tester) async {
    await _pumpChat(tester);

    await tester.tap(find.text('A past decision'));
    await tester.pump();

    final field = tester.widget<TextField>(find.byType(TextField));
    expect(field.controller!.text, 'What did I decide about ');
    // Nothing was sent: the transcript is still empty, so the starters are
    // still on screen.
    expect(find.text('What are you working on?'), findsOneWidget);
  });

  testWidgets('the caret lands at the end, ready to keep typing', (tester) async {
    // A starter that ends mid-sentence is useless if the cursor sits at
    // position zero and the next keystroke goes in front of it.
    await _pumpChat(tester);

    await tester.tap(find.text('A past decision'));
    await tester.pump();

    final controller = tester.widget<TextField>(find.byType(TextField)).controller!;
    expect(controller.selection.baseOffset, controller.text.length);
  });
}
