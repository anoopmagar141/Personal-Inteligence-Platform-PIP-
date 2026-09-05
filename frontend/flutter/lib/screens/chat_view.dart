// stage_hint is still buffered and rendered into the sidebar once done/error
// arrives (Part 14.3: "static display, populated once response completes") -
// it summarises a finished turn and that is the right moment for it.
//
// The live per-stage display is a different event and a different question.
// `stage` events (shared/ws_spec.py) arrive as each pipeline stage FINISHES,
// before the first token, and are rendered by ReasoningStrip while the answer
// is being written. Part 14.3 ruled out animating stage_hint, which was
// correct - four booleans sent once cannot describe a process. It did not rule
// out the backend reporting its stages, which is what this consumes.
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
import '../markdown.dart';
import '../profile_picture.dart';
import '../theme.dart';
import '../widgets/aurora_background.dart';
import '../widgets/reasoning_strip.dart';
import '../ws_chat_client.dart';

/// Public, unlike the rest of this file's helpers, so that
/// test/chat_bubble_test.dart can build one directly.
///
/// The alternative was to reach the bubble through ChatView, which means
/// feeding events into a WsChatClient - a socket client with no injection
/// seam. Exposing a presentational widget is a smaller change to production
/// code than adding a test-only door into the network layer.
class ChatMessage {
  final String role; // 'user' | 'assistant' | 'system'
  final String content;
  final bool stopped; // true if this assistant turn was interrupted by the user

  /// When this message was written, in LOCAL time, or null for one that never
  /// came from the database.
  ///
  /// The backend stores UTC and sends it as such; this is converted on the way
  /// in so that everything downstream of here is already in the reader's own
  /// timezone. A transcript resumed on a machine that has since moved should
  /// read in the time that machine keeps.
  ///
  /// Nullable rather than defaulted, because "no time" is a real state and a
  /// fabricated one would be worse than a blank: a system notice has no send
  /// time, and the streaming bubble has not finished being written yet.
  final DateTime? createdAt;

  const ChatMessage(this.role, this.content, {this.stopped = false, this.createdAt});
}

/// The clock time of a message, 24-hour.
///
/// Hand-formatted rather than reached for through package:intl. This project
/// carries one dependency it does not import and documents at length why (see
/// pubspec.yaml on cupertino_icons); adding a localisation package to print
/// four digits would not survive the same scrutiny.
String formatMessageTime(DateTime local) =>
    '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';

