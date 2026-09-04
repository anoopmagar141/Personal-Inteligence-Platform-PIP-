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
  final List<String> calls = [];
  Object? grantError;
  Object? revokeError;

  @override
  Future<List<dynamic>> getProviders() async => providers;

  @override
  Future<List<dynamic>> getLlmModels() async => [];

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
