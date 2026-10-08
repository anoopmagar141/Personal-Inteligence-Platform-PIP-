// The first-run "Import existing PIP" dialog.
//
// It used to be a signpost: it said close PIP, run a shortcut and sign in to a profile
// called "Default", because the in-app restore replaces the profile you are signed in
// to and a welcome screen has nobody signed in. At first run there is nothing to
// replace, so the dialog now does the import itself: it asks for the backup's password
// and a NEW one for this computer, hands both to the backend (POST /backup/import) and
// closes with the result, and the screen carries on to sign-in for the imported profile.
//
// What is held here is what a person meets: the file and where it is (a name alone made
// them find it again), the three fields and the refusals the client can make without a
// round trip, the backend's own sentence when it refuses, a dialog that stays open on a
// refusal so the person can correct a typo, and the shortcut still described for anybody
// who would rather use it - including that it may ask to close PIP (D-09) and that it
// restores into a profile called "Default".

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/sign_in_screen.dart';
import 'package:pip_flutter_client/theme.dart';

const _path = r'D:\Backups\BatMan_PIP_story.pipbak';
const _name = 'BatMan_PIP_story.pipbak';

typedef _Import = Future<Map<String, dynamic>> Function(String backupPassword, String newPassword);

class _Opened {
  Map<String, dynamic>? result;
  bool closed = false;
}

Future<_Opened> _pump(WidgetTester tester, {_Import? onImport}) async {
  final opened = _Opened();
  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.light,
      home: Builder(
        builder: (context) => Scaffold(
          body: Center(
            child: TextButton(
              onPressed: () async {
                opened.result = await showDialog<Map<String, dynamic>>(
                  context: context,
                  builder: (_) => ImportBackupDialog(
                    fileName: _name,
                    path: _path,
                    onImport: onImport ?? (b, n) async => {'slug': 'batman', 'name': 'BatMan', 'state': 'locked'},
                  ),
                );
                opened.closed = true;
              },
              child: const Text('open'),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
  return opened;
}

Future<void> _fill(WidgetTester tester, {String backup = '77777777', String fresh = 'batman-local-1', String again = 'batman-local-1'}) async {
  final fields = find.byType(TextField);
  await tester.enterText(fields.at(0), backup);
  await tester.enterText(fields.at(1), fresh);
  await tester.enterText(fields.at(2), again);
}

void main() {
  testWidgets('names the file and shows where it is, selectable', (tester) async {
    await _pump(tester);

    expect(find.textContaining(_name), findsWidgets);
    expect(find.widgetWithText(SelectableText, _path), findsOneWidget);
  });

  testWidgets('Copy path puts the full path on the clipboard and says so', (tester) async {
    String? copied;
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, (call) async {
      if (call.method == 'Clipboard.setData') {
        copied = (call.arguments as Map)['text'] as String?;
      }
      return null;
    });
    addTearDown(() => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, null));
    await _pump(tester);

    await tester.tap(find.byTooltip('Copy path'));
    await tester.pumpAndSettle();

    expect(copied, _path);
    expect(find.byTooltip('Copied'), findsOneWidget);
  });

  testWidgets('asks for the backup password and a new one, twice', (tester) async {
    await _pump(tester);

    expect(find.byType(TextField), findsNWidgets(3));
    expect(find.text('The backup\u2019s password'), findsOneWidget);
    expect(find.text('New password for this computer'), findsOneWidget);
    expect(find.text('New password again'), findsOneWidget);
    expect(find.text('Import'), findsOneWidget);
  });

  testWidgets('still describes the shortcut, including the close-PIP question and "Default"', (tester) async {
    await _pump(tester);

    expect(find.textContaining('Restore PIP from backup'), findsOneWidget);
    expect(find.textContaining('still running in the background'), findsOneWidget);
    expect(find.textContaining('\u201cDefault\u201d'), findsOneWidget);
  });

  testWidgets('hands both passwords to the import and closes with its result', (tester) async {
    String? gotBackup;
    String? gotNew;
    final opened = await _pump(tester, onImport: (b, n) async {
      gotBackup = b;
      gotNew = n;
      return {'slug': 'batman', 'name': 'BatMan', 'state': 'locked'};
    });

    await _fill(tester);
    await tester.tap(find.text('Import'));
    await tester.pumpAndSettle();

    expect(gotBackup, '77777777');
    expect(gotNew, 'batman-local-1');
    expect(opened.closed, isTrue);
    expect(opened.result?['name'], 'BatMan');
  });

  group('refusals the client makes without a round trip', () {
    for (final c in [
      ('an empty backup password', '', 'batman-local-1', 'batman-local-1', 'Enter the backup password'),
      ('a new password under 8 characters', '77777777', 'short', 'short', 'at least 8'),
      ('two new passwords that differ', '77777777', 'batman-local-1', 'batman-local-2', 'different'),
      ('a new password equal to the backup password', '77777777', '77777777', '77777777', 'different from the backup'),
    ]) {
      testWidgets(c.$1, (tester) async {
        var called = false;
        await _pump(tester, onImport: (b, n) async {
          called = true;
          return {};
        });

        await _fill(tester, backup: c.$2, fresh: c.$3, again: c.$4);
        await tester.tap(find.text('Import'));
        await tester.pumpAndSettle();

        expect(find.textContaining(c.$5), findsOneWidget);
        expect(called, isFalse, reason: 'a refusal the client can make was sent to the backend');
        expect(find.byType(ImportBackupDialog), findsOneWidget);
      });
    }
  });

  testWidgets("shows the backend's own sentence and stays open so a typo can be corrected", (tester) async {
    final opened = await _pump(tester, onImport: (b, n) async {
      throw ApiException(422, '{"detail":"carried.pipbak did not open with that password. Nothing was written."}');
    });

    await _fill(tester);
    await tester.tap(find.text('Import'));
    await tester.pumpAndSettle();

    expect(find.textContaining('did not open with that password'), findsOneWidget);
    expect(find.byType(ImportBackupDialog), findsOneWidget);
    expect(opened.closed, isFalse);
  });

  testWidgets('Cancel closes it with nothing imported', (tester) async {
    final opened = await _pump(tester);

    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(find.byType(ImportBackupDialog), findsNothing);
    expect(opened.closed, isTrue);
    expect(opened.result, isNull);
  });
}
