// When each message was sent, and how that is said on screen.
//
// The database has carried messages.created_at from the start and the client
// dropped it: get_messages() returned it, the WebSocket's session_info did
// not forward it, and the transcript had nowhere to put it. So a conversation
// resumed from a week ago read as though every turn had just happened.
//
// The formatting helpers are tested directly rather than only through the
// widget, because the two decisions worth protecting are not visual: that a
// day boundary is a calendar question rather than a 24-hour one, and that a
// message with no time shows none rather than an invented one.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/screens/chat_view.dart';

Future<void> pumpBubble(WidgetTester tester, ChatMessage message) async {
  await tester.pumpWidget(
    MaterialApp(home: Scaffold(body: ChatMessageBubble(message: message))),
  );
  await tester.pumpAndSettle();
}

void main() {
  group('formatMessageTime', () {
    test('pads both halves to two digits', () {
      expect(formatMessageTime(DateTime(2026, 9, 4, 9, 5)), '09:05');
      expect(formatMessageTime(DateTime(2026, 9, 4, 14, 32)), '14:32');
    });

    test('midnight is 00:00, not 24:00 or blank', () {
      expect(formatMessageTime(DateTime(2026, 9, 4, 0, 0)), '00:00');
    });
  });

  group('isSameDay', () {
    test('two times on one date are the same day', () {
      expect(
        isSameDay(DateTime(2026, 9, 4, 0, 1), DateTime(2026, 9, 4, 23, 59)),
        isTrue,
      );
    });

    test('two times minutes apart across midnight are not', () {
      // The reason this compares date parts instead of subtracting: these are
      // two minutes apart and belong under different headings.
      expect(
        isSameDay(DateTime(2026, 9, 4, 23, 59), DateTime(2026, 9, 5, 0, 1)),
        isFalse,
      );
    });

    test('the same date a year apart is not the same day', () {
      expect(isSameDay(DateTime(2025, 9, 4), DateTime(2026, 9, 4)), isFalse);
    });
  });

  group('messageDateLabel', () {
    final now = DateTime(2026, 9, 4, 12, 0);

    test('names today and yesterday', () {
      expect(messageDateLabel(DateTime(2026, 9, 4, 8, 0), now: now), 'Today');
      expect(messageDateLabel(DateTime(2026, 9, 3, 23, 0), now: now), 'Yesterday');
    });

    test('anything older gets a full date', () {
      // Deliberately not a weekday name: "Tuesday" stops meaning anything the
      // moment a conversation is more than a week old, which is exactly when
      // somebody is scrolling back to find something.
      expect(messageDateLabel(DateTime(2026, 9, 2), now: now), '2 September 2026');
      expect(messageDateLabel(DateTime(2025, 12, 25), now: now), '25 December 2025');
    });

    test('yesterday across a month boundary is still yesterday', () {
      expect(
        messageDateLabel(DateTime(2026, 8, 31, 22, 0), now: DateTime(2026, 9, 1, 9, 0)),
        'Yesterday',
      );
    });
  });

  group('the bubble', () {
    testWidgets('shows the time a message was sent', (tester) async {
      await pumpBubble(
        tester,
        ChatMessage('user', 'hello', createdAt: DateTime(2026, 9, 4, 14, 32)),
      );

      expect(find.text('14:32'), findsOneWidget);
    });

    testWidgets('shows no time when there is none to show', (tester) async {
      // A message from before created_at crossed the wire, or one still being
      // streamed. A blank is honest; a fabricated time is not.
      await pumpBubble(tester, const ChatMessage('assistant', 'still typing'));

      expect(find.textContaining(':'), findsNothing);
    });

    testWidgets('an interrupted reply shows both its time and that it stopped',
        (tester) async {
      await pumpBubble(
        tester,
        ChatMessage(
          'assistant',
          'half an answer',
          stopped: true,
          createdAt: DateTime(2026, 9, 4, 9, 5),
        ),
      );

      expect(find.text('09:05'), findsOneWidget);
      expect(find.text('Stopped'), findsOneWidget);
    });
  });
}
