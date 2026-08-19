// PIP - Flutter client (Part 14.1: "Phase 8+: Flutter client (second real
// client). Built after web client is proven. Shares the same API surface.")
//
// Same feature set as frontend/web/app.js, validated live against the real
// backend earlier this session: onboarding, WebSocket chat with a
// static-on-done stage-hints panel, and the four REST CRUD views (Profile,
// Decisions, Projects, Providers). Part 14.4: "Frontend has zero
// intelligence. All logic in PIP Core backend" - this app is a renderer over
// api_client.dart/ws_chat_client.dart, nothing more.

import 'package:flutter/material.dart';

import 'api_client.dart';
import 'home_shell.dart';
import 'onboarding_screen.dart';

// PIP Core's default dev server address (matches every `uvicorn
// backend.api.server:app --host 127.0.0.1 --port 8765` run used to validate
// the backend and web client this session). Overridable per-build via
// --dart-define=PIP_API_BASE=... / PIP_WS_URL=... for a real deployment.
const String kApiBase = String.fromEnvironment(
  'PIP_API_BASE',
  defaultValue: 'http://127.0.0.1:8765/api/v1',
);
const String kWsUrl = String.fromEnvironment(
  'PIP_WS_URL',
  defaultValue: 'ws://127.0.0.1:8765/ws/chat',
);
// Security fix: every /api/v1/* route and /ws/chat now require this token
// (see backend/core/auth.py) - PIP prints a ready-to-use value at startup.
// No default: an empty token simply fails every request with 401/4401,
// which is the correct behavior for "wasn't configured," not a silent bypass.
const String kApiToken = String.fromEnvironment('PIP_API_TOKEN');

void main() {
  runApp(const PipApp());
}

class PipApp extends StatelessWidget {
  const PipApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PIP',
      theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal), useMaterial3: true),
      home: const AppRoot(),
    );
  }
}

class AppRoot extends StatefulWidget {
  const AppRoot({super.key});

  @override
  State<AppRoot> createState() => _AppRootState();
}

enum _RootState { loading, onboarding, error, ready }

class _AppRootState extends State<AppRoot> {
  final ApiClient api = ApiClient(kApiBase, apiToken: kApiToken);
  _RootState _state = _RootState.loading;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _checkOnboarding();
  }

  Future<void> _checkOnboarding() async {
    try {
      final status = await api.getStatus();
      setState(() {
        _state = (status['onboarding_complete'] as bool? ?? false) ? _RootState.ready : _RootState.onboarding;
      });
    } catch (error) {
      setState(() {
        _state = _RootState.error;
        _errorMessage = error.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    switch (_state) {
      case _RootState.loading:
        return const Scaffold(body: Center(child: CircularProgressIndicator()));
      case _RootState.error:
        return Scaffold(
          body: Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text("Can't reach PIP", style: TextStyle(fontSize: 20)),
                  const SizedBox(height: 8),
                  Text(_errorMessage ?? '', textAlign: TextAlign.center),
                  const SizedBox(height: 16),
                  ElevatedButton(onPressed: _checkOnboarding, child: const Text('Retry')),
                ],
              ),
            ),
          ),
        );
      case _RootState.onboarding:
        return OnboardingScreen(api: api, onComplete: () => setState(() => _state = _RootState.ready));
      case _RootState.ready:
        return HomeShell(api: api);
    }
  }
}
