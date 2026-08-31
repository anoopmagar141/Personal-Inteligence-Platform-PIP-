// Matches frontend/web/app.js's chat flow: stage_hint is buffered
// (pendingStageHints) and only rendered into the sidebar once done/error
// arrives (Part 14.3: "static display, populated once response completes",
// not a live per-stage animation).
//
// Conversation history sidebar: mirrors Claude/ChatGPT - a list of past
// conversations, a "New chat" button, click to switch. Backed by
// backend/api/server.py's /conversations REST endpoints (list/messages/
// delete) plus the WS wire protocol's session_info event (see
// shared/ws_spec.py) for resuming a conversation's messages and learning a
// freshly (lazily) created conversation's real id.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api_client.dart';
import '../theme.dart';
import '../ws_chat_client.dart';

class _ChatMessage {
  final String role; // 'user' | 'assistant' | 'system'
  final String content;
  final bool stopped; // true if this assistant turn was interrupted by the user
  const _ChatMessage(this.role, this.content, {this.stopped = false});
}

/// Enter-to-send, as an intent so Shift+Enter can still reach the TextField
/// and insert a newline instead.
class _SendIntent extends Intent {
  const _SendIntent();
}

class ChatView extends StatefulWidget {
  final ApiClient api;
  final WsChatClient chatClient;
  final String? activeProjectId;
  const ChatView({super.key, required this.api, required this.chatClient, required this.activeProjectId});

  @override
  State<ChatView> createState() => ChatViewState();
}

