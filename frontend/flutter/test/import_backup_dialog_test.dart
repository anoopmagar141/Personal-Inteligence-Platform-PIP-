// What the first-run "Import existing PIP" dialog tells somebody to do.
//
// The button deliberately does not restore anything itself - a restore replaces
// the database file the running backend has open, and this screen has no proof
// of ownership of anything - so everything it can do for the person is to say,
// accurately, what happens next. It was not accurate. It told them to "close
// PIP" and run the shortcut, and closing the window does not stop PIP's
// background process (FREEZE_LIST D-09), so on the one machine this screen is
// shown on the shortcut refused to run. The shortcut now offers to close PIP;
// this dialog has to say so, or the person meets a question the screen that sent
// them there never mentioned.
//
// It also never said where the file was. The shortcut asks for a path on a
// machine whose data folder is empty, and the dialog showed only the file's
// NAME - so the person had to find the file again in a second window. The full
// path is shown, selectable, with a Copy button.
//
// And it did not say that the restored profile arrives called "Default" - the
// name the shortcut's layout gives it - so somebody who restored "BatMan" went
// looking for BatMan on the sign-in screen.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/screens/sign_in_screen.dart';
import 'package:pip_flutter_client/theme.dart';

const _path = r'D:\Backups\BatMan_PIP_story.pipbak';
const _name = 'BatMan_PIP_story.pipbak';

Future<void> _pump(WidgetTester tester) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.light,
      home: Builder(
        builder: (context) => Scaffold(
          body: Center(
            child: TextButton(
              onPressed: () => showDialog<void>(
                context: context,
                builder: (_) => const ImportBackupDialog(fileName: _name, path: _path),
              ),
              child: const Text('open'),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('names the file and shows where it is, selectable', (tester) async {
    await _pump(tester);

    expect(find.textContaining(_name), findsWidgets);
    expect(find.widgetWithText(SelectableText, _path), findsOneWidget);
  });

  testWidgets('says the shortcut may ask to close PIP, and that this is normal', (tester) async {
    await _pump(tester);

    expect(find.textContaining('still running in the background'), findsOneWidget);
    expect(find.textContaining('Type yes to close it'), findsOneWidget);
  });

  testWidgets('says which passwords are asked for', (tester) async {
    await _pump(tester);

    expect(find.textContaining('the backup password'), findsOneWidget);
    expect(find.textContaining('a new password for this computer'), findsOneWidget);
  });

  testWidgets('says the restored profile is called Default', (tester) async {
    await _pump(tester);

    expect(find.textContaining('“Default”'), findsOneWidget);
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

  testWidgets('Close dismisses it and nothing else happens', (tester) async {
    await _pump(tester);

    await tester.tap(find.text('Close'));
    await tester.pumpAndSettle();

    expect(find.byType(ImportBackupDialog), findsNothing);
  });
}
