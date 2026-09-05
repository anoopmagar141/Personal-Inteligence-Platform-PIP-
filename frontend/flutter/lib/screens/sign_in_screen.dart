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
// WHY THE PROFILE SWITCHER IS HERE AND NOT IN THE LAUNCHER
//
// It was in the launcher, for the same reason the password was:
// scripts/_profiles.ps1 printed "Which profile?" and read a number, because
// the four path variables had to be set before uvicorn started. That stopped
// being true once nothing captures those variables at import - the backend
// re-points itself through POST /auth/profile, and the only rule is that it
// must not be holding a key when it does.
//
// Which puts the choice exactly where a person looks for it. "Who am I
// signing in as" and "what is my password" are one question asked twice, and
// answering the first in a console window several seconds before the
// application appears was answering it in the wrong place, to somebody who
// had not seen the product yet.
//
// The switcher is drawn only when there is more than one profile, so a normal
// installation is unchanged - the same screen, with nothing extra on it.
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

/// One profile as the sign-in screen needs it: a name to show, a slug to send,
/// and whether it has ever been opened.
class _ProfileOption {
  final String slug;
  final String name;
  final bool exists;

  const _ProfileOption({required this.slug, required this.name, required this.exists});

  factory _ProfileOption.fromJson(Map<String, dynamic> json) => _ProfileOption(
        slug: json['slug'] as String,
        name: json['name'] as String? ?? json['slug'] as String,
        exists: json['exists'] as bool? ?? true,
      );
}

class _SignInScreenState extends State<SignInScreen> {
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  final _passwordFocus = FocusNode();

  bool _busy = false;
  bool _obscured = true;
  String? _error;

  /// Which situation the SELECTED profile is in.
  ///
  /// Seeded from what AppRoot was told and then owned here, because switching
  /// profile changes the answer - a name with no database behind it is a
  /// "choose a password" screen even though the one before it was not. Reading
  /// widget.state in build() would have shown the previous profile's words
  /// under the new profile's name.
  late AuthState _state = widget.state;

  List<_ProfileOption> _profiles = const [];
  String? _activeSlug;

  bool get _isSetup => _state == AuthState.setup;

  @override
  void initState() {
    super.initState();
    // The only field on the screen, and the only thing anybody is here to do.
    _passwordFocus.requestFocus();
    _loadProfiles();
  }

  /// Ask who this installation can be signed in as.
  ///
  /// Failure is swallowed on purpose. This screen's job is to take a password,
  /// and it can do that against the profile the backend is already pointed at
  /// whether or not a registry could be read. An error banner about a list
  /// that most installations do not even have would be noise in front of the
  /// one thing somebody came here to do.
  Future<void> _loadProfiles() async {
    try {
      final payload = await widget.api.authProfiles();
      if (!mounted) return;
      setState(() {
        _profiles = (payload['profiles'] as List<dynamic>? ?? [])
            .map((e) => _ProfileOption.fromJson(e as Map<String, dynamic>))
            .toList();
        _activeSlug = payload['active'] as String?;
      });
    } catch (_) {
      // Left as it was: no list, no switcher, one profile's worth of screen.
    }
  }

