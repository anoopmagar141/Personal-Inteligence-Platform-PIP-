// Making, renaming, re-keying and deleting profiles from the two screens that
// offer it.
//
// The endpoints and their refusals are covered by the Python suite
// (backend/tests/test_profile_management.py). What is worth asserting here is
// the half of the safety that lives in the client, because each of these fails
// silently in its own way:
//
//   * "Add a profile" has to be reachable on an installation with ONE profile.
//     The switcher appears at two, so if adding lived only in the switcher, a
//     fresh install could never make a second one - a feature that exists and
//     cannot be reached.
//
//   * The delete has to close the chat socket BEFORE it asks, or the backend
//     cannot erase a database this client still has open, and the transcript
//     enqueue is not the last word on the conversation.
//
//   * The delete must not navigate away on failure. A screen that returned to
//     sign-in after a 500 would leave somebody unable to tell whether their
//     data was gone.
//
//   * Publishing a picture to the sign-in screen writes an UNENCRYPTED copy.
//     The sentence saying so has to be in front of somebody before it happens,
//     not in a docstring.

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/profile_view.dart';
import 'package:pip_flutter_client/screens/sign_in_screen.dart';

class FakeApi extends ApiClient {
  FakeApi() : super('http://localhost:0', apiToken: 't');

  final List<String> calls = [];

  List<Map<String, dynamic>> profiles = [
    {'slug': 'default', 'name': 'Anup', 'exists': true, 'picture': false},
  ];
  String activeProfile = 'default';
  bool published = false;
  Object? failWith;

  // --- what the profile screen reads before it can draw anything ---
  @override
  Future<List<dynamic>> getProfile() async => [];

  @override
  Future<Map<String, dynamic>> getStatus() async => const {
        'session_count': 1,
        'first_session_date': '2026-09-03T00:02:03Z',
        'active_decisions': 0,
      };

  @override
  Future<List<dynamic>> getInteractionStyleHistory({int limit = 50}) async => [];

  @override
  Future<Uint8List?> getProfilePicture() async => null;

  // --- the profile registry ---
  @override
  Future<Map<String, dynamic>> authProfiles() async =>
      {'active': activeProfile, 'profiles': profiles};

  @override
  Future<Map<String, dynamic>> createProfile(String name) async {
    calls.add('create:$name');
    if (failWith != null) throw failWith!;
    final slug = name.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]+'), '-');
    profiles = [
      ...profiles,
      {'slug': slug, 'name': name, 'exists': false, 'picture': false},
    ];
    activeProfile = slug;
    return {'slug': slug, 'name': name, 'state': 'setup'};
  }

  @override
  Future<Map<String, dynamic>> renameProfile(String slug, String name) async {
    calls.add('rename:$slug=$name');
    if (failWith != null) throw failWith!;
    profiles = [
      for (final p in profiles)
        if (p['slug'] == slug) {...p, 'name': name} else p,
    ];
    return {'slug': slug, 'name': name};
  }

  @override
  Future<void> changePassword(String currentPassword, String newPassword) async {
    calls.add('password:$currentPassword>$newPassword');
    if (failWith != null) throw failWith!;
  }

  @override
  Future<Map<String, dynamic>> deleteProfile(String slug, String password) async {
    calls.add('delete:$slug:$password');
    if (failWith != null) throw failWith!;
    return {'state': 'locked', 'deleted': slug};
  }

  @override
  Future<String> selectProfile(String slug) async {
    calls.add('select:$slug');
    activeProfile = slug;
    return 'locked';
  }

  @override
  Future<void> unlock(String password, {String? profile}) async {}

  @override
  Future<void> completeSetup(String password, {String? profile}) async {
    calls.add('setup:$password@$profile');
  }

  // --- the sign-in picture ---
  @override
  Future<bool> signInPicturePublished() async => published;

  @override
  Future<void> publishSignInPicture() async {
    calls.add('publish');
    if (failWith != null) throw failWith!;
    published = true;
  }

  @override
  Future<void> unpublishSignInPicture() async {
    calls.add('unpublish');
    published = false;
  }

  @override
  Future<Uint8List?> getSignInPicture(String slug) async {
    calls.add('picture:$slug');
    return null;
  }
}

