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
    _chatClient = WsChatClient(_wsUrlFromApiBase(widget.api.baseUrl));
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
    return Scaffold(
      body: Column(
        children: [
          Material(
            elevation: 1,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Row(
                children: [
                  for (var i = 0; i < _tabs.length; i++)
                    Padding(
                      padding: const EdgeInsets.only(right: 4),
                      child: ChoiceChip(
                        label: Text(_tabs[i]),
                        selected: _selectedIndex == i,
                        onSelected: (_) => setState(() => _selectedIndex = i),
                      ),
                    ),
                  const Spacer(),
                  Chip(
                    label: Text(_connectionStatus),
                    backgroundColor: _connectionStatus == 'connected'
                        ? Colors.green.shade100
                        : Colors.grey.shade200,
                  ),
                ],
              ),
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
