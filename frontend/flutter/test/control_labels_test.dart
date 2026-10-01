// Every control a screen reader can reach has a name it can read.
//
// The 2026-10-01 audit found no Semantics anywhere in lib/ and four controls
// that were an icon and nothing else: send/stop, the delete-conversation "x",
// the sidebar's collapse toggle, and every sidebar item once the sidebar is
// collapsed (the text goes, and nothing replaced it). To a screen reader each
// of those is "button", with no way to tell which.
//
// Asserted on the semantics tree rather than on the presence of Tooltip
// widgets, because the tree is what assistive technology actually reads: a
// tooltip that is excluded from semantics, or a label on the wrong node, would
// satisfy a widget search and still announce "button". And it walks every
// tappable node on every tab rather than naming the four, so the fifth one -
// added next month - fails here too.

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/home_shell.dart';
import 'package:pip_flutter_client/theme.dart';

class FakeApi extends ApiClient {
  FakeApi() : super('http://127.0.0.1:1/api/v1');

  @override
  Future<Map<String, dynamic>> getStatus() async => {'pending_count': 0};

  @override
  Future<List<dynamic>> getProjects() async => [];

  // One conversation, so the list has a row to hover and its delete control
  // exists to be checked.
  @override
  Future<List<dynamic>> getConversations({String? projectId}) async => [
        {'id': 'c1', 'title': 'Planning the move'},
      ];
}

const _tabs = ['Chat', 'Review', 'Profile', 'Decisions', 'Projects', 'Documents', 'Providers', 'Backup', 'Trace'];

/// Every node that answers a tap but has neither a label nor a tooltip.
List<String> _unnamedTappables(WidgetTester tester) {
  final root = RendererBinding.instance.renderViews.first.owner!.semanticsOwner!.rootSemanticsNode!;
  final unnamed = <String>[];
  void visit(SemanticsNode node) {
    final data = node.getSemanticsData();
    final tappable = data.hasAction(SemanticsAction.tap);
    final named = data.label.trim().isNotEmpty || data.tooltip.trim().isNotEmpty;
    if (tappable && !named) unnamed.add('node ${node.id} at ${node.rect}');
    node.visitChildren((child) {
      visit(child);
      return true;
    });
  }

  visit(root);
  return unnamed;
}

Future<void> _pumpShell(WidgetTester tester) async {
  tester.view.physicalSize = const Size(1600, 1000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light,
    home: HomeShell(api: FakeApi(), themeMode: ThemeMode.light, onCycleTheme: () {}, onSignedOut: () {}),
  ));
  // pump, never pumpAndSettle: the chat client retries a dead port forever.
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 300));
}

void main() {
  testWidgets('every tappable control on every tab has a name, sidebar open', (tester) async {
    final semantics = tester.ensureSemantics();
    await _pumpShell(tester);

    final failures = <String>[];
    for (final tab in _tabs) {
      await tester.tap(find.text(tab).first, warnIfMissed: false);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      for (final node in _unnamedTappables(tester)) {
        failures.add('$tab: $node');
      }
    }

    expect(failures, isEmpty, reason: 'unnamed controls:\n${failures.join('\n')}');
    semantics.dispose();
  });

  testWidgets('sidebar items keep a name once the sidebar collapses to icons', (tester) async {
    final semantics = tester.ensureSemantics();
    await _pumpShell(tester);

    // The toggle is the chevron beside the PIP wordmark.
    await tester.tap(find.byIcon(Icons.chevron_left));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Decisions'), findsNothing, reason: 'the sidebar did not collapse');

    expect(_unnamedTappables(tester), isEmpty);
    // And the names are the tabs' own, not a generic "navigation item".
    for (final tab in _tabs) {
      expect(find.bySemanticsLabel(tab).evaluate().isNotEmpty || find.byTooltip(tab).evaluate().isNotEmpty, isTrue,
          reason: 'collapsed "$tab" item has no name of its own');
    }
    semantics.dispose();
  });

  testWidgets('the delete control on a hovered conversation has a name', (tester) async {
    final semantics = tester.ensureSemantics();
    await _pumpShell(tester);

    final mouse = await tester.createGesture(kind: PointerDeviceKind.mouse);
    addTearDown(mouse.removePointer);
    await mouse.addPointer(location: Offset.zero);
    await mouse.moveTo(tester.getCenter(find.text('Planning the move')));
    await tester.pump();
    expect(find.byIcon(Icons.close), findsOneWidget, reason: 'hovering did not reveal the delete control');

    expect(_unnamedTappables(tester), isEmpty);
    semantics.dispose();
  });
}
