// The first-run model step.
//
// What is worth protecting is not that a list renders. It is the three things
// that decide whether somebody ends up with a working PIP or a chat that
// cannot answer: that "no Ollama" is told apart from "no models yet" and gets
// its own screen, that the size of the download is stated BEFORE it starts,
// and that this step can always be left - because a first run that cannot be
// finished is worse than one that ends without a model.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/screens/model_setup_screen.dart';

class FakeApi extends ApiClient {
  Map<String, dynamic> catalog;
  Map<String, dynamic> pull;
  final List<String> started = [];
  int catalogCalls = 0;
  Object? catalogThrows;

  FakeApi({Map<String, dynamic>? catalog, Map<String, dynamic>? pull})
      : catalog = catalog ?? {'models': <dynamic>[]},
        pull = pull ?? {'status': 'idle'},
        super('http://localhost:0', apiToken: 't');

  @override
  Future<Map<String, dynamic>> getModelCatalog() async {
    catalogCalls++;
    if (catalogThrows != null) throw catalogThrows!;
    return catalog;
  }

  @override
  Future<Map<String, dynamic>> getPullStatus() async => pull;

  @override
  Future<void> startPull(String modelName) async {
    started.add(modelName);
    pull = {'status': 'pulling', 'model': modelName, 'completed': 0, 'total': 0};
  }
}

Map<String, dynamic> model(
  String name, {
  double sizeGb = 4.7,
  bool pulled = false,
  bool? fits = true,
  String note = '',
}) =>
    {'name': name, 'size_gb': sizeGb, 'pulled': pulled, 'fits': fits, 'note': note};

Future<FakeApi> pumpSetup(WidgetTester tester, FakeApi api, {VoidCallback? onDone}) async {
  await tester.pumpWidget(
    MaterialApp(home: ModelSetupScreen(api: api, onDone: onDone ?? () {})),
  );
  // pump rather than pumpAndSettle, because a download in progress never
  // settles and should not: the progress bar is indeterminate until Ollama
  // reports a total, and the status poll is a periodic timer. Two frames is
  // enough to let the catalogue future resolve and rebuild.
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 50));
  return api;
}

void main() {
  group('when Ollama is not there', () {
    testWidgets('says so instead of listing models nobody can download',
        (tester) async {
      // The catalogue is fail-open: it still lists what COULD be pulled and
      // reports why in `error`. Without reading that, this screen would offer
      // Download buttons that cannot work.
      await pumpSetup(
        tester,
        FakeApi(catalog: {
          'models': [model('llama3.1:8b')],
          'error': 'Ollama is unreachable at http://localhost:11434',
        }),
      );

      expect(find.text('PIP needs Ollama'), findsOneWidget);
      expect(find.textContaining('ollama.com/download'), findsOneWidget);
      expect(find.text('Download'), findsNothing);
    });

    testWidgets('offers to look again, for somebody who just installed it',
        (tester) async {
      final api = await pumpSetup(
        tester,
        FakeApi(catalog: {'models': <dynamic>[], 'error': 'unreachable'}),
      );
      final before = api.catalogCalls;

      await tester.tap(find.text('Check again'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(api.catalogCalls, greaterThan(before));
    });
  });

  group('choosing one', () {
    testWidgets('states the size before the download starts', (tester) async {
      // The number nobody is told until they are already waiting for it.
      await pumpSetup(
        tester,
        FakeApi(catalog: {
          'models': [model('llama3.1:8b', sizeGb: 4.7)]
        }),
      );

      expect(find.text('llama3.1:8b'), findsOneWidget);
      expect(find.text('4.7 GB'), findsOneWidget);
    });

    testWidgets('downloading asks the backend for that model', (tester) async {
      final api = await pumpSetup(
        tester,
        FakeApi(catalog: {
          'models': [model('llama3.1:8b')]
        }),
      );

      await tester.tap(find.text('Download'));
      await tester.pump();

      expect(api.started, ['llama3.1:8b']);
    });

    testWidgets('hides models this machine cannot run', (tester) async {
      await pumpSetup(
        tester,
        FakeApi(catalog: {
          'models': [model('fits-fine'), model('far-too-big', fits: false)]
        }),
      );

      expect(find.text('fits-fine'), findsOneWidget);
      expect(find.text('far-too-big'), findsNothing);
    });

    testWidgets('shows a model when it cannot tell whether it fits', (tester) async {
      // fits is null when VRAM could not be detected, which is not the same as
      // false: a machine with no NVIDIA card is one where this cannot tell.
      await pumpSetup(
        tester,
        FakeApi(catalog: {
          'models': [model('unknown-fit', fits: null)]
        }),
      );

      expect(find.text('unknown-fit'), findsOneWidget);
    });

    testWidgets('a model already downloaded is marked, not offered again',
        (tester) async {
      await pumpSetup(
        tester,
        FakeApi(catalog: {
          'models': [model('llama3.1:8b', pulled: true)]
        }),
      );

      expect(find.text('Ready'), findsOneWidget);
      expect(find.text('Download'), findsNothing);
    });
  });

  group('while it downloads', () {
    testWidgets('shows progress and what is being fetched', (tester) async {
      await pumpSetup(
        tester,
        FakeApi(
          catalog: {'models': [model('llama3.1:8b')]},
          pull: {
            'status': 'pulling',
            'model': 'llama3.1:8b',
            'completed': 1073741824,
            'total': 5046586572,
          },
        ),
      );

      expect(find.textContaining('Downloading llama3.1:8b'), findsOneWidget);
      expect(find.textContaining('1.0 GB of 4.7 GB'), findsOneWidget);
    });

    testWidgets('the button says the download keeps going', (tester) async {
      // It is server-side and survives this screen closing, so calling the
      // button "Skip" would be a lie about what happens next.
      await pumpSetup(
        tester,
        FakeApi(
          catalog: {'models': [model('llama3.1:8b')]},
          pull: {'status': 'pulling', 'model': 'llama3.1:8b', 'completed': 0, 'total': 0},
        ),
      );

      expect(find.text('Continue while it downloads'), findsOneWidget);
    });
  });

  group('leaving', () {
    testWidgets('can always be skipped', (tester) async {
      // A first run that cannot be finished is worse than one that ends
      // without a model. Everything except answering still works.
      var done = false;
      await pumpSetup(
        tester,
        FakeApi(catalog: {'models': [model('llama3.1:8b')]}),
        onDone: () => done = true,
      );

      expect(find.text('Skip for now'), findsOneWidget);
      await tester.tap(find.text('Skip for now'));
      await tester.pump();

      expect(done, isTrue);
    });

    testWidgets('warns what skipping costs', (tester) async {
      await pumpSetup(tester, FakeApi(catalog: {'models': [model('llama3.1:8b')]}));

      expect(find.textContaining('will not be able to answer'), findsOneWidget);
    });

    testWidgets('a catalogue that will not load does not trap anybody',
        (tester) async {
      await pumpSetup(
        tester,
        FakeApi()..catalogThrows = Exception('backend fell over'),
      );

      expect(find.text('Skip for now'), findsOneWidget);
    });
  });
}
