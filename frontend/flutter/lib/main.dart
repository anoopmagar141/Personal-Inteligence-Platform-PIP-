// PIP - Flutter client (Part 14.1: "Phase 8+: Flutter client (second real
// client). Built after web client is proven. Shares the same API surface.")
//
// Same feature set as frontend/web/app.js, validated live against the real
// backend earlier this session: onboarding, WebSocket chat with a
// static-on-done stage-hints panel, and the four REST CRUD views (Profile,
// Decisions, Projects, Providers). Part 14.4: "Frontend has zero
// intelligence. All logic in PIP Core backend" - this app is a renderer over
// api_client.dart/ws_chat_client.dart, nothing more.
//
// Native desktop target only from here (dart:io) - the web/-d edge debug
// workflow this session used during the UI redesign is retired in favor of
// a real `flutter build windows` app with its own window, launched by
// scripts/launch_pip.ps1 instead of a browser tab.
//
// Config is read at RUNTIME (Platform.environment / a token file), not baked
// in via --dart-define at build time: --dart-define values are fixed the
// moment the .exe is compiled, but auth.py generates a fresh random token on
// each machine's first real run, which doesn't exist yet at build time. The
// launcher only needs to tell this app WHERE to look (PIP_DATA_DIR) - not
// WHAT the token is - so a backend restart or a slow first boot (the token
// file not existing yet when this app starts) is just something the retry
// loop below tolerates, the same way it already tolerates the backend port
// not being open yet.

import 'dart:io';

import 'package:flutter/material.dart';

import 'api_client.dart';
import 'home_shell.dart';
import 'onboarding_screen.dart';
import 'theme.dart';

String _dataDir() {
  final override = Platform.environment['PIP_DATA_DIR'];
  if (override != null && override.isNotEmpty) return override;
  // Dev fallback: `flutter run -d windows` from frontend/flutter/ as cwd.
  return '../../data';
}

String _envOr(String key, String fallback) {
  final value = Platform.environment[key];
  return (value == null || value.isEmpty) ? fallback : value;
}

final String kApiBase = _envOr('PIP_API_BASE', 'http://127.0.0.1:8765/api/v1');
final String kWsUrl = _envOr('PIP_WS_URL', 'ws://127.0.0.1:8765/ws/chat');
final String kTokenPath = '${_dataDir()}/api_token.txt';

void main() {
  runApp(const PipApp());
}

class PipApp extends StatelessWidget {
  const PipApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PIP',
      theme: AppTheme.light,
      darkTheme: AppTheme.light,
      themeMode: ThemeMode.light,
      home: const AppRoot(),
    );
  }
}

class AppRoot extends StatefulWidget {
  const AppRoot({super.key});

  @override
  State<AppRoot> createState() => _AppRootState();
}

enum _RootState { connecting, onboarding, error, ready }

class _AppRootState extends State<AppRoot> {
  late ApiClient api;
  _RootState _state = _RootState.connecting;
  String _statusMessage = 'Starting PIP...';
  String? _errorDetail;

  // ~45s of retrying before giving up and showing a manual-retry screen -
  // generous enough to cover a cold uvicorn start plus a slow disk, but not
  // so long that a genuinely dead backend leaves the window looking frozen
  // with no way for the user to act on it.
  static const _maxAttempts = 45;

  @override
  void initState() {
    super.initState();
    api = ApiClient(kApiBase, apiToken: '');
    _connect();
  }

  Future<void> _connect() async {
    setState(() {
      _state = _RootState.connecting;
      _statusMessage = 'Starting PIP...';
      _errorDetail = null;
    });

    for (var attempt = 1; attempt <= _maxAttempts; attempt++) {
      if (!mounted) return;

      final token = await _tryReadToken();
      if (token != null) {
        try {
          final status = await ApiClient(kApiBase, apiToken: token).getStatus();
          if (!mounted) return;
          setState(() {
            api = ApiClient(kApiBase, apiToken: token);
            _state = (status['onboarding_complete'] as bool? ?? false) ? _RootState.ready : _RootState.onboarding;
          });
          return;
        } catch (_) {
          // Backend not answering yet, or this token is stale (e.g. a
          // previous run's token file, backend hasn't regenerated it since
          // restarting) - both look identical from here, and both resolve
          // the same way: keep retrying, the loop below re-reads the token
          // file fresh on every attempt.
        }
      }

      if (!mounted) return;
      setState(() {
        _statusMessage = attempt < 8
            ? 'Starting PIP...'
            : "Still preparing things - this can take a little longer on first launch...";
      });
      await Future.delayed(const Duration(seconds: 1));
    }

    if (!mounted) return;
    setState(() {
      _state = _RootState.error;
      _errorDetail = "PIP's backend didn't respond in time. Make sure it's running, then try again.";
    });
  }

  Future<String?> _tryReadToken() async {
    try {
      final file = File(kTokenPath);
      if (!await file.exists()) return null;
      final token = (await file.readAsString()).trim();
      return token.isEmpty ? null : token;
    } catch (_) {
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    switch (_state) {
      case _RootState.connecting:
        return _LoadingScreen(message: _statusMessage);
      case _RootState.error:
        return Scaffold(
          body: Center(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.xl),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const TagLabel('Connection error', color: AppColors.danger, size: 12),
                  const SizedBox(height: AppSpacing.sm),
                  const Text("Can't reach PIP", style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600)),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    _errorDetail ?? '',
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 12.5, color: AppColors.textMuted),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  FilledButton(onPressed: _connect, child: const Text('Retry')),
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

class _LoadingScreen extends StatelessWidget {
  final String message;
  const _LoadingScreen({required this.message});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'PIP',
              style: TextStyle(fontWeight: FontWeight.w800, fontSize: 32, color: AppColors.accent),
            ),
            const SizedBox(height: AppSpacing.lg),
            const SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(strokeWidth: 2.5),
            ),
            const SizedBox(height: AppSpacing.lg),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 13, color: AppColors.textMuted),
            ),
          ],
        ),
      ),
    );
  }
}