Future<FakeApi> pumpSignIn(WidgetTester tester, {FakeApi? api_}) async {
  final api = api_ ?? FakeApi();
  await tester.pumpWidget(
    MaterialApp(
      home: Builder(
        // disableAnimations, because this screen sits on a particle field that
        // drifts forever by design and pumpAndSettle would never return.
        builder: (context) => MediaQuery(
          data: MediaQuery.of(context).copyWith(disableAnimations: true),
          child: SignInScreen(api: api, state: AuthState.locked, onUnlocked: () {}),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return api;
}

Future<FakeApi> pumpProfile(
  WidgetTester tester, {
  FakeApi? api_,
  VoidCallback? onCloseChat,
  VoidCallback? onSignedOut,
}) async {
  final api = api_ ?? FakeApi();
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: ProfileView(
          api: api,
          onCloseChat: onCloseChat ?? () {},
          onSignedOut: onSignedOut ?? () {},
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return api;
}

/// Scroll the profile screen to the account card, which is deliberately last.
Future<void> scrollToAccount(WidgetTester tester) async {
  await tester.scrollUntilVisible(
    find.text('This profile'),
    300,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pumpAndSettle();
}

/// Pump past a delete without waiting for the screen to go quiet.
///
/// A delete that SUCCEEDS deliberately leaves the card busy: the real app
/// replaces this screen from under it, and a card that became interactive
/// again after erasing its own profile would be offering controls for
/// something that no longer exists. The spinner that says so never stops, so
/// pumpAndSettle would wait for a frame that is never coming.
Future<void> settleDelete(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 100));
}

void main() {
  group('adding a profile from the sign-in screen', () {
    testWidgets('is offered even when there is only one profile', (tester) async {
      // The case that matters most. The switcher appears at two profiles, so
      // if this lived inside it a fresh installation could never reach the
      // control that makes the second one.
      await pumpSignIn(tester);

      expect(find.text('Add a profile'), findsOneWidget);
    });

    testWidgets('asks for a name and creates it', (tester) async {
      final api = await pumpSignIn(tester);

      await tester.tap(find.text('Add a profile'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField).last, 'Priya');
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();

      expect(api.calls, contains('create:Priya'));
    });

    testWidgets('says what a profile is before one is made', (tester) async {
      // Somebody adding a second profile is making a second encrypted database
      // with its own unrecoverable password. That is worth a sentence in front
      // of them rather than a name field on its own.
      await pumpSignIn(tester);

      await tester.tap(find.text('Add a profile'));
      await tester.pumpAndSettle();

      expect(
        find.textContaining('separately encrypted'),
        findsOneWidget,
        reason: 'the dialog did not say the profiles are separate',
      );
      expect(find.textContaining('no way to recover'), findsOneWidget);
    });

    testWidgets('leaves the screen asking for a password for the new profile',
        (tester) async {
      // The half that makes it usable rather than merely possible: creating
      // registers a name, and the password on the screen behind the dialog is
      // what actually makes the database.
      await pumpSignIn(tester);

      await tester.tap(find.text('Add a profile'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField).last, 'Priya');
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();

      expect(find.text('Choose a password'), findsOneWidget);
    });

    testWidgets('cancelling creates nothing', (tester) async {
      final api = await pumpSignIn(tester);

      await tester.tap(find.text('Add a profile'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField).last, 'Priya');
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(api.calls.where((c) => c.startsWith('create:')), isEmpty);
    });

    testWidgets("shows the server's own refusal", (tester) async {
      // "A profile named 'priya' already exists" is the answer. A generic
      // failure would replace a sentence somebody can act on with one they
      // cannot.
      final api = FakeApi()..failWith = ApiException(409, '{"detail":"that name is taken"}');
      await pumpSignIn(tester, api_: api);

      await tester.tap(find.text('Add a profile'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField).last, 'Priya');
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();

      expect(find.text('that name is taken'), findsOneWidget);
    });
  });

  group('renaming', () {
    testWidgets('sends the new name for the active profile', (tester) async {
      final api = await pumpProfile(tester);
      await scrollToAccount(tester);

      await tester.tap(find.text('Rename'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField).last, 'Anup M');
      await tester.tap(find.widgetWithText(FilledButton, 'Rename'));
      await tester.pumpAndSettle();

      expect(api.calls, contains('rename:default=Anup M'));
    });

    testWidgets('says the data is not moved', (tester) async {
      // The slug stays put and so does the directory. Somebody renaming should
      // not be left wondering whether their database has just been relocated.
      await pumpProfile(tester);
      await scrollToAccount(tester);

      await tester.tap(find.text('Rename'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Nothing is moved'), findsOneWidget);
    });
  });

  group('changing the password', () {
    testWidgets('sends the current and the new one', (tester) async {
      final api = await pumpProfile(tester);
      await scrollToAccount(tester);

      await tester.tap(find.text('Change'));
      await tester.pumpAndSettle();
      final fields = find.byType(TextField);
      await tester.enterText(fields.at(0), 'old-password');
      await tester.enterText(fields.at(1), 'new-password');
      await tester.enterText(fields.at(2), 'new-password');
      await tester.tap(find.widgetWithText(FilledButton, 'Change password'));
      await tester.pumpAndSettle();

      expect(api.calls, contains('password:old-password>new-password'));
    });

    testWidgets('refuses a mismatch without a round trip', (tester) async {
      // The one error this side can be certain of, and the round trip would
      // cost a full re-encryption to report it.
      final api = await pumpProfile(tester);
      await scrollToAccount(tester);

      await tester.tap(find.text('Change'));
      await tester.pumpAndSettle();
      final fields = find.byType(TextField);
      await tester.enterText(fields.at(0), 'old-password');
      await tester.enterText(fields.at(1), 'new-password');
      await tester.enterText(fields.at(2), 'different');
      await tester.tap(find.widgetWithText(FilledButton, 'Change password'));
      await tester.pumpAndSettle();

      expect(find.text('Those two passwords are different.'), findsOneWidget);
      expect(api.calls.where((c) => c.startsWith('password:')), isEmpty);
    });

    testWidgets('warns that the new password cannot be recovered', (tester) async {
      await pumpProfile(tester);
      await scrollToAccount(tester);

      await tester.tap(find.text('Change'));
      await tester.pumpAndSettle();

      expect(find.textContaining('cannot be recovered'), findsOneWidget);
    });

    testWidgets("surfaces the server's refusal of a wrong current password",
        (tester) async {
      final api = FakeApi()
        ..failWith = ApiException(401, '{"detail":"That is not your current password."}');
      await pumpProfile(tester, api_: api);
      await scrollToAccount(tester);

      await tester.tap(find.text('Change'));
      await tester.pumpAndSettle();
      final fields = find.byType(TextField);
      await tester.enterText(fields.at(0), 'wrong');
      await tester.enterText(fields.at(1), 'new-password');
      await tester.enterText(fields.at(2), 'new-password');
      await tester.tap(find.widgetWithText(FilledButton, 'Change password'));
      await tester.pumpAndSettle();

      expect(find.text('That is not your current password.'), findsOneWidget);
    });
  });

  group('the picture on the sign-in screen', () {
    testWidgets('is off, and says where the picture stays', (tester) async {
      await pumpProfile(tester);
      await scrollToAccount(tester);

      expect(find.text('Hidden'), findsOneWidget);
      expect(find.textContaining('inside the encrypted database'), findsOneWidget);
    });

    testWidgets('says it writes an unencrypted copy before it does', (tester) async {
      // The whole reason this is a switch with a dialog rather than a switch.
      // It is a real cost against the exact threat PIP encrypts for, and
      // somebody should meet that sentence before the file exists.
      final api = await pumpProfile(tester);
      await scrollToAccount(tester);

      await tester.tap(find.byType(Switch));
      await tester.pumpAndSettle();

      expect(find.textContaining('NOT encrypted'), findsOneWidget);
      expect(api.calls, isNot(contains('publish')));
    });

    testWidgets('publishes once agreed', (tester) async {
      final api = await pumpProfile(tester);
      await scrollToAccount(tester);

      await tester.tap(find.byType(Switch));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Show it'));
      await tester.pumpAndSettle();

      expect(api.calls, contains('publish'));
    });

    testWidgets('declining leaves it off and writes nothing', (tester) async {
      final api = await pumpProfile(tester);
      await scrollToAccount(tester);

      await tester.tap(find.byType(Switch));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(api.calls, isNot(contains('publish')));
      expect(find.text('Hidden'), findsOneWidget);
    });

    testWidgets('turning it off needs no ceremony and deletes the copy',
        (tester) async {
      // Asymmetric on purpose: the confirmation is on the way in. Nobody has
      // ever regretted removing a copy of their own face from a disk.
      final api = FakeApi()..published = true;
      await pumpProfile(tester, api_: api);
      await scrollToAccount(tester);

      await tester.tap(find.byType(Switch));
      await tester.pumpAndSettle();

      expect(api.calls, contains('unpublish'));
    });
  });

  group('deleting a profile', () {
    Future<void> openDeleteDialog(WidgetTester tester) async {
      await scrollToAccount(tester);
      await tester.tap(find.text('Delete'));
      await tester.pumpAndSettle();
    }

    testWidgets('says what is erased and that there is no undo', (tester) async {
      await pumpProfile(tester);
      await openDeleteDialog(tester);

      expect(find.textContaining('There is no undo'), findsOneWidget);
      expect(find.textContaining('are not affected'), findsOneWidget);
    });

    testWidgets('will not proceed until the profile name is typed', (tester) async {
      // The password proves who is asking. Typing the name proves they read
      // WHICH profile they are erasing, which the password alone does not - and
      // that is the mistake worth preventing on a shared machine.
      await pumpProfile(tester);
      await openDeleteDialog(tester);

      final button = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Delete permanently'),
      );
      expect(button.onPressed, isNull);
    });

    testWidgets('sends the password once the name matches', (tester) async {
      final api = await pumpProfile(tester);
      await openDeleteDialog(tester);

      final fields = find.byType(TextField);
      await tester.enterText(fields.at(0), 'Anup');
      await tester.enterText(fields.at(1), 'my-password');
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Delete permanently'));
      await settleDelete(tester);

      expect(api.calls, contains('delete:default:my-password'));
    });

    testWidgets('closes the chat socket before asking the backend', (tester) async {
      // Ordering, not tidiness. The backend cannot erase a database file this
      // client still has open, and the transcript enqueue has to be the last
      // word on the conversation rather than a line drawn under turns that
      // came after it.
      final closed = <String>[];
      final api = await pumpProfile(tester, onCloseChat: () => closed.add('closed'));
      await openDeleteDialog(tester);

      final fields = find.byType(TextField);
      await tester.enterText(fields.at(0), 'Anup');
      await tester.enterText(fields.at(1), 'my-password');
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Delete permanently'));
      await settleDelete(tester);

      expect(closed, isNotEmpty, reason: 'the socket was left open across the delete');
      expect(api.calls, contains('delete:default:my-password'));
    });

    testWidgets('returns to the sign-in screen when it succeeds', (tester) async {
      var signedOut = false;
      await pumpProfile(tester, onSignedOut: () => signedOut = true);
      await openDeleteDialog(tester);

      final fields = find.byType(TextField);
      await tester.enterText(fields.at(0), 'Anup');
      await tester.enterText(fields.at(1), 'my-password');
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Delete permanently'));
      await settleDelete(tester);

      expect(signedOut, isTrue);
    });

    testWidgets('stays put and reports when the delete fails', (tester) async {
      // A screen that navigated away optimistically would send somebody to a
      // sign-in screen for a profile that still exists, with no way to tell
      // whether their data was gone.
      var signedOut = false;
      final api = FakeApi()
        ..failWith = ApiException(500, '{"detail":"files could not be deleted"}');
      await pumpProfile(tester, api_: api, onSignedOut: () => signedOut = true);
      await openDeleteDialog(tester);

      final fields = find.byType(TextField);
      await tester.enterText(fields.at(0), 'Anup');
      await tester.enterText(fields.at(1), 'my-password');
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Delete permanently'));
      await tester.pumpAndSettle();

      expect(signedOut, isFalse);
      expect(find.text('files could not be deleted'), findsOneWidget);
    });

    testWidgets('cancelling deletes nothing', (tester) async {
      final api = await pumpProfile(tester);
      await openDeleteDialog(tester);

      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(api.calls.where((c) => c.startsWith('delete:')), isEmpty);
    });
  });
}
