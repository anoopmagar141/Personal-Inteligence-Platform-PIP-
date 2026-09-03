// Backup: export your data to one encrypted file, and carry it to another
// machine.
//
// WHY THE BUTTON LAUNCHES A CONSOLE INSTEAD OF DOING THE WORK
// -----------------------------------------------------------
// ADR-027 is explicit that the export must not be reachable from the API. The
// backend's live connection already holds the real key, so an HTTP route
// producing a re-encrypted copy would hand that capability to anything able to
// read data/api_token.txt - which is any process running as this user - without
// it ever knowing the live key. That is precisely the capability the
// password-derived key model exists to withhold.
//
// So this screen is a launcher, not a participant. It starts
// scripts/export_pip.ps1 in a visible console, and export_backup.py's
// authenticate() demands the live password there, from a person, in a window
// this app cannot read. The app never sees either password. Pressing the button
// grants nobody anything they did not already have by opening a terminal.
//
// It is worth being precise about what that buys, because a security control
// described in bigger terms than it deserves is how the next person builds
// something on top of it that does not hold: the boundary is the operating
// system account, and always was. Somebody who can already run code as this
// user does not need this button. What the arrangement preserves is that
// nothing REACHABLE OVER HTTP can take a full copy of the profile - and that
// taking one is a deliberate act by somebody who knows the live password.
//
// WHY THERE IS NO RESTORE BUTTON
// ------------------------------
// A restore replaces the database file the running backend has open, and
// restore_backup.py refuses while PIP holds the lock. There is no arrangement
// in which a button inside the running app can do it: the app being open is the
// thing that stops it. It lives on a Desktop shortcut
// (scripts/install_shortcuts.ps1), which is also where it is actually needed -
// a fresh machine, or one whose database is gone, has no app window to click.

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../theme.dart';

class BackupView extends StatefulWidget {
  /// The data directory, resolved the way main.dart resolves it. Injected
  /// rather than read from the environment here so a test can point the screen
  /// at a directory it controls.
  final String dataDir;

  /// Runs a console command. Injected for the same reason: a widget test must
  /// not spawn PowerShell, and asserting on what WOULD have been launched is a
  /// better test than one that launches nothing.
  final Future<void> Function(String executable, List<String> arguments)? launch;

  const BackupView({super.key, required this.dataDir, this.launch});

  @override
  State<BackupView> createState() => BackupViewState();
}

class BackupViewState extends State<BackupView> {
  List<FileSystemEntity> _backups = [];
  String? _error;
  bool _launching = false;
  String? _note;
  String? _failure;

  @override
  void initState() {
    super.initState();
    refresh();
  }

  /// What is on disk right now, newest first.
  ///
  /// Read straight from the filesystem rather than through an endpoint. The
  /// backend has no route for this and should not get one - see the header -
  /// and a directory listing needs no key, so there is nothing an endpoint
  /// would add except a second way for this to be wrong.
  void refresh() {
    try {
      final dir = Directory(widget.dataDir);
      if (!dir.existsSync()) {
        setState(() {
          _backups = [];
          _error = null;
        });
        return;
      }
      final found = dir
          .listSync()
          .whereType<File>()
          .where((f) => f.path.toLowerCase().endsWith('.pipbak'))
          .toList()
        ..sort((a, b) => b.statSync().modified.compareTo(a.statSync().modified));
      setState(() {
        _backups = found;
        _error = null;
      });
    } catch (e) {
      setState(() => _error = 'Could not read ${widget.dataDir}: $e');
    }
  }

  String get _repoRoot {
    // The data directory's parent. main.dart resolves data/ from PIP_DATA_DIR
    // or a dev-relative fallback, and the scripts sit beside it - so deriving
    // one from the other keeps a single source of truth for where the
    // installation is, rather than adding a second env var to keep in step.
    final normalised = widget.dataDir.replaceAll('\\', '/');
    final trimmed = normalised.endsWith('/')
        ? normalised.substring(0, normalised.length - 1)
        : normalised;
    final cut = trimmed.lastIndexOf('/');
    return cut <= 0 ? '.' : trimmed.substring(0, cut);
  }

  String get exportScriptPath => '$_repoRoot/scripts/export_pip.ps1';