const _monthNames = <String>[
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

/// Whether two moments fall on the same calendar day, locally.
///
/// Compared by date parts rather than by subtracting: a difference of under 24
/// hours is not the same question, and across a daylight-saving boundary a
/// "day" is 23 or 25 hours long.
bool isSameDay(DateTime a, DateTime b) =>
    a.year == b.year && a.month == b.month && a.day == b.day;

/// What to call the day a message was sent, for the separator between days.
///
/// "Today" and "Yesterday" are named because those are the two a reader can
/// place without doing arithmetic, and they are most of what a chat history
/// contains. Everything older gets its full date - a bare weekday would be
/// ambiguous the moment a conversation is more than a week old, which is
/// exactly when somebody is scrolling back to find something.
String messageDateLabel(DateTime local, {DateTime? now}) {
  final today = now ?? DateTime.now();
  if (isSameDay(local, today)) return 'Today';
  if (isSameDay(local, today.subtract(const Duration(days: 1)))) return 'Yesterday';
  return '${local.day} ${_monthNames[local.month - 1]} ${local.year}';
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
  final List<ChatMessage> _transcript = [];
  StreamSubscription? _subscription;

  String _streamingText = '';
  bool _isStreaming = false;
  Map<String, dynamic>? _pendingStageHint;
  Map<String, dynamic>? _lastStageHint;

  /// The live pipeline steps for the turn being answered.
  ///
  /// Kept after the answer lands rather than cleared on `done`: "why did it
  /// say that" is asked about the answer already on screen, and a strip that
  /// vanished at the moment the reply appeared would only ever be readable by
  /// someone watching for it. Cleared when the NEXT turn starts.
  List<ReasoningStep> _steps = [];

  String? _activeConversationId;
  List<dynamic>? _conversations;

  /// Whether the sidebar is scoped to the active project.
  ///
  /// Defaults to scoped when a project is selected, because that is the whole
  /// point of selecting one. "All chats" exists because filtering strictly
  /// would otherwise hide every conversation started before a project was
  /// picked, with no way to find them again.
  bool _scopedToProject = true;

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
    // The composer's border colour tracks focus. Without this the field would
    // take focus and keep the resting border until some unrelated setState
    // happened to repaint it.
    _inputFocus.addListener(_onFocusChanged);
    _loadConversations();
  }

  Future<void> _loadConversations() async {
    try {
      final scope = _scopedToProject ? widget.activeProjectId : null;
      final conversations = await widget.api.getConversations(projectId: scope);
      if (mounted) setState(() => _conversations = conversations);
    } catch (_) {
      // Sidebar is a convenience, not the chat's critical path - a failed
      // list load just leaves it empty rather than blocking chat itself.
    }
  }

  @override
  void didUpdateWidget(ChatView oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Switching project on the Projects screen has to change what this list
    // shows, or the scoping silently describes whichever project happened to
    // be active when the view was first built.
    if (oldWidget.activeProjectId != widget.activeProjectId) _loadConversations();
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
              ..addAll(messages.map((m) => ChatMessage(
                    m['role'] as String,
                    m['content'] as String,
                    // Parsed leniently: a message written before created_at
                    // was sent over the wire has none, and an unreadable one
                    // should cost that message its timestamp rather than the
                    // whole transcript its replay.
                    createdAt: DateTime.tryParse(m['created_at'] as String? ?? '')?.toLocal(),
                  )));
          }
        });
        _loadConversations(); // title/ordering may have changed
        _scrollToBottom();
        return;
      case 'stage':
        setState(() => _steps = [
              ..._steps,
              ReasoningStep.fromEvent(event.data as Map<String, dynamic>),
            ]);
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
          _transcript.add(ChatMessage('assistant', _streamingText, createdAt: DateTime.now()));
          _streamingText = '';
          _isStreaming = false;
          _lastStageHint = _pendingStageHint;
          _pendingStageHint = null;
        });
        _scrollToBottom();
        return;
      case 'error':
        setState(() {
          _transcript.add(ChatMessage('system', 'Error: ${event.data}'));
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
          _transcript.add(
            ChatMessage('assistant', _streamingText, stopped: true, createdAt: DateTime.now()),
          );
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

  void _onFocusChanged() {
    if (mounted) setState(() {});
  }

  /// Puts a starter question in the composer without sending it.
  ///
  /// Deliberately not send-on-tap: these are openings, not commands, and the
  /// useful thing is usually the question with a name or a date added to it.
  /// Sending immediately would make the pill a worse version of typing.
  void _prefill(String text) {
    _controller.text = text;
    _controller.selection = TextSelection.collapsed(offset: text.length);
    _inputFocus.requestFocus();
  }

  void _send() {
    final text = _controller.text.trim();
    if (text.isEmpty || _isStreaming) return;
    setState(() {
      _transcript.add(ChatMessage('user', text, createdAt: DateTime.now()));
      _streamingText = '';
      _steps = [];
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
      _steps = [];
      _isStreaming = false;
      _lastStageHint = null;
      _activeConversationId = null;
    });
    widget.chatClient.switchConversation(null);
    _inputFocus.requestFocus();
  }

  void _setScope(bool scoped) {
    if (scoped == _scopedToProject) return;
    setState(() {
      _scopedToProject = scoped;
      _conversations = null;
    });
    _loadConversations();
  }

  void _switchTo(String conversationId) {
    if (conversationId == _activeConversationId) return;
    setState(() {
      _transcript.clear();
      _streamingText = '';
      // Belongs to the turn being left behind. The steps describe how ONE
      // answer was built, and carrying them into another conversation would
      // caption a reply they had nothing to do with.
      _steps = [];
      _isStreaming = false;
      _lastStageHint = null;
    });
    widget.chatClient.switchConversation(conversationId);
  }

  Future<void> _delete(String conversationId) async {
    // Was unguarded, and this is the one delete with no error surface of its
    // own - the sidebar is a list of titles. A conversation that refuses to
    // delete has to say so somewhere, or it silently reappears on the next
    // load and looks like the click was missed.
    try {
      await widget.api.deleteConversation(conversationId);
      if (conversationId == _activeConversationId) _newChat();
      await _loadConversations();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Couldn't delete that conversation: $error")),
      );
    }
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
    _inputFocus.removeListener(_onFocusChanged);
    _controller.dispose();
    _scrollController.dispose();
    _inputFocus.dispose();
    super.dispose();
  }

  Future<void> _showConversationsDialog() async {
    await showDialog<void>(
      context: context,
      // StatefulBuilder because a dialog is its own route: the scope switch
      // calls setState on the SCREEN, which does not rebuild anything inside
      // here. Without it the list reloads correctly and the tab that triggered
      // it stays visibly unselected.
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) => Dialog(
          child: SizedBox(
            width: 320,
            height: 420,
            child: _ConversationSidebar(
              conversations: _conversations,
              activeConversationId: _activeConversationId,
              hasProject: widget.activeProjectId != null,
              scopedToProject: _scopedToProject,
              onScopeChanged: (scoped) {
                _setScope(scoped);
                setDialogState(() {});
              },
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
                hasProject: widget.activeProjectId != null,
                scopedToProject: _scopedToProject,
                onScopeChanged: _setScope,
                onNewChat: _newChat,
                onSelect: _switchTo,
                onDelete: _delete,
              ),
            Expanded(
              child: AuroraBackground(
                child: Column(
                children: [
                  Expanded(
                    // .builder, not ListView(children: [...]): streaming calls
                    // setState once per token, and the eager form rebuilt every
                    // bubble in the transcript on each of those - so the cost of
                    // one reply grew with the length of the whole conversation.
                    // The builder only builds what is on screen, which makes that
                    // per-token cost independent of how long the chat is.
                    child: _transcript.isEmpty && !_isStreaming
                        ? _EmptyChat(onPick: _prefill)
                        : ListView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.all(AppSpacing.lg),
                      // Two extra rows past the transcript: the reasoning strip
                      // (whenever there are steps to show) and the streaming
                      // bubble. The strip comes first because it describes the
                      // answer being written underneath it.
                      itemCount: _transcript.length +
                          (_steps.isNotEmpty || _isStreaming ? 1 : 0) +
                          (_isStreaming ? 1 : 0),
                      itemBuilder: (context, index) {
                        if (index < _transcript.length) {
                          final message = _transcript[index];
                          // A separator wherever the day changes, and above the
                          // first message that has a date at all - so the top of
                          // a resumed transcript says when it started rather
                          // than leaving the reader to infer it from the first
                          // clock time they see.
                          final previous = index > 0 ? _transcript[index - 1].createdAt : null;
                          final showDate = message.createdAt != null &&
                              (previous == null || !isSameDay(previous, message.createdAt!));
                          if (!showDate) {
                            return ChatMessageBubble(message: message);
                          }
                          return Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              _DaySeparator(day: message.createdAt!),
                              ChatMessageBubble(message: message),
                            ],
                          );
                        }
                        if (index == _transcript.length &&
                            (_steps.isNotEmpty || _isStreaming)) {
                          return ReasoningStrip(steps: _steps, active: _isStreaming);
                        }
                        return ChatMessageBubble(
                          message: ChatMessage('assistant', _streamingText),
                        );
                      },
                    ),
                  ),
                  // The composer is a raised card floating on the page rather
                  // than a strip welded to the bottom edge. The old top border
                  // ran the full width and read as a divider between two
                  // regions; this reads as the one thing you type into.
                  Padding(
                    padding: const EdgeInsets.fromLTRB(
                        AppSpacing.lg, AppSpacing.sm, AppSpacing.lg, AppSpacing.lg),
                    child: Center(
                      child: ConstrainedBox(
                        // Matched to the transcript's own comfortable measure.
                        // A composer stretched across an ultrawide window puts
                        // the send button a head-turn away from the text.
                        constraints: const BoxConstraints(maxWidth: 820),
                        child: Container(
                          decoration: BoxDecoration(
                            color: pip.surfaceRaised,
                            borderRadius: AppRadius.lg,
                            border: Border.all(
                              color: _inputFocus.hasFocus ? pip.accent : pip.border,
                              width: _inputFocus.hasFocus ? 1.5 : 1,
                            ),
                          ),
                          padding: const EdgeInsets.fromLTRB(
                              AppSpacing.md, AppSpacing.sm, AppSpacing.sm, AppSpacing.sm),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Shortcuts(
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
                                      style: TextStyle(fontSize: 14.5, color: pip.text, height: 1.45),
                                      // The card draws the border now, so the field
                                      // must not draw a second one inside it.
                                      decoration: InputDecoration(
                                        hintText: 'Ask PIP anything...',
                                        border: InputBorder.none,
                                        enabledBorder: InputBorder.none,
                                        focusedBorder: InputBorder.none,
                                        isDense: true,
                                        contentPadding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
                                        hintStyle: TextStyle(color: pip.textFaint, fontSize: 14.5),
                                      ),
                                      minLines: 1,
                                      maxLines: 8,
                                      enabled: !_isStreaming,
                                    ),
                                  ),
                              ),
                              // Footer: what you can do with the message, kept under
                              // the text rather than beside it, so a long message
                              // grows upward and the controls never move.
                              Row(
                                children: [
                                  if (!showConversations)
                                    _IconAction(
                                      icon: Icons.forum_outlined,
                                      tooltip: 'Conversations',
                                      onTap: _showConversationsDialog,
                                    ),
                                  if (!showHints)
                                    _IconAction(
                                      icon: Icons.insights_outlined,
                                      tooltip: 'How this answer was built',
                                      onTap: _showHintsDialog,
                                    ),
                                  // Both icons are hidden at wide widths,
                                  // because their panels are on screen
                                  // already - which left the footer as a
                                  // Spacer and a button, and a band of empty
                                  // card that read as something failing to
                                  // load. The shortcut is worth saying and
                                  // nothing else was using the space.
                                  if (showConversations && showHints)
                                    Padding(
                                      padding: const EdgeInsets.only(left: AppSpacing.xs),
                                      child: Text(
                                        'Enter to send  ·  Shift+Enter for a new line',
                                        style: TextStyle(fontSize: 11.5, color: pip.textFaint),
                                      ),
                                    ),
                                  const Spacer(),
                                  _isStreaming
                                      ? _SendButton(enabled: true, onTap: _stop, icon: Icons.stop_rounded, color: pip.danger)
                                      : _SendButton(enabled: true, onTap: _send, icon: Icons.arrow_upward_rounded),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
                ),
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

  /// Whether a project is selected at all. With none, there is nothing to
  /// scope to and the toggle would be a control with one setting.
  final bool hasProject;
  final bool scopedToProject;
  final ValueChanged<bool> onScopeChanged;

  /// False when this is shown in a dialog on a narrow window, where the fixed
  /// width and the right-hand border belong to the dialog instead.
  final bool bordered;

  const _ConversationSidebar({
    required this.conversations,
    required this.activeConversationId,
    required this.hasProject,
    required this.scopedToProject,
    required this.onScopeChanged,
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
          if (hasProject)
            Padding(
              padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.md),
              child: Row(
                children: [
                  Expanded(
                    child: _ScopeTab(
                      label: 'This project',
                      selected: scopedToProject,
                      onTap: () => onScopeChanged(true),
                    ),
                  ),
                  const SizedBox(width: 4),
                  Expanded(
                    child: _ScopeTab(
                      label: 'All chats',
                      selected: !scopedToProject,
                      onTap: () => onScopeChanged(false),
                    ),
                  ),
                ],
              ),
            ),
          const Divider(height: 1),
          Expanded(
            child: conversations == null
                ? const SizedBox.shrink()
                : conversations!.isEmpty
                    ? Padding(
                        padding: const EdgeInsets.all(AppSpacing.md),
                        child: Text(
                          // Distinct wording, because these are different
                          // facts: one is about the project, the other about
                          // the whole database.
                          hasProject && scopedToProject
                              ? 'No chats in this project yet.'
                              : 'No conversations yet.',
                          style: TextStyle(fontSize: 12, color: pip.textFaint),
                        ),
                      )
                    // .builder for the same reason as the transcript: this
                    // sidebar is rebuilt by every setState in ChatView, token
                    // events included, so the eager form rebuilt a row per
                    // conversation on every token of every reply.
                    : ListView.builder(
                        padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
                        itemCount: conversations!.length,
                        itemBuilder: (context, index) {
                          final conversation = conversations![index];
                          return _ConversationRow(
                            title: '${conversation['title']}',
                            selected: conversation['id'] == activeConversationId,
                            onTap: () => onSelect(conversation['id'] as String),
                            onDelete: () => onDelete(conversation['id'] as String),
                          );
                        },
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

class ChatMessageBubble extends StatelessWidget {
  final ChatMessage message;
  const ChatMessageBubble({super.key, required this.message});

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
          // Assistant replies are Markdown; the user's own message is not.
          //
          // That asymmetry is deliberate. A local model emits **bold**,
          // backticks and fenced blocks constantly, and printing them raw
          // makes a correct answer look worse than it is. What the USER typed
          // is theirs, and re-rendering it would change what they said - a
          // filename with asterisks in it would silently lose them, and they
          // would have no way to tell.
          //
          // Both stay selectable: an answer is often the thing worth keeping.
          child: isUser
              ? SelectableText(
                  message.content,
                  style: TextStyle(fontSize: 14.5, height: 1.5, color: pip.text),
                )
              : MarkdownBody(
                  source: message.content,
                  baseStyle: TextStyle(fontSize: 14.5, height: 1.5, color: pip.text),
                ),
        ),
        // Time and interruption on one line under the bubble, kept as two
        // Texts rather than one joined string so each reads on its own - the
        // clock time is plain and "Stopped" is a caveat about the content.
        if (message.createdAt != null || message.stopped) ...[
          const SizedBox(height: 4),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (message.createdAt != null)
                Text(
                  formatMessageTime(message.createdAt!),
                  style: TextStyle(fontSize: 11, color: pip.textFaint),
                ),
              if (message.createdAt != null && message.stopped)
                Text('  ·  ', style: TextStyle(fontSize: 11, color: pip.textFaint)),
              if (message.stopped)
                Text('Stopped', style: TextStyle(fontSize: 11, color: pip.textFaint, fontStyle: FontStyle.italic)),
            ],
          ),
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

    // The assistant's marker is fixed; only the user's can be a photograph.
    if (!isUser) {
      return Container(
        width: 26,
        height: 26,
        alignment: Alignment.center,
        decoration: BoxDecoration(color: pip.accent, shape: BoxShape.circle),
        child: Text('P', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: pip.accentOn)),
      );
    }

    // Listened to rather than passed in: this widget is rebuilt once per
    // message on screen, and threading the bytes down from ChatView would put
    // a parameter through three widgets that have no use for it.
    return ValueListenableBuilder<Uint8List?>(
      valueListenable: profilePicture,
      builder: (context, picture, _) {
        return Container(
          width: 26,
          height: 26,
          alignment: Alignment.center,
          clipBehavior: Clip.antiAlias,
          decoration: BoxDecoration(
            color: pip.surfaceRaised,
            shape: BoxShape.circle,
          ),
          child: picture == null
              ? Icon(Icons.person_outline, size: 15, color: pip.textMuted)
              : Image.memory(
                  picture,
                  fit: BoxFit.cover,
                  width: 26,
                  height: 26,
                  // gaplessPlayback so replacing the picture swaps it in place
                  // instead of blanking every avatar on screen for a frame
                  // while the new bytes decode.
                  gaplessPlayback: true,
                ),
        );
      },
    );
  }
}


/// One half of the sidebar's scope switch.
class _ScopeTab extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _ScopeTab({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Material(
      color: selected ? pip.accentSoft : Colors.transparent,
      borderRadius: AppRadius.sm,
      child: InkWell(
        onTap: onTap,
        borderRadius: AppRadius.sm,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Text(
            label,
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 11.5,
              fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
              color: selected ? pip.accent : pip.textMuted,
            ),
          ),
        ),
      ),
    );
  }
}


/// The dated rule between one day's messages and the next.
///
/// A centred label on a hairline rather than a heading: it marks a boundary
/// between turns rather than starting a section, and the transcript's own
/// hierarchy is the conversation, not the calendar.
class _DaySeparator extends StatelessWidget {
  final DateTime day;
  const _DaySeparator({required this.day});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
      child: Row(
        children: [
          Expanded(child: Divider(color: pip.border, height: 1)),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
            child: Text(
              messageDateLabel(day),
              style: TextStyle(
                fontSize: 11,
                color: pip.textFaint,
                letterSpacing: 0.3,
              ),
            ),
          ),
          Expanded(child: Divider(color: pip.border, height: 1)),
        ],
      ),
    );
  }
}

/// What an empty conversation shows instead of a blank column.
///
/// The starters are PIP-specific on purpose. A generic set ("Generate code",
/// "Launch app") would be decoration; these each exercise a real part of the
/// pipeline a newcomer would not otherwise know exists - the decision log, the
/// document index, the warm-start gap detector - and tapping one only fills
/// the composer, so the question can be finished before it is asked.
class _EmptyChat extends StatelessWidget {
  final void Function(String) onPick;
  const _EmptyChat({required this.onPick});

  static const _starters = <({IconData icon, String label, String prompt})>[
    (
      icon: Icons.fact_check_outlined,
      label: 'A past decision',
      prompt: 'What did I decide about ',
    ),
    (
      icon: Icons.description_outlined,
      label: 'My documents',
      prompt: 'What do my documents say about ',
    ),
    (
      icon: Icons.history_outlined,
      label: 'Where we left off',
      prompt: 'Where were we?',
    ),
    (
      icon: Icons.person_outline,
      label: 'What PIP knows',
      prompt: 'What do you know about me?',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSpacing.xl),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 620),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const SizedBox(height: AppSpacing.xl),
              Text(
                'What are you working on?',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700, color: pip.text),
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                'PIP remembers your decisions, your documents and your projects, '
                'and will say which of them an answer came from.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 13.5, color: pip.textMuted, height: 1.55),
              ),
              const SizedBox(height: AppSpacing.xl),
              Wrap(
                alignment: WrapAlignment.center,
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.sm,
                children: [
                  for (final starter in _starters)
                    _StarterPill(
                      icon: starter.icon,
                      label: starter.label,
                      onTap: () => onPick(starter.prompt),
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StarterPill extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _StarterPill({required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: AppRadius.lg,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: 10),
          decoration: BoxDecoration(
            color: pip.surface,
            borderRadius: AppRadius.lg,
            border: Border.all(color: pip.border),
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, size: 15, color: pip.textMuted),
            const SizedBox(width: AppSpacing.sm),
            Text(label, style: TextStyle(fontSize: 12.5, color: pip.text)),
          ]),
        ),
      ),
    );
  }
}
