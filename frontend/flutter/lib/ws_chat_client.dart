// PIP - /ws/chat client (Part 14.2: chat is WebSocket-only, no REST /chat
// exists per ADR-028; Part 14.3: the wire protocol is exactly
// stage_hint -> token* -> done, or -> error).
//
// Mirrors frontend/web/app.js's connectChat()/handleChatEvent() logic one for
// one - same reconnect-on-close behavior, same event types, same "stage_hint
// is buffered and only rendered once done/error arrives" rule from Part 14.3
// ("static display, populated once response completes", not a live per-stage
// animation). Kept deliberately dumb per Part 14.4 - this class only relays
// what the backend sends, it never decides anything.

import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

class ChatEvent {
  final String type; // 'stage_hint' | 'token' | 'done' | 'error' | 'stopped' | 'session_info' | 'web_search_offer'
  final dynamic data;
  const ChatEvent(this.type, this.data);
}

class WsChatClient {
  final String wsUrl;
  // Security fix: /ws/chat now requires ?token=... on every connection (see
  // backend/core/auth.py) - a browser WebSocket client can't set custom
  // headers on connect, so the token travels as a query param instead.
  final String apiToken;
  final Duration reconnectDelay;
  // Which conversation to resume (?conversation_id=... - see server.py's
  // ws_chat()/_resolve_connection_state()). null means "start a fresh one."
  String? _conversationId;

  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  bool _disposed = false;

  final _eventController = StreamController<ChatEvent>.broadcast();
  final _statusController = StreamController<String>.broadcast();

  Stream<ChatEvent> get events => _eventController.stream;
  Stream<String> get status => _statusController.stream;

  // How a connection is opened: WebSocketChannel.connect, unless a test hands
  // in one that is refused at once (flutter_test never completes a real
  // handshake, so a refused connection cannot be had any other way there).
  final WebSocketChannel Function(Uri uri) _open;

  // The private field's leading underscore shouldn't leak into the
  // constructor's public parameter name, hence the manual assignment below
  // instead of an initializing formal (this._conversationId).
  WsChatClient(this.wsUrl,
      {this.apiToken = '',
      this.reconnectDelay = const Duration(seconds: 2),
      String? conversationId,
      @visibleForTesting WebSocketChannel Function(Uri uri)? connector})
      : _conversationId = conversationId, // ignore: prefer_initializing_formals
        _open = connector ?? WebSocketChannel.connect;

  /// What the next connection will ask for. Visible for tests, which cannot open a socket.
  @visibleForTesting
  Uri get connectUri => Uri.parse(wsUrl).replace(queryParameters: {
        'token': apiToken,
        if (_conversationId != null) 'conversation_id': _conversationId,
      });

  /// One frame from the server. Visible for tests.
  ///
  /// A session_info that names a conversation is REMEMBERED here, not only passed on
  /// (FREEZE_LIST D-23). The id used to be held only by switchConversation, and the
  /// server names none for a connection that has not sent a message, so after a drop
  /// the reconnect asked for "a fresh conversation": the screen went on showing one
  /// transcript while the next message started a second conversation on the server.
  /// A session_info with no id never forgets one we have.
  @visibleForTesting
  void handleRaw(String raw) {
    final decoded = jsonDecode(raw) as Map<String, dynamic>;
    final type = decoded['type'] as String;
    if (type == 'session_info') {
      final id = (decoded['data'] as Map<String, dynamic>?)?['conversation_id'];
      if (id is String && id.isNotEmpty) _conversationId = id;
    }
    _eventController.add(ChatEvent(type, decoded['data']));
  }

  /// The one reconnect waiting to happen, if any (D-47).
  Timer? _reconnectTimer;

