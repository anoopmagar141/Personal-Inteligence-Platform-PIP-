// Behaviour tests for the retrieval preview on the Documents screen.
//
// The panel exists to answer "why did PIP not use my document", and the way it
// can fail at that is by treating an empty result as an outcome rather than as
// a question. Nothing above 0.6 is not the same claim as nothing in the
// corpus, and a screen that renders the first as if it were the second sends
// someone off to re-upload a file that was already there.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/documents_view.dart';

class FakeApi extends ApiClient {
  FakeApi() : super('http://127.0.0.1:8765/api/v1');

  List<dynamic> documents = [];
  List<dynamic> matches = [];
  final List<String> calls = [];
  Object? queryError;

  @override
  Future<List<dynamic>> getDocuments() async => documents;

  @override
  Future<List<dynamic>> queryRag(String query, {double threshold = 0.6, String? projectId}) async {
    calls.add('query:$query@${threshold.toStringAsFixed(2)}');
    if (queryError != null) throw queryError!;
    return matches;
  }
}

Map<String, dynamic> document(String path, {int chunks = 4}) => {
      'file_path': path,
      'chunk_count': chunks,
      'ingested_at': '2026-08-31T10:00:00Z',
    };

Map<String, dynamic> match(String path, {double similarity = 0.82, int index = 3}) => {
      'chunk_text': 'PIP stores decisions with a reason attached.',
      'file_path': path,
      'chunk_index': index,
      'similarity': similarity,
    };

Future<FakeApi> pumpDocuments(
  WidgetTester tester, {
  List<dynamic>? documents,
  List<dynamic>? matches,
  Object? queryError,
}) async {
  final api = FakeApi()
    ..documents = documents ?? []
    ..matches = matches ?? []
    ..queryError = queryError;
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(body: DocumentsView(api: api, activeProjectId: null)),
    ),
  );
  await tester.pumpAndSettle();
  return api;
}

Future<void> searchFor(WidgetTester tester, String query) async {
  await tester.enterText(find.widgetWithText(TextField, 'Ask something your documents should answer...'), query);
  await tester.tap(find.widgetWithText(FilledButton, 'Search'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('sends the query and the backend default threshold', (tester) async {
    // 0.60 is Stage 5's own default, so the first result set is what a real
    // question would actually have retrieved - not a looser view of it.
    final api = await pumpDocuments(tester, documents: [document('notes.md')]);

    await searchFor(tester, 'how are decisions stored');

    expect(api.calls, contains('query:how are decisions stored@0.60'));
  });

  testWidgets('shows where each passage came from and how close it was', (tester) async {
    await pumpDocuments(
      tester,
      documents: [document('notes.md')],
      matches: [match('D:/docs/notes.md', similarity: 0.826, index: 3)],
    );

    await searchFor(tester, 'decisions');

    expect(find.textContaining('notes.md'), findsWidgets);
    expect(find.textContaining('chunk 3'), findsOneWidget);
    expect(find.text('0.826'), findsOneWidget);
    expect(find.textContaining('decisions with a reason'), findsOneWidget);
  });

  testWidgets('an empty result points at the threshold, not at the corpus', (tester) async {
    await pumpDocuments(tester, documents: [document('notes.md')]);

    await searchFor(tester, 'quantum tunnelling');

    expect(find.textContaining('Lower the threshold'), findsOneWidget);
  });

  testWidgets('does not run a search before there is a query', (tester) async {
    final api = await pumpDocuments(tester, documents: [document('notes.md')]);

    await tester.tap(find.widgetWithText(FilledButton, 'Search'));
    await tester.pumpAndSettle();

    expect(api.calls, isEmpty);
  });

  testWidgets('a failed search is reported without clearing the screen', (tester) async {
    await pumpDocuments(
      tester,
      documents: [document('notes.md')],
      queryError: ApiException(422, '{"detail": "query is required"}'),
    );

    await searchFor(tester, 'anything');

    expect(find.text('query is required'), findsOneWidget);
    // The document list is still there - a failed query is not a failed page.
    expect(find.textContaining('4 chunks'), findsOneWidget);
  });

  testWidgets('the panel is offered even with nothing ingested yet', (tester) async {
    // Documents can exist in Chroma that this list does not show, and someone
    // debugging retrieval should not have to upload something first to get a
    // search box.
    await pumpDocuments(tester);

    expect(find.text('No documents yet'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Search'), findsOneWidget);
  });
}
