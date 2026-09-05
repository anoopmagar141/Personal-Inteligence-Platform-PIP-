// The sign-in screen, which is now the first thing anybody sees.
//
// What is worth asserting here is not that a button submits. It is the three
// things that would be quietly wrong in a way nobody notices until it matters:
// that an unfamiliar state falls back to asking for a password rather than
// skipping one, that the server's own sentence reaches the person who typed
// the password, and that the screen says out loud that nothing can be
// recovered - because the whole design depends on somebody having been told.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/sign_in_screen.dart';
import 'package:pip_flutter_client/theme.dart';

class FakeApi extends ApiClient {
  final List<String> unlocked = [];
  final List<String> created = [];
  Object? throwThis;

  FakeApi() : super('http://localhost:0', apiToken: 't');

  @override
  Future<void> unlock(String password) async {
    if (throwThis != null) throw throwThis!;
    unlocked.add(password);
  }

  @override
  Future<void> completeSetup(String password) async {
    if (throwThis != null) throw throwThis!;
    created.add(password);
  }
}

Future<FakeApi> pumpSignIn(
  WidgetTester tester,
  AuthState state, {
  VoidCallback? onUnlocked,
  Object? throwThis,
}) async {
  final api = FakeApi()..throwThis = throwThis;
  // disableAnimations, so pumpAndSettle below has something to settle to. This
  // screen now sits on the launch screen's particle field, which drifts
  // forever by design; these tests are about passwords and should not have to
  // know that. Inside MaterialApp, not around it - MaterialApp installs its
  // own MediaQuery from the view and would replace anything above it.
  await tester.pumpWidget(
    MaterialApp(
      home: Builder(
        builder: (context) => MediaQuery(
          data: MediaQuery.of(context).copyWith(disableAnimations: true),
          child: SignInScreen(
            api: api,
            state: state,
            onUnlocked: onUnlocked ?? () {},
          ),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return api;
}

void main() {
  _legibilityTests();
  _migrationTests();
  group('authStateFrom', () {
    test('reads the four states the backend reports', () {
      expect(authStateFrom('locked'), AuthState.locked);
      expect(authStateFrom('setup'), AuthState.setup);
      expect(authStateFrom('needs_migration'), AuthState.needsMigration);
      expect(authStateFrom('unlocked'), AuthState.unlocked);
    });

    test('an unfamiliar state asks for a password rather than skipping one', () {
      // A client and backend that disagree must fail towards the lock. The
      // opposite default would turn a version skew into an open database.
      expect(authStateFrom('something-new'), AuthState.locked);
      expect(authStateFrom(''), AuthState.locked);
    });
  });

  group('signing in', () {
    testWidgets('asks for one password and sends it', (tester) async {
      final api = await pumpSignIn(tester, AuthState.locked);

      expect(find.text('Welcome back'), findsOneWidget);
      expect(find.byType(TextField), findsOneWidget);

      await tester.enterText(find.byType(TextField), 'correct-horse');
      await tester.tap(find.text('Unlock'));
      await tester.pumpAndSettle();

      expect(api.unlocked, ['correct-horse']);
    });

    testWidgets('says there is no way to recover a forgotten password',
        (tester) async {
      // The key is derived from the password and never written down, so this
      // is true by construction - and only defensible if somebody is told
      // before they rely on it.
      await pumpSignIn(tester, AuthState.locked);

      expect(find.textContaining('no password reset'), findsOneWidget);
    });

    testWidgets('shows the server\'s own sentence when the password is wrong',
        (tester) async {
      final api = await pumpSignIn(
        tester,
        AuthState.locked,
        throwThis: Exception('401 {"detail":"That password did not open your data."}'),
      );

      await tester.enterText(find.byType(TextField), 'wrong');
      await tester.tap(find.text('Unlock'));
      await tester.pumpAndSettle();

      expect(find.text('That password did not open your data.'), findsOneWidget);
      expect(api.unlocked, isEmpty);
    });

    testWidgets('clears the field after a wrong password', (tester) async {
      await pumpSignIn(
        tester,
        AuthState.locked,
        throwThis: Exception('401 {"detail":"nope"}'),
      );

      await tester.enterText(find.byType(TextField), 'wrong');
      await tester.tap(find.text('Unlock'));
      await tester.pumpAndSettle();

      // Retyping should not mean selecting the old value first.
      expect(tester.widget<TextField>(find.byType(TextField)).controller!.text, '');
    });

    testWidgets('an empty password is refused without a round trip',
        (tester) async {
      final api = await pumpSignIn(tester, AuthState.locked);

      await tester.tap(find.text('Unlock'));
      await tester.pumpAndSettle();

      expect(find.text('Enter your password.'), findsOneWidget);
      expect(api.unlocked, isEmpty);
    });

    testWidgets('reports unlocking to the caller', (tester) async {
      var opened = false;
      await pumpSignIn(tester, AuthState.locked, onUnlocked: () => opened = true);

      await tester.enterText(find.byType(TextField), 'correct-horse');
      await tester.tap(find.text('Unlock'));
      await tester.pumpAndSettle();

      expect(opened, isTrue);
    });
  });

  group('choosing a first password', () {
    testWidgets('asks twice and warns that it cannot be recovered',
        (tester) async {
      await pumpSignIn(tester, AuthState.setup);

      expect(find.text('Choose a password'), findsOneWidget);
      expect(find.byType(TextField), findsNWidgets(2));
      expect(find.textContaining('cannot be recovered'), findsOneWidget);
    });

    testWidgets('refuses two different passwords before asking the server',
        (tester) async {
      // The one error the client can be certain about on its own, and the
      // round trip would cost a quarter-second of key derivation to report it.
      final api = await pumpSignIn(tester, AuthState.setup);

      await tester.enterText(find.byType(TextField).first, 'first-password');
      await tester.enterText(find.byType(TextField).last, 'second-password');
      await tester.tap(find.text('Create password'));
      await tester.pumpAndSettle();

      expect(find.text('Those two passwords are different.'), findsOneWidget);
      expect(api.created, isEmpty);
    });

    testWidgets('sends a matching pair', (tester) async {
      final api = await pumpSignIn(tester, AuthState.setup);

      await tester.enterText(find.byType(TextField).first, 'matching-password');
      await tester.enterText(find.byType(TextField).last, 'matching-password');
      await tester.tap(find.text('Create password'));
      await tester.pumpAndSettle();

      expect(api.created, ['matching-password']);
    });

    testWidgets('surfaces the server\'s refusal of a weak password',
        (tester) async {
      await pumpSignIn(
        tester,
        AuthState.setup,
        throwThis: Exception('422 {"detail":"Use at least 8 characters."}'),
      );

      await tester.enterText(find.byType(TextField).first, 'short');
      await tester.enterText(find.byType(TextField).last, 'short');
      await tester.tap(find.text('Create password'));
      await tester.pumpAndSettle();

      expect(find.text('Use at least 8 characters.'), findsOneWidget);
    });
  });

  group('an unencrypted database from before passwords', () {
    testWidgets('points at the migration script instead of offering a button',
        (tester) async {
      // Encrypting data somebody already has backs up first and proves the new
      // key works before removing anything. A button here would be the least
      // ceremonious irreversible action in PIP.
      await pumpSignIn(tester, AuthState.needsMigration);

      expect(find.textContaining('not encrypted yet'), findsOneWidget);
      expect(find.textContaining('set_db_password.py'), findsOneWidget);
      expect(find.byType(TextField), findsNothing);
    });
  });
}


// --- Legibility on the fixed dark stage ------------------------------------
//
// Sign-in sits on the launch screen's particle field, which forces a dark
// stage in both themes. That makes every colour on this screen a decision
// rather than an inheritance, and the failure mode is not cosmetic: a password
// that cannot be recovered, typed into a field somebody cannot see.

Future<void> _pumpUnderLightTheme(WidgetTester tester) async {
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light,
    home: Builder(
      builder: (context) => MediaQuery(
        data: MediaQuery.of(context).copyWith(disableAnimations: true),
        child: SignInScreen(api: FakeApi(), state: AuthState.locked, onUnlocked: () {}),
      ),
    ),
  ));
  await tester.pumpAndSettle();
}

void _expectLightOnDark(Color? colour) {
  expect(colour, isNotNull);
  // Anything this bright cannot be one of the light theme's dark inks, which
  // is the whole assertion - not the exact shade, which is free to change.
  expect(colour!.computeLuminance(), greaterThan(0.4));
}

void _legibilityTests() {
  testWidgets('the heading stays readable under the light theme', (tester) async {
    await _pumpUnderLightTheme(tester);

    final heading = tester.widget<Text>(find.text('Welcome back'));
    _expectLightOnDark(heading.style?.color);
  });

  testWidgets('the password field shows what is typed into it', (tester) async {
    await _pumpUnderLightTheme(tester);

    final field = tester.widget<TextField>(find.byType(TextField));
    _expectLightOnDark(field.style?.color);
    // And the field is not left transparent over the field of dots, which
    // would put moving specks behind the characters.
    expect(field.decoration?.filled, isTrue);
  });

  testWidgets('the unrecoverable-password warning is still legible', (tester) async {
    // The one piece of copy on this screen somebody has to read BEFORE they
    // rely on it.
    await _pumpUnderLightTheme(tester);

    final warning = tester.widget<Text>(find.textContaining('no password reset'));
    expect(warning.style!.color!.computeLuminance(), greaterThan(0.12));
  });
}


// --- The migration notice --------------------------------------------------
//
// The screen shown instead of the password prompt when an installation still
// has an unencrypted database. It is one instruction and nothing else, so what
// is worth holding it to is that the instruction survives: readable, copyable
// by hand, and copyable by button.

Future<void> _pumpMigration(WidgetTester tester) async {
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light,
    home: Builder(
      builder: (context) => MediaQuery(
        data: MediaQuery.of(context).copyWith(disableAnimations: true),
        child: SignInScreen(
          api: FakeApi(),
          state: AuthState.needsMigration,
          onUnlocked: () {},
        ),
      ),
    ),
  ));
  await tester.pumpAndSettle();
}

