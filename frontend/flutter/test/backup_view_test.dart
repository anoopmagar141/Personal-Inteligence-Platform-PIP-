// Tests for the Backup screen.
//
// The property worth testing is not "a button rendered" but "the button starts
// a console and never asks this app for a password". ADR-027's whole argument
// is that the export must not be performed by anything reachable over HTTP, and
// a screen that quietly grew a password field and a POST would look identical
// in a screenshot.

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pip_flutter_client/screens/backup_view.dart';
import 'package:pip_flutter_client/theme.dart';

Widget _wrap(Widget child) => MaterialApp(
      theme: AppTheme.light,
      home: Scaffold(body: child),
    );

Directory _tempDataDir() {
  final dir = Directory.systemTemp.createTempSync('pip_backup_test');
  return Directory('${dir.path}/data')..createSync();
}

void main() {
  testWidgets('lists the .pipbak files that are on disk', (tester) async {
    final data = _tempDataDir();
    File('${data.path}/pip_backup_20260902.pipbak').writeAsBytesSync(List.filled(2048, 7));
    File('${data.path}/notes.txt').writeAsStringSync('not a backup');

    await tester.pumpWidget(_wrap(BackupView(dataDir: data.path, launch: (_, _) async {})));
    await tester.pumpAndSettle();

    expect(find.text('pip_backup_20260902.pipbak'), findsOneWidget);
    expect(find.text('notes.txt'), findsNothing);

    data.parent.deleteSync(recursive: true);
  });

  testWidgets('says so plainly when there are no backups', (tester) async {
    // Distinct from an error. "No backups yet" is a fact about the directory;
    // a red failure message would be a claim that something went wrong.
    final data = _tempDataDir();

    await tester.pumpWidget(_wrap(BackupView(dataDir: data.path, launch: (_, _) async {})));
    await tester.pumpAndSettle();

    expect(find.textContaining('No .pipbak files'), findsOneWidget);

    data.parent.deleteSync(recursive: true);
  });

  testWidgets('Export now launches a console running the export script', (tester) async {
    final data = _tempDataDir();
    String? executable;
    List<String>? arguments;

    await tester.pumpWidget(_wrap(BackupView(
      dataDir: data.path,
      launch: (exe, args) async {
        executable = exe;
        arguments = args;
      },
    )));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Export now'));
    await tester.pumpAndSettle();

    // cmd /c start, not powershell directly: a GUI-subsystem app spawning
    // PowerShell gives it no console to draw in, and the password prompt would
    // block against a window that does not exist - which looks, from the user's
    // side, exactly like the button doing nothing.
    expect(executable, 'cmd.exe');
    expect(arguments, isNotNull);
    // A real window title, not the empty string start technically accepts:
    // it names the taskbar entry, and it avoids depending on how an empty
    // argument survives Dart's command-line quoting and cmd's re-parsing.
    expect(arguments!.take(3), ['/c', 'start', 'PIP Export']);
    expect(arguments!, contains('powershell.exe'));
    expect(arguments!.last, endsWith('scripts/export_pip.ps1'));

    data.parent.deleteSync(recursive: true);
  });

  testWidgets('the script path is resolved beside the data directory', (tester) async {
    // Not a second environment variable. main.dart already owns where the
    // installation is; deriving the scripts directory from data/'s parent keeps
    // one answer to that question instead of two that can disagree.
    final data = _tempDataDir();
    final key = GlobalKey<BackupViewState>();

    await tester.pumpWidget(_wrap(BackupView(key: key, dataDir: data.path, launch: (_, _) async {})));
    await tester.pumpAndSettle();

    final root = data.parent.path.replaceAll(r'\', '/');
    expect(key.currentState!.exportScriptPath, '$root/scripts/export_pip.ps1');

    data.parent.deleteSync(recursive: true);
  });

  testWidgets('never offers to take a password', (tester) async {
    // The regression this guards is a plausible, well-meant one: somebody
    // decides the console is clumsy, adds a password field and a POST, and
    // ADR-027 is gone with no test failing. An export the app can perform on
    // its own is an export anything talking to the backend can perform.
    final data = _tempDataDir();

    await tester.pumpWidget(_wrap(BackupView(dataDir: data.path, launch: (_, _) async {})));
    await tester.pumpAndSettle();

    expect(find.byType(TextField), findsNothing);
    expect(find.byType(TextFormField), findsNothing);
    expect(
      find.byWidgetPredicate((w) => w is EditableText && w.obscureText),
      findsNothing,
      reason: 'the live password belongs in the console, never in this app',
    );

    data.parent.deleteSync(recursive: true);
  });

  testWidgets('offers no restore button, and explains why', (tester) async {
    // Restore replaces the database this app has open. There is no arrangement
    // in which a button here can do it, so the screen has to say that rather
    // than leave someone hunting for a control that cannot exist.
    final data = _tempDataDir();

    await tester.pumpWidget(_wrap(BackupView(dataDir: data.path, launch: (_, _) async {})));
    await tester.pumpAndSettle();

    expect(find.text('Restore now'), findsNothing);
    expect(find.textContaining('no restore button'), findsOneWidget);
    expect(find.textContaining('restore_pip.ps1'), findsOneWidget);

    data.parent.deleteSync(recursive: true);
  });

  testWidgets('says documents are included, and what is not', (tester) async {
    // This assertion was the exact opposite until document_blobs existed, and
    // the inversion is the feature: the bytes now travel inside the same single
    // .pipbak. What genuinely cannot be in it - Ollama's models, PIP itself -
    // is still named, because "everything" with an unstated exception is how
    // somebody ends up stuck on a new machine.
    final data = _tempDataDir();

    await tester.pumpWidget(_wrap(BackupView(dataDir: data.path, launch: (_, _) async {})));
    await tester.pumpAndSettle();

    expect(find.textContaining('documents themselves'), findsOneWidget);
    expect(find.textContaining('Not in it: Ollama'), findsOneWidget);
    expect(find.textContaining('every message'), findsOneWidget);

    data.parent.deleteSync(recursive: true);
  });

  testWidgets('a missing data directory is not an error', (tester) async {
    // A fresh machine, before anything has been written. Showing a red failure
    // for the expected state of a new install would train people to ignore it.
    await tester.pumpWidget(_wrap(
      BackupView(dataDir: '${Directory.systemTemp.path}/pip-does-not-exist', launch: (_, _) async {}),
    ));
    await tester.pumpAndSettle();

    expect(find.textContaining('Could not read'), findsNothing);
    expect(find.textContaining('No .pipbak files'), findsOneWidget);
  });

  testWidgets('always shows which script it will run', (tester) async {
    // The first question any failure here raises. This screen's whole job is
    // launching something that lives outside the app, so which file it is
    // aiming at should never require a debugger to find out.
    final data = _tempDataDir();

    await tester.pumpWidget(_wrap(BackupView(dataDir: data.path, launch: (_, _) async {})));
    await tester.pumpAndSettle();

    expect(find.textContaining('scripts/export_pip.ps1'), findsWidgets);

    data.parent.deleteSync(recursive: true);
  });

  testWidgets('a missing export script fails visibly, not silently', (tester) async {
    // The failure mode that produced this test: PowerShell handed a -File path
    // that does not exist prints one line and exits, so the console appears and
    // vanishes inside a frame. From the outside that is indistinguishable from
    // a button that does nothing - which leaves the user nothing to report.
    //
    // No injected runner here, so the real existence check runs against a
    // temporary directory that has no scripts/ beside it.
    final data = _tempDataDir();

    await tester.pumpWidget(_wrap(BackupView(dataDir: data.path)));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Export now'));
    await tester.pumpAndSettle();

    expect(find.textContaining('was not found'), findsOneWidget);

    data.parent.deleteSync(recursive: true);
  });
}
