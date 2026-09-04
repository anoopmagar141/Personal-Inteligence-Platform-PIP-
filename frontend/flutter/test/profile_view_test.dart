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

  @override
  Future<List<dynamic>> getProfile() async => fields;

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
    MaterialApp(home: Scaffold(body: ProfileView(api: api))),
  );
  await tester.pumpAndSettle();
  return api;
}

void main() {
  group('profileRowCapability', () {
    test('offers correction on identity, but never deletion', () {
      // Asserted the opposite until identity became correctable. The columns
      // are NOT NULL and are what PIP addresses you by, so a correction has a
      // meaning here and a retraction does not.
      final capability = profileRowCapability('identity');
      expect(capability.canEdit, isTrue);
      expect(capability.canDelete, isFalse);
      expect(capability.note, isNull);
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

      expect(find.text('You'), findsOneWidget);
      expect(find.text('Goals'), findsOneWidget);
      expect(find.text('Topics you keep returning to'), findsOneWidget);
      // The raw table name is no longer a label on every single row.
      expect(find.text('goal_memory'), findsNothing);
      expect(find.text('topic_interests'), findsNothing);
    });

    testWidgets('a table this build has never heard of still gets a section', (tester) async {
      // A profile screen that silently omits part of the profile is the one
      // thing it must never be.
      await pumpProfile(tester, [row('brand_new_table', 'thing', 'value')]);

      expect(find.text('brand_new_table'), findsOneWidget);
      expect(find.text('value'), findsOneWidget);
    });
  });

  testWidgets('a name can be corrected but not forgotten', (tester) async {
    await pumpProfile(tester, [row('identity', 'name', 'BatMan', confidence: 1.0, source: 'explicit')]);

    expect(find.text('BatMan'), findsOneWidget);
    expect(find.text('Correct'), findsOneWidget);
    expect(find.text('Forget'), findsNothing);
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

    expect(api.calls, isEmpty);
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
}