  Future<void> _runExport() async {
    setState(() {
      _launching = true;
      _note = null;
      _failure = null;
    });
    try {
      // Checked before spawning, because the failure it catches is otherwise
      // completely silent: PowerShell handed a -File path that does not exist
      // prints one line and exits, so the console appears and vanishes inside a
      // frame. From the user's side that is indistinguishable from a button
      // that does nothing, which is the worst way for this to fail - it gives
      // them nothing to report and nowhere to look.
      //
      // Only skipped when a test has injected its own runner, which has no
      // script to find.
      if (widget.launch == null && !File(exportScriptPath).existsSync()) {
        setState(() => _failure =
            'export_pip.ps1 was not found. PIP resolved its installation from '
            'the data directory, and got:');
        return;
      }

      final runner = widget.launch ?? _startConsole;
      // cmd /c start is what actually gives a GUI-subsystem app a NEW console
      // window. A direct Process.start would run PowerShell with nowhere to
      // draw - measured: with a detached spawn, which is what a GUI app gets,
      // the script never runs at all - and the password prompt would block
      // against a console that does not exist.
      //
      // The title is a real string rather than the empty one start technically
      // accepts: it names the window in the taskbar, and it sidesteps the
      // question of how an empty argument survives Dart's command-line
      // quoting and cmd's re-parsing of it.
      await runner('cmd.exe', [
        '/c',
        'start',
        'PIP Export', // start's first quoted argument is the window title
        'powershell.exe',
        '-ExecutionPolicy',
        'Bypass',
        '-NoProfile',
        '-File',
        exportScriptPath,
      ]);
      setState(() => _note =
          'Export running in a new window. It will ask for your live password, '
          'then a backup password. Refresh this screen when it finishes.');
    } catch (e) {
      setState(() => _failure = 'Could not open a console: $e');
    } finally {
      if (mounted) setState(() => _launching = false);
    }
  }

  static Future<void> _startConsole(String executable, List<String> arguments) async {
    await Process.start(executable, arguments, mode: ProcessStartMode.detached);
  }

