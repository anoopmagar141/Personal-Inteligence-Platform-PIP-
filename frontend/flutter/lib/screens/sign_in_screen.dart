// The first thing anybody sees, and until now it was a PowerShell console.
//
// scripts/launch_pip.ps1 used to derive the database key before starting the
// backend, which meant asking for a password from a blue terminal window - for
// a database that, on a machine PIP had just been installed on, did not exist
// yet. Its own docstring called that the one place the launcher is not silent
// and called the cost deliberate. It stopped being worth paying the moment PIP
// became something other people install.
//
// WHY ONE SCREEN AND NOT TWO
//
// Signing in and choosing a first password are the same screen with different
// words, because they are the same moment in a person's head: "let me in". The
// backend already knows which one it is - /auth/state answers before the
// database is touched - so the difference is copy and one extra field, not a
// separate route the app has to decide between.
//
// WHAT IT DOES NOT DO
//
// Recover anything. There is no reset, no hint, no security question, and the
// screen says so plainly rather than leaving somebody to discover it by
// hoping. The key is derived from the password and a salt and never written
// down (Part 10.1), so a forgotten password is unrecoverable by construction -
// which is the point, and is only defensible if it is stated before somebody
// relies on it.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api_client.dart';
import '../theme.dart';
import '../widgets/gateway_flow.dart';

/// What the backend says this installation needs.
enum AuthState { locked, setup, needsMigration, unlocked }

AuthState authStateFrom(String raw) {
  switch (raw) {
    case 'locked':
      return AuthState.locked;
    case 'setup':
      return AuthState.setup;
    case 'needs_migration':
      return AuthState.needsMigration;
    case 'unlocked':
      return AuthState.unlocked;
    default:
      // An unfamiliar state is treated as locked rather than as unlocked. A
      // client and backend that disagree should fail towards asking for a
      // password, never towards skipping one.
      return AuthState.locked;
  }
}

