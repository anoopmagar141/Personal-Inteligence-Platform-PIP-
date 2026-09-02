// Scoping the chat sidebar to the active project.
//
// The backend has always been able to filter conversations by project - the
// column, its foreign key, and list_conversations()'s parameter were all
// there. The client never passed one, so the sidebar was a single flat pile
// regardless of what you were working on, and every conversation the app
// created was filed against nothing.
//
// The risk in fixing that is hiding things. A chat started before any project
// was selected belongs to no project, and strict filtering would make it
// unreachable - which is why "All chats" is a real option rather than a
// decoration, and why the two empty states say different things.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/chat_view.dart';
import 'package:pip_flutter_client/ws_chat_client.dart';

class FakeApi extends ApiClient {
  FakeApi() : super('http://127.0.0.1:8765/api/v1');

  /// Keyed by the project filter asked for; null is "everything".
  Map<String?, List<dynamic>> byProject = {};
  final List<String?> requestedScopes = [];

  @override
  Future<List<dynamic>> getConversations({String? projectId}) async {
    requestedScopes.add(projectId);
    return byProject[projectId] ?? [];
  }
}

Map<String, dynamic> conversation(String id, String title) => {'id': id, 'title': title};

Future<FakeApi> pumpChat(
  WidgetTester tester, {
  String? activeProjectId,
  Map<String?, List<dynamic>>? byProject,
}) async {
  final api = FakeApi()..byProject = byProject ?? {};
  // Never connected: ChatView only listens to the stream, and connect() is the
  // shell's job. No socket is opened by constructing one.
  final chatClient = WsChatClient('ws://127.0.0.1:1/ws/chat');
  addTearDown(chatClient.dispose);

  tester.view.physicalSize = const Size(1600, 1000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: ChatView(api: api, chatClient: chatClient, activeProjectId: activeProjectId),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return api;
}

void main() {
  testWidgets('with a project active, the sidebar asks for that project only', (tester) async {
    final api = await pumpChat(
      tester,
      activeProjectId: 'p1',
      byProject: {
        'p1': [conversation('c1', 'Thesis chapter 4')],
        null: [conversation('c1', 'Thesis chapter 4'), conversation('c2', 'Unrelated')],
      },
    );

    expect(api.requestedScopes, contains('p1'));
    expect(find.text('Thesis chapter 4'), findsOneWidget);
    expect(find.text('Unrelated'), findsNothing);
  });

  testWidgets('with no project active, it asks for everything', (tester) async {
    // Nothing to scope to, so scoping would be a filter on nothing.
    final api = await pumpChat(
      tester,
      byProject: {
        null: [conversation('c2', 'Unrelated')],
      },
    );

    expect(api.requestedScopes, [null]);
    expect(find.text('Unrelated'), findsOneWidget);
    // A switch with one setting is not a switch.
    expect(find.text('All chats'), findsNothing);
  });

  testWidgets('All chats reaches a conversation the project filter hides', (tester) async {
    // The whole reason the escape exists: a chat started before any project
    // was picked belongs to none, and must not become unreachable.
    final api = await pumpChat(
      tester,
      activeProjectId: 'p1',
      byProject: {
        'p1': [conversation('c1', 'Thesis chapter 4')],
        null: [conversation('c1', 'Thesis chapter 4'), conversation('c2', 'Started before projects')],
      },
    );

    expect(find.text('Started before projects'), findsNothing);

    await tester.tap(find.text('All chats'));
    await tester.pumpAndSettle();

    expect(api.requestedScopes.last, isNull);
    expect(find.text('Started before projects'), findsOneWidget);
    expect(find.text('Thesis chapter 4'), findsOneWidget);
  });

  testWidgets('an empty project says so, without claiming there are no chats at all', (tester) async {
    // Two different facts. Borrowing the wording of the other one would tell
    // someone their history was gone.
    await pumpChat(
      tester,
      activeProjectId: 'p1',
      byProject: {
        'p1': [],
        null: [conversation('c2', 'Unrelated')],
      },
    );

    expect(find.text('No chats in this project yet.'), findsOneWidget);
    expect(find.text('No conversations yet.'), findsNothing);
  });

  testWidgets('switching project re-asks rather than showing the old one', (tester) async {
    final api = FakeApi()
      ..byProject = {
        'p1': [conversation('c1', 'First project chat')],
        'p2': [conversation('c3', 'Second project chat')],
      };
    final chatClient = WsChatClient('ws://127.0.0.1:1/ws/chat');
    addTearDown(chatClient.dispose);

    Widget build(String projectId) => MaterialApp(
          home: Scaffold(
            body: ChatView(api: api, chatClient: chatClient, activeProjectId: projectId),
          ),
        );

    await tester.pumpWidget(build('p1'));
    await tester.pumpAndSettle();
    expect(find.text('First project chat'), findsOneWidget);

    await tester.pumpWidget(build('p2'));
    await tester.pumpAndSettle();

    expect(api.requestedScopes.last, 'p2');
    expect(find.text('Second project chat'), findsOneWidget);
    expect(find.text('First project chat'), findsNothing);
  });
}
