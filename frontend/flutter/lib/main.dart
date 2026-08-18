// PIP - Throwaway Flutter spike (Part 14.1).
//
// "Weeks 3-4: Throwaway Flutter spike (2-3 days). Connects to fake echo
// WebSocket server. Renders streamed tokens in Dart. Tests async stream
// handling. DISCARDED after - de-risks Dart before Phase 8."
//
// This is NOT the real Phase 8+ Flutter client - it does not talk to the real
// PIP backend, has no REST calls, no local storage, nothing beyond what's
// needed to prove Dart can consume a live token stream over a WebSocket and
// render it incrementally. It connects to scripts/fake_echo_server.py, which
// speaks the real Part 14.3 event shape (stage_hint -> token* -> done, or ->
// error) so this is exercising the actual shape the real client will need,
// not an arbitrary echo format.

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

void main() {
  runApp(const SpikeApp());
}

class SpikeApp extends StatelessWidget {
  const SpikeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PIP Flutter Spike',
      theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal)),
      home: const EchoSpikePage(),
    );
  }
}

class ChatTurn {
  final String role; // 'user' | 'assistant'
  final String content;
  const ChatTurn(this.role, this.content);
}

class EchoSpikePage extends StatefulWidget {
  const EchoSpikePage({super.key});

  @override
  State<EchoSpikePage> createState() => _EchoSpikePageState();
}

class _EchoSpikePageState extends State<EchoSpikePage> {
  final TextEditingController _hostController = TextEditingController(text: 'ws://127.0.0.1:8766');
  final TextEditingController _messageController = TextEditingController();
  final List<ChatTurn> _transcript = [];
  final ScrollController _scrollController = ScrollController();

  WebSocketChannel? _channel;
  String _connectionStatus = 'disconnected';
  String _streamingText = '';
  Map<String, dynamic>? _lastStageHint;
  bool _isStreaming = false;
  String? _lastError;

  void _connect() {
    _channel?.sink.close();
    setState(() {
      _connectionStatus = 'connecting';
      _lastError = null;
    });
    try {
      final channel = WebSocketChannel.connect(Uri.parse(_hostController.text));
      _channel = channel;
      channel.stream.listen(
        _handleEvent,
        onDone: () => setState(() => _connectionStatus = 'disconnected'),
        onError: (Object error) => setState(() {
          _connectionStatus = 'error';
          _lastError = error.toString();
        }),
      );
      setState(() => _connectionStatus = 'connected');
    } catch (error) {
      setState(() {
        _connectionStatus = 'error';
        _lastError = error.toString();
      });
    }
  }

  // The whole point of the spike: proving Dart can consume a live async
  // stream of WS frames and update the UI incrementally as they arrive, not
  // just render one complete payload at the end.
  void _handleEvent(dynamic raw) {
    final Map<String, dynamic> event = jsonDecode(raw as String) as Map<String, dynamic>;
    switch (event['type']) {
      case 'stage_hint':
        setState(() => _lastStageHint = event['data'] as Map<String, dynamic>?);
        break;
      case 'token':
        setState(() => _streamingText += event['data'] as String);
        break;
      case 'done':
        setState(() {
          _transcript.add(ChatTurn('assistant', _streamingText));
          _streamingText = '';
          _isStreaming = false;
        });
        _scrollToBottom();
        break;
      case 'error':
        setState(() {
          _lastError = event['data'] as String?;
          _isStreaming = false;
        });
        break;
    }
  }

  void _sendMessage() {
    final text = _messageController.text.trim();
    if (text.isEmpty || _channel == null || _isStreaming) return;

    setState(() {
      _transcript.add(ChatTurn('user', text));
      _streamingText = '';
      _isStreaming = true;
      _lastError = null;
    });
    _channel!.sink.add(jsonEncode({'message': text}));
    _messageController.clear();
    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  void dispose() {
    _channel?.sink.close();
    _hostController.dispose();
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('PIP Flutter Spike - fake echo WS'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _hostController,
                    decoration: const InputDecoration(labelText: 'Fake echo server URL', border: OutlineInputBorder()),
                  ),
                ),
                const SizedBox(width: 8),
                ElevatedButton(onPressed: _connect, child: const Text('Connect')),
                const SizedBox(width: 8),
                Chip(label: Text(_connectionStatus)),
              ],
            ),
          ),
          if (_lastError != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Text(_lastError!, style: const TextStyle(color: Colors.red)),
            ),
          if (_lastStageHint != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              child: Wrap(
                spacing: 8,
                children: _lastStageHint!.entries
                    .map((e) => Chip(label: Text('${e.key}: ${e.value}')))
                    .toList(),
              ),
            ),
          Expanded(
            child: ListView(
              controller: _scrollController,
              padding: const EdgeInsets.all(12),
              children: [
                for (final turn in _transcript) _TurnBubble(turn: turn),
                if (_isStreaming) _TurnBubble(turn: ChatTurn('assistant', _streamingText)),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _messageController,
                    decoration: const InputDecoration(labelText: 'Message', border: OutlineInputBorder()),
                    onSubmitted: (_) => _sendMessage(),
                  ),
                ),
                const SizedBox(width: 8),
                ElevatedButton(onPressed: _isStreaming ? null : _sendMessage, child: const Text('Send')),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TurnBubble extends StatelessWidget {
  final ChatTurn turn;
  const _TurnBubble({required this.turn});

  @override
  Widget build(BuildContext context) {
    final isUser = turn.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.7),
        decoration: BoxDecoration(
          color: isUser ? Colors.teal.shade100 : Colors.grey.shade200,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Text(turn.content),
      ),
    );
  }
}
