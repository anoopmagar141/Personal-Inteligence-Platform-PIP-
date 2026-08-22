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

import 'package:web_socket_channel/web_socket_channel.dart';

class ChatEvent {
  final String type; // 'stage_hint' | 'token' | 'done' | 'error' | 'stopped' | 'session_info'
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

  // The private field's leading underscore shouldn't leak into the
  // constructor's public parameter name, hence the manual assignment below
  // instead of an initializing formal (this._conversationId).
  WsChatClient(this.wsUrl, {this.apiToken = '', this.reconnectDelay = const Duration(seconds: 2), String? conversationId})
      : _conversationId = conversationId; // ignore: prefer_initializing_formals

  void connect() {
    if (_disposed) return;
    _statusController.add('connecting');
    try {
      final uri = Uri.parse(wsUrl).replace(queryParameters: {
        'token': apiToken,
        if (_conversationId != null) 'conversation_id': _conversationId,
      });
      final channel = WebSocketChannel.connect(uri);
      _channel = channel;
      _subscription = channel.stream.listen(
        (raw) {
          final decoded = jsonDecode(raw as String) as Map<String, dynamic>;
          _eventController.add(ChatEvent(decoded['type'] as String, decoded['data']));
        },
        onDone: () {
          _statusController.add('disconnected');
          _scheduleReconnect();
        },
        onError: (Object error) {
          _statusController.add('disconnected');
          _scheduleReconnect();
        },
      );
      _statusController.add('connected');
    } catch (_) {
      _statusController.add('disconnected');
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_disposed) return;
    Future.delayed(reconnectDelay, connect);
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

  void dispose() {
    _disposed = true;
    _subscription?.cancel();
    _channel?.sink.close();
    _eventController.close();
    _statusController.close();
  }
}
