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

  /// What the backend says PIP is currently using. Null means it could not be
  /// read, which the browser treats as "do not withhold Delete from anything".
  String? active;
  bool cancelled = false;
  final List<String> deleted = [];
  Object? deleteThrows;

  @override
  Future<String> getActiveModel() async {
    if (active == null) throw Exception('no active model');
    return active!;
  }

  @override
  Future<void> cancelPull() async {
    cancelled = true;
    pullStatus = {...?pullStatus, 'status': 'cancelled', 'detail': 'cancelled'};
  }

  @override
  Future<void> deleteModel(String modelName) async {
    if (deleteThrows != null) throw deleteThrows!;
    deleted.add(modelName);
  }

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

  // --- stopping a download -------------------------------------------------

  testWidgets('a running download offers to be cancelled', (tester) async {
    final api = FakeApi(
      catalog: {'vram_gb': 8.0, 'models': [_model('mistral:7b', sizeGb: 4.1)], 'error': null},
      pullStatus: {
        'status': 'pulling', 'model': 'qwen2.5:7b',
        'completed': 900000000, 'total': 4400000000, 'detail': 'downloading', 'error': null,
      },
    );

    await tester.pumpWidget(_wrap(ModelBrowser(api: api, onChanged: () {})));
    await tester.pump();

    expect(find.text('Downloading qwen2.5:7b'), findsOneWidget);
    await tester.tap(find.widgetWithText(TextButton, 'Cancel'));
    await tester.pump();

    expect(api.cancelled, isTrue);
  });

  testWidgets('nothing offers to be cancelled when nothing is downloading', (tester) async {
    final api = FakeApi(
      catalog: {'vram_gb': 8.0, 'models': [_model('mistral:7b', sizeGb: 4.1)], 'error': null},
    );

    await tester.pumpWidget(_wrap(ModelBrowser(api: api, onChanged: () {})));
    await tester.pumpAndSettle();

    expect(find.widgetWithText(TextButton, 'Cancel'), findsNothing);
  });

  testWidgets('a cancelled download is not dressed as a failure', (tester) async {
    // A red line under something somebody chose to do is the wrong answer, and
    // what they most want to know next is whether stopping cost them the 900MB.
    final api = FakeApi(
      catalog: {'vram_gb': 8.0, 'models': [_model('mistral:7b', sizeGb: 4.1)], 'error': null},
      pullStatus: {
        'status': 'cancelled', 'model': 'qwen2.5:7b',
        'completed': 900000000, 'total': 4400000000, 'detail': 'cancelled', 'error': null,
      },
    );

    await tester.pumpWidget(_wrap(ModelBrowser(api: api, onChanged: () {})));
    await tester.pump();

    expect(find.text('Stopped downloading qwen2.5:7b'), findsOneWidget);
    expect(find.textContaining('carries on from here'), findsOneWidget);
  });

  // --- removing a pulled model ---------------------------------------------

  testWidgets('a pulled model offers to be deleted', (tester) async {
    final api = FakeApi(catalog: {
      'vram_gb': 8.0,
      'models': [
        _model('llama3.1:8b', pulled: true, fits: true, sizeGb: 4.7),
        _model('mistral:7b', fits: true, sizeGb: 4.1),
      ],
      'error': null,
    })..active = 'phi3:mini';

    await tester.pumpWidget(_wrap(ModelBrowser(api: api, onChanged: () {})));
    await tester.pumpAndSettle();

    expect(find.widgetWithText(TextButton, 'Delete'), findsOneWidget);
    expect(find.widgetWithText(TextButton, 'Download'), findsOneWidget);
  });

  testWidgets('the model PIP is using is not offered for deletion', (tester) async {
    // The backend refuses it too. A button whose only outcome is an
    // explanation of why it did nothing is worse than saying what to do.
    final api = FakeApi(catalog: {
      'vram_gb': 8.0,
      'models': [_model('llama3.1:8b', pulled: true, fits: true, sizeGb: 4.7)],
      'error': null,
    })..active = 'llama3.1:8b';

    await tester.pumpWidget(_wrap(ModelBrowser(api: api, onChanged: () {})));
    await tester.pumpAndSettle();

    expect(find.widgetWithText(TextButton, 'Delete'), findsNothing);
    expect(find.text('In use'), findsOneWidget);
  });

  testWidgets('deleting asks first, and says what it gives back', (tester) async {
    final api = FakeApi(catalog: {
      'vram_gb': 8.0,
      'models': [_model('gemma2:9b', pulled: true, fits: true, sizeGb: 5.4)],
      'error': null,
    })..active = 'phi3:mini';

    await tester.pumpWidget(_wrap(ModelBrowser(api: api, onChanged: () {})));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, 'Delete'));
    await tester.pumpAndSettle();

    expect(find.text('Delete gemma2:9b?'), findsOneWidget);
    expect(find.textContaining('frees about 5.4GB on disk'), findsOneWidget);
    // The reason this is a light confirmation and not the profile delete's.
    expect(find.textContaining('Nothing of yours is in a model'), findsOneWidget);
    expect(api.deleted, isEmpty);
  });

  testWidgets('cancelling the confirmation deletes nothing', (tester) async {
    final api = FakeApi(catalog: {
      'vram_gb': 8.0,
      'models': [_model('gemma2:9b', pulled: true, fits: true, sizeGb: 5.4)],
      'error': null,
    })..active = 'phi3:mini';

    await tester.pumpWidget(_wrap(ModelBrowser(api: api, onChanged: () {})));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, 'Delete'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, 'Cancel'));
    await tester.pumpAndSettle();

    expect(api.deleted, isEmpty);
  });

  testWidgets('confirming deletes it and tells the caller to re-read', (tester) async {
    // The list one screen up still offers a name Ollama no longer has.
    var changed = false;
    final api = FakeApi(catalog: {
      'vram_gb': 8.0,
      'models': [_model('gemma2:9b', pulled: true, fits: true, sizeGb: 5.4)],
      'error': null,
    })..active = 'phi3:mini';

    await tester.pumpWidget(_wrap(ModelBrowser(api: api, onChanged: () => changed = true)));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, 'Delete'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Delete'));
    await tester.pumpAndSettle();

    expect(api.deleted, ['gemma2:9b']);
    expect(changed, isTrue);
  });

  testWidgets("a refused delete shows the server's own sentence", (tester) async {
    final api = FakeApi(catalog: {
      'vram_gb': 8.0,
      'models': [_model('gemma2:9b', pulled: true, fits: true, sizeGb: 5.4)],
      'error': null,
    })
      ..active = 'phi3:mini'
      ..deleteThrows = ApiException(422, '{"detail":"gemma2:9b is downloading right now"}');

    await tester.pumpWidget(_wrap(ModelBrowser(api: api, onChanged: () {})));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, 'Delete'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Delete'));
    await tester.pumpAndSettle();

    expect(find.text('gemma2:9b is downloading right now'), findsOneWidget);
  });
}