class ChatViewState extends State<ChatView> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final _inputFocus = FocusNode();
  final List<_ChatMessage> _transcript = [];
  StreamSubscription? _subscription;

  String _streamingText = '';
  bool _isStreaming = false;
  Map<String, dynamic>? _pendingStageHint;
  Map<String, dynamic>? _lastStageHint;

  String? _activeConversationId;
  List<dynamic>? _conversations;

  /// Width below which the stage-hint panel stops being worth 240px of a
  /// window, and below which the conversation list stops being worth 220.
  ///
  /// The shell's own sidebar is 216 (72 collapsed) and this screen adds 460
  /// more, so at the runner's default 1280x720 the conversation itself gets
  /// about 600px - and nothing stops the window being dragged narrower than
  /// the fixed chrome, at which point the row overflows outright. Neither
  /// panel is dropped without replacement: both stay reachable from the
  /// composer, because a panel that silently vanishes at some width is worse
  /// than one that was never offered.
  static const _hintsBreakpoint = 940.0;
  static const _conversationsBreakpoint = 640.0;

  @override
  void initState() {
    super.initState();
    _subscription = widget.chatClient.events.listen(_handleEvent);
    _loadConversations();
  }

  Future<void> _loadConversations() async {
    try {
      final conversations = await widget.api.getConversations();
      if (mounted) setState(() => _conversations = conversations);
    } catch (_) {
      // Sidebar is a convenience, not the chat's critical path - a failed
      // list load just leaves it empty rather than blocking chat itself.
    }
  }

  void _handleEvent(ChatEvent event) {
    if (!mounted) return;
    switch (event.type) {
      case 'session_info':
        final data = event.data as Map<String, dynamic>;
        final messages = (data['messages'] as List<dynamic>).cast<Map<String, dynamic>>();
        setState(() {
          _activeConversationId = data['conversation_id'] as String?;
          // Only replay when there's something to replay - the lazy-create
          // send (real id, empty messages, mid-turn) must NOT clear a
          // transcript that already has the in-progress turn in it.
          if (messages.isNotEmpty) {
            _transcript
              ..clear()
              ..addAll(messages.map((m) => _ChatMessage(m['role'] as String, m['content'] as String)));
          }
        });
        _loadConversations(); // title/ordering may have changed
        _scrollToBottom();
        return;
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
      case 'stopped':
        setState(() {
          // Whatever streamed in before the stop lands as a normal assistant
          // turn, not discarded - the user still read it, and it belongs in
          // conversation_history the same way the backend keeps it (Part
          // 15.2's server-side counterpart to this).
          _transcript.add(_ChatMessage('assistant', _streamingText, stopped: true));
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

  void _stop() {
    if (!_isStreaming) return;
    widget.chatClient.stop();
    // Not setState(_isStreaming = false) here - the server's own "stopped"
    // event is what actually finalizes the turn (into _transcript, with
    // whatever partial text had streamed in). Flipping the flag locally
    // first would let a fresh _send() race ahead of that event arriving.
  }

  /// Public so the shell's Ctrl+N binding can reach it without this view
  /// having to know a shell exists.
  void newChat() => _newChat();

  void _newChat() {
    if (_activeConversationId == null && _transcript.isEmpty) return; // already a fresh, empty chat
    setState(() {
      _transcript.clear();
      _streamingText = '';
      _isStreaming = false;
      _lastStageHint = null;
      _activeConversationId = null;
    });
    widget.chatClient.switchConversation(null);
    _inputFocus.requestFocus();
  }

  void _switchTo(String conversationId) {
    if (conversationId == _activeConversationId) return;
    setState(() {
      _transcript.clear();
      _streamingText = '';
      _isStreaming = false;
      _lastStageHint = null;
    });
    widget.chatClient.switchConversation(conversationId);
  }

  Future<void> _delete(String conversationId) async {
    await widget.api.deleteConversation(conversationId);
    if (conversationId == _activeConversationId) _newChat();
    await _loadConversations();
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
    _inputFocus.dispose();
    super.dispose();
  }

  Future<void> _showConversationsDialog() async {
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => Dialog(
        child: SizedBox(
          width: 320,
          height: 420,
          child: _ConversationSidebar(
            conversations: _conversations,
            activeConversationId: _activeConversationId,
            bordered: false,
            onNewChat: () {
              Navigator.of(dialogContext).pop();
              _newChat();
            },
            onSelect: (id) {
              Navigator.of(dialogContext).pop();
              _switchTo(id);
            },
            onDelete: _delete,
          ),
        ),
      ),
    );
  }

  Future<void> _showHintsDialog() async {
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => Dialog(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: SizedBox(width: 320, child: _hintPanelContents()),
        ),
      ),
    );
  }

  /// The stage-hint list itself, so the inline panel and the narrow-window
  /// dialog cannot drift apart.
  Widget _hintPanelContents() {
    final pip = context.pip;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const TagLabel('Last response'),
        const SizedBox(height: AppSpacing.md),
        if (_lastStageHint == null)
          Text('No response yet.', style: TextStyle(fontSize: 12.5, color: pip.textFaint))
        else
          for (final entry in _lastStageHint!.entries) _HintRow(label: entry.key, value: entry.value == true),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return LayoutBuilder(
      builder: (context, constraints) {
        final showConversations = constraints.maxWidth >= _conversationsBreakpoint;
        final showHints = constraints.maxWidth >= _hintsBreakpoint;
        return Row(
          children: [
            if (showConversations)
              _ConversationSidebar(
                conversations: _conversations,
                activeConversationId: _activeConversationId,
                onNewChat: _newChat,
                onSelect: _switchTo,
                onDelete: _delete,
              ),
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
                    decoration: BoxDecoration(border: Border(top: BorderSide(color: pip.border))),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        if (!showConversations) ...[
                          _IconAction(
                            icon: Icons.forum_outlined,
                            tooltip: 'Conversations',
                            onTap: _showConversationsDialog,
                          ),
                          const SizedBox(width: AppSpacing.sm),
                        ],
                        Expanded(
                          child: Shortcuts(
                            shortcuts: const {
                              // Enter sends; Shift+Enter falls through to the
                              // TextField and inserts a newline. The field is
                              // multi-line now, so without this binding Enter
                              // would only ever add a line and never send.
                              SingleActivator(LogicalKeyboardKey.enter): _SendIntent(),
                            },
                            child: Actions(
                              actions: {
                                _SendIntent: CallbackAction<_SendIntent>(
                                  onInvoke: (_) {
                                    _send();
                                    return null;
                                  },
                                ),
                              },
                              child: TextField(
                                controller: _controller,
                                focusNode: _inputFocus,
                                style: TextStyle(fontSize: 14.5, color: pip.text),
                                decoration: const InputDecoration(hintText: 'Ask PIP anything...'),
                                minLines: 1,
                                maxLines: 5,
                                enabled: !_isStreaming,
                              ),
                            ),
                          ),
                        ),
                        if (!showHints) ...[
                          const SizedBox(width: AppSpacing.sm),
                          _IconAction(
                            icon: Icons.insights_outlined,
                            tooltip: 'How this answer was built',
                            onTap: _showHintsDialog,
                          ),
                        ],
                        const SizedBox(width: AppSpacing.sm),
                        _isStreaming
                            ? _SendButton(enabled: true, onTap: _stop, icon: Icons.stop_rounded, color: pip.danger)
                            : _SendButton(enabled: true, onTap: _send, icon: Icons.arrow_forward),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            if (showHints)
              Container(
                width: 240,
                decoration: BoxDecoration(
                  color: pip.surface,
                  border: Border(left: BorderSide(color: pip.border)),
                ),
                padding: const EdgeInsets.all(AppSpacing.lg),
                child: _hintPanelContents(),
              ),
          ],
        );
      },
    );
  }
}

