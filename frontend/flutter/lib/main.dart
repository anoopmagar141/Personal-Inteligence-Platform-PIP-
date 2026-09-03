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
import 'startup_progress.dart';
import 'theme.dart';

/// The data directory, exported so screens that read it directly (Backup) get
/// the same answer this file resolves at startup rather than deriving a second
/// one.
final String kDataDir = _dataDir();

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

/// Where the launcher and the backend record what they are doing, for the
/// launch screen to read. See lib/startup_progress.dart for why this is a file
/// and not an endpoint.
final String kStartupProgressPath = '${_dataDir()}/startup.jsonl';

void main() {
  runApp(const PipApp());
}

/// Where the chosen theme is remembered between launches.
///
/// A one-line file beside the token rather than a new package: the app already
/// reads its data directory at startup, and shared_preferences would be a
/// platform dependency carried for a single enum. Every failure path falls
/// back to following the OS, so a missing, unreadable, or garbled file costs
/// nothing.
String get kThemePrefPath => '${_dataDir()}/ui_theme.txt';

ThemeMode _readThemeMode() {
  try {
    final file = File(kThemePrefPath);
    if (!file.existsSync()) return ThemeMode.system;
    return switch (file.readAsStringSync().trim()) {
      'light' => ThemeMode.light,
      'dark' => ThemeMode.dark,
      _ => ThemeMode.system,
    };
  } catch (_) {
    return ThemeMode.system;
  }
}

void _writeThemeMode(ThemeMode mode) {
  try {
    File(kThemePrefPath).writeAsStringSync(mode.name);
  } catch (_) {
    // Not being able to remember the preference is not a reason to refuse to
    // apply it for this session.
  }
}

class PipApp extends StatefulWidget {
  const PipApp({super.key});

  @override
  State<PipApp> createState() => _PipAppState();
}

class _PipAppState extends State<PipApp> {
  ThemeMode _themeMode = _readThemeMode();

  /// Cycles system -> light -> dark -> system.
  ///
  /// "System" is a real third option rather than a tidy-up of two: Windows 11
  /// has an app-theme setting, and following it is the right default for a
  /// desktop app. Someone who wants to override it can, and gets to go back.
  void _cycleTheme() {
    setState(() {
      _themeMode = switch (_themeMode) {
        ThemeMode.system => ThemeMode.light,
        ThemeMode.light => ThemeMode.dark,
        ThemeMode.dark => ThemeMode.system,
      };
    });
    _writeThemeMode(_themeMode);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PIP',
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: _themeMode,
      home: AppRoot(themeMode: _themeMode, onCycleTheme: _cycleTheme),
    );
  }
}

class AppRoot extends StatefulWidget {
  final ThemeMode themeMode;
  final VoidCallback onCycleTheme;
  const AppRoot({super.key, required this.themeMode, required this.onCycleTheme});

  @override
  State<AppRoot> createState() => _AppRootState();
}

enum _RootState { connecting, onboarding, error, ready }

class _AppRootState extends State<AppRoot> {
  late ApiClient api;
  _RootState _state = _RootState.connecting;
  String _statusMessage = 'Starting PIP...';
  String? _errorDetail;
  List<StartupPhase> _phases = const [];

  /// Anything in the progress file older than this belongs to a previous run.
  ///
  /// The launcher truncates the file, so under a normal double-click this
  /// never triggers. It exists for the other ways the backend gets started -
  /// run_dev.ps1, a bare uvicorn - where nothing clears it and the app would
  /// otherwise open onto last week's completed checklist and call it progress.
  final DateTime _startedAt = DateTime.now();

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

      await _refreshPhases();
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
        // Only ever a fallback now. When the progress file is being written
        // the checklist below says what is actually happening, and this line
        // is not shown at all - a counter cannot know whether a slow start is
        // a decrypting database or a backend that never launched, and saying
        // "still preparing things" to both was the whole problem.
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

