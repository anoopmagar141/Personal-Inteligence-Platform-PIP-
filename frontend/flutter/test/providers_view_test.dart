// Behaviour tests for consent granting.
//
// This screen is where the constitution's hard stop at
// stage_8_before_network_call gets the permission it enforces. Sending
// full_inference for everything, as this did, left that machinery real but
// unused - the gate would faithfully enforce a scope nobody had chosen. The
// tests below pin the two things that make the choice real: that it is asked
// for at all, and that nothing is picked on the user's behalf.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/providers_view.dart';

class FakeApi extends ApiClient {
  FakeApi() : super('http://127.0.0.1:8765/api/v1');

  List<dynamic> providers = [];

  /// What Ollama has pulled. Empty by default so the consent tests below are
  /// not also exercising a dropdown.
  List<dynamic> models = [];
  final List<String> calls = [];
  Object? grantError;
  Object? revokeError;

  @override
  Future<List<dynamic>> getProviders() async => providers;

  @override
  Future<List<dynamic>> getLlmModels() async => models;

  @override
  Future<String> getActiveModel() async => 'llama3.1:8b';

  // ProvidersView hosts the ModelBrowser, which loads on mount. Left to the
  // real implementations these reach the network, never resolve, and every
  // pumpAndSettle in this file times out on a spinner - a failure with nothing
  // to do with the consent behaviour under test.
  @override
  Future<Map<String, dynamic>> getModelCatalog() async =>
      {'vram_gb': null, 'models': const [], 'error': null};

  @override
  Future<Map<String, dynamic>> getPullStatus() async =>
      {'status': 'idle', 'model': null, 'completed': 0, 'total': 0, 'detail': '', 'error': null};

  @override
  Future<void> grantConsent(String providerId, String scope) async {
    calls.add('grant:$providerId=$scope');
    if (grantError != null) throw grantError!;
  }

  @override
  Future<void> revokeConsent(String providerId) async {
    calls.add('revoke:$providerId');
    if (revokeError != null) throw revokeError!;
  }
}

Map<String, dynamic> provider(
  String id, {
  bool isCloud = true,
  bool consented = false,
  String? scope,
}) =>
    {
      'provider_id': id,
      'is_cloud': isCloud,
      'user_consented': consented,
      'revoked': false,
      'consent_scope': scope,
    };

