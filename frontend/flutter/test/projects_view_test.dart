// Behaviour tests for the Projects screen's status transitions.
//
// The one that matters most is the cross-screen consequence: shelving the
// project the chat is currently pointed at has to let go of that pointer.
// Nothing on the chat screen would show that it had not, so new conversation
// would keep being filed against a project the user had just put away - a
// wrong result that is invisible from the place it goes wrong.
//
// The endpoints themselves are covered by the Python suite.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/projects_view.dart';

class FakeApi extends ApiClient {
  FakeApi() : super('http://127.0.0.1:8765/api/v1');

  List<dynamic> projects = [];
  final List<String> calls = [];
  Object? statusError;
  Object? createError;

  @override
  Future<void> createProject(Map<String, dynamic> payload) async {
    calls.add('create:${payload['name']}');
    if (createError != null) throw createError!;
  }

  @override
  Future<List<dynamic>> getProjects() async => projects;

  @override
  Future<void> activateProject(String projectId) async {
    calls.add('activate:$projectId');
  }

  @override
  Future<void> updateProjectStatus(String projectId, String status) async {
    calls.add('status:$projectId=$status');
    if (statusError != null) throw statusError!;
  }
}

Map<String, dynamic> project(String id, String name, {String status = 'active'}) => {
      'project_id': id,
      'name': name,
      'description': '',
      'status': status,
      'last_active': '2026-08-31T10:00:00Z',
    };

Future<({FakeApi api, List<String?> activations})> pumpProjects(
  WidgetTester tester,
  List<dynamic> projects, {
  String? activeProjectId,
}) async {
  final api = FakeApi()..projects = projects;
  final activations = <String?>[];
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: ProjectsView(
          api: api,
          activeProjectId: activeProjectId,
          onActivate: activations.add,
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return (api: api, activations: activations);
}

void main() {
  testWidgets('offers archive and complete on an active project', (tester) async {
    await pumpProjects(tester, [project('p1', 'PIP')]);

    expect(find.text('Archive'), findsOneWidget);
    expect(find.text('Complete'), findsOneWidget);
    expect(find.text('Work in this'), findsOneWidget);
  });

  testWidgets('a refused create keeps what was typed', (tester) async {
    // Was unguarded, and cleared the fields unconditionally - so a failed
    // create threw away the name and description AND said nothing, leaving
    // nothing to retry with and no reason to retry it.
    final harness = await pumpProjects(tester, []);
    harness.api.createError = ApiException(422, '{"detail": "A project needs a name."}');

    await tester.enterText(find.widgetWithText(TextField, 'Project name'), 'Thesis');
    await tester.tap(find.widgetWithText(FilledButton, 'Create'));
    await tester.pumpAndSettle();

    expect(find.textContaining('A project needs a name'), findsOneWidget);
    expect(find.text('Thesis'), findsOneWidget);
  });

  testWidgets('offers only reopening on a shelved project', (tester) async {
    // list_projects() returns every status and orders active first, so a
    // finished project is already in this list - it just must not be offered
    // the verbs that only make sense for a live one.
    await pumpProjects(tester, [project('p1', 'Old thing', status: 'completed')]);

    expect(find.text('Reopen'), findsOneWidget);
    expect(find.text('Archive'), findsNothing);
    expect(find.text('Complete'), findsNothing);
  });

  testWidgets('archiving sends the status the backend accepts', (tester) async {
    final harness = await pumpProjects(tester, [project('p1', 'PIP')]);

    await tester.tap(find.text('Archive'));
    await tester.pumpAndSettle();

    expect(harness.api.calls, contains('status:p1=archived'));
  });

  testWidgets('shelving the project the chat is pointed at lets go of it', (tester) async {
    final harness = await pumpProjects(
      tester,
      [project('p1', 'PIP')],
      activeProjectId: 'p1',
    );

    await tester.tap(find.text('Complete'));
    await tester.pumpAndSettle();

    expect(harness.api.calls, contains('status:p1=completed'));
    expect(harness.activations, [null]);
  });

  testWidgets('shelving a different project leaves the chat pointer alone', (tester) async {
    final harness = await pumpProjects(
      tester,
      [project('p1', 'PIP'), project('p2', 'Side quest')],
      activeProjectId: 'p1',
    );

    // The SECOND project's Archive - p1 is the one the chat points at, and
    // archiving that one is the other test.
    await tester.tap(find.text('Archive').last);
    await tester.pumpAndSettle();

    expect(harness.api.calls, contains('status:p2=archived'));
    expect(harness.activations, isEmpty);
  });

  testWidgets('the project the chat is pointed at is marked as such', (tester) async {
    await pumpProjects(
      tester,
      [project('p1', 'PIP')],
      activeProjectId: 'p1',
    );

    expect(find.text('in this chat'), findsOneWidget);
  });

  testWidgets('reopening goes through activate, which both restores and points here', (tester) async {
    final harness = await pumpProjects(tester, [project('p1', 'Old thing', status: 'archived')]);

    await tester.tap(find.text('Reopen'));
    await tester.pumpAndSettle();

    expect(harness.api.calls, contains('activate:p1'));
    expect(harness.activations, ['p1']);
  });

  testWidgets("a refused status change shows the server's sentence on that row", (tester) async {
    final harness = await pumpProjects(tester, [project('p1', 'PIP')]);
    harness.api.statusError = ApiException(422, '{"detail": "invalid project status"}');

    await tester.tap(find.text('Archive'));
    await tester.pumpAndSettle();

    expect(find.text('invalid project status'), findsOneWidget);
  });
}