  /// Opens a connection, ending whatever this client had before.
  ///
  /// One waiting reconnect at a time (D-47, found by V-1, FREEZE_LIST §7.71).
  /// A reconnect was scheduled from BOTH onError and onDone, and a refused
  /// connection - a backend that came back locked, or one that is down - fires
  /// both, so every failure started two attempts and each of those two more:
  /// 30,800 in two minutes in the real window, 277 CPU-seconds. Nor was a
  /// waiting reconnect ever cancelled, so switchConversation during a drop
  /// started a second chain beside the first, and disconnect() let one more
  /// attempt through. So a connection's loss is handled once, by whichever
  /// callback comes first, and the reconnect is a Timer that connect(),
  /// disconnect() and dispose() cancel. connect() also ends the connection it
  /// replaces (its subscription, so none of its callbacks run, and its socket):
  /// a second connect() used to leave two live connections, and two chains
  /// once both dropped (found reviewing D-47).
  ///
  /// "connected" is said when the handshake has finished, not when the
  /// connection was asked for: it was said at once, so the sidebar showed
  /// Connected for a moment on every attempt a backend refused, and the
  /// handshake's own failure (channel.ready) went unhandled, one console error
  /// per attempt (also found reviewing D-47). The stream reports that failure
  /// too, and it is handled there.
  void connect() {
    if (_disposed) return;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _subscription?.cancel();
    _channel?.sink.close();
    _statusController.add('connecting');
    try {
      final channel = _open(connectUri);
      _channel = channel;
      var lost = false;
      void onLost() {
        if (lost) return;
        lost = true;
        _statusController.add('disconnected');
        _scheduleReconnect();
      }

      _subscription = channel.stream.listen(
        (raw) => handleRaw(raw as String),
        onDone: onLost,
        onError: (Object error) => onLost(),
      );
      channel.ready.then((_) {
        if (!lost && !_disposed && identical(channel, _channel)) _statusController.add('connected');
      }, onError: (Object _) {});
    } catch (_) {
      _statusController.add('disconnected');
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_disposed) return;
    _reconnectTimer = Timer(reconnectDelay, () {
      _reconnectTimer = null;
      connect();
    });
  }

  void sendMessage(String text, {String? projectId}) {
    _channel?.sink.add(jsonEncode({'message': text, 'project_id': projectId}));
  }

  // Interrupts a response currently streaming (backend/api/server.py's
  // stream_pipeline_to_websocket polls for exactly this shape between
  // tokens). Sending it when nothing is streaming is harmless - the backend
  // just drops it, per the /ws/chat wire protocol's "one request per turn"
  // rule (Part 15.2).
  void stop() {
    _channel?.sink.add(jsonEncode({'type': 'stop'}));
  }

  // The click on a web search offer (D-45): the backend answers that offer's
  // question again, sending exactly the words the offer showed. Nothing is
  // searched without this; an offer it no longer holds gets an error.
  void approveWebSearch(String offerId) {
    _channel?.sink.add(jsonEncode({'type': 'web_search', 'offer_id': offerId}));
  }

  // Switches to a different conversation (or starts a fresh one, if null) by
  // tearing down the current connection and reconnecting with the new id -
  // ADR-028's "connection = one conversation" extends naturally to "switch
  // conversation = new connection," matching how the backend only ever
  // resolves conversation_id once, at connect time (server.py's ws_chat()).
  void switchConversation(String? conversationId) {
    if (_disposed) return;
    _conversationId = conversationId;
    _subscription?.cancel();
    _channel?.sink.close();
    connect();
  }

  /// Closes the connection for good without tearing the client down.
  ///
  /// Three different closes exist here and they are not interchangeable.
  /// switchConversation closes in order to reconnect. dispose() closes and
  /// also shuts the event and status streams the widget tree is still
  /// listening to. Sign-out needs the one in between: stop talking to the
  /// backend, keep the object usable until the screen goes away.
  ///
  /// Sets _disposed because that flag is what _scheduleReconnect checks.
  /// Without it a bare sink.close() here would be followed a second later by
  /// the reconnect timer reopening the very connection this exists to end -
  /// against a backend that has since locked, so it would fail, and retry.
  void disconnect() {
    _disposed = true;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _subscription?.cancel();
    _channel?.sink.close();
    // After dispose() there is nobody left to tell, and adding to the closed
    // stream threw - reached once a dialog outlived its shell (D-47's review).
    if (!_statusController.isClosed) _statusController.add('disconnected');
  }

  /// Opens the chat again after disconnect(), for a close that turned out not
  /// to end the session: a sign-out the backend refused, a profile delete that
  /// failed (D-49, found reviewing D-47). Both close the chat first, as they
  /// must, and nothing opened it again, so the chat stayed dead - and with no
  /// reconnects, a later lock went unnoticed - until the app was restarted.
  /// After dispose() it does nothing: its streams are closed.
  void reopen() {
    if (_eventController.isClosed) return;
    _disposed = false;
    connect();
  }

  void dispose() {
    _disposed = true;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _subscription?.cancel();
    _channel?.sink.close();
    _eventController.close();
    _statusController.close();
  }
}
