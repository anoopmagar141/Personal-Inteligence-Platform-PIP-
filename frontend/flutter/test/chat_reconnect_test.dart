// The chat's reconnects, after a refused or lost connection (docs/FREEZE_LIST.md D-47).
//
// Found by V-1 in the real window (FREEZE_LIST §7.71): the backend was started again and
// came back locked, so it refused the chat socket. WsChatClient scheduled a reconnect from
// BOTH onError and onDone, and a refused connection fires both, so every failure started two
// attempts two seconds later: 30,800 attempts in about two minutes, over 1,000 a second and
// rising, 277 CPU-seconds, until the window was closed. And nothing took the app back to
// sign-in, so the chat could not resume in that window.
//
// Two halves, both held here:
//   - one reconnect at a time, whatever fires and whatever else is called meanwhile;
//   - a dropped connection asks the backend whether it is still unlocked, and a backend that
//     is not sends the app back to where it signs in.
//
// Each connection here is refused at once, as a locked or stopped backend refuses it: its
// stream reports an error and then closes, which is what fired onError AND onDone. (A real
// handshake never completes under flutter_test, so the client is handed this connection.)

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/home_shell.dart';
import 'package:pip_flutter_client/theme.dart';
import 'package:pip_flutter_client/ws_chat_client.dart';

const _delay = Duration(seconds: 2);

class _NullSink implements WebSocketSink {
  @override
  void add(dynamic data) {}
  @override
  void addError(Object error, [StackTrace? stackTrace]) {}
  @override
  Future addStream(Stream stream) async {}
  @override
  Future close([int? closeCode, String? closeReason]) async {}
  @override
  Future get done => Future.value();
}

/// A connection the backend refused: one error, then closed.
class RefusedChannel implements WebSocketChannel {
  @override
  final Stream stream = Stream.error(WebSocketChannelException('refused: PIP is locked'));
  @override
  final WebSocketSink sink = _NullSink();
  @override
  String? get protocol => null;
  @override
  int? get closeCode => null;
  @override
  String? get closeReason => null;
  @override
  final Future<void> ready = Future<void>.error(WebSocketChannelException('refused: PIP is locked'));
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

WebSocketChannel _refused(Uri uri) => RefusedChannel();

/// A connection the backend accepted, open until the test closes it.
class OpenChannel implements WebSocketChannel {
  final _incoming = StreamController<dynamic>();
  final _ready = Completer<void>();

  /// The handshake finishing.
  void accept() => _ready.complete();

  /// The backend going away.
  void drop() => _incoming.close();

  @override
  Stream get stream => _incoming.stream;
  @override
  final WebSocketSink sink = _NullSink();
  @override
  String? get protocol => null;
  @override
  int? get closeCode => null;
  @override
  String? get closeReason => null;
  @override
  Future<void> get ready => _ready.future;
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

/// The real client, counting how often it tries.
class CountingClient extends WsChatClient {
  CountingClient() : super('ws://127.0.0.1:1/ws/chat', reconnectDelay: _delay, connector: _refused);

  int attempts = 0;