const _migrationCommand = r'.venv\Scripts\python.exe scripts\set_db_password.py';

void _migrationTests() {
  testWidgets('shows the command, and never a password field', (tester) async {
    await _pumpMigration(tester);

    expect(find.text(_migrationCommand), findsOneWidget);
    // The point of this state: there is nothing to unlock yet, so offering a
    // password box would invite somebody to set one on the wrong path.
    expect(find.byType(TextField), findsNothing);
  });

  testWidgets('the command stays selectable by hand', (tester) async {
    // The copy button is the easy path, not the only one.
    await _pumpMigration(tester);

    expect(find.byType(SelectableText), findsOneWidget);
  });

  testWidgets('the copy button puts the command on the clipboard', (tester) async {
    await _pumpMigration(tester);

    String? copied;
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform,
      (call) async {
        if (call.method == 'Clipboard.setData') {
          copied = (call.arguments as Map)['text'] as String?;
        }
        return null;
      },
    );

    await tester.tap(find.byTooltip('Copy command'));
    await tester.pumpAndSettle();

    expect(copied, _migrationCommand);
    // And it says so, because "did that work" is the next thought on a screen
    // whose whole content is one instruction.
    expect(find.byTooltip('Copied'), findsOneWidget);
  });

  testWidgets('every word of it is legible on the dark stage', (tester) async {
    // This screen is met on an installation where something is already not as
    // expected, and it is the only instruction anybody gets. Under the light
    // theme it used to inherit near-black ink, which on this stage would have
    // been the whole screen gone.
    await _pumpMigration(tester);

    for (final finder in [
      find.text('Your data is not encrypted yet'),
      find.textContaining('one-off migration'),
      find.text('Then start PIP again.'),
    ]) {
      final text = tester.widget<Text>(finder);
      expect(text.style!.color!.computeLuminance(), greaterThan(0.25),
          reason: 'too dark to read on the stage: ${text.data}');
    }
  });
}
