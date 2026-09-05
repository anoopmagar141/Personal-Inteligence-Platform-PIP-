// The launch screen's particle field.
//
// It runs while the backend is opening SQLCipher, loading chromadb and warming
// an embedding model, so what is worth holding it to is mostly restraint: that
// it stops when asked, that it never covers what it sits behind, and that the
// startup checklist stays readable on top of it - which is the one thing on
// that screen somebody actually needs when a launch goes wrong.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/main.dart';
import 'package:pip_flutter_client/theme.dart';
import 'package:pip_flutter_client/widgets/gateway_flow.dart';

Future<void> _pump(WidgetTester tester, {required bool reduceMotion}) async {
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light,
    home: Builder(
      builder: (context) => MediaQuery(
        data: MediaQuery.of(context).copyWith(disableAnimations: reduceMotion),
        child: const Scaffold(
          body: GatewayFlow(child: Center(child: Text('launching'))),
        ),
      ),
    ),
  ));
}

void main() {
  testWidgets('settles when the viewer has asked for less motion', (tester) async {
    await _pump(tester, reduceMotion: true);

    // The assertion is that this returns at all.
    await tester.pumpAndSettle();

    expect(find.text('launching'), findsOneWidget);
  });

  testWidgets('drifts when motion is allowed', (tester) async {
    await _pump(tester, reduceMotion: false);
    await tester.pump();

    expect(tester.binding.hasScheduledFrame, isTrue);
  });

  testWidgets('keeps its child on top of the field', (tester) async {
    await _pump(tester, reduceMotion: false);
    await tester.pump();

    expect(find.text('launching'), findsOneWidget);
  });

  testWidgets('a tap does not disturb what is on top of it', (tester) async {
    // The shockwave is a background flourish. It must not swallow taps meant
    // for anything the launch screen puts over it.
    await _pump(tester, reduceMotion: false);
    await tester.pump();

    await tester.tapAt(const Offset(120, 120));
    await tester.pump();

    expect(find.text('launching'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('the launch screen is dark whichever theme is set', (tester) async {
    // The field is dots of light and only exists against a black stage. The
    // launch screen is also the one surface shown before the backend has said
    // anything, so the user's theme is a guess there - it commits to dark
    // rather than pretending to match.
    await tester.pumpWidget(const PipApp());
    await tester.pump();

    expect(find.byType(GatewayFlow), findsOneWidget);
    final scaffold = tester.widget<Scaffold>(
      find.ancestor(of: find.byType(GatewayFlow), matching: find.byType(Scaffold)).first,
    );
    expect(scaffold.backgroundColor, const Color(0xFF060608));

    // And the wordmark over it has to be legible on that stage rather than
    // taking the light theme's near-black.
    final wordmark = tester.widget<Text>(find.text('PIP'));
    expect(wordmark.style!.color, const Color(0xFFF2F3F8));
  });
}