  /// Re-read on every attempt, in the same loop and for the same reason as the
  /// token: both are written by another process after this one has already
  /// started, so neither can be read once and cached.
  Future<void> _refreshPhases() async {
    try {
      final file = File(kStartupProgressPath);
      if (!await file.exists()) return;
      if ((await file.lastModified()).isBefore(_startedAt)) return;
      final phases = parseStartupProgress(await file.readAsString());
      if (mounted && phases.isNotEmpty) setState(() => _phases = phases);
    } catch (_) {
      // No progress to show is the state this screen started in. A file that
      // cannot be read costs the detail, not the launch.
    }
  }

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    switch (_state) {
      case _RootState.connecting:
        return _LoadingScreen(message: _statusMessage, phases: _phases);
      case _RootState.error:
        return Scaffold(
          body: Center(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.xl),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TagLabel('Connection error', color: pip.danger, size: 12),
                  const SizedBox(height: AppSpacing.sm),
                  const Text("Can't reach PIP", style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600)),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    _errorDetail ?? '',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 12.5, color: pip.textMuted),
                  ),
                  // The phases that DID complete before it stalled. "PIP's
                  // backend didn't respond" is the same sentence whether
                  // Ollama never started or the database is still decrypting,
                  // and the list is the only thing that separates them.
                  if (_phases.isNotEmpty) ...[
                    const SizedBox(height: AppSpacing.lg),
                    ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 320),
                      child: _PhaseList(phases: _phases),
                    ),
                  ],
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
        return HomeShell(
          api: api,
          themeMode: widget.themeMode,
          onCycleTheme: widget.onCycleTheme,
        );
    }
  }
}

class _LoadingScreen extends StatelessWidget {
  final String message;
  final List<StartupPhase> phases;
  const _LoadingScreen({required this.message, this.phases = const []});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Scaffold(
      backgroundColor: pip.bg,
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 340),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'PIP',
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: 32, color: pip.accent),
              ),
              const SizedBox(height: AppSpacing.lg),
              const SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(strokeWidth: 2.5),
              ),
              const SizedBox(height: AppSpacing.lg),
              // The checklist replaces the message rather than sitting under
              // it. Both at once would be a real account of the startup next
              // to a counter's guess about the same startup, and the guess
              // would be the one that looked authoritative.
              if (phases.isEmpty)
                Text(
                  message,
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 13, color: pip.textMuted),
                )
              else
                _PhaseList(phases: phases),
            ],
          ),
        ),
      ),
    );
  }
}


/// The startup checklist: what is done, what is happening, what is still to
/// come. Used on the loading screen and again on the failure screen, where it
/// is the only thing that says how far the launch actually got.
class _PhaseList extends StatelessWidget {
  final List<StartupPhase> phases;
  const _PhaseList({required this.phases});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final phase in phases)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 5),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 20,
                  child: switch (phase.state) {
                    StartupPhaseState.done => Icon(Icons.check, size: 14, color: pip.accent),
                    StartupPhaseState.current => SizedBox(
                        width: 11,
                        height: 11,
                        child: CircularProgressIndicator(strokeWidth: 2, color: pip.accent),
                      ),
                    StartupPhaseState.pending => Icon(Icons.circle_outlined, size: 11, color: pip.textFaint),
                  },
                ),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        phase.label,
                        style: TextStyle(
                          fontSize: 12.5,
                          fontWeight: phase.state == StartupPhaseState.current
                              ? FontWeight.w600
                              : FontWeight.w400,
                          color: phase.state == StartupPhaseState.pending ? pip.textFaint : pip.text,
                        ),
                      ),
                      // The detail is where "already running" lives, which is
                      // the difference between a fast launch and a broken one.
                      if (phase.detail.isNotEmpty && phase.state != StartupPhaseState.pending)
                        Text(
                          phase.detail,
                          style: TextStyle(fontSize: 11, color: pip.textFaint),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}