  static String _humanSize(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(0)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  static String _humanDate(DateTime when) {
    String two(int n) => n.toString().padLeft(2, '0');
    return '${when.year}-${two(when.month)}-${two(when.day)} ${two(when.hour)}:${two(when.minute)}';
  }

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSpacing.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _header(pip),
          const SizedBox(height: AppSpacing.lg),
          if (_error != null) ...[
            Text(_error!, style: TextStyle(color: pip.danger, fontSize: 13)),
            const SizedBox(height: AppSpacing.md),
          ],
          _exportCard(pip),
          const SizedBox(height: AppSpacing.md),
          _backupsCard(pip),
          const SizedBox(height: AppSpacing.md),
          _notIncludedCard(pip),
          const SizedBox(height: AppSpacing.md),
          _restoreCard(pip),
        ],
      ),
    );
  }

  Widget _header(PipPalette pip) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        TagLabel('YOUR DATA', color: pip.accent, size: 11),
        const SizedBox(height: AppSpacing.xs),
        Text('Backup',
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: pip.text)),
        const SizedBox(height: 4),
        Text(
          'Everything PIP knows, in one encrypted file you can carry to another machine.',
          style: TextStyle(fontSize: 13.5, color: pip.textMuted, height: 1.5),
        ),
      ],
    );
  }

  Widget _exportCard(PipPalette pip) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Export',
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: pip.text)),
          const SizedBox(height: AppSpacing.xs),
          Text(
            'Writes a single .pipbak file - a complete copy of your database, encrypted '
            'under a backup password kept separate from your live one, so losing or '
            'leaking either does not cost you the other.',
            style: TextStyle(fontSize: 13, color: pip.textMuted, height: 1.55),
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            'Opens a console window. Your live password is asked for there, never here - '
            'an export that this app could perform on its own would be one anything '
            'talking to the backend could perform too.',
            style: TextStyle(fontSize: 12.5, color: pip.textFaint, height: 1.55),
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              FilledButton.icon(
                onPressed: _launching ? null : _runExport,
                icon: const Icon(Icons.ios_share, size: 18),
                label: Text(_launching ? 'Opening...' : 'Export now'),
              ),
              const SizedBox(width: AppSpacing.sm),
              OutlinedButton.icon(
                onPressed: refresh,
                icon: const Icon(Icons.refresh, size: 18),
                label: const Text('Refresh'),
              ),
            ],
          ),
          if (_note != null) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(_note!, style: TextStyle(fontSize: 12.5, color: pip.textMuted, height: 1.5)),
          ],
          if (_failure != null) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(_failure!, style: TextStyle(fontSize: 12.5, color: pip.danger, height: 1.5)),
          ],
          const SizedBox(height: AppSpacing.sm),
          Text(
            'Runs: $exportScriptPath',
            style: TextStyle(fontSize: 11.5, color: pip.textFaint, fontFamily: AppTheme.mono),
          ),
        ],
      ),
    );
  }

  Widget _backupsCard(PipPalette pip) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Backups on this machine',
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: pip.text)),
          const SizedBox(height: AppSpacing.xs),
          Text(
            'A backup that has never left this machine does not protect you from '
            'losing it. Copy one somewhere else.',
            style: TextStyle(fontSize: 13, color: pip.textMuted, height: 1.55),
          ),
          const SizedBox(height: AppSpacing.md),
          if (_backups.isEmpty)
            Text(
              'No .pipbak files in ${widget.dataDir} yet.',
              style: TextStyle(fontSize: 13, color: pip.textFaint),
            )
          else
            for (final file in _backups)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: Row(
                  children: [
                    Icon(Icons.lock_outline, size: 16, color: pip.textFaint),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: Text(
                        file.uri.pathSegments.last,
                        style: TextStyle(
                            fontSize: 13, color: pip.text, fontFamily: AppTheme.mono),
                      ),
                    ),
                    Text(
                      '${_humanSize(file.statSync().size)}  ·  '
                      '${_humanDate(file.statSync().modified)}',
                      style: TextStyle(fontSize: 12, color: pip.textMuted),
                    ),
                  ],
                ),
              ),
        ],
      ),
    );
  }

  /// What is and is not in the file, stated on the screen rather than left in
  /// a docstring somebody discovers on the machine they were relying on.
  Widget _notIncludedCard(PipPalette pip) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.info_outline, size: 16, color: pip.textMuted),
              const SizedBox(width: AppSpacing.sm),
              Text("What's in a backup",
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: pip.text)),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            'Everything PIP knows: your profile, skills, preferences and goals, every '
            'project, every decision with its reasoning, every conversation and every '
            'message in it, the review queue, provider consent - and the uploaded '
            'documents themselves, stored inside the database rather than only '
            'recorded there.',
            style: TextStyle(fontSize: 13, color: pip.textMuted, height: 1.55),
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            'Not in it: Ollama and its models, which are gigabytes and are not your '
            'data, and PIP itself. Install those on the new machine, restore, and '
            'nothing has to be re-entered or re-uploaded.',
            style: TextStyle(fontSize: 13, color: pip.textMuted, height: 1.55),
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            'The search index is not carried either, because it is derived - the '
            'restore rebuilds it from the documents it just wrote back.',
            style: TextStyle(fontSize: 12.5, color: pip.textFaint, height: 1.55),
          ),
        ],
      ),
    );
  }

  Widget _restoreCard(PipPalette pip) {
    const command = r'powershell -ExecutionPolicy Bypass -File scripts\restore_pip.ps1';
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Restoring on another machine',
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: pip.text)),
          const SizedBox(height: AppSpacing.xs),
          Text(
            'There is no restore button, and there cannot be one: a restore replaces the '
            'database this app has open, so it refuses to run while PIP is running. Use '
            'the "Restore PIP from backup" Desktop shortcut with PIP closed, or run:',
            style: TextStyle(fontSize: 13, color: pip.textMuted, height: 1.55),
          ),
          const SizedBox(height: AppSpacing.sm),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(AppSpacing.sm),
            decoration: BoxDecoration(
              color: pip.bg,
              borderRadius: AppRadius.sm,
              border: Border.all(color: pip.border),
            ),
            child: Row(
              children: [
                Expanded(
                  child: SelectableText(
                    command,
                    style: TextStyle(fontSize: 12.5, fontFamily: AppTheme.mono, color: pip.text),
                  ),
                ),
                IconButton(
                  tooltip: 'Copy',
                  iconSize: 16,
                  icon: Icon(Icons.copy_all_outlined, color: pip.textMuted),
                  onPressed: () {
                    Clipboard.setData(const ClipboardData(text: command));
                    setState(() => _note = 'Restore command copied.');
                  },
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            'It asks for the backup password, then a NEW live password for that machine. '
            'The old one is not recovered - a .pipbak carries your data, never your live '
            'secret.',
            style: TextStyle(fontSize: 12.5, color: pip.textFaint, height: 1.55),
          ),
        ],
      ),
    );
  }
}
