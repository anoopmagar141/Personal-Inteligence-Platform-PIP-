// Behaviour tests for the Profile screen, now that it can write.
//
// The interesting cases are about NOT offering an action the backend cannot
// honour, because each failure mode is silent in a different way:
//
//   * identity rows are refused server-side, so an edit button on one would
//     always fail;
//   * set-membership rows (topic_interests, preferred_tools,
//     document_access_patterns) have no separate value to edit into - the
//     field IS the value - so there is nothing an in-place correction could
//     mean, and the backend says so.
//
// Skills used to be in that second group for a worse reason: correcting one
// was not refused at all, because correct_profile_field() wrote to
// preference_memory unconditionally. The edit appeared to succeed while
// filing a new preference of the same name and leaving the skill exactly as
// wrong as it was - the only failure here that no error message would ever
// reveal. The backend now routes by table, so skills and goals are editable
// and the tests below pin that instead.
//
// The endpoints themselves are covered by the Python suite.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/profile_view.dart';

class FakeApi extends ApiClient {
  FakeApi() : super('http://127.0.0.1:8765/api/v1');

  List<dynamic> fields = [];
  List<dynamic> styleHistory = [];
  final List<String> calls = [];
  Object? correctError;
  String deleteStatus = 'deleted';

  /// What /status answers. Null makes it throw, which is the case the card
  /// has to survive without losing the profile behind it.
  Map<String, dynamic>? status = const {
    'session_count': 12,
    'first_session_date': '2026-09-03T00:02:03Z',
    'active_decisions': 3,
  };

  @override
  Future<List<dynamic>> getProfile() async => fields;

  @override
  Future<Map<String, dynamic>> getStatus() async {
    calls.add('status');
    if (status == null) throw Exception('500 status unavailable');
    return status!;
  }

  @override
  Future<List<dynamic>> getInteractionStyleHistory({int limit = 50}) async {
    calls.add('style-history');
    return styleHistory;
  }

  @override
  Future<void> correctMemory(String field, String value) async {
    calls.add('correct:$field=$value');
    if (correctError != null) throw correctError!;
  }

  @override
  Future<Map<String, dynamic>> deleteProfileField(String field) async {
    calls.add('delete:$field');
    return {'status': deleteStatus, 'field': field};
  }
}

Map<String, dynamic> row(
  String table,
  String field,
  String value, {
  double? confidence = 0.8,
  String source = 'inferred',
}) =>
    {
      'table': table,
      'field': field,
      'value': value,
      'confidence': confidence,
      'source_label': source,
    };

Future<FakeApi> pumpProfile(WidgetTester tester, List<dynamic> fields) async {
  final api = FakeApi()..fields = fields;
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: ProfileView(api: api, onCloseChat: () {}, onSignedOut: () {}),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return api;
}

