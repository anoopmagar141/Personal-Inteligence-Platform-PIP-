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

import 'api_client.dart';
import 'screens/chat_view.dart';
import 'screens/decisions_view.dart';
import 'screens/documents_view.dart';
import 'screens/profile_view.dart';
import 'screens/projects_view.dart';
import 'screens/providers_view.dart';
import 'screens/review_view.dart';
import 'theme.dart';
import 'ws_chat_client.dart';

class HomeShell extends StatefulWidget {
  final ApiClient api;
  const HomeShell({super.key, required this.api});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  static const _tabs = ['Chat', 'Review', 'Profile', 'Decisions', 'Projects', 'Documents', 'Providers'];
  static const _tabIcons = <IconData>[
    Icons.chat_bubble_outline,
    Icons.rule,
    Icons.person_outline,
    Icons.fact_check_outlined,
    Icons.folder_outlined,
    Icons.description_outlined,
    Icons.power_settings_new,
  ];
  static const _reviewIndex = 1;

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
    return Scaffold(
      body: Row(
        children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 160),
            width: _collapsed ? 72 : 216,
            decoration: const BoxDecoration(
              color: AppColors.surface,
              border: Border(right: BorderSide(color: AppColors.border)),
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
                        const Text('PIP', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18, color: AppColors.accent)),
                      InkWell(
                        onTap: () => setState(() => _collapsed = !_collapsed),
                        borderRadius: AppRadius.sm,
                        child: Padding(
                          padding: const EdgeInsets.all(4),
                          child: Icon(_collapsed ? Icons.chevron_right : Icons.chevron_left, size: 18, color: AppColors.textMuted),
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
                  onActivate: (id) => setState(() => _activeProjectId = id),
                ),
                DocumentsView(api: widget.api, activeProjectId: _activeProjectId),
                ProvidersView(api: widget.api),
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
    final pill = Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
      decoration: const BoxDecoration(color: AppColors.accent, borderRadius: AppRadius.sm),
      child: Text(
        '$badge',
        style: const TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, color: AppColors.accentOn),
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
            backgroundColor: AppColors.accent,
            child: Icon(icon, size: 18, color: selected ? AppColors.accent : AppColors.textMuted),
          )
        else
          Icon(icon, size: 18, color: selected ? AppColors.accent : AppColors.textMuted),
        if (!collapsed) ...[
          const SizedBox(width: 12),
          Text(label, style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: selected ? AppColors.accent : AppColors.textMuted)),
          if (badge > 0) ...[const SizedBox(width: 8), pill],
        ],
      ],
    );
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 2),
      child: Material(
        color: selected ? AppColors.accentSoft : Colors.transparent,
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
    final dot = Container(
      width: 7,
      height: 7,
      decoration: BoxDecoration(
        color: connected ? AppColors.accent : AppColors.textFaint,
        shape: BoxShape.circle,
        boxShadow: connected ? [const BoxShadow(color: AppColors.accent, blurRadius: 5)] : null,
      ),
    );
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(color: AppColors.surfaceRaised, borderRadius: AppRadius.sm),
      child: collapsed
          ? Center(child: dot)
          : Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                dot,
                const SizedBox(width: 7),
                TagLabel(status, color: connected ? AppColors.accent : AppColors.textMuted, size: 10.5),
              ],
            ),
    );
  }
}