/// The look of a text field on the dark stage.
///
/// Spelled out rather than inherited. The app-wide InputDecorationTheme is
/// filled with PipPalette.surface, which on this fixed dark stage is a white
/// slab under a light theme - and on a sign-in screen that is not a cosmetic
/// problem: somebody typing a password they cannot recover needs to see the
/// field they are typing into, and see which one has focus.
InputDecoration _stageField(String label, {Widget? suffix}) => InputDecoration(
      labelText: label,
      suffixIcon: suffix,
      filled: true,
      fillColor: const Color(0xFF15161F),
      labelStyle: const TextStyle(color: kGatewayTextMuted),
      floatingLabelStyle: const TextStyle(color: kGatewayAccent),
      border: OutlineInputBorder(
        borderRadius: AppRadius.sm,
        borderSide: const BorderSide(color: Color(0xFF2C2F43)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: AppRadius.sm,
        borderSide: const BorderSide(color: Color(0xFF2C2F43)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: AppRadius.sm,
        borderSide: const BorderSide(color: kGatewayAccent, width: 1.5),
      ),
    );

class SignInScreen extends StatefulWidget {
  final ApiClient api;
  final AuthState state;
  final VoidCallback onUnlocked;

  const SignInScreen({
    super.key,
    required this.api,
    required this.state,
    required this.onUnlocked,
  });

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  final _passwordFocus = FocusNode();

  bool _busy = false;
  bool _obscured = true;
  String? _error;

  bool get _isSetup => widget.state == AuthState.setup;

  @override
  void initState() {
    super.initState();
    // The only field on the screen, and the only thing anybody is here to do.
    _passwordFocus.requestFocus();
  }

  @override
  void dispose() {
    _password.dispose();
    _confirm.dispose();
    _passwordFocus.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_busy) return;

    final password = _password.text;
    if (password.isEmpty) {
      setState(() => _error = 'Enter your password.');
      return;
    }
    // Checked here as well as on the server, because a mismatch is the one
    // error the client can be certain about without asking - and the round
    // trip would cost a quarter of a second of key derivation to tell
    // somebody something they could have been told immediately.
    if (_isSetup && password != _confirm.text) {
      setState(() => _error = 'Those two passwords are different.');
      return;
    }

    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      if (_isSetup) {
        await widget.api.completeSetup(password);
      } else {
        await widget.api.unlock(password);
      }
      if (!mounted) return;
      widget.onUnlocked();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = _sentence(e);
        // Cleared on failure, kept on success-that-never-came. Somebody
        // retyping after a wrong password should not have to select the old
        // one first.
        _password.clear();
        _confirm.clear();
      });
      _passwordFocus.requestFocus();
    }
  }

  /// The server's own sentence where there is one, because it is more specific
  /// than anything this screen could invent - "that password did not open your
  /// data" and "use at least 8 characters" are both answers, and a generic
  /// "sign-in failed" would replace them with less.
  String _sentence(Object error) {
    final text = error.toString();
    final marker = text.indexOf('detail');
    if (marker >= 0) {
      final quoted = RegExp(r'"detail"\s*:\s*"([^"]+)"').firstMatch(text);
      if (quoted != null) return quoted.group(1)!;
    }
    return 'Could not open your data. Is PIP still starting?';
  }

  @override
  Widget build(BuildContext context) {
    // No `context.pip` here any more, and its absence is the point: every
    // colour on the three auth screens is now stated against the fixed dark
    // stage rather than inherited from a theme that may be the wrong one.

    if (widget.state == AuthState.needsMigration) {
      return const _MigrationNotice();
    }

    // The same dark stage and the same field as the launch screen, because
    // these two are consecutive: the launch screen becomes this one, and a
    // hard cut from a black particle field to a white form would read as two
    // different applications.
    //
    // Everything below states its colours rather than taking PipPalette's.
    // The stage is fixed, so the palette here would be the wrong one half the
    // time - and on a sign-in screen "wrong" means a password field somebody
    // cannot see what they are typing into.
    return Scaffold(
      backgroundColor: kGatewayStage,
      body: GatewayFlow(
        child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 400),
            child: Container(
              padding: const EdgeInsets.all(AppSpacing.xl),
              decoration: gatewayGlass(),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  _isSetup ? 'Choose a password' : 'Welcome back',
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w600, color: kGatewayText),
                ),
                const SizedBox(height: AppSpacing.sm),
                Text(
                  _isSetup
                      ? 'This password encrypts everything PIP remembers. It is never '
                          'stored, and it cannot be recovered - if you forget it, your '
                          'data is gone.'
                      : 'Your data is encrypted. Enter your password to open it.',
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 13.5, height: 1.5, color: kGatewayTextMuted),
                ),
                const SizedBox(height: AppSpacing.xl),

                TextField(
                  controller: _password,
                  focusNode: _passwordFocus,
                  obscureText: _obscured,
                  enabled: !_busy,
                  autofillHints: const [],
                  onSubmitted: (_) => _isSetup ? null : _submit(),
                  style: const TextStyle(color: kGatewayText, fontSize: 15),
                  cursorColor: kGatewayAccent,
                  decoration: _stageField(
                    'Password',
                    suffix: IconButton(
                      icon: Icon(
                        _obscured ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                        color: kGatewayTextMuted,
                      ),
                      tooltip: _obscured ? 'Show password' : 'Hide password',
                      onPressed: () => setState(() => _obscured = !_obscured),
                    ),
                  ),
                ),

                if (_isSetup) ...[
                  const SizedBox(height: AppSpacing.md),
                  TextField(
                    controller: _confirm,
                    obscureText: _obscured,
                    enabled: !_busy,
                    onSubmitted: (_) => _submit(),
                    style: const TextStyle(color: kGatewayText, fontSize: 15),
                    cursorColor: kGatewayAccent,
                    decoration: _stageField('Confirm password'),
                  ),
                ],

                if (_error != null) ...[
                  const SizedBox(height: AppSpacing.md),
                  Text(
                    _error!,
                    style: const TextStyle(fontSize: 13, color: Color(0xFFFF8A8A)),
                  ),
                ],

                const SizedBox(height: AppSpacing.lg),
                FilledButton(
                  onPressed: _busy ? null : _submit,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    child: _busy
                        // The label says what is happening rather than only
                        // spinning: deriving the key is a quarter-second of
                        // deliberate work, and a button that merely went dead
                        // would read as a hang.
                        ? const Text('Opening your data...')
                        : Text(_isSetup ? 'Create password' : 'Unlock'),
                  ),
                ),

                if (!_isSetup) ...[
                  const SizedBox(height: AppSpacing.lg),
                  Text(
                    'There is no password reset. PIP never stores your password, '
                    'so nobody - including PIP - can recover your data without it.',
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 11.5, height: 1.5, color: kGatewayTextFaint),
                  ),
                ],
              ],
            ),
            ),
          ),
        ),
        ),
      ),
    );
  }
}

