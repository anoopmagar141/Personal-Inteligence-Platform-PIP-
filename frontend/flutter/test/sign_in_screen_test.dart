// The sign-in screen, which is now the first thing anybody sees.
//
// What is worth asserting here is not that a button submits. It is the things
// that would be quietly wrong in a way nobody notices until it matters: that
// an unfamiliar state falls back to asking for a password rather than skipping
// one, that the server's own sentence reaches the person who typed the
// password, that the screen says out loud that nothing can be recovered -
// because the whole design depends on somebody having been told - and, since
// the profile menu moved here out of the PowerShell launcher, that switching
// profile redresses the screen for the profile switched TO rather than leaving
// one profile's words under another profile's name.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/sign_in_screen.dart';
import 'package:pip_flutter_client/theme.dart';

class FakeApi extends ApiClient {
  final List<String> unlocked = [];
  final List<String> created = [];
  final List<String?> unlockedProfiles = [];
  final List<String> selected = [];
  Object? throwThis;

  /// What /auth/profiles answers. Empty by default, which is the shape of an
  /// installation that has never made a second profile - and therefore the
  /// shape every test that is not about the switcher should be running under.
  List<Map<String, dynamic>> profiles = const [];
  String activeProfile = 'default';

  /// What /auth/profile answers for each slug.
  Map<String, String> stateAfterSwitch = const {};

  FakeApi() : super('http://localhost:0', apiToken: 't');

  @override
  Future<void> unlock(String password, {String? profile}) async {
    if (throwThis != null) throw throwThis!;
    unlocked.add(password);
    unlockedProfiles.add(profile);
  }

  @override
  Future<void> completeSetup(String password, {String? profile}) async {
    if (throwThis != null) throw throwThis!;
    created.add(password);
    unlockedProfiles.add(profile);
  }

  @override
  Future<Map<String, dynamic>> authProfiles() async =>
      {'active': activeProfile, 'profiles': profiles};

  @override
  Future<String> selectProfile(String slug) async {
    selected.add(slug);
    activeProfile = slug;
    return stateAfterSwitch[slug] ?? 'locked';
  }
}

/// Two profiles, one opened before and one only registered.
///
/// The second having no database is the case worth carrying in the default
/// fixture: it is what makes the switcher change the screen's words rather
/// than only its label, and it is the state scripts/new_profile.py leaves
/// behind for a first sign-in to resolve.
List<Map<String, dynamic>> get _twoProfiles => [
      {'slug': 'default', 'name': 'Default', 'exists': true},
      {'slug': 'jenisha', 'name': 'Jenisha', 'exists': false},
    ];

Future<FakeApi> pumpSignIn(
  WidgetTester tester,
  AuthState state, {
  VoidCallback? onUnlocked,
  Object? throwThis,
  FakeApi? api_,
}) async {
  final api = (api_ ?? FakeApi())..throwThis = throwThis;
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

  group('choosing which profile to sign in as', () {
    // This was a numbered menu printed by scripts/_profiles.ps1 before the
    // application window existed. The point of moving it is that the choice
    // and the password are now one screen, so what these assert is that the
    // screen stays consistent with itself while the choice changes.

    testWidgets('is not drawn at all on a single-profile installation',
        (tester) async {
      // Most installations. A control offering one choice is not a choice, and
      // this screen has to remain exactly what it was before profiles existed.
      final api = FakeApi()
        ..profiles = [
          {'slug': 'default', 'name': 'Default', 'exists': true},
        ];
      await pumpSignIn(tester, AuthState.locked, api_: api);

      expect(find.text('Switch'), findsNothing);
    });

    testWidgets('names the profile being signed in as', (tester) async {
      final api = FakeApi()..profiles = _twoProfiles;
      await pumpSignIn(tester, AuthState.locked, api_: api);

      expect(find.text('Default'), findsOneWidget);
      expect(find.text('Switch'), findsOneWidget);
    });

    testWidgets('switching redresses the screen for the profile switched to',
        (tester) async {
      // The assertion the whole feature turns on. A profile with no database
      // behind it is a "choose a password" screen even though the one before
      // it was not, and a screen that kept the old heading would be asking
      // for a password that cannot exist yet.
      final api = FakeApi()
        ..profiles = _twoProfiles
        ..stateAfterSwitch = {'jenisha': 'setup'};
      await pumpSignIn(tester, AuthState.locked, api_: api);

      await tester.tap(find.text('Switch'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Jenisha').last);
      await tester.pumpAndSettle();

      expect(api.selected, ['jenisha']);
      expect(find.text('Choose a password'), findsOneWidget);
      expect(find.byType(TextField), findsNWidgets(2));
    });

    testWidgets('sends the password with the profile it was typed for',
        (tester) async {
      // Two profiles are two databases under two keys. A password that arrived
      // without saying which profile it was meant for could be checked against
      // whichever one the server happened to be pointed at.
      final api = FakeApi()..profiles = _twoProfiles;
      await pumpSignIn(tester, AuthState.locked, api_: api);

      await tester.enterText(find.byType(TextField), 'correct-horse');
      await tester.tap(find.text('Unlock'));
      await tester.pumpAndSettle();

      expect(api.unlocked, ['correct-horse']);
      expect(api.unlockedProfiles, ['default']);
    });

    testWidgets('clears a password typed for the profile left behind',
        (tester) async {
      // Not tidiness. Two profiles have two passwords by construction, so a
      // password typed for one is never the right answer for the other -
      // leaving it in the field invites somebody to submit it and be told it
      // did not open their data.
      final api = FakeApi()..profiles = _twoProfiles;
      await pumpSignIn(tester, AuthState.locked, api_: api);

      await tester.enterText(find.byType(TextField), 'the-other-password');
      await tester.tap(find.text('Switch'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Jenisha').last);
      await tester.pumpAndSettle();

      expect(tester.widget<TextField>(find.byType(TextField).first).controller!.text, '');
    });

    testWidgets('a registry that cannot be read costs nothing', (tester) async {
      // This screen's job is to take a password, and it can do that against
      // whichever profile the backend is already pointed at. An error banner
      // about a list most installations do not even have would be noise in
      // front of the one thing somebody came here to do.
      final api = _ProfilesRefused();
      await pumpSignIn(tester, AuthState.locked, api_: api);

      expect(find.text('Welcome back'), findsOneWidget);
      expect(find.text('Switch'), findsNothing);

      await tester.enterText(find.byType(TextField), 'correct-horse');
      await tester.tap(find.text('Unlock'));
      await tester.pumpAndSettle();

      expect(api.unlocked, ['correct-horse']);
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

    testWidgets('still lets another profile be reached', (tester) async {
      // A legacy plaintext database in one profile is no reason to be stuck on
      // the screen about it while another profile on the same machine opens
      // perfectly well - and this screen's whole instruction is "run a script
      // and come back", which is a long time to be locked out of your own data.
      final api = FakeApi()..profiles = _twoProfiles;
      await pumpSignIn(tester, AuthState.needsMigration, api_: api);

      expect(find.text('Switch'), findsOneWidget);
    });
  });
}

/// An installation whose profile registry cannot be read.
class _ProfilesRefused extends FakeApi {
  @override
  Future<Map<String, dynamic>> authProfiles() async =>
      throw Exception('500 {"detail":"profiles.json is unreadable"}');
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
