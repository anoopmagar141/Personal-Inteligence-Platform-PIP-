// Sidebar shell matching frontend/web/index.html's #tabs bar: Chat / Profile /
// Decisions / Projects / Documents / Providers, plus a connection-status
// indicator for the WS chat connection. IndexedStack keeps every view's state
// alive across tab switches (chat transcript, in-progress form fields), the
// same way the web client's CSS-hidden <section> views never leave the DOM.
//
// A left sidebar rather than a top tab bar (matches 21st.dev's "Dashboard
// with Collapsible Sidebar" reference) - six tabs was starting to crowd a
// horizontal bar, and a sidebar scales further without needing to shrink
// labels or wrap. Collapsible to icon-only for more content width.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api_client.dart';
import 'screens/chat_view.dart';
import 'screens/decisions_view.dart';
import 'screens/documents_view.dart';
import 'screens/profile_view.dart';
import 'screens/projects_view.dart';
import 'screens/providers_view.dart';
import 'screens/review_view.dart';
import 'screens/trace_view.dart';
import 'theme.dart';
import 'ws_chat_client.dart';

class HomeShell extends StatefulWidget {
  final ApiClient api;
  final ThemeMode themeMode;
  final VoidCallback onCycleTheme;
  const HomeShell({
    super.key,
    required this.api,
    required this.themeMode,
    required this.onCycleTheme,
  });

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  static const _tabs = ['Chat', 'Review', 'Profile', 'Decisions', 'Projects', 'Documents', 'Providers', 'Trace'];
  static const _tabIcons = <IconData>[
    Icons.chat_bubble_outline,
    Icons.rule,
    Icons.person_outline,
    Icons.fact_check_outlined,
    Icons.folder_outlined,
    Icons.description_outlined,
    Icons.power_settings_new,
    Icons.timeline_outlined,
  ];
  static const _reviewIndex = 1;
  static const _traceIndex = 7;

  /// Ctrl+1..8 jump straight to a tab, in sidebar order. Eight tabs is enough
  /// that reaching for the mouse to check the review queue mid-thought is a
  /// real interruption, and the digits map to what the sidebar already shows
  /// rather than to a second thing to memorise.
  static final Map<ShortcutActivator, Intent> _shortcuts = {
    for (var i = 0; i < _tabs.length; i++)
      SingleActivator(
        [
          LogicalKeyboardKey.digit1,
          LogicalKeyboardKey.digit2,
          LogicalKeyboardKey.digit3,
          LogicalKeyboardKey.digit4,
          LogicalKeyboardKey.digit5,
          LogicalKeyboardKey.digit6,
          LogicalKeyboardKey.digit7,
          LogicalKeyboardKey.digit8,
        ][i],
        control: true,
      ): _SelectTabIntent(i),
    const SingleActivator(LogicalKeyboardKey.keyN, control: true): const _NewChatIntent(),
  };

  /// Lets Ctrl+N reach the chat's own "new chat" without this shell knowing
  /// anything about how a conversation is started.
  final GlobalKey<ChatViewState> _chatKey = GlobalKey<ChatViewState>();

  late final WsChatClient _chatClient;
  int _selectedIndex = 0;
  String _connectionStatus = 'connecting';
  String? _activeProjectId;
  bool _collapsed = false;
  int _pendingCount = 0;
  // IndexedStack keeps ReviewView alive for the app's lifetime, so its
  // initState runs exactly once. Bumping this on each selection is what makes
  // reopening the tab actually re-read the queue.
  int _reviewEpoch = 0;
  // Same for Trace, and more sharply: a trace is written by every message, so
  // a view that only loaded at startup would be stale by the first reply.
  int _traceEpoch = 0;

  @override
  void initState() {
    super.initState();
    _chatClient = WsChatClient(_wsUrlFromApiBase(widget.api.baseUrl), apiToken: widget.api.apiToken);
    _chatClient.status.listen((status) {
      if (mounted) setState(() => _connectionStatus = status);
    });
    _chatClient.connect();
    _refreshPendingCount();
  }

