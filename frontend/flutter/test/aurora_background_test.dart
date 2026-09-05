// The decorative glow behind the chat.
//
// Two things are worth holding it to. It must respect a reduce-motion setting,
// because a thing that drifts forever behind what somebody is reading is
// precisely what that setting is for. And it must still PAINT when motion is
// off - the glow is a colour wash, and switching it off entirely would change
// the look of the app for the people least able to opt back in.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/theme.dart';
import 'package:pip_flutter_client/widgets/aurora_background.dart';

Future<void> _pump(WidgetTester tester, {required bool reduceMotion}) async {
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light,
    home: Builder(
      builder: (context) => MediaQuery(
        data: MediaQuery.of(context).copyWith(disableAnimations: reduceMotion),
        child: const Scaffold(
          body: AuroraBackground(child: Center(child: Text('content'))),
        ),
      ),
    ),
  ));
}

void main() {
  testWidgets('settles when the viewer has asked for less motion', (tester) async {
    await _pump(tester, reduceMotion: true);

    // The assertion IS that this returns. With the animation running it never
    // does, which is how five unrelated chat tests failed when this widget was
    // first dropped into the screen.
    await tester.pumpAndSettle();

    expect(find.text('content'), findsOneWidget);
  });

  testWidgets('still draws the glow when motion is off', (tester) async {
    await _pump(tester, reduceMotion: true);
    await tester.pumpAndSettle();

    // Painting, just not moving.
    expect(find.byType(CustomPaint), findsWidgets);
  });

  testWidgets('keeps its child above the glow', (tester) async {
    await _pump(tester, reduceMotion: false);
    await tester.pump();

    expect(find.text('content'), findsOneWidget);
  });

  testWidgets('animates when motion is allowed', (tester) async {
    await _pump(tester, reduceMotion: false);
    await tester.pump();

    // A frame scheduled after a pump with no input is the animation asking for
    // the next one. pumpAndSettle would hang here, which is the point.
    expect(tester.binding.hasScheduledFrame, isTrue);
  });
}
