// The client's password minimum is the server's, not a second opinion.
//
// The backend is the authority: session_key.set_password, change_password
// and restore all refuse a password under eight characters. The client checks
// the same rule first only to save the round trip - a quarter-second of key
// derivation at sign-in, a full re-encryption on a password change - so the
// two must never disagree. A client minimum lower than the server's means the
// early check is decoration; a higher one means refusing passwords the server
// would accept.
//
// The backend writes the rule as literal `len(x) < 8` comparisons. This test
// finds every one in the files that enforce it and holds kMinPasswordLength to
// them, so changing either side alone fails here.

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';

void main() {
  test('kMinPasswordLength matches every minimum the backend enforces', () {
    final sources = ['../../backend/core/session_key.py', '../../backend/core/restore.py'];
    final minimums = <String, int>{};
    for (final path in sources) {
      final text = File(path).readAsStringSync();
      for (final match in RegExp(r'len\((\w*password\w*)\) < (\d+)').allMatches(text)) {
        minimums['$path ${match.group(1)}'] = int.parse(match.group(2)!);
      }
    }

    // Two in session_key (set and change), one in restore. Fewer means the
    // pattern stopped matching, and an empty map would pass vacuously.
    expect(minimums.length, greaterThanOrEqualTo(3), reason: 'found only $minimums');
    minimums.forEach((where, minimum) {
      expect(kMinPasswordLength, minimum, reason: '$where enforces $minimum');
    });
  });
}