  /// Read at startup rather than only when the Review tab is opened. The
  /// Observer runs at session end, so a queue filled by the previous
  /// conversation would otherwise sit unnoticed until the user happened to
  /// look - which is the failure the badge exists to prevent.
  ///
  /// Fails quietly: a badge is an affordance, and a backend hiccup must not put
  /// an error in front of someone who was trying to open a chat.
  Future<void> _refreshPendingCount() async {
    try {
      final status = await widget.api.getStatus();
      final waiting = ((status['pending_memory'] ?? 0) as num).toInt() +
          ((status['pending_decisions'] ?? 0) as num).toInt();
      if (mounted) setState(() => _pendingCount = waiting);
    } catch (_) {
      if (mounted) setState(() => _pendingCount = 0);
    }
  }

  void _selectTab(int index) {
    setState(() {
      _selectedIndex = index;
      if (index == _reviewIndex) _reviewEpoch++;
      if (index == _traceIndex) _traceEpoch++;
    });
  }

  static String _wsUrlFromApiBase(String apiBase) {
    // http://host:port/api/v1 -> ws://host:port/ws/chat
    final uri = Uri.parse(apiBase);
    final scheme = uri.scheme == 'https' ? 'wss' : 'ws';
    return '$scheme://${uri.authority}/ws/chat';
  }

  @override
  void dispose() {
    _chatClient.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final connected = _connectionStatus == 'connected';
    return Shortcuts(
      shortcuts: _shortcuts,
      child: Actions(
        actions: {
          _SelectTabIntent: CallbackAction<_SelectTabIntent>(
            onInvoke: (intent) {
              _selectTab(intent.index);
              return null;
            },
          ),
          _NewChatIntent: CallbackAction<_NewChatIntent>(
            onInvoke: (_) {
              // Jump to Chat first: starting a new conversation from the
              // Providers screen and staying there would look like nothing
              // happened.
              _selectTab(0);
              _chatKey.currentState?.newChat();
              return null;
            },
          ),
        },
        // autofocus so the bindings are live from launch rather than only
        // after something inside the shell has been clicked.
        child: Focus(
          autofocus: true,
          child: _shell(connected),
        ),
      ),
    );
  }

  Widget _shell(bool connected) {
    final pip = context.pip;
    return Scaffold(
      body: Row(
        children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 160),
            width: _collapsed ? 72 : 216,
            decoration: BoxDecoration(
              color: pip.surface,
              border: Border(right: BorderSide(color: pip.border)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.md),
                  child: Row(
                    mainAxisAlignment: _collapsed ? MainAxisAlignment.center : MainAxisAlignment.spaceBetween,
                    children: [
                      if (!_collapsed)
                        Text('PIP', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18, color: pip.accent)),
                      InkWell(
                        onTap: () => setState(() => _collapsed = !_collapsed),
                        borderRadius: AppRadius.sm,
                        child: Padding(
                          padding: const EdgeInsets.all(4),
                          child: Icon(_collapsed ? Icons.chevron_right : Icons.chevron_left, size: 18, color: pip.textMuted),
                        ),
                      ),
                    ],
                  ),
                ),
                for (var i = 0; i < _tabs.length; i++)
                  _SidebarItem(
                    label: _tabs[i],
                    icon: _tabIcons[i],
                    selected: _selectedIndex == i,
                    collapsed: _collapsed,
                    badge: i == _reviewIndex ? _pendingCount : 0,
                    onTap: () => _selectTab(i),
                  ),
                const Spacer(),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                  child: _ThemeToggle(
                    mode: widget.themeMode,
                    collapsed: _collapsed,
                    onTap: widget.onCycleTheme,
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: _ConnectionPill(connected: connected, status: _connectionStatus, collapsed: _collapsed),
                ),
              ],
            ),
          ),
          Expanded(
            child: IndexedStack(
              index: _selectedIndex,
              children: [
                ChatView(
                  key: _chatKey,
                  api: widget.api,
                  chatClient: _chatClient,
                  activeProjectId: _activeProjectId,
                ),
                ReviewView(
                  api: widget.api,
                  refreshToken: _reviewEpoch,
                  onQueueChanged: _refreshPendingCount,
                ),
                ProfileView(api: widget.api),
                DecisionsView(api: widget.api, activeProjectId: _activeProjectId),
                ProjectsView(
                  api: widget.api,
                  activeProjectId: _activeProjectId,
                  // Nullable: archiving or completing the project the chat is
                  // pointed at clears the pointer rather than leaving new
                  // conversation filed against a project just put away.
                  onActivate: (id) => setState(() => _activeProjectId = id),
                  // The shell owns both halves of "start a chat here": which
                  // tab is showing, and telling the chat to begin a fresh
                  // conversation. ProjectsView knows neither, and should not.
                  onStartChat: (id) {
                    setState(() => _activeProjectId = id);
                    _selectTab(0);
                    _chatKey.currentState?.newChat();
                  },
                ),
                DocumentsView(api: widget.api, activeProjectId: _activeProjectId),
                ProvidersView(api: widget.api),
                TraceView(api: widget.api, refreshToken: _traceEpoch),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SidebarItem extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool selected;
  final bool collapsed;
  final int badge;
  final VoidCallback onTap;
  const _SidebarItem({
    required this.label,
    required this.icon,
    required this.selected,
    required this.collapsed,
    required this.onTap,
    this.badge = 0,
  });

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    final pill = Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
      decoration: BoxDecoration(color: pip.accent, borderRadius: AppRadius.sm),
      child: Text(
        '$badge',
        style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, color: pip.accentOn),
      ),
    );
    final row = Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Collapsed to icons, the count still has to be visible or the sidebar
        // silently stops telling you PIP is waiting on something.
        if (collapsed && badge > 0)
          Badge(
            label: Text('$badge', style: const TextStyle(fontSize: 9)),
            backgroundColor: pip.accent,
            child: Icon(icon, size: 18, color: selected ? pip.accent : pip.textMuted),
          )
        else
          Icon(icon, size: 18, color: selected ? pip.accent : pip.textMuted),
        if (!collapsed) ...[
          const SizedBox(width: 12),
          Text(label, style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: selected ? pip.accent : pip.textMuted)),
          if (badge > 0) ...[const SizedBox(width: 8), pill],
        ],
      ],
    );
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 2),
      child: Material(
        color: selected ? pip.accentSoft : Colors.transparent,
        borderRadius: AppRadius.sm,
        child: InkWell(
          onTap: onTap,
          borderRadius: AppRadius.sm,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
            child: collapsed ? Center(child: row) : row,
          ),
        ),
      ),
    );
  }
}

