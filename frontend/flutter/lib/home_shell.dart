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
import 'main.dart' show kDataDir;
import 'screens/backup_view.dart';
import 'screens/chat_view.dart';
import 'screens/decisions_view.dart';
import 'screens/documents_view.dart';
import 'screens/profile_view.dart';
import 'screens/projects_view.dart';
import 'screens/providers_view.dart';
import 'screens/review_view.dart';
import 'screens/sign_in_screen.dart' show AuthState, authStateFrom;
import 'screens/trace_view.dart';
import 'theme.dart';
import 'ws_chat_client.dart';

class HomeShell extends StatefulWidget {
  final ApiClient api;
  final ThemeMode themeMode;
  final VoidCallback onCycleTheme;
  final VoidCallback onSignedOut;

  /// The chat dropped and the backend is no longer unlocked, or no longer takes
  /// this app's token (a restart): the chat socket will be refused for as long
  /// as that is true, so the app has to go back to where it signs in (D-47).
  /// Only a drop asks: a lock from somewhere else leaves an open chat socket
  /// open (server.py's auth_lock), so it is not noticed here.
  final VoidCallback onBackendLocked;

  /// The chat connection to use instead of a real one. Tests only.
  final WsChatClient? chatClient;
  const HomeShell({
    super.key,
    required this.api,
    required this.themeMode,
    required this.onCycleTheme,
    required this.onSignedOut,
    required this.onBackendLocked,
    @visibleForTesting this.chatClient,
  });

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  static const _tabs = ['Chat', 'Review', 'Profile', 'Decisions', 'Projects', 'Documents', 'Providers', 'Backup', 'Trace'];
  static const _tabIcons = <IconData>[
    Icons.chat_bubble_outline,
    Icons.rule,
    Icons.person_outline,
    Icons.fact_check_outlined,
    Icons.folder_outlined,
    Icons.description_outlined,
    Icons.power_settings_new,
    Icons.shield_outlined,
    Icons.timeline_outlined,
  ];
  static const _reviewIndex = 1;
  static const _backupIndex = 7;
  static const _traceIndex = 8;

  /// Ctrl+1..9 jump straight to a tab, in sidebar order. Nine tabs is enough
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
          LogicalKeyboardKey.digit9,
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

  /// Lets opening the Backup tab re-list what is on disk.
  ///
  /// A key rather than an epoch, unlike Review and Trace above, because the
  /// thing that goes stale here is not a query this shell could re-issue: the
  /// .pipbak files are written by a console window the app deliberately does
  /// not watch (see backup_view.dart on why the export is not an endpoint), so
  /// nothing arrives to tell it to look again. Re-listing when the tab is
  /// opened is the moment the user expects the answer to be current.
  final GlobalKey<BackupViewState> _backupKey = GlobalKey<BackupViewState>();

  /// This shell closed the chat itself (sign-out, a profile deleted) or has
  /// handed back to the sign-in screen: a drop from here on is not news.
  bool _leaving = false;
  bool _askingWhetherLocked = false;