/// A small square icon button, standing in for a panel the window is too
/// narrow to show inline.
class _IconAction extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final VoidCallback onTap;
  const _IconAction({required this.icon, required this.tooltip, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Tooltip(
      message: tooltip,
      child: Material(
        color: pip.surfaceRaised,
        borderRadius: AppRadius.sm,
        child: InkWell(
          onTap: onTap,
          borderRadius: AppRadius.sm,
          child: Container(
            width: 40,
            height: 40,
            alignment: Alignment.center,
            child: Icon(icon, size: 18, color: pip.textMuted),
          ),
        ),
      ),
    );
  }
}

/// The Claude/ChatGPT-style conversation list: "New chat" up top, then every
/// past conversation (most recently active first, per the backend's own
/// ordering), each with a delete affordance that only appears on hover.
class _ConversationSidebar extends StatelessWidget {
  final List<dynamic>? conversations;
  final String? activeConversationId;
  final VoidCallback onNewChat;
  final ValueChanged<String> onSelect;
  final ValueChanged<String> onDelete;

  /// False when this is shown in a dialog on a narrow window, where the fixed
  /// width and the right-hand border belong to the dialog instead.
  final bool bordered;

  const _ConversationSidebar({
    required this.conversations,
    required this.activeConversationId,
    required this.onNewChat,
    required this.onSelect,
    required this.onDelete,
    this.bordered = true,
  });

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Container(
      width: bordered ? 220 : null,
      decoration: bordered
          ? BoxDecoration(
              color: pip.surface,
              border: Border(right: BorderSide(color: pip.border)),
            )
          : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: GhostButton(label: '+ New chat', onTap: onNewChat),
          ),
          const Divider(height: 1),
          Expanded(
            child: conversations == null
                ? const SizedBox.shrink()
                : conversations!.isEmpty
                    ? Padding(
                        padding: EdgeInsets.all(AppSpacing.md),
                        child: Text('No conversations yet.', style: TextStyle(fontSize: 12, color: pip.textFaint)),
                      )
                    : ListView(
                        padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
                        children: [
                          for (final conversation in conversations!)
                            _ConversationRow(
                              title: '${conversation['title']}',
                              selected: conversation['id'] == activeConversationId,
                              onTap: () => onSelect(conversation['id'] as String),
                              onDelete: () => onDelete(conversation['id'] as String),
                            ),
                        ],
                      ),
          ),
        ],
      ),
    );
  }
}

class _ConversationRow extends StatefulWidget {
  final String title;
  final bool selected;
  final VoidCallback onTap;
  final VoidCallback onDelete;
  const _ConversationRow({required this.title, required this.selected, required this.onTap, required this.onDelete});