  @override
  void connect() {
    attempts++;
    super.connect();
  }
}

/// Lets the refused handshake land, then moves the clock one reconnect period on.
Future<void> _onePeriod(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(_delay);
  await tester.pump();
}

void main() {
  group('one reconnect at a time', () {
    testWidgets('a refused connection is tried again once per period, not twice', (tester) async {
      final client = CountingClient()..connect();

      for (var i = 0; i < 6; i++) {
        await _onePeriod(tester);
      }

      // The first try plus one per period. With a reconnect from both onError and onDone
      // this was 2^6 = 64 and doubling.
      expect(client.attempts, inInclusiveRange(6, 7));
      client.dispose();
      await tester.pump(_delay);
    });

    testWidgets('switching conversation while a reconnect waits does not start a second chain', (tester) async {
      final client = CountingClient()..connect();
      await tester.pump();

      client.switchConversation('a-conversation');
      for (var i = 0; i < 5; i++) {
        await _onePeriod(tester);
      }

      // Two starts (connect, switch) and one try per period after them, never two chains.
      expect(client.attempts, inInclusiveRange(6, 7));
      client.dispose();
      await tester.pump(_delay);
    });

    testWidgets('a reconnect that is waiting is cancelled by disconnect', (tester) async {
      final client = CountingClient()..connect();
      await tester.pump();
      client.disconnect();
      final before = client.attempts;

      for (var i = 0; i < 3; i++) {
        await _onePeriod(tester);
      }

      expect(client.attempts, before, reason: 'it kept trying after it was told to stop');
      client.dispose();
    });

    testWidgets('a second connect() while connected leaves one connection and one chain', (tester) async {
      // connect() says it ends whatever the client had; it did not, so a second call left two
      // live connections, and when both dropped, two reconnect chains (found reviewing D-47).
      final opened = <OpenChannel>[];
      var attempts = 0;
      final client = WsChatClient('ws://127.0.0.1:1/ws/chat', reconnectDelay: _delay, connector: (uri) {
        attempts++;
        if (opened.length < 2) {
          final channel = OpenChannel()..accept();
          opened.add(channel);
          return channel;
        }
        return RefusedChannel();
      });

      client.connect();
      client.connect();
      await tester.pump();
      for (final channel in opened) {
        channel.drop();
      }
      for (var i = 0; i < 5; i++) {
        await _onePeriod(tester);
      }

      // Two starts, then one try per period: two chains made it about twice that.
      expect(attempts, inInclusiveRange(6, 8));
      client.dispose();
      await tester.pump(_delay);
    });

    testWidgets('a refused attempt never reports connected; an accepted one does', (tester) async {
      final refused = WsChatClient('ws://127.0.0.1:1/ws/chat', reconnectDelay: _delay, connector: _refused);
      final said = <String>[];
      refused.status.listen(said.add);
      refused.connect();
      await tester.pump();
      expect(said, ['connecting', 'disconnected'], reason: 'the pill said Connected to a backend refusing every handshake');
      refused.dispose();

      final open = OpenChannel();
      final accepted = WsChatClient('ws://127.0.0.1:1/ws/chat', reconnectDelay: _delay, connector: (_) => open);
      final saidOpen = <String>[];
      accepted.status.listen(saidOpen.add);
      accepted.connect();
      await tester.pump();
      expect(saidOpen, ['connecting']);
      open.accept();
      await tester.pump();
      expect(saidOpen, ['connecting', 'connected']);
      accepted.dispose();
      await tester.pump(_delay);
    });

    testWidgets('a handshake that finishes too late says nothing', (tester) async {
      // Late for three reasons: the client moved on to another connection, it was disposed, or the
      // connection dropped first. "connected" then would describe nothing that is open.
      final channels = <OpenChannel>[];
      WsChatClient client() => WsChatClient('ws://127.0.0.1:1/ws/chat', reconnectDelay: _delay, connector: (_) {
            final channel = OpenChannel();
            channels.add(channel);
            return channel;
          });

      final replaced = client();
      final said = <String>[];
      replaced.status.listen(said.add);
      replaced.connect();
      replaced.connect();
      channels[0].accept();
      await tester.pump();
      expect(said, ['connecting', 'connecting'], reason: 'a replaced connection said connected');
      replaced.dispose();

      final disposed = client()..connect();
      disposed.dispose();
      channels.last.accept();
      await tester.pump();
      expect(tester.takeException(), isNull, reason: 'a handshake after dispose() added to a closed stream');

      final dropped = client();
      final saidDropped = <String>[];
      dropped.status.listen(saidDropped.add);
      dropped.connect();
      channels.last.drop();
      await tester.pump();
      channels.last.accept();
      await tester.pump();
      expect(saidDropped, ['connecting', 'disconnected'], reason: 'a dropped connection said connected');
      dropped.dispose();
      await tester.pump(_delay);
    });

    testWidgets('disconnect() after dispose() does nothing', (tester) async {
      final client = CountingClient()..connect();
      await tester.pump();
      client.dispose();

      expect(client.disconnect, returnsNormally);
    });
  });

  group('a locked backend takes the app back to sign-in', () {
    testWidgets('a dropped chat and a locked backend: the app goes back, and stops trying', (tester) async {
      final api = FakeApi('locked');
      final spy = await _pumpShell(tester, api);

      for (var i = 0; i < 3; i++) {
        await _onePeriod(tester);
      }

      expect(spy.backendLocked, 1, reason: 'the app stayed on a chat that can never connect');
      expect(spy.signedOut, 0);
      final asked = api.authStateCalls;
      for (var i = 0; i < 3; i++) {
        await _onePeriod(tester);
      }
      expect(api.authStateCalls, asked, reason: 'it went on asking after it had handed back');
    });

    testWidgets('a dropped chat and an unlocked backend: the app stays and keeps reconnecting', (tester) async {
      final api = FakeApi('unlocked');
      final spy = await _pumpShell(tester, api);

      for (var i = 0; i < 3; i++) {
        await _onePeriod(tester);
      }

      expect(spy.backendLocked, 0);
      expect(api.authStateCalls, greaterThan(0), reason: 'a dropped connection never asked the backend');
    });

    testWidgets('a backend that refuses the token (it started with a new one): the app goes back', (tester) async {
      // The start screen re-reads the token file; this shell cannot (found reviewing D-47).
      final api = FakeApi(null)..failure = ApiException(401, '{"detail": "missing or invalid bearer token"}');
      final spy = await _pumpShell(tester, api);

      for (var i = 0; i < 3; i++) {
        await _onePeriod(tester);
      }

      expect(spy.backendLocked, 1);
    });

    testWidgets('a dialog open when the backend is found locked does not stay over the sign-in screen', (tester) async {
      // Dialogs sit on the root navigator, above the screen the root swaps, so one left open
      // would be drawn over sign-in, and confirming it ran a shell that was gone (found
      // reviewing D-47).
      final api = FakeApi('unlocked');
      final spy = await _pumpShell(tester, api);
      await tester.tap(find.text('Sign out'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));
      expect(find.text('Sign out?'), findsOneWidget);

      api.state = 'locked';
      for (var i = 0; i < 3; i++) {
        await _onePeriod(tester);
      }

      expect(spy.backendLocked, 1);
      expect(find.text('Sign out?'), findsNothing);
      expect(spy.signedOut, 0);
    });

    testWidgets('a backend that does not answer: the app stays', (tester) async {
      final api = FakeApi(null);
      final spy = await _pumpShell(tester, api);

      for (var i = 0; i < 3; i++) {
        await _onePeriod(tester);
      }

      expect(spy.backendLocked, 0);
    });

    testWidgets('signing out is not also reported as a locked backend', (tester) async {
      // Unlocked until the sign-out locks it, as the real backend is.
      final api = FakeApi('unlocked');
      final spy = await _pumpShell(tester, api);

      await tester.tap(find.text('Sign out'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));
      await tester.tap(find.widgetWithText(FilledButton, 'Sign out'));
      for (var i = 0; i < 3; i++) {
        await _onePeriod(tester);
      }

      expect(spy.signedOut, 1);
      expect(spy.backendLocked, 0, reason: 'one sign-out was taken for two');
    });
  });
}

/// Answers what HomeShell asks on the way up; /auth/state answers [state], or throws when null.
class FakeApi extends ApiClient {
  FakeApi(this.state) : super('http://127.0.0.1:1/api/v1');

  String? state;
  int authStateCalls = 0;

  /// What /auth/state throws when [state] is null: no answer at all, unless set.
  Object failure = Exception('the backend did not answer');

  @override
  Future<String> authState() async {
    authStateCalls++;
    if (state == null) throw failure;
    return state!;
  }

  @override
  Future<void> lock() async => state = 'locked';

  @override
  Future<Map<String, dynamic>> getStatus() async => {'pending_count': 0};

  @override
  Future<List<dynamic>> getProjects() async => [];

  @override
  Future<List<dynamic>> getConversations({String? projectId}) async => [];
}

class ShellSpy {
  int signedOut = 0;
  int backendLocked = 0;
}

Future<ShellSpy> _pumpShell(WidgetTester tester, FakeApi api) async {
  final spy = ShellSpy();
  tester.view.physicalSize = const Size(1600, 1200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.light,
    home: HomeShell(
      api: api,
      themeMode: ThemeMode.light,
      onCycleTheme: () {},
      onSignedOut: () => spy.signedOut++,
      onBackendLocked: () => spy.backendLocked++,
      chatClient: WsChatClient('ws://127.0.0.1:1/ws/chat', reconnectDelay: _delay, connector: _refused),
    ),
  ));
  await tester.pump();
  return spy;
}
