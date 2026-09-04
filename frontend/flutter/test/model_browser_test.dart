// Tests for the model browser.
//
// The requirement was "any open-source model", and the two halves of that pull
// against each other: the list must never become a limit, and a model that
// cannot run on this card must not be presented as though it can. Most of what
// is asserted here is about keeping both true at once.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/model_browser.dart';
import 'package:pip_flutter_client/theme.dart';

class FakeApi extends ApiClient {
  FakeApi({required this.catalog, this.pullStatus}) : super('http://x', apiToken: 't');

  final Map<String, dynamic> catalog;
  Map<String, dynamic>? pullStatus;
  String? pulled;
  Object? startPullThrows;

  @override
  Future<Map<String, dynamic>> getModelCatalog() async => catalog;

  @override
  Future<Map<String, dynamic>> getPullStatus() async =>
      pullStatus ?? {'status': 'idle', 'model': null, 'completed': 0, 'total': 0, 'detail': '', 'error': null};

  @override
  Future<void> startPull(String modelName) async {
    if (startPullThrows != null) throw startPullThrows!;
    pulled = modelName;
  }
}

Map<String, dynamic> _model(String name, {bool pulled = false, Object? fits, double? sizeGb, double? vramGb, String note = ''}) => {
      'name': name,
      'size_gb': sizeGb,
      'vram_gb': vramGb,
      'note': note,
      'pulled': pulled,
      'fits': fits,
    };

Widget _wrap(Widget child) => MaterialApp(
      theme: AppTheme.light,
      home: Scaffold(body: SingleChildScrollView(child: child)),
    );

void main() {
  testWidgets('lists what can be downloaded, and marks what is already here', (tester) async {
    final api = FakeApi(catalog: {
      'vram_gb': 8.0,
      'models': [
        _model('llama3.1:8b', pulled: true, fits: true, sizeGb: 4.7),
        _model('mistral:7b', fits: true, sizeGb: 4.1),
      ],
      'error': null,
    });

    await tester.pumpWidget(_wrap(ModelBrowser(api: api, onChanged: () {})));
    await tester.pumpAndSettle();

    expect(find.text('llama3.1:8b'), findsOneWidget);
    expect(find.text('mistral:7b'), findsOneWidget);
    // Only the one that is missing offers to be fetched.
    expect(find.widgetWithText(TextButton, 'Download'), findsOneWidget);
  });

  testWidgets('a model too big for the card is marked but still offered', (tester) async {
    // Warn, never refuse. vram_gb is what the weights need resident and is
    // approximate - context and KV cache push real usage above it - so it must
    // not be a gate. The user knows things about their machine that nvidia-smi
    // does not, and blocking somebody from their own hardware is the worse error.
    final api = FakeApi(catalog: {
      'vram_gb': 8.0,
      'models': [_model('qwen2.5:14b', fits: false, sizeGb: 9.0, vramGb: 11.0)],
      'error': null,
    });

    await tester.pumpWidget(_wrap(ModelBrowser(api: api, onChanged: () {})));
    await tester.pumpAndSettle();

    expect(find.text('needs 11.0GB'), findsOneWidget);

    await tester.tap(find.widgetWithText(TextButton, 'Download'));
    await tester.pumpAndSettle();

    expect(api.pulled, 'qwen2.5:14b', reason: 'the warning became a block');
  });

  testWidgets('says nothing about fit when VRAM is unknown', (tester) async {
    // A machine with no NVIDIA GPU is not one where every model fails - it is
    // one where this cannot tell. Inventing a warning here would train people
    // to ignore the real ones.
    final api = FakeApi(catalog: {
      'vram_gb': null,
      'models': [_model('mistral:7b', fits: null, sizeGb: 4.1)],
      'error': null,
    });

    await tester.pumpWidget(_wrap(ModelBrowser(api: api, onChanged: () {})));
    await tester.pumpAndSettle();

    expect(find.textContaining('needs'), findsNothing);
    expect(find.textContaining('could not read'), findsOneWidget);
  });

  testWidgets('accepts a name that is not in the list', (tester) async {
    // The whole requirement. A picker limited to the curated names would be a
    // worse product than the terminal it replaces.
    final api = FakeApi(catalog: {'vram_gb': 8.0, 'models': const [], 'error': null});

    await tester.pumpWidget(_wrap(ModelBrowser(api: api, onChanged: () {})));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 'hf.co/someone/their-model:Q4_K_M');
    await tester.tap(find.widgetWithText(FilledButton, 'Download'));
    await tester.pumpAndSettle();

    expect(api.pulled, 'hf.co/someone/their-model:Q4_K_M');
  });

  testWidgets('shows a download that was already running when the screen opened', (tester) async {
    // The backend holds the pull state, not this widget, so navigating away and
    // back does not lose a 5GB download or its progress.
    final api = FakeApi(
      catalog: {'vram_gb': 8.0, 'models': const [], 'error': null},
      pullStatus: {
        'status': 'pulling', 'model': 'gemma2:9b', 'completed': 2147483648,
        'total': 5368709120, 'detail': 'downloading', 'error': null,
      },
    );

    await tester.pumpWidget(_wrap(ModelBrowser(api: api, onChanged: () {})));
    await tester.pump();

    expect(find.textContaining('Downloading gemma2:9b'), findsOneWidget);
    expect(find.textContaining('40%'), findsOneWidget);

    await tester.pumpAndSettle(const Duration(milliseconds: 100));
  });

  testWidgets('a failed pull says why', (tester) async {
    // The cost of accepting free text, and why it is still right: Ollama is a
    // better judge of what exists in its library than any list PIP ships.
    final api = FakeApi(
      catalog: {'vram_gb': 8.0, 'models': const [], 'error': null},
      pullStatus: {
        'status': 'error', 'model': 'not-a-model:9b', 'completed': 0, 'total': 0,
        'detail': '', 'error': "Ollama could not pull 'not-a-model:9b': file does not exist",
      },
    );

    await tester.pumpWidget(_wrap(ModelBrowser(api: api, onChanged: () {})));
    await tester.pumpAndSettle();

    expect(find.textContaining('Could not download'), findsOneWidget);
    expect(find.textContaining('file does not exist'), findsOneWidget);
  });

  testWidgets('an unreachable Ollama does not empty the list', (tester) async {
    // The case that matters most and is easiest to get backwards: choosing a
    // model to download is exactly what you do when nothing is downloaded yet,
    // which is frequently when Ollama is not up.
    final api = FakeApi(catalog: {
      'vram_gb': 8.0,
      'models': [_model('llama3.1:8b', fits: true, sizeGb: 4.7)],
      'error': 'Ollama is unreachable at http://localhost:11434',
    });

    await tester.pumpWidget(_wrap(ModelBrowser(api: api, onChanged: () {})));
    await tester.pumpAndSettle();

    expect(find.text('llama3.1:8b'), findsOneWidget);
  });
}