/// An unencrypted database from before a password was ever set.
///
/// Reported rather than repaired, and this screen is the reporting. Encrypting
/// data somebody already has is a rekey with backup implications, and
/// scripts/set_db_password.py does it carefully - backing up first, and proving
/// the new key opens the copy before removing anything. A button here that did
/// it silently would be the least ceremonious irreversible action in PIP.
class _MigrationNotice extends StatefulWidget {
  const _MigrationNotice();

  @override
  State<_MigrationNotice> createState() => _MigrationNoticeState();
}

class _MigrationNoticeState extends State<_MigrationNotice> {
  static const _command = r'.venv\Scripts\python.exe scripts\set_db_password.py';

  bool _copied = false;

  @override
  Widget build(BuildContext context) {
    // On the same field as the other two auth screens, because this IS one of
    // them - /auth/state returns needs_migration where it would otherwise
    // return locked, so somebody meeting this screen met it INSTEAD of the
    // password prompt, not on some separate error route.
    //
    // Contrast is held higher here than on sign-in. This screen is read rather
    // than glanced at, it is the only instruction anybody gets, and it is met
    // by definition on an installation where something is already not as
    // expected.
    return Scaffold(
      backgroundColor: kGatewayStage,
      body: GatewayFlow(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.xl),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520),
              child: Container(
                padding: const EdgeInsets.all(AppSpacing.xl),
                decoration: gatewayGlass(),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'Your data is not encrypted yet',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w600,
                        color: kGatewayText,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.md),
                    const Text(
                      'This installation has a database from before PIP had passwords. '
                      'Encrypting it is a one-off migration that backs up your data first '
                      'and checks the new key works before changing anything, so it runs '
                      'as a script rather than from here.',
                      textAlign: TextAlign.center,
                      // Muted, not faint. On sign-in the faint tone carries a
                      // warning somebody has already been told; here it would
                      // carry the explanation of what to do next, and there is
                      // nothing else on screen to fall back on.
                      style: TextStyle(fontSize: 13.5, height: 1.55, color: kGatewayTextMuted),
                    ),
                    const SizedBox(height: AppSpacing.lg),
                    Container(
                      padding: const EdgeInsets.fromLTRB(
                          AppSpacing.md, AppSpacing.sm, AppSpacing.sm, AppSpacing.sm),
                      decoration: BoxDecoration(
                        color: const Color(0xFF05060A),
                        borderRadius: AppRadius.sm,
                        border: Border.all(color: const Color(0xFF2C2F43)),
                      ),
                      child: Row(
                        children: [
                          const Expanded(
                            // Still selectable. The copy button is the easy
                            // path, not the only one - somebody whose
                            // clipboard is doing something strange still has
                            // to be able to get this command out by hand.
                            child: SelectableText(
                              _command,
                              style: TextStyle(
                                fontFamily: AppTheme.mono,
                                fontSize: 13,
                                height: 1.4,
                                color: kGatewayText,
                              ),
                            ),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          IconButton(
                            icon: Icon(
                              _copied ? Icons.check : Icons.copy_outlined,
                              size: 17,
                              color: _copied ? kGatewayAccent : kGatewayTextMuted,
                            ),
                            tooltip: _copied ? 'Copied' : 'Copy command',
                            onPressed: () async {
                              await Clipboard.setData(const ClipboardData(text: _command));
                              if (!mounted) return;
                              // Confirmed rather than silently assumed: the
                              // whole screen is one instruction, and "did that
                              // work" is the very next thought.
                              setState(() => _copied = true);
                            },
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: AppSpacing.md),
                    const Text(
                      'Then start PIP again.',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 12.5, color: kGatewayTextMuted),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
