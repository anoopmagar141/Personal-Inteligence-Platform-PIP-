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
import 'theme.dart';
import 'ws_chat_client.dart';

class HomeShell extends StatefulWidget {
  final ApiClient api;
  const HomeShell({super.key, required this.api});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  static const _tabs = ['Chat', 'Profile', 'Decisions', 'Projects', 'Documents', 'Providers'];
  static const _tabIcons = <IconData>[
    Icons.chat_bubble_outline,
    Icons.person_outline,
    Icons.fact_check_outlined,
    Icons.folder_outlined,
    Icons.description_outlined,
    Icons.power_settings_new,
  ];

  late final WsChatClient _chatClient;
  int _selectedIndex = 0;
  String _connectionStatus = 'connecting';
  String? _activeProjectId;
  bool _collapsed = false;

  @override
  void initState() {
    super.initState();
    _chatClient = WsChatClient(_wsUrlFromApiBase(widget.api.baseUrl), apiToken: widget.api.apiToken);
    _chatClient.status.listen((status) {
      if (mounted) setState(() => _connectionStatus = status);
    });
    _chatClient.connect();
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
                    onTap: () => setState(() => _selectedIndex = i),
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
  final VoidCallback onTap;
  const _SidebarItem({
    required this.label,
    required this.icon,
    required this.selected,
    required this.collapsed,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final row = Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 18, color: selected ? AppColors.accent : AppColors.textMuted),
        if (!collapsed) ...[
          const SizedBox(width: 12),
          Text(label, style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: selected ? AppColors.accent : AppColors.textMuted)),
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