Future<FakeApi> pumpProviders(WidgetTester tester, List<dynamic> providers) async {
  // The runner opens PIP at 1280x720; flutter_test defaults to 800x600. At the
  // smaller size the model picker pushes the provider cards below the fold and
  // a tap on one lands on nothing, which measures the test window rather than
  // the screen. Sized to what the app actually opens at.
  tester.view.physicalSize = const Size(1400, 1000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  final api = FakeApi()..providers = providers;
  await tester.pumpWidget(
    MaterialApp(home: Scaffold(body: ProvidersView(api: api))),
  );
  await tester.pumpAndSettle();
  return api;
}

void main() {
  _dropdownTests();
  testWidgets('granting asks which scope instead of assuming one', (tester) async {
    final api = await pumpProviders(tester, [provider('anthropic')]);

    await tester.tap(find.text('Grant consent'));
    await tester.pumpAndSettle();

    expect(find.textContaining('What may anthropic receive?'), findsOneWidget);
    // Nothing has been sent yet - opening the dialog is not consenting.
    expect(api.calls, isEmpty);
  });

  testWidgets('offers every scope that means something, and not the one that does not', (tester) async {
    await pumpProviders(tester, [provider('anthropic')]);

    await tester.tap(find.text('Grant consent'));
    await tester.pumpAndSettle();

    expect(find.text('embedding_only'), findsOneWidget);
    expect(find.text('web_search_only'), findsOneWidget);
    expect(find.text('full_inference'), findsOneWidget);
    // 'none' is a valid scope but would set user_consented while consenting to
    // nothing - Revoke already says that without the ambiguity.
    expect(find.text('none'), findsNothing);
  });

  testWidgets('will not grant until a scope is chosen', (tester) async {
    // No preselection: a default here would be this screen making the
    // least-privilege decision the gate exists to leave to the user.
    await pumpProviders(tester, [provider('anthropic')]);

    await tester.tap(find.text('Grant consent'));
    await tester.pumpAndSettle();

    final grant = find.widgetWithText(FilledButton, 'Grant');
    expect(tester.widget<FilledButton>(grant).onPressed, isNull);
  });

  testWidgets('sends the scope that was actually picked', (tester) async {
    final api = await pumpProviders(tester, [provider('anthropic')]);

    await tester.tap(find.text('Grant consent'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('embedding_only'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Grant'));
    await tester.pumpAndSettle();

    expect(api.calls, contains('grant:anthropic=embedding_only'));
    expect(api.calls, isNot(contains('grant:anthropic=full_inference')));
  });

  testWidgets('cancelling consents to nothing', (tester) async {
    final api = await pumpProviders(tester, [provider('anthropic')]);

    await tester.tap(find.text('Grant consent'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('web_search_only'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(api.calls, isEmpty);
  });

  testWidgets('a local provider is never asked about', (tester) async {
    await pumpProviders(tester, [provider('ollama', isCloud: false)]);

    expect(find.text('Grant consent'), findsNothing);
    expect(find.textContaining('n/a'), findsWidgets);
  });

  testWidgets("a refused grant reports on the row and keeps the screen", (tester) async {
    // The earlier version of this test asserted only that the sentence was
    // findable - and it was, on an otherwise blank page. A failed grant used
    // to be written into the page-level _error that build() returns early on,
    // so one refusal replaced the provider list, the model picker and the way
    // back with a single line of red text.
    final api = await pumpProviders(tester, [provider('anthropic')]);
    api.grantError = ApiException(
      422,
      '{"detail": "Invalid consent_scope \'bogus\'. Must be one of: [...]"}',
    );

    await tester.tap(find.text('Grant consent'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('full_inference'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Grant'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Invalid consent_scope'), findsOneWidget);
    // Everything that was on screen is still on screen.
    expect(find.text('anthropic'), findsOneWidget);
    expect(find.text('Providers'), findsOneWidget);
    expect(find.text('Grant consent'), findsOneWidget);
  });

  testWidgets('a refused revoke says so instead of doing nothing visible', (tester) async {
    // Revoke was unguarded: the exception went nowhere and the row simply did
    // not change, which is indistinguishable from a button that does not
    // work. On a consent screen that is the worst thing to be unsure about.
    final api = await pumpProviders(
      tester,
      [provider('anthropic', consented: true, scope: 'full_inference')],
    );
    api.revokeError = ApiException(500, '{"detail": "database is locked"}');

    await tester.tap(find.text('Revoke'));
    await tester.pumpAndSettle();

    expect(find.textContaining('database is locked'), findsOneWidget);
    expect(find.text('anthropic'), findsOneWidget);
  });
}

// --- the active-model dropdown at a narrow window --------------------------
//
// Reported from a real run: a console filling with "A RenderFlex overflowed by
// N pixels on the right", one line per pulled model, each by a different
// amount. DropdownButtonFormField sizes its button to its WIDEST item and the
// field then clamps it, so the row inside exceeds by however much the longest
// name did not fit - and with the menu open, every item too wide for it
// overflows on its own account, which is where the one-per-model came from.
//
// It only appeared below about 720px, because that is where this screen's own
// maxWidth stops being the binding constraint and the window starts being it.
// A maximised window never showed it; the developer's `flutter run` window
// always did - which is why every test here had passed at the 800px default.

void _dropdownTests() {
  Future<void> pumpAt(WidgetTester tester, double width, FakeApi api) async {
    tester.view.physicalSize = Size(width, 1600);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: ProvidersView(api: api))));
    await tester.pumpAndSettle();
  }

  FakeApi withModels() => FakeApi()
    ..providers = [provider('ollama', isCloud: false)]
    ..models = [
      for (final entry in const [
        ['llama3.1:8b', 4700000000], ['qwen2.5:7b', 4700000000],
        ['mistral:7b', 4100000000], ['gemma2:9b', 5400000000],
        ['phi3:3.8b', 2200000000], ['deepseek-r1:8b', 4900000000],
        ['qwen2.5:14b', 9000000000], ['gemma4:latest', 8900000000],
        ['phi3:mini', 2000000000], ['nomic-embed-text:latest', 274000000],
        ['deepseek-coder-v2:16b', 8900000000], ['qwen2.5-coder:7b', 4700000000],
      ])
        {'name': entry[0], 'size': entry[1]},
    ];

  // Widths either side of the 720 the screen constrains itself to. A single
  // width would have kept passing at 800, which is exactly how this reached a
  // user.
  for (final width in [320.0, 440.0, 600.0, 660.0, 720.0, 900.0]) {
    testWidgets('the model dropdown fits its field at $width', (tester) async {
      await pumpAt(tester, width, withModels());
      // A RenderFlex overflow is an exception, and an exception fails the test
      // - so reaching here at all is the assertion. The expect below is for
      // the reader, and to fail loudly if the dropdown stops being drawn.
      expect(find.byType(DropdownButtonFormField<String>), findsOneWidget);
    });
  }

  testWidgets('the open menu fits too, one item per model', (tester) async {
    // The button and the menu are laid out separately, and the report was of
    // one overflow per model - which is the menu, not the button.
    final api = withModels();
    await pumpAt(tester, 440.0, api);

    await tester.tap(find.byType(DropdownButtonFormField<String>));
    await tester.pumpAndSettle();

    expect(find.text('mistral:7b (3.8 GB)'), findsWidgets);
  });

  testWidgets('a Hugging Face reference does not burst the field', (tester) async {
    // The "Something else" field accepts any GGUF reference, so a name can be
    // three times the length of anything in the curated list.
    final api = withModels()
      ..models = [
        {'name': 'hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M', 'size': 8900000000},
      ];
    await pumpAt(tester, 440.0, api);

    expect(find.byType(DropdownButtonFormField<String>), findsOneWidget);
  });
}