class _ConnectionPill extends StatelessWidget {
  final bool connected;
  final String status;
  final bool collapsed;
  const _ConnectionPill({required this.connected, required this.status, required this.collapsed});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    final dot = Container(
      width: 7,
      height: 7,
      decoration: BoxDecoration(
        color: connected ? pip.accent : pip.textFaint,
        shape: BoxShape.circle,
        boxShadow: connected ? [BoxShadow(color: pip.accent, blurRadius: 5)] : null,
      ),
    );
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(color: pip.surfaceRaised, borderRadius: AppRadius.sm),
      child: collapsed
          ? Center(child: dot)
          : Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                dot,
                const SizedBox(width: 7),
                TagLabel(status, color: connected ? pip.accent : pip.textMuted, size: 10.5),
              ],
            ),
    );
  }
}

/// `Ctrl+<n>` - switch to the nth sidebar tab.
class _SelectTabIntent extends Intent {
  final int index;
  const _SelectTabIntent(this.index);
}

/// Ctrl+N - start a new conversation, from wherever you are.
class _NewChatIntent extends Intent {
  const _NewChatIntent();
}

/// Cycles the app between following the OS, forced light, and forced dark.
///
/// Labelled with what it currently IS, not with what tapping it would do - a
/// three-state control whose caption describes the next state leaves you
/// unable to tell which one you are in.
class _ThemeToggle extends StatelessWidget {
  final ThemeMode mode;
  final bool collapsed;
  final VoidCallback onTap;
  const _ThemeToggle({required this.mode, required this.collapsed, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    final (icon, label) = switch (mode) {
      ThemeMode.system => (Icons.brightness_auto_outlined, 'System theme'),
      ThemeMode.light => (Icons.light_mode_outlined, 'Light'),
      ThemeMode.dark => (Icons.dark_mode_outlined, 'Dark'),
    };
    return Tooltip(
      message: '$label - click to change',
      child: Material(
        color: Colors.transparent,
        borderRadius: AppRadius.sm,
        child: InkWell(
          onTap: onTap,
          borderRadius: AppRadius.sm,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
            child: Row(
              mainAxisAlignment: collapsed ? MainAxisAlignment.center : MainAxisAlignment.start,
              children: [
                Icon(icon, size: 17, color: pip.textMuted),
                if (!collapsed) ...[
                  const SizedBox(width: 10),
                  Text(label, style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: pip.textMuted)),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
