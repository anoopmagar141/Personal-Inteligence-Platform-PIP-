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

import '../api_client.dart';
import '../theme.dart';

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
    final pip = context.pip;

    if (widget.state == AuthState.needsMigration) {
      return _MigrationNotice(pip: pip);
    }

    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 380),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  _isSetup ? 'Choose a password' : 'Welcome back',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.w600, color: pip.text),
                ),
                const SizedBox(height: AppSpacing.sm),
                Text(
                  _isSetup
                      ? 'This password encrypts everything PIP remembers. It is never '
                          'stored, and it cannot be recovered - if you forget it, your '
                          'data is gone.'
                      : 'Your data is encrypted. Enter your password to open it.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 13.5, height: 1.5, color: pip.textFaint),
                ),
                const SizedBox(height: AppSpacing.xl),

                TextField(
                  controller: _password,
                  focusNode: _passwordFocus,
                  obscureText: _obscured,
                  enabled: !_busy,
                  autofillHints: const [],
                  onSubmitted: (_) => _isSetup ? null : _submit(),
                  decoration: InputDecoration(
                    labelText: 'Password',
                    border: const OutlineInputBorder(),
                    suffixIcon: IconButton(
                      icon: Icon(_obscured ? Icons.visibility_outlined : Icons.visibility_off_outlined),
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
                    decoration: const InputDecoration(
                      labelText: 'Confirm password',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ],

                if (_error != null) ...[
                  const SizedBox(height: AppSpacing.md),
                  Text(
                    _error!,
                    style: TextStyle(fontSize: 13, color: pip.danger),
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
                    style: TextStyle(fontSize: 11.5, height: 1.5, color: pip.textFaint),
                  ),
                ],
              ],
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
class _MigrationNotice extends StatelessWidget {
  final PipPalette pip;
  const _MigrationNotice({required this.pip});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 460),
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.xl),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Your data is not encrypted yet',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600, color: pip.text),
                ),
                const SizedBox(height: AppSpacing.md),
                Text(
                  'This installation has a database from before PIP had passwords. '
                  'Encrypting it is a one-off migration that backs up your data first '
                  'and checks the new key works before changing anything, so it runs '
                  'as a script rather than from here.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 13.5, height: 1.55, color: pip.textFaint),
                ),
                const SizedBox(height: AppSpacing.lg),
                SelectableText(
                  r'.venv\Scripts\python.exe scripts\set_db_password.py',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 13,
                    color: pip.text,
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
                Text(
                  'Then start PIP again.',
                  style: TextStyle(fontSize: 12.5, color: pip.textFaint),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