  /// Point the backend at another profile and redress the screen for it.
  ///
  /// The password fields are cleared rather than carried across, and that is
  /// not tidiness. Two profiles have two passwords by construction - separate
  /// databases under separate keys - so a password typed for one is never the
  /// right answer for the other, and leaving it in the field invites somebody
  /// to submit it and be told it did not open their data.
  Future<void> _switchTo(_ProfileOption profile) async {
    if (_busy || profile.slug == _activeSlug) return;

    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      final state = await widget.api.selectProfile(profile.slug);
      if (!mounted) return;
      setState(() {
        _busy = false;
        _activeSlug = profile.slug;
        _state = authStateFrom(state);
        _password.clear();
        _confirm.clear();
      });
      _passwordFocus.requestFocus();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = _sentence(e);
      });
    }
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
        await widget.api.completeSetup(password, profile: _activeSlug);
      } else {
        await widget.api.unlock(password, profile: _activeSlug);
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

  /// The row of names, or nothing at all.
  ///
  /// Null below two profiles, which is most installations - a control offering
  /// one choice is not a choice, and the screen those people see is exactly
  /// the screen that was here before profiles existed.
  ///
  /// A menu rather than a row of chips or a dropdown form field. Chips would
  /// spread with the number of profiles and push the password field down the
  /// card; a DropdownButtonFormField would read as a fourth thing to fill in,
  /// next to two fields that genuinely are. This is one line that says who is
  /// signing in, and opens when that is the wrong answer.
  Widget? _profileSwitcher() {
    if (_profiles.length <= 1) return null;

    final active = _profiles.firstWhere(
      (p) => p.slug == _activeSlug,
      orElse: () => _profiles.first,
    );

    // The menu is sized to the control rather than to its longest name.
    // PopupMenuButton defaults to hugging its content, which on a card this
    // wide opens a narrow box under a full-width row and reads as a different
    // control appearing rather than that one unfolding. LayoutBuilder because
    // the width is the card's, and the card is a max-width that a narrow
    // window can be smaller than.
    return LayoutBuilder(
      builder: (context, constraints) => PopupMenuButton<_ProfileOption>(
        enabled: !_busy,
        tooltip: 'Switch profile',
        position: PopupMenuPosition.under,
        offset: const Offset(0, AppSpacing.xs),
        constraints: BoxConstraints(
          minWidth: constraints.maxWidth,
          maxWidth: constraints.maxWidth,
        ),
        // Stated, not inherited, for the reason every other colour on this
        // screen is: the app-wide theme may be the light one, and a white menu
        // dropped onto this fixed dark stage is the same visual break the
        // launch-to-sign-in cut was built to avoid.
        color: const Color(0xFF15161F),
        shape: const RoundedRectangleBorder(
          borderRadius: AppRadius.sm,
          side: BorderSide(color: Color(0xFF2C2F43)),
        ),
        onSelected: _switchTo,
        itemBuilder: (context) => [
          for (final profile in _profiles)
            PopupMenuItem<_ProfileOption>(
              value: profile,
              child: Row(
                children: [
                  SizedBox(
                    width: 22,
                    child: profile.slug == active.slug
                        ? const Icon(Icons.check, size: 15, color: kGatewayAccent)
                        : null,
                  ),
                  Expanded(
                    child: Text(
                      profile.name,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 14, color: kGatewayText),
                    ),
                  ),
                  // The same distinction the console menu drew with "(no
                  // database yet - will onboard)", in the two words there is
                  // room for. Somebody about to be asked to CHOOSE a password
                  // rather than enter one should be able to see why before the
                  // heading changes under them.
                  if (!profile.exists)
                    const Padding(
                      padding: EdgeInsets.only(left: AppSpacing.sm),
                      child: Text('New', style: TextStyle(fontSize: 11.5, color: kGatewayTextFaint)),
                    ),
                ],
              ),
            ),
        ],
        child: Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: AppSpacing.sm + 2,
          ),
          decoration: BoxDecoration(
            color: const Color(0xFF15161F),
            borderRadius: AppRadius.sm,
            border: Border.all(color: const Color(0xFF2C2F43)),
          ),
          child: Row(
            children: [
              const Icon(Icons.person_outline, size: 17, color: kGatewayTextMuted),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Text(
                  active.name,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 14, color: kGatewayText),
                ),
              ),
              const Text('Switch', style: TextStyle(fontSize: 12, color: kGatewayTextFaint)),
              const SizedBox(width: AppSpacing.xs),
              const Icon(Icons.expand_more, size: 17, color: kGatewayTextMuted),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // No `context.pip` here any more, and its absence is the point: every
    // colour on the three auth screens is now stated against the fixed dark
    // stage rather than inherited from a theme that may be the wrong one.

    if (_state == AuthState.needsMigration) {
      // The switcher goes with it. A legacy plaintext database in one profile
      // is no reason to be stuck on the screen about it when another profile
      // on the same machine opens perfectly well - and this screen's whole
      // instruction is "run a script and come back", which is a long time to
      // be unable to reach your own data.
      return _MigrationNotice(header: _profileSwitcher());
    }

    final switcher = _profileSwitcher();

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
                // Above the heading, because it changes what the heading says.
                // "Choose a password" under a name somebody has just switched
                // away from would be the screen contradicting itself, and the
                // order here is the order the two are read in.
                if (switcher != null) ...[
                  switcher,
                  const SizedBox(height: AppSpacing.lg),
                ],
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
  /// The profile switcher, when there is more than one profile. Passed in
  /// rather than rebuilt here: it belongs to the sign-in state that owns the
  /// selection, and two copies of that control would be two answers to "which
  /// profile is selected" that could disagree.
  final Widget? header;

  const _MigrationNotice({this.header});

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
                    if (widget.header != null) ...[
                      widget.header!,
                      const SizedBox(height: AppSpacing.lg),
                    ],
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