  @override
  void initState() {
    super.initState();
    _chatClient = widget.chatClient ?? WsChatClient(_wsUrlFromApiBase(widget.api.baseUrl), apiToken: widget.api.apiToken);
    _chatClient.status.listen((status) {
      if (mounted) setState(() => _connectionStatus = status);
      if (status == 'disconnected') _askWhetherStillUnlocked();
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

  /// A dropped chat asks the backend whether it is still unlocked (D-47).
  ///
  /// Found by V-1 (FREEZE_LIST §7.71): the backend was started again and came
  /// back locked, it refused the chat socket for as long as it stayed locked,
  /// and nothing took the window back to sign-in, so the chat could not resume
  /// there. The refusal itself says nothing: the server closes the socket
  /// before accepting it, so this end sees a failed handshake, not its 4423.
  /// /auth/state is the answer the start screen already asks for, and it is
  /// open while locked. Anything but "unlocked" stops the chat and hands back
  /// to the root, which asks again and shows the sign-in screen the backend
  /// needs. No answer (stopped, or still starting) decides nothing: the
  /// client keeps trying, one attempt at a time. One question at a time too:
  /// a drop that arrives while one is out is answered by it.
  Future<void> _askWhetherStillUnlocked() async {
    if (_leaving || _askingWhetherLocked) return;
    _askingWhetherLocked = true;
    try {
      final state = authStateFrom(await widget.api.authState());
      if (!mounted || _leaving || state == AuthState.unlocked) return;
      _handBack();
    } on ApiException catch (error) {
      // A 401 is an answer: this backend no longer takes the token this shell
      // holds (it was started again with a new one). The start screen re-reads
      // the token file and this shell cannot, so it goes back there (found
      // reviewing D-47; before, it reconnected with the old token forever).
      if (mounted && !_leaving && error.statusCode == 401) _handBack();
    } catch (_) {
      // Not answering: nothing to decide yet.
    } finally {
      _askingWhetherLocked = false;
    }
  }

  /// Stops the chat and hands back to the root.
  ///
  /// Any dialog this shell opened is closed first. Dialogs sit on the root
  /// navigator, above the screen the root swaps, so one left open (Sign out?,
  /// Delete profile) was drawn over the sign-in screen, and confirming it ran
  /// code of a shell that was gone (found reviewing D-47).
  void _handBack() {
    _leaving = true;
    _chatClient.disconnect();
    Navigator.of(context).popUntil((route) => route.isFirst);
    widget.onBackendLocked();
  }

  /// Closes the chat for a reason of this app's own (a profile being deleted),
  /// which is not the backend locking under it.
  void _closeChat() {
    _leaving = true;
    _chatClient.disconnect();
  }

  /// Locks the database and returns to the sign-in screen.
  ///
  /// Confirmed first, because the cost of a misclick here is not symmetric:
  /// signing out takes one click and getting back in takes the password, in
  /// the middle of whatever the person was saying.
  ///
  /// The socket is closed BEFORE the call, not after. /auth/lock persists the
  /// transcripts of every session the registry knows about, so leaving a live
  /// connection open across it means the turns typed after that point belong
  /// to a session already enqueued - and the server would have no way to reach
  /// them again. Closing first makes the enqueue the last word on this
  /// conversation, which is what it claims to be.
  Future<void> _signOut() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Sign out?'),
        content: const Text(
          'PIP will close your data and ask for your password again. '
          'Anything said this session is saved first.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Sign out')),
        ],
      ),
    );
    if (confirmed != true) return;

    _closeChat();
    try {
      await widget.api.lock();
    } catch (error) {
      // Reported rather than swallowed, and the screen does NOT change: a
      // failed lock means the data is still open, and sending somebody to a
      // sign-in screen over an unlocked database would be the one outcome
      // worse than the error itself.
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not sign out: $error')),
        );
      }
      return;
    }
    widget.onSignedOut();
  }

  void _selectTab(int index) {
    setState(() {
      _selectedIndex = index;
      if (index == _reviewIndex) _reviewEpoch++;
      if (index == _traceIndex) _traceEpoch++;
    });
    // Outside setState: BackupView lives in the IndexedStack and is already
    // mounted, so this is a call on an existing state object rather than a
    // rebuild of this shell.
    if (index == _backupIndex) _backupKey.currentState?.refresh();
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
                  // Narrower sides when collapsed: 72px less 24px each side
                  // left 24px for a 26px toggle, which clipped it by 2px.
                  // Found by control_labels_test, the first test to collapse
                  // the sidebar.
                  padding: EdgeInsets.fromLTRB(
                    _collapsed ? AppSpacing.md : AppSpacing.lg,
                    AppSpacing.lg,
                    _collapsed ? AppSpacing.md : AppSpacing.lg,
                    AppSpacing.md,
                  ),
                  child: Row(
                    mainAxisAlignment: _collapsed ? MainAxisAlignment.center : MainAxisAlignment.spaceBetween,
                    children: [
                      if (!_collapsed)
                        Text('PIP', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18, color: pip.accent)),
                      // A chevron alone is "button" to a screen reader. The
                      // Tooltip is what gives it a name (control_labels_test).
                      Tooltip(
                        message: _collapsed ? 'Expand sidebar' : 'Collapse sidebar',
                        child: InkWell(
                          onTap: () => setState(() => _collapsed = !_collapsed),
                          borderRadius: AppRadius.sm,
                          child: Padding(
                            padding: const EdgeInsets.all(4),
                            child: Icon(_collapsed ? Icons.chevron_right : Icons.chevron_left, size: 18, color: pip.textMuted),
                          ),
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
                _SidebarItem(
                  label: 'Sign out',
                  icon: Icons.lock_outline,
                  selected: false,
                  collapsed: _collapsed,
                  onTap: _signOut,
                ),
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
                ProfileView(
                  api: widget.api,
                  // Deleting a profile signs you out of it, because the files
                  // the key belongs to stop existing. The socket is closed
                  // first for the same two reasons sign-out closes it - the
                  // transcript enqueue has to be the last word on the
                  // conversation, and the backend cannot delete a database
                  // file this client still has open.
                  onCloseChat: _closeChat,
                  onSignedOut: widget.onSignedOut,
                ),
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
                BackupView(key: _backupKey, dataDir: kDataDir, api: widget.api),
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
    final item = Material(
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
    );
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 2),
      // Collapsed, the label Text is gone and the item is an icon. The tooltip
      // puts the name back, for the mouse and for a screen reader alike.
      // Expanded, the visible label already names it, and a tooltip repeating
      // it would only be noise.
      child: collapsed ? Tooltip(message: label, child: item) : item,
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
