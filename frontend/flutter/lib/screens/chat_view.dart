// Matches frontend/web/app.js's chat flow: stage_hint is buffered
// (pendingStageHints) and only rendered into the sidebar once done/error
// arrives (Part 14.3: "static display, populated once response completes",
// not a live per-stage animation).

import 'dart:async';

import 'package:flutter/material.dart';

import '../theme.dart';
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
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  children: [
                    for (final message in _transcript) _MessageBubble(message: message),
                    if (_isStreaming) _MessageBubble(message: _ChatMessage('assistant', _streamingText)),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.all(AppSpacing.lg),
                decoration: const BoxDecoration(border: Border(top: BorderSide(color: AppColors.border))),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _controller,
                        style: const TextStyle(fontFamily: AppTheme.mono, fontSize: 13.5, color: AppColors.text),
                        decoration: const InputDecoration(hintText: '> ask pip anything...'),
                        onSubmitted: (_) => _send(),
                      ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    _SendButton(enabled: !_isStreaming, onTap: _send),
                  ],
                ),
              ),
            ],
          ),
        ),
        Container(
          width: 240,
          decoration: const BoxDecoration(
            color: AppColors.surface,
            border: Border(left: BorderSide(color: AppColors.border)),
          ),
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const TagLabel('Last response'),
              const SizedBox(height: AppSpacing.md),
              if (_lastStageHint == null)
                const Text('No response yet.', style: TextStyle(fontFamily: AppTheme.mono, fontSize: 12, color: AppColors.textFaint))
              else
                for (final entry in _lastStageHint!.entries) _HintRow(label: entry.key, value: entry.value == true),
            ],
          ),
        ),
      ],
    );
  }
}

class _HintRow extends StatelessWidget {
  final String label;
  final bool value;
  const _HintRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 9),
      decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: AppColors.border))),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(
            child: Text(label, style: const TextStyle(fontFamily: AppTheme.mono, fontSize: 11.5, color: AppColors.textMuted)),
          ),
          Text(
            value ? 'true' : 'false',
            style: TextStyle(
              fontFamily: AppTheme.mono,
              fontSize: 11.5,
              fontWeight: FontWeight.w600,
              color: value ? AppColors.accent : AppColors.textFaint,
            ),
          ),
        ],
      ),
    );
  }
}

class _SendButton extends StatelessWidget {
  final bool enabled;
  final VoidCallback onTap;
  const _SendButton({required this.enabled, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: enabled ? AppColors.accent : AppColors.surfaceRaised,
      borderRadius: AppRadius.sm,
      child: InkWell(
        onTap: enabled ? onTap : null,
        borderRadius: AppRadius.sm,
        child: Container(
          width: 40,
          height: 40,
          alignment: Alignment.center,
          child: Icon(Icons.arrow_forward, size: 18, color: enabled ? AppColors.accentOn : AppColors.textFaint),
        ),
      ),
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
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
        child: Center(
          child: Text(
            message.content,
            style: const TextStyle(fontFamily: AppTheme.mono, color: AppColors.danger, fontSize: 12),
          ),
        ),
      );
    }
    final isUser = message.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: AppSpacing.xs + 2),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.6),
        child: Column(
          crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
          children: [
            if (!isUser) ...[
              const TagLabel('PIP', color: AppColors.accent, size: 10),
              const SizedBox(height: 5),
            ],
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 11),
              decoration: isUser
                  ? BoxDecoration(color: AppColors.surfaceRaised, borderRadius: AppRadius.sm, border: Border.all(color: AppColors.border))
                  : null,
              child: Text(
                message.content,
                style: const TextStyle(fontSize: 14.5, height: 1.5, color: AppColors.text),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
