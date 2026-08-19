// Tab shell matching frontend/web/index.html's #tabs bar: Chat / Profile /
// Decisions / Projects / Providers, plus a connection-status indicator for
// the WS chat connection. IndexedStack keeps every view's state alive across
// tab switches (chat transcript, in-progress form fields), the same way the
// web client's CSS-hidden <section> views never leave the DOM.

import 'package:flutter/material.dart';

import 'api_client.dart';
import 'screens/chat_view.dart';
import 'screens/decisions_view.dart';
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
  static const _tabs = ['Chat', 'Profile', 'Decisions', 'Projects', 'Providers'];

  late final WsChatClient _chatClient;
  int _selectedIndex = 0;
  String _connectionStatus = 'connecting';
  String? _activeProjectId;

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

  static const _tabIcons = <IconData>[
    Icons.chat_bubble_outline,
    Icons.person_outline,
    Icons.fact_check_outlined,
    Icons.folder_outlined,
    Icons.power_settings_new,
  ];

  @override
  Widget build(BuildContext context) {
    final connected = _connectionStatus == 'connected';
    return Scaffold(
      body: Column(
        children: [
          Container(
            decoration: const BoxDecoration(
              color: AppColors.surface,
              border: Border(bottom: BorderSide(color: AppColors.border)),
            ),
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.sm),
            child: Row(
              children: [
                const Text(
                  'PIP',
                  style: TextStyle(fontFamily: AppTheme.mono, fontWeight: FontWeight.w700, fontSize: 15, color: AppColors.accent, letterSpacing: 1.2),
                ),
                const SizedBox(width: AppSpacing.lg),
                for (var i = 0; i < _tabs.length; i++)
                  _TabButton(
                    label: _tabs[i],
                    icon: _tabIcons[i],
                    selected: _selectedIndex == i,
                    onTap: () => setState(() => _selectedIndex = i),
                  ),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(color: AppColors.surfaceRaised, borderRadius: AppRadius.sm),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 7,
                        height: 7,
                        decoration: BoxDecoration(
                          color: connected ? AppColors.accent : AppColors.textFaint,
                          shape: BoxShape.circle,
                          boxShadow: connected ? [const BoxShadow(color: AppColors.accent, blurRadius: 5)] : null,
                        ),
                      ),
                      const SizedBox(width: 7),
                      TagLabel(_connectionStatus, color: connected ? AppColors.accent : AppColors.textMuted, size: 10.5),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: IndexedStack(
              index: _selectedIndex,
              children: [
                ChatView(
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
                ProvidersView(api: widget.api),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TabButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;
  const _TabButton({required this.label, required this.icon, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: AppSpacing.xs),
      child: Material(
        color: selected ? AppColors.surfaceRaised : Colors.transparent,
        borderRadius: AppRadius.sm,
        child: InkWell(
          onTap: onTap,
          borderRadius: AppRadius.sm,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, size: 15, color: selected ? AppColors.accent : AppColors.textMuted),
                const SizedBox(width: 7),
                TagLabel(label, color: selected ? AppColors.accent : AppColors.textMuted),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
