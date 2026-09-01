// The one rule in the chat bubble that is a correctness decision rather than
// a styling one: assistant replies are Markdown, and the user's own message is
// not.
//
// It would be tidier to render both the same way, and that is exactly the
// "simplification" this test exists to stop. What the user typed is theirs.
// Re-rendering it means a filename with asterisks in it silently loses them,
// a password pasted into chat gets mangled, and there is no way for them to
// tell that the text on screen is not the text they sent.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/markdown.dart';
import 'package:pip_flutter_client/screens/chat_view.dart';

Future<void> pumpBubble(WidgetTester tester, ChatMessage message) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(body: ChatMessageBubble(message: message)),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('an assistant reply is rendered as Markdown', (tester) async {
    await pumpBubble(tester, const ChatMessage('assistant', 'Run **pytest** first'));

    expect(find.byType(MarkdownBody), findsOneWidget);
    expect(find.textContaining('**'), findsNothing);
  });

  testWidgets('a user message is shown exactly as typed', (tester) async {
    await pumpBubble(tester, const ChatMessage('user', 'rename **draft**.md for me'));

    expect(find.byType(MarkdownBody), findsNothing);
    // The asterisks are part of the filename they asked about. Losing them
    // changes the question.
    expect(find.text('rename **draft**.md for me'), findsOneWidget);
  });

  testWidgets('an interrupted reply still says it was stopped', (tester) async {
    await pumpBubble(
      tester,
      const ChatMessage('assistant', 'I was saying **something', stopped: true),
    );

    expect(find.text('Stopped'), findsOneWidget);
    // Half-written emphasis, because the stop landed mid-marker. It stays
    // literal rather than eating the rest of the turn.
    expect(find.textContaining('**something'), findsOneWidget);
  });

  testWidgets('an error turn is plain, not Markdown', (tester) async {
    // These are PIP's own words about a failure. There is no reason to run a
    // formatter over a message whose whole job is to be read literally.
    await pumpBubble(tester, const ChatMessage('system', 'Error: connection refused'));

    expect(find.byType(MarkdownBody), findsNothing);
    expect(find.text('Error: connection refused'), findsOneWidget);
  });
}
