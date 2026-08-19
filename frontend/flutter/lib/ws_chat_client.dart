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
  final String type; // 'stage_hint' | 'token' | 'done' | 'error'
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

  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  bool _disposed = false;

  final _eventController = StreamController<ChatEvent>.broadcast();
  final _statusController = StreamController<String>.broadcast();

  Stream<ChatEvent> get events => _eventController.stream;
  Stream<String> get status => _statusController.stream;

  WsChatClient(this.wsUrl, {this.apiToken = '', this.reconnectDelay = const Duration(seconds: 2)});

  void connect() {
    if (_disposed) return;
    _statusController.add('connecting');
    try {
      final uri = Uri.parse(wsUrl).replace(queryParameters: {'token': apiToken});
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

  void dispose() {
    _disposed = true;
    _subscription?.cancel();
    _channel?.sink.close();
    _eventController.close();
    _statusController.close();
  }
}