void main() {
  group('profileRowCapability', () {
    test('offers correction on identity, but deletion on one field only', () {
      // Asserted the opposite until identity became correctable. name,
      // language_preference and timezone are NOT NULL and are what PIP
      // addresses you by, so a correction has a meaning there and a retraction
      // does not.
      for (final field in ['name', 'language_preference', 'timezone']) {
        final capability = profileRowCapability('identity', field: field);
        expect(capability.canEdit, isTrue, reason: '$field should be correctable');
        expect(capability.canDelete, isFalse, reason: '$field should not be deletable');
        expect(capability.note, isNull);
      }

      // preferred_name is the exception, and the reason is in
      // soft_delete_profile_field(): it is the one identity column that is
      // optional to begin with, so removing it means "go back to calling me by
      // my name" rather than "I have no name". The backend gives it its own
      // branch; offering no button for a delete the backend implements leaves
      // the only way to undo a calling name being to set it to something else.
      expect(profileRowCapability('identity', field: 'preferred_name').canDelete, isTrue);
    });

    test('offers both on the tables the correction endpoint can route to', () {
      for (final table in ['preference_memory', 'skill_memory', 'goal_memory']) {
        expect(profileRowCapability(table).canEdit, isTrue, reason: '$table should be editable');
        expect(profileRowCapability(table).canDelete, isTrue, reason: '$table should be deletable');
      }
    });

    test('does not offer to correct a set-membership row', () {
      // The field is the value in these tables, so there is nothing to edit
      // into. _write_profile_value() raises for them rather than inventing an
      // update, and the UI should not ask in the first place.
      for (final table in ['topic_interests', 'preferred_tools', 'document_access_patterns']) {
        expect(profileRowCapability(table).canEdit, isFalse, reason: '$table should not be editable');
        expect(profileRowCapability(table).canDelete, isTrue, reason: '$table should be deletable');
      }
    });

    test('offers history only on the one row that has any', () {
      // interaction_style_history is the profile's only audit trail.
      expect(profileRowCapability('interaction_style').hasHistory, isTrue);
      expect(profileRowCapability('preference_memory').hasHistory, isFalse);
      expect(profileRowCapability('identity').hasHistory, isFalse);
    });

    test('offers edit but not delete on interaction_style', () {
      // set_interaction_style() handles the correction; soft_delete's loop
      // does not touch the interaction_style table at all.
      expect(profileRowCapability('interaction_style').canEdit, isTrue);
      expect(profileRowCapability('interaction_style').canDelete, isFalse);
    });

    test('offers nothing on a table it does not recognise', () {
      expect(profileRowCapability('some_future_table').canEdit, isFalse);
      expect(profileRowCapability('some_future_table').canDelete, isFalse);
    });
  });

  group('presentation', () {
    test('a goal shows its text, not its synthetic handle', () {
      // goal_memory's key is the "goal:<id>" handle get_profile() invents so
      // the UI has something stable to send back. It is addressing, not
      // content - and heading the row with it buried nine real goals behind
      // "goal:1".."goal:9".
      final content = profileRowContent(
        row('goal_memory', 'goal:1', 'Thesis objective: demonstrate a working governance layer'),
      );
      expect(content.title, startsWith('Thesis objective'));
      expect(content.detail, isNull);
    });

    test('a set-membership row says its word once', () {
      // field == value for these tables, which is how "data privacy / data
      // privacy" ended up on screen twice.
      final content = profileRowContent(row('topic_interests', 'data privacy', 'data privacy'));
      expect(content.title, 'data privacy');
      expect(content.detail, isNull);
    });

    test('an ordinary field is humanised with its value beneath', () {
      final content = profileRowContent(row('preference_memory', 'answer_style', 'adaptive'));
      expect(content.title, 'Answer style');
      expect(content.detail, 'adaptive');
    });

    test('labels are capitalised consistently, paths are left alone', () {
      // "Language preference" next to a lowercase "name" and "timezone" is the
      // inconsistency this fixes - it was only capitalising when there was an
      // underscore to replace.
      expect(humaniseFieldName('language_preference'), 'Language preference');
      expect(humaniseFieldName('name'), 'Name');
      expect(humaniseFieldName('timezone'), 'Timezone');
      // Already capital, so the same rule is a no-op rather than a special case.
      expect(humaniseFieldName('Python'), 'Python');
      // User text, not an identifier: a document path stays byte-for-byte.
      expect(humaniseFieldName('D:/notes/thesis.md'), 'D:/notes/thesis.md');
    });

    testWidgets('groups rows under headings a person would recognise', (tester) async {
      await pumpProfile(tester, [
        row('identity', 'name', 'BatMan', confidence: 1.0, source: 'explicit'),
        row('goal_memory', 'goal:1', 'Finish chapter 4'),
        row('topic_interests', 'rust', 'rust'),
      ]);

      expect(find.text('Goals'), findsOneWidget);
      expect(find.text('Topics you keep returning to'), findsOneWidget);
      // The raw table name is no longer a label on every single row.
      expect(find.text('goal_memory'), findsNothing);
      expect(find.text('topic_interests'), findsNothing);
    });

    testWidgets('identity is the card, not a section in the learned list',
        (tester) async {
      // The split this screen now makes: a name is something you stated and
      // PIP is merely storing, a topic interest is something PIP inferred and
      // may have got wrong. Only the second kind belongs under a heading that
      // says PIP learned it.
      await pumpProfile(tester, [
        row('identity', 'name', 'BatMan', confidence: 1.0, source: 'explicit'),
        row('topic_interests', 'rust', 'rust'),
      ]);

      expect(find.text('BatMan'), findsOneWidget);
      expect(find.text('You'), findsNothing);
      // And never leaks through as its own raw-table section either.
      expect(find.text('identity'), findsNothing);
      expect(find.text('What PIP has learned'), findsOneWidget);
    });

    testWidgets('an onboarded profile with nothing inferred says so plainly',
        (tester) async {
      // Not an error and not a gap to apologise for: an installation that has
      // only been onboarded has stated facts and inferred none.
      await pumpProfile(tester, [
        row('identity', 'name', 'BatMan', confidence: 1.0, source: 'explicit'),
      ]);

      expect(find.textContaining('has not learned anything yet'), findsOneWidget);
      expect(find.text('BatMan'), findsOneWidget);
    });

    testWidgets('a table this build has never heard of still gets a section', (tester) async {
      // A profile screen that silently omits part of the profile is the one
      // thing it must never be.
      await pumpProfile(tester, [row('brand_new_table', 'thing', 'value')]);

      expect(find.text('brand_new_table'), findsOneWidget);
      expect(find.text('value'), findsOneWidget);
    });
  });

  testWidgets('a skill can be corrected, and says what a level is', (tester) async {
    final api = await pumpProfile(tester, [row('skill_memory', 'Python', '0.7')]);

    expect(find.text('Forget'), findsOneWidget);
    await tester.tap(find.text('Correct'));
    await tester.pumpAndSettle();

    // skill_memory.level is a REAL. Someone typing "expert" would be refused
    // by the backend, so the dialog says what is wanted before they try.
    expect(find.textContaining('number from 0 to 1'), findsOneWidget);

    await tester.enterText(find.byType(TextField), '0.9');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    expect(api.calls, contains('correct:Python=0.9'));
  });

  testWidgets('a topic interest can only be forgotten', (tester) async {
    await pumpProfile(tester, [row('topic_interests', 'rust', 'rust')]);

    expect(find.text('Forget'), findsOneWidget);
    expect(find.text('Correct'), findsNothing);
  });

  testWidgets('the interaction style offers its history', (tester) async {
    await pumpProfile(tester, [row('interaction_style', 'interaction_style', 'terse')]);

    expect(find.text('History'), findsOneWidget);
  });

  testWidgets('the style history reads the backend, newest first', (tester) async {
    final api = await pumpProfile(tester, [row('interaction_style', 'interaction_style', 'detailed')]);
    api.styleHistory = [
      {'value': 'detailed', 'changed_at': '2026-08-30T10:00:00Z'},
      {'value': 'terse', 'changed_at': '2026-07-01T10:00:00Z'},
    ];

    await tester.tap(find.text('History'));
    await tester.pumpAndSettle();

    expect(api.calls, contains('style-history'));
    expect(find.text('terse'), findsOneWidget);
    expect(find.text('2026-07-01T10:00:00Z'), findsOneWidget);
  });

  testWidgets('an unchanged style says so rather than showing an empty list', (tester) async {
    // interaction_style_history only gains a row when the value CHANGES, so a
    // style set once at onboarding genuinely has nothing to show. That is not
    // an error and must not read like one.
    await pumpProfile(tester, [row('interaction_style', 'interaction_style', 'terse')]);

    await tester.tap(find.text('History'));
    await tester.pumpAndSettle();

    expect(find.textContaining('No changes recorded'), findsOneWidget);
  });

  testWidgets('correcting a preference sends the new value to the backend', (tester) async {
    final api = await pumpProfile(tester, [row('preference_memory', 'answer_depth', 'verbose')]);

    await tester.tap(find.text('Correct'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'brief');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    expect(api.calls, contains('correct:answer_depth=brief'));
  });

  testWidgets('forgetting a field asks first, then calls the backend', (tester) async {
    final api = await pumpProfile(tester, [row('preference_memory', 'editor', 'vim')]);

    await tester.tap(find.text('Forget'));
    await tester.pumpAndSettle();
    expect(find.text('Forget this?'), findsOneWidget);
    // The wording has to be honest about ADR-022: this is a retraction, and
    // the row survives it.
    expect(find.textContaining('kept and marked'), findsOneWidget);

    await tester.tap(find.text('Forget it'));
    await tester.pumpAndSettle();

    expect(api.calls, contains('delete:editor'));
  });

  testWidgets('cancelling the confirmation writes nothing', (tester) async {
    final api = await pumpProfile(tester, [row('preference_memory', 'editor', 'vim')]);

    await tester.tap(find.text('Forget'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    // No WRITE. The list is no longer the only thing this screen loads - the
    // card reads /status for its counts - so "called nothing at all" stopped
    // being the same statement as "changed nothing".
    expect(api.calls.where((c) => c.startsWith('delete:')), isEmpty);
    expect(api.calls.where((c) => c.startsWith('correct:')), isEmpty);
  });

  testWidgets("a refusal shows the server's sentence on the row it came from", (tester) async {
    final api = await pumpProfile(tester, [row('preference_memory', 'answer_depth', 'verbose')]);
    api.correctError = ApiException(
      422,
      '{"detail": "immutable identity fields cannot be edited after onboarding"}',
    );

    await tester.tap(find.text('Correct'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'brief');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    expect(find.textContaining('immutable identity fields'), findsOneWidget);
  });

  testWidgets('a delete the backend could not match is reported, not swallowed', (tester) async {
    // Reloading an unchanged table would look exactly like a button that did
    // nothing, which is the one outcome the user cannot act on.
    final api = await pumpProfile(tester, [row('topic_interests', 'rust', 'rust')]);
    api.deleteStatus = 'not_found';

    await tester.tap(find.text('Forget'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Forget it'));
    await tester.pumpAndSettle();

    expect(find.textContaining('no active record'), findsOneWidget);
  });


  // --- the profile card ------------------------------------------------------
  //
  // Identity used to be four rows in the learned list, each with its own
  // Correct button, each under a confidence meter that always read 1.00. They
  // are not inferred, so there is nothing to be confident about and nothing to
  // retract - and changing a name and the timezone it is greeted in was two
  // dialogs and two round trips.
  //
  // What is asserted here is mostly restraint: that only what CHANGED is sent
  // (every write stamps source_label as an explicit statement, so re-asserting
  // an untouched field is a lie about what the person did), that clearing the
  // one optional column deletes rather than writing an empty string, and that
  // the counts are absent rather than invented when /status cannot be read.

  List<dynamic> fullIdentity() => [
        row('identity', 'name', 'Anup Magar', confidence: 1.0, source: 'explicit'),
        row('identity', 'preferred_name', 'Anup', confidence: 1.0, source: 'explicit'),
        row('identity', 'language_preference', 'English', confidence: 1.0, source: 'explicit'),
        row('identity', 'timezone', 'Asia/Kathmandu', confidence: 1.0, source: 'explicit'),
      ];

  testWidgets('the card reads as a person, not as four rows', (tester) async {
    await pumpProfile(tester, fullIdentity());

    expect(find.text('Anup Magar'), findsOneWidget);
    expect(find.text('English'), findsOneWidget);
    expect(find.text('Asia/Kathmandu'), findsOneWidget);
    // The calling name gets its own line because it is the one fact here that
    // changes what PIP says out loud.
    expect(find.text('PIP calls you Anup'), findsOneWidget);
    expect(find.text('Edit'), findsOneWidget);
  });

  testWidgets('says nothing about a calling name when there is none', (tester) async {
    // "PIP calls you Anup Magar" under the heading "Anup Magar" states the
    // default twice.
    await pumpProfile(tester, [
      row('identity', 'name', 'Anup Magar', confidence: 1.0, source: 'explicit'),
    ]);

    expect(find.textContaining('PIP calls you'), findsNothing);
  });

  testWidgets('shows the counts the backend can actually answer for', (tester) async {
    await pumpProfile(tester, [
      ...fullIdentity(),
      row('preference_memory', 'answer_depth', 'verbose'),
    ]);

    expect(find.text('12'), findsOneWidget); // sessions
    expect(find.text('3'), findsOneWidget); // active decisions
    expect(find.text('3 Sep 2026'), findsOneWidget); // first session
    expect(find.text('Things learned'), findsOneWidget);
  });

  testWidgets('a status that will not load costs the counts, not the profile',
      (tester) async {
    // The counts are the least important thing on this screen and the profile
    // is the most.
    final api = FakeApi()
      ..fields = fullIdentity()
      ..status = null;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: ProfileView(api: api, onCloseChat: () {}, onSignedOut: () {}),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Anup Magar'), findsOneWidget);
    expect(find.text('Sessions'), findsOneWidget);
  });

  testWidgets('editing sends only the fields that changed', (tester) async {
    // Not an optimisation. Every write here stamps source_label as an explicit
    // correction, so re-sending an untouched timezone re-asserts it as a fresh
    // statement about a field the person did not look at.
    final api = await pumpProfile(tester, fullIdentity());

    await tester.tap(find.text('Edit'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Anup Magar'), 'Anup Bahadur Magar');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    expect(api.calls, contains('correct:name=Anup Bahadur Magar'));
    expect(api.calls.where((c) => c.startsWith('correct:timezone')), isEmpty);
    expect(api.calls.where((c) => c.startsWith('correct:language_preference')), isEmpty);
  });

  testWidgets('all four fields are editable in one dialog', (tester) async {
    final api = await pumpProfile(tester, fullIdentity());

    await tester.tap(find.text('Edit'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'English'), 'Nepali');
    await tester.enterText(find.widgetWithText(TextField, 'Asia/Kathmandu'), 'UTC');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    expect(api.calls, contains('correct:language_preference=Nepali'));
    expect(api.calls, contains('correct:timezone=UTC'));
  });

  testWidgets('clearing a calling name deletes it rather than storing nothing',
      (tester) async {
    // "No calling name" has to stay ONE state. An empty string in the column
    // would be a second one that every "IS NULL" test disagrees with.
    final api = await pumpProfile(tester, fullIdentity());

    await tester.tap(find.text('Edit'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Anup'), '');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    expect(api.calls, contains('delete:preferred_name'));
    expect(api.calls.where((c) => c.startsWith('correct:preferred_name')), isEmpty);
  });

  testWidgets('leaving a blank calling name blank is not a delete', (tester) async {
    // The row does not exist, so a delete would be a call the backend can only
    // answer not_found to.
    final api = await pumpProfile(tester, [
      row('identity', 'name', 'Anup Magar', confidence: 1.0, source: 'explicit'),
      row('identity', 'language_preference', 'English', confidence: 1.0, source: 'explicit'),
      row('identity', 'timezone', 'UTC', confidence: 1.0, source: 'explicit'),
    ]);

    await tester.tap(find.text('Edit'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    expect(api.calls.where((c) => c.contains('preferred_name')), isEmpty);
  });

  testWidgets('setting a calling name for the first time is an ordinary correction',
      (tester) async {
    // correct_profile_field() routes an unset identity field to the identity
    // table precisely so this works - without that branch the first attempt
    // would file a PREFERENCE called preferred_name and leave the column NULL.
    final api = await pumpProfile(tester, [
      row('identity', 'name', 'Anup Magar', confidence: 1.0, source: 'explicit'),
      row('identity', 'language_preference', 'English', confidence: 1.0, source: 'explicit'),
      row('identity', 'timezone', 'UTC', confidence: 1.0, source: 'explicit'),
    ]);

    await tester.tap(find.text('Edit'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, ''), 'Anup');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    expect(api.calls, contains('correct:preferred_name=Anup'));
  });

  testWidgets('an emptied required field is refused before the round trip',
      (tester) async {
    // The backend does refuse it, and being told after a round trip is worse
    // than being told by the field that is empty.
    final api = await pumpProfile(tester, fullIdentity());

    await tester.tap(find.text('Edit'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Anup Magar'), '');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    expect(find.textContaining('cannot be empty'), findsOneWidget);
    expect(api.calls.where((c) => c.startsWith('correct:')), isEmpty);
  });

  testWidgets("a refused edit shows the server's sentence on the card", (tester) async {
    final api = await pumpProfile(tester, fullIdentity());
    api.correctError = ApiException(422, '{"detail": "Your timezone cannot be empty."}');

    await tester.tap(find.text('Edit'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Asia/Kathmandu'), 'Mars/Olympus');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Your timezone cannot be empty'), findsOneWidget);
  });

  testWidgets('cancelling the edit writes nothing', (tester) async {
    final api = await pumpProfile(tester, fullIdentity());

    await tester.tap(find.text('Edit'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Anup Magar'), 'Someone Else');
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(api.calls.where((c) => c.startsWith('correct:')), isEmpty);
  });
}
