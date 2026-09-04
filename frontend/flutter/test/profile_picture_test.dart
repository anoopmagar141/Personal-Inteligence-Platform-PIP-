// The profile picture on the client side.
//
// Three things are worth protecting here, and none of them is "an image
// renders". A failure to load the picture must not stop the app - it is
// decoration in front of a chat window. The initials fallback has to be
// initials rather than the first two letters of one word. And the avatar has
// to follow the notifier, because the alternative that was rejected was
// threading the bytes through three widgets that have no use for them.

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/profile_picture.dart';

class FakeApi extends ApiClient {
  Uint8List? stored;
  Object? throwThis;
  int fetches = 0;

  FakeApi() : super('http://localhost:0', apiToken: 't');

  @override
  Future<Uint8List?> getProfilePicture() async {
    fetches++;
    if (throwThis != null) throw throwThis!;
    return stored;
  }
}

/// Four bytes that are not a decodable image, which is all these tests need -
/// what happens to real pixels is Flutter's business, not this file's.
Uint8List someBytes() => Uint8List.fromList([1, 2, 3, 4]);

void main() {
  setUp(() => profilePicture.value = null);
  tearDown(() => profilePicture.value = null);

  group('initialsFrom', () {
    test('takes one letter from each of the first two words', () {
      expect(initialsFrom('Anup Magar'), 'AM');
      expect(initialsFrom('ada lovelace king'), 'AL');
    });

    test('a single word gives one letter, not two from the same word', () {
      // "BA" for "BatMan" would read as an abbreviation of the word rather
      // than as initials.
      expect(initialsFrom('BatMan'), 'B');
    });

    test('nothing to work with gives nothing', () {
      expect(initialsFrom(null), '');
      expect(initialsFrom(''), '');
      expect(initialsFrom('    '), '');
    });

    test('extra spacing does not become an empty initial', () {
      expect(initialsFrom('  Anup   Magar  '), 'AM');
    });
  });

  group('loading', () {
    test('a stored picture reaches the notifier', () async {
      final api = FakeApi()..stored = someBytes();

      await loadProfilePicture(api);

      expect(profilePicture.value, someBytes());
    });

    test('no picture leaves it null rather than raising', () async {
      // The backend answers 404 for "none is set", which the client turns into
      // null - a real answer, and what makes the initials appear.
      final api = FakeApi()..stored = null;

      await loadProfilePicture(api);

      expect(profilePicture.value, isNull);
    });

    test('a failure is swallowed, because the app must still open', () async {
      // Nothing about a chat window should stop working because a decorative
      // image could not be loaded.
      final api = FakeApi()..throwThis = Exception('backend on fire');

      await loadProfilePicture(api);

      expect(profilePicture.value, isNull);
    });

    test('replacing a picture with a failure clears the old one', () async {
      profilePicture.value = someBytes();
      final api = FakeApi()..throwThis = Exception('gone');

      await loadProfilePicture(api);

      // Keeping the previous bytes would show somebody a picture they had
      // just deleted.
      expect(profilePicture.value, isNull);
    });
  });

  group('downscaleForAvatar', () {
    test('undecodable bytes come back unchanged', () async {
      // The decision about what counts as an image belongs to the backend,
      // which reads the actual header. Two places disagreeing about it is
      // worse than one refusal.
      final original = someBytes();

      expect(await downscaleForAvatar(original), original);
    });
  });

  group('the notifier', () {
    testWidgets('a widget listening to it follows a change', (tester) async {
      // The property that makes one holder work for the dozens of avatars on a
      // long transcript.
      await tester.pumpWidget(
        MaterialApp(
          home: ValueListenableBuilder<Uint8List?>(
            valueListenable: profilePicture,
            builder: (context, picture, _) =>
                Text(picture == null ? 'initials' : 'picture'),
          ),
        ),
      );

      expect(find.text('initials'), findsOneWidget);

      profilePicture.value = someBytes();
      await tester.pump();

      expect(find.text('picture'), findsOneWidget);
    });
  });
}