  @override
  State<_ConversationRow> createState() => _ConversationRowState();
}

class _ConversationRowState extends State<_ConversationRow> {
  bool _hovering = false;

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return MouseRegion(
      onEnter: (_) => setState(() => _hovering = true),
      onExit: (_) => setState(() => _hovering = false),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 2),
        child: Material(
          color: widget.selected ? pip.accentSoft : Colors.transparent,
          borderRadius: AppRadius.sm,
          child: InkWell(
            onTap: widget.onTap,
            borderRadius: AppRadius.sm,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      widget.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 13,
                        color: widget.selected ? pip.accent : pip.text,
                        fontWeight: widget.selected ? FontWeight.w600 : FontWeight.w400,
                      ),
                    ),
                  ),
                  if (_hovering)
                    InkWell(
                      onTap: widget.onDelete,
                      borderRadius: AppRadius.sm,
                      child: Padding(
                        padding: EdgeInsets.all(2),
                        child: Icon(Icons.close, size: 14, color: pip.textFaint),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _HintRow extends StatelessWidget {
  final String label;
  final bool value;
  const _HintRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 9),
      decoration: BoxDecoration(border: Border(bottom: BorderSide(color: pip.border))),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(
            child: Text(label, style: TextStyle(fontSize: 12.5, color: pip.textMuted)),
          ),
          Text(
            value ? 'Yes' : 'No',
            style: TextStyle(
              fontSize: 12.5,
              fontWeight: FontWeight.w600,
              color: value ? pip.accent : pip.textFaint,
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
  final IconData icon;
  /// Null means the palette's accent - a default argument has to be a
  /// compile-time constant, which a theme-resolved color cannot be.
  final Color? color;
  const _SendButton({required this.enabled, required this.onTap, required this.icon, this.color});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Material(
      color: enabled ? (color ?? pip.accent) : pip.surfaceRaised,
      borderRadius: AppRadius.sm,
      child: InkWell(
        onTap: enabled ? onTap : null,
        borderRadius: AppRadius.sm,
        child: Container(
          width: 40,
          height: 40,
          alignment: Alignment.center,
          child: Icon(icon, size: 18, color: enabled ? pip.accentOn : pip.textFaint),
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
    final pip = context.pip;
    if (message.role == 'system') {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
        child: Center(
          child: Text(
            message.content,
            style: TextStyle(color: pip.danger, fontSize: 12.5),
          ),
        ),
      );
    }
    final isUser = message.role == 'user';
    final bubble = Column(
      crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: isUser
              ? BoxDecoration(color: pip.accentSoft, borderRadius: AppRadius.md)
              : null,
          // Selectable so an answer can actually be copied out - the whole
          // point of some of them is that they are worth keeping.
          child: SelectableText(
            message.content,
            style: TextStyle(fontSize: 14.5, height: 1.5, color: pip.text),
          ),
        ),
        if (message.stopped) ...[
          const SizedBox(height: 4),
          Text('Stopped', style: TextStyle(fontSize: 11, color: pip.textFaint, fontStyle: FontStyle.italic)),
        ],
      ],
    );
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: AppSpacing.xs + 2),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.5),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: isUser
              ? [Flexible(child: bubble), const SizedBox(width: 8), const _Avatar(isUser: true)]
              : [const _Avatar(isUser: false), const SizedBox(width: 8), Flexible(child: bubble)],
        ),
      ),
    );
  }
}

/// Small circular avatar next to each message (matches 21st.dev's "Message"
/// component from Vercel's AI SDK - a consistent user/assistant marker
/// instead of relying on bubble color/alignment alone).
class _Avatar extends StatelessWidget {
  final bool isUser;
  const _Avatar({required this.isUser});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Container(
      width: 26,
      height: 26,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: isUser ? pip.surfaceRaised : pip.accent,
        shape: BoxShape.circle,
      ),
      child: isUser
          ? Icon(Icons.person_outline, size: 15, color: pip.textMuted)
          : Text('P', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: pip.accentOn)),
    );
  }
}
