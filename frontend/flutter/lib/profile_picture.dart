// The user's picture, loaded once and shared by everything that draws it.
//
// WHY A HOLDER AND NOT A FETCH PER WIDGET
//
// The avatar appears beside every message the user has sent, which on a long
// transcript is dozens of widgets asking for the same bytes. Fetching per
// widget would be dozens of HTTP round trips for one image, and passing it
// down by constructor would thread a parameter through ChatView, the message
// list, the bubble and the avatar to reach the one place that uses it.
//
// So it is held here and listened to. A ValueNotifier rather than a state
// management package, because the whole of the state is "these bytes, or
// none" and there is exactly one writer.
//
// WHY THE APP DOWNSCALES BEFORE UPLOADING
//
// A picture chosen from a phone camera roll is several megabytes of pixels
// nobody will ever see: it is drawn at 26 logical pixels beside a chat
// message and 72 on the profile screen. Sending it whole would put those
// megabytes inside the encrypted database, decrypt them on every read, and
// decode them on every frame.
//
// Done in Dart with dart:ui rather than by adding an image package: resizing
// on decode is what instantiateImageCodec's targetWidth already does, and this
// project carries one dependency it does not import and documents at length
// why - a second one to scale a square would not survive the same scrutiny.

import 'dart:ui' as ui;

import 'package:flutter/foundation.dart';

import 'api_client.dart';

/// What the stored picture is scaled to before it is uploaded.
///
/// 256 rather than the 72 it is drawn at, so the same file still looks right
/// if the profile screen ever shows it larger, and on a high-DPI display where
/// a logical pixel is two or three real ones.
const int avatarStoredSize = 256;

/// The picture, or null when there is none. Null is a real value here - it is
/// what makes the initials fallback appear, rather than a placeholder image.
final ValueNotifier<Uint8List?> profilePicture = ValueNotifier<Uint8List?>(null);

/// Read the stored picture into [profilePicture].
///
/// A missing picture is not an error and leaves the notifier at null: the
/// backend answers 404 for "none is set", which is a real answer rather than
/// a failure, and every other failure resolves the same way from here - the
/// app draws initials and carries on. Nothing about a chat window should stop
/// working because a decorative image could not be loaded.
Future<void> loadProfilePicture(ApiClient api) async {
  try {
    profilePicture.value = await api.getProfilePicture();
  } catch (_) {
    profilePicture.value = null;
  }
}

/// Scale [original] down to [avatarStoredSize] on its longest side and
/// re-encode as PNG.
///
/// Returns the original bytes unchanged when they cannot be decoded, so the
/// decision about whether something is an image stays with the backend, which
/// checks the actual header. Silently accepting a file here that the server
/// will refuse is better than two places disagreeing about what an image is.
Future<Uint8List> downscaleForAvatar(Uint8List original) async {
  try {
    final codec = await ui.instantiateImageCodec(
      original,
      // Only the width is given: supplying both would stretch a rectangular
      // photo into a square, and the circle it is drawn in crops it anyway.
      targetWidth: avatarStoredSize,
    );
    final frame = await codec.getNextFrame();
    final encoded = await frame.image.toByteData(format: ui.ImageByteFormat.png);
    frame.image.dispose();
    codec.dispose();
    if (encoded == null) return original;
    return encoded.buffer.asUint8List();
  } catch (_) {
    return original;
  }
}

/// The letters to draw when there is no picture.
///
/// One from each of the first two words, so "Anup Magar" is AM and a
/// single-word name is one letter rather than two from the same word - which
/// reads as an abbreviation of something rather than as initials.
String initialsFrom(String? name) {
  final words = (name ?? '').trim().split(RegExp(r'\s+')).where((w) => w.isNotEmpty).toList();
  if (words.isEmpty) return '';
  if (words.length == 1) return words.first.characters.first.toUpperCase();
  return (words[0].characters.first + words[1].characters.first).toUpperCase();
}

extension _FirstCharacter on String {
  Iterable<String> get characters sync* {
    for (final rune in runes) {
      yield String.fromCharCode(rune);
    }
  }
}
