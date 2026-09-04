// The sign-in screen, which is now the first thing anybody sees.
//
// What is worth asserting here is not that a button submits. It is the three
// things that would be quietly wrong in a way nobody notices until it matters:
// that an unfamiliar state falls back to asking for a password rather than
// skipping one, that the server's own sentence reaches the person who typed
// the password, and that the screen says out loud that nothing can be
// recovered - because the whole design depends on somebody having been told.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/sign_in_screen.dart';

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
  await tester.pumpWidget(
    MaterialApp(
      home: SignInScreen(
        api: api,
        state: state,
        onUnlocked: onUnlocked ?? () {},
      ),
    ),
  );
  await tester.pumpAndSettle();
  return api;
}

void main() {
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
