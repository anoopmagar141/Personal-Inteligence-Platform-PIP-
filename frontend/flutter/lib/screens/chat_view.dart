// Matches frontend/web/app.js's chat flow: stage_hint is buffered
// (pendingStageHints) and only rendered into the sidebar once done/error
// arrives (Part 14.3: "static display, populated once response completes",
// not a live per-stage animation).

import 'dart:async';

import 'package:flutter/material.dart';

import '../ws_chat_client.dart';

class _ChatMessage {
  final String role; // 'user' | 'assistant' | 'system'
  final String content;
  const _ChatMessage(this.role, this.content);
}

class ChatView extends StatefulWidget {
  final WsChatClient chatClient;
  final String? activeProjectId;
  const ChatView({super.key, required this.chatClient, required this.activeProjectId});

  @override
  State<ChatView> createState() => _ChatViewState();
}

class _ChatViewState extends State<ChatView> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final List<_ChatMessage> _transcript = [];
  StreamSubscription? _subscription;

  String _streamingText = '';
  bool _isStreaming = false;
  Map<String, dynamic>? _pendingStageHint;
  Map<String, dynamic>? _lastStageHint;

  @override
  void initState() {
    super.initState();
    _subscription = widget.chatClient.events.listen(_handleEvent);
  }

  void _handleEvent(ChatEvent event) {
    if (!mounted) return;
    switch (event.type) {
      case 'stage_hint':
        _pendingStageHint = event.data as Map<String, dynamic>?;
        break;
      case 'token':
        setState(() => _streamingText += event.data as String);
        return;
      case 'done':
        setState(() {
          _transcript.add(_ChatMessage('assistant', _streamingText));
          _streamingText = '';
          _isStreaming = false;
          _lastStageHint = _pendingStageHint;
          _pendingStageHint = null;
        });
        _scrollToBottom();
        return;
      case 'error':
        setState(() {
          _transcript.add(_ChatMessage('system', 'Error: ${event.data}'));
          _streamingText = '';
          _isStreaming = false;
          _lastStageHint = _pendingStageHint;
          _pendingStageHint = null;
        });
        _scrollToBottom();
        return;
    }
    setState(() {});
  }

  void _send() {
    final text = _controller.text.trim();
    if (text.isEmpty || _isStreaming) return;
    setState(() {
      _transcript.add(_ChatMessage('user', text));
      _streamingText = '';
      _isStreaming = true;
    });
    widget.chatClient.sendMessage(text, projectId: widget.activeProjectId);
    _controller.clear();
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
    _subscription?.cancel();
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Column(
            children: [
              Expanded(
                child: ListView(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(12),
                  children: [
                    for (final message in _transcript) _MessageBubble(message: message),
                    if (_isStreaming) _MessageBubble(message: _ChatMessage('assistant', _streamingText)),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(12),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _controller,
                        decoration: const InputDecoration(
                          labelText: 'Ask PIP anything…',
                          border: OutlineInputBorder(),
                        ),
                        onSubmitted: (_) => _send(),
                      ),
                    ),
                    const SizedBox(width: 8),
                    FilledButton(onPressed: _isStreaming ? null : _send, child: const Text('Send')),
                  ],
                ),
              ),
            ],
          ),
        ),
        SizedBox(
          width: 220,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Last response', style: Theme.of(context).textTheme.titleSmall),
                    const SizedBox(height: 8),
                    if (_lastStageHint == null)
                      const Text('No response yet.', style: TextStyle(color: Colors.grey))
                    else
                      for (final entry in _lastStageHint!.entries)
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 2),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(entry.key),
                              Text(
                                '${entry.value}',
                                style: TextStyle(
                                  color: entry.value == true ? Colors.green : Colors.grey,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                        ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _MessageBubble extends StatelessWidget {
  final _ChatMessage message;
  const _MessageBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    if (message.role == 'system') {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Center(
          child: Text(message.content, style: const TextStyle(color: Colors.grey, fontSize: 12)),
        ),
      );
    }
    final isUser = message.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.6),
        decoration: BoxDecoration(
          color: isUser ? Colors.teal.shade100 : Colors.grey.shade200,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Text(message.content),
      ),
    );
  }
}
