// Behaviour tests for the Profile screen, now that it can write.
//
// The interesting cases are all about NOT offering an action the backend
// cannot honour, because each failure mode is silent in a different way:
//
//   * identity rows are refused server-side, so an edit button on one would
//     always fail;
//   * a skill row would not be refused at all - correct_profile_field() writes
//     to preference_memory unconditionally, so "correcting" a skill would
//     appear to succeed while filing a new preference and leaving the skill
//     exactly as wrong as it was. That is the worst of the three, and the only
//     one no error message would ever reveal.
//
// The endpoints themselves are covered by the Python suite.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/profile_view.dart';

class FakeApi extends ApiClient {
  FakeApi() : super('http://127.0.0.1:8765/api/v1');

  List<dynamic> fields = [];
  final List<String> calls = [];
  Object? correctError;
  String deleteStatus = 'deleted';

  @override
  Future<List<dynamic>> getProfile() async => fields;

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
    test('offers nothing on identity, and says why', () {
      final capability = profileRowCapability('identity');
      expect(capability.canEdit, isFalse);
      expect(capability.canDelete, isFalse);
      expect(capability.note, 'set at onboarding');
    });

    test('does not offer to correct a skill', () {
      // correct_profile_field() writes to preference_memory, so this would
      // file a stray preference and leave the skill untouched - a silent
      // wrong answer rather than a visible refusal.
      expect(profileRowCapability('skill_memory').canEdit, isFalse);
      expect(profileRowCapability('skill_memory').canDelete, isTrue);
    });

    test('offers both on a preference, which is what the endpoint writes', () {
      expect(profileRowCapability('preference_memory').canEdit, isTrue);
      expect(profileRowCapability('preference_memory').canDelete, isTrue);
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

  testWidgets('shows no write affordances on an identity row', (tester) async {
    await pumpProfile(tester, [row('identity', 'name', 'BatMan', confidence: 1.0, source: 'explicit')]);

    expect(find.text('BatMan'), findsOneWidget);
    expect(find.text('Correct'), findsNothing);
    expect(find.text('Forget'), findsNothing);
    expect(find.textContaining('set at onboarding'), findsOneWidget);
  });

  testWidgets('a skill can be forgotten but not corrected', (tester) async {
    await pumpProfile(tester, [row('skill_memory', 'Python', '0.7')]);

    expect(find.text('Forget'), findsOneWidget);
    expect(find.text('Correct'), findsNothing);
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
