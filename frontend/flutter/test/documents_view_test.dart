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
  Object? deleteError;
  Object? defaultsError;
  // Deliberately not 0.6: a client that passes these tests on the real
  // default would also pass them while ignoring the backend entirely.
  double backendThreshold = 0.75;

  @override
  Future<List<dynamic>> getDocuments() async => documents;

  @override
  Future<Map<String, dynamic>> getRagDefaults() async {
    calls.add('defaults');
    if (defaultsError != null) throw defaultsError!;
    return {'similarity_threshold': backendThreshold, 'top_k_results': 3};
  }

  @override
  Future<void> deleteDocument(String filePath) async {
    calls.add('delete:$filePath');
    if (deleteError != null) throw deleteError!;
    documents = documents.where((d) => d['file_path'] != filePath).toList();
  }

  @override
  Future<List<dynamic>> queryRag(String query, {double? threshold, String? projectId}) async {
    calls.add('query:$query@${threshold?.toStringAsFixed(2) ?? 'none'}');
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
  Object? defaultsError,
  double backendThreshold = 0.75,
}) async {
  final api = FakeApi()
    ..documents = documents ?? []
    ..matches = matches ?? []
    ..queryError = queryError
    ..defaultsError = defaultsError
    ..backendThreshold = backendThreshold;
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
  testWidgets('searches at the threshold the backend reports, not a copy of it', (tester) async {
    // The first result set has to be what a real question would actually have
    // retrieved, which means the floor has to come from the backend that will
    // run the retrieval. This used to be a literal 0.6 on the client, correct
    // only until someone edited rag.similarity_threshold in settings.json.
    final api = await pumpDocuments(
      tester,
      documents: [document('notes.md')],
      backendThreshold: 0.45,
    );

    await searchFor(tester, 'how are decisions stored');

    expect(api.calls, contains('defaults'));
    expect(api.calls, contains('query:how are decisions stored@0.45'));
    expect(find.text('0.45'), findsOneWidget);
  });

  testWidgets('will not search on a guessed threshold when the defaults fail', (tester) async {
    // Falling back to a literal here would be the original bug wearing an
    // error path: a plausible number on the slider, results that look like
    // Stage 5's, and nothing on screen admitting the difference.
    final api = await pumpDocuments(
      tester,
      documents: [document('notes.md')],
      defaultsError: ApiException(500, '{"detail": "settings unreadable"}'),
    );

    await searchFor(tester, 'how are decisions stored');

    expect(api.calls.where((c) => c.startsWith('query:')), isEmpty);
    expect(find.textContaining('Could not read the retrieval settings'), findsOneWidget);
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

    expect(find.textContaining('Nothing above 0.75'), findsOneWidget);
    expect(find.textContaining('Lower the threshold'), findsOneWidget);
  });

  testWidgets('does not run a search before there is a query', (tester) async {
    final api = await pumpDocuments(tester, documents: [document('notes.md')]);

    await tester.tap(find.widgetWithText(FilledButton, 'Search'));
    await tester.pumpAndSettle();

    expect(api.calls.where((c) => c.startsWith('query:')), isEmpty);
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

  testWidgets('a refused delete says why, and the document stays listed', (tester) async {
    // Was unguarded: the exception went nowhere, the list reloaded unchanged,
    // and the row looked like it had ignored the click.
    final api = await pumpDocuments(tester, documents: [document('notes.md')]);
    api.deleteError = ApiException(422, '{"detail": "No active document at that path."}');

    await tester.tap(find.text('Remove'));
    await tester.pumpAndSettle();

    expect(find.textContaining('No active document'), findsOneWidget);
    expect(find.textContaining('notes.md'), findsWidgets);
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
