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
// WHY THE RESTORE BUTTON STAGES INSTEAD OF RESTORING
// --------------------------------------------------
// This said, for a long time, that there could be no restore button at all: a
// restore replaces the database the running backend has open, and
// restore_backup.py refuses while PIP holds the lock. That was right about the
// SWAP and wrong about the operation, because a restore is two separable
// things - converting the backup into a live database, which needs both
// passwords and touches nothing that is open, and moving the result into
// place, which needs no password and cannot be done while the file is held.
//
// So the button does the first half now and records the second for the next
// start, where the lifespan performs it before anything opens a database. The
// conversion is proven before it is recorded - the backup opens, its integrity
// passes, and the new database opens under the new key with the same row
// counts - so what waits for the restart is a rename, not a gamble.
//
// Deferring the WHOLE restore was the obvious alternative and is the one thing
// that could not be done: it would mean writing two passwords to disk for the
// next launch to read. See backend/core/restore.py.
//
// scripts/restore_backup.py is still there and still does the whole job in one
// pass, on the Desktop shortcut (scripts/install_shortcuts.ps1). That is the
// path for a machine with no app window - a fresh install, or one whose
// database is gone - which is exactly when a button in the app is unreachable.

import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api_client.dart';
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

  /// Needed since this screen learned to restore: the staged restore lives in
  /// the backend, because it has to survive the app being closed - which is
  /// the very thing that completes it.
  final ApiClient api;

  const BackupView({super.key, required this.dataDir, required this.api, this.launch});

  @override
  State<BackupView> createState() => BackupViewState();
}

class BackupViewState extends State<BackupView> {
  /// The staged restore, or null. Read from the backend rather than remembered
  /// here: it survives closing the app, which is the entire point of it.
  Map<String, dynamic>? _pendingRestore;
  bool _busyRestore = false;
  String? _restoreError;

  List<FileSystemEntity> _backups = [];
  String? _error;
  bool _launching = false;
  String? _note;
  String? _failure;

  @override
  void initState() {
    super.initState();
    refresh();
    _loadRestoreStatus();
  }

  /// What is on disk right now, newest first.
  ///
  /// Read straight from the filesystem rather than through an endpoint. The
  /// backend has no route for this and should not get one - see the header -
  /// and a directory listing needs no key, so there is nothing an endpoint
  /// would add except a second way for this to be wrong.
  void refresh() {
    // The staged restore is re-read here and not only in initState, because
    // this screen never re-mounts: home_shell keeps every tab alive in an
    // IndexedStack and calls refresh() when the tab is selected. Without this
    // the card kept offering to choose a file while the backend already had
    // one staged - found by opening the screen after staging one.
    _loadRestoreStatus();
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
          _importCard(pip),
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

  /// Ask the backend whether a restore is already staged.
  ///
  /// Failure is swallowed: this screen's job is exporting, and a restore that
  /// could not be reported is not a reason to put an error banner over it.
  Future<void> _loadRestoreStatus() async {
    try {
      final status = await widget.api.restoreStatus();
      if (!mounted) return;
      setState(() => _pendingRestore = status['pending'] == true ? status : null);
    } catch (_) {}
  }

  Future<void> _pickAndStageRestore() async {
    final picked = await FilePicker.pickFile(
      type: FileType.custom,
      allowedExtensions: ['pipbak'],
    );
    if (picked == null) return;

    // The picker can hand back an entry with no filesystem path (a stream on
    // some platforms). Nothing here can read those - the backend opens the
    // file itself, by path - so it is refused rather than half-attempted.
    final path = picked.path;
    if (path == null || path.isEmpty) {
      setState(() => _restoreError = 'That file has no path PIP can read.');
      return;
    }
    if (!mounted) return;

    final passwords = await showDialog<List<String>>(
      context: context,
      builder: (context) => _RestoreDialog(fileName: picked.name),
    );
    if (passwords == null) return;

    setState(() {
      _busyRestore = true;
      _restoreError = null;
    });
    try {
      final staged = await widget.api.stageRestore(
        path: path,
        backupPassword: passwords[0],
        newPassword: passwords[1],
      );
      if (!mounted) return;
      setState(() => _pendingRestore = staged);
    } catch (e) {
      if (!mounted) return;
      setState(() => _restoreError = e is ApiException ? e.detail : '$e');
    } finally {
      if (mounted) setState(() => _busyRestore = false);
    }
  }

  Future<void> _cancelRestore() async {
    setState(() {
      _busyRestore = true;
      _restoreError = null;
    });
    try {
      await widget.api.cancelRestore();
      if (mounted) setState(() => _pendingRestore = null);
    } catch (e) {
      if (mounted) setState(() => _restoreError = e is ApiException ? e.detail : '$e');
    } finally {
      if (mounted) setState(() => _busyRestore = false);
    }
  }

  /// Import a .pipbak and stage it to replace this profile.
  ///
  /// The card that used to say a restore button could not exist. That was
  /// right about the swap and wrong about the operation: converting the backup
  /// needs both passwords and touches nothing that is open, and only the
  /// rename has to wait for a restart. See backend/core/restore.py.
  Widget _importCard(PipPalette pip) {
    final pending = _pendingRestore;
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.download_outlined, size: 18, color: pip.textMuted),
              const SizedBox(width: AppSpacing.sm),
              Text('Restore from a backup',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: pip.text)),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            'Replaces everything in this profile with the contents of a .pipbak. '
            'You choose a NEW password for it here - a backup carries your data, '
            'never your live secret.',
            style: TextStyle(fontSize: 13, color: pip.textMuted, height: 1.55),
          ),
          const SizedBox(height: AppSpacing.md),

          if (pending != null) ...[
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(AppSpacing.md),
              decoration: BoxDecoration(
                color: pip.accentSoft,
                borderRadius: AppRadius.sm,
                border: Border.all(color: pip.accent.withValues(alpha: 0.4)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Ready to restore on the next start',
                    style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: pip.accent),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${pending['source']} - ${pending['rows']} rows across '
                    '${pending['tables']} tables, checked and ready. Close PIP and '
                    'open it again to finish. Nothing has been replaced yet.',
                    style: TextStyle(fontSize: 12.5, color: pip.text, height: 1.55),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  GhostButton(
                    label: 'Cancel the restore',
                    color: pip.danger,
                    onTap: _busyRestore ? null : _cancelRestore,
                  ),
                ],
              ),
            ),
          ] else
            Row(
              children: [
                FilledButton.icon(
                  onPressed: _busyRestore ? null : _pickAndStageRestore,
                  icon: const Icon(Icons.folder_open_outlined, size: 16),
                  label: Text(_busyRestore ? 'Checking the backup...' : 'Choose a .pipbak'),
                ),
              ],
            ),

          if (_restoreError != null) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(_restoreError!,
                style: TextStyle(fontSize: 12.5, color: pip.danger, height: 1.55)),
          ],

          const SizedBox(height: AppSpacing.sm),
          Text(
            'Nothing is replaced until PIP restarts, and what was there is kept '
            'beside the new database rather than deleted.',
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
          Text('Restoring somewhere else',
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: pip.text)),
          const SizedBox(height: AppSpacing.xs),
          Text(
            'The card above restores into THIS installation. On a machine where PIP '
            'is not installed, or whose database is gone, there is no window to click '
            'in - use the "Restore PIP from backup" Desktop shortcut, or run:',
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

/// The two passwords a restore needs, and the one sentence that explains why
/// there are two.
///
/// A .pipbak is encrypted under the password it was exported with, and the
/// live database is encrypted under the password this machine will use. They
/// are different secrets on purpose: a backup carries your data across, never
/// your live key.
class _RestoreDialog extends StatefulWidget {
  final String fileName;
  const _RestoreDialog({required this.fileName});

  @override
  State<_RestoreDialog> createState() => _RestoreDialogState();
}

class _RestoreDialogState extends State<_RestoreDialog> {
  final _backup = TextEditingController();
  final _fresh = TextEditingController();
  final _confirm = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _backup.dispose();
    _fresh.dispose();
    _confirm.dispose();
    super.dispose();
  }

  void _submit() {
    if (_backup.text.isEmpty) {
      setState(() => _error = 'Enter the password this backup was exported with.');
      return;
    }
    if (_fresh.text != _confirm.text) {
      setState(() => _error = 'Those two passwords are different.');
      return;
    }
    if (_fresh.text.length < 8) {
      setState(() => _error = 'Use at least 8 characters for the new password.');
      return;
    }
    Navigator.pop(context, [_backup.text, _fresh.text]);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('Restore ${widget.fileName}?'),
      content: SizedBox(
        width: 420,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Everything in this profile will be replaced by what is in the backup: '
                'every conversation, everything PIP learned, your decisions and your '
                'documents.',
                style: TextStyle(fontSize: 13, height: 1.5, color: context.pip.text),
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                'Nothing is replaced until PIP restarts, and what is there now is kept '
                'beside the new database rather than deleted.',
                style: TextStyle(fontSize: 13, height: 1.5, color: context.pip.textMuted),
              ),
              const SizedBox(height: AppSpacing.lg),
              TextField(
                controller: _backup,
                obscureText: true,
                autofocus: true,
                decoration: const InputDecoration(labelText: "The backup's password"),
              ),
              const SizedBox(height: AppSpacing.md),
              TextField(
                controller: _fresh,
                obscureText: true,
                decoration: const InputDecoration(labelText: 'New password for this machine'),
              ),
              const SizedBox(height: AppSpacing.md),
              TextField(
                controller: _confirm,
                obscureText: true,
                onSubmitted: (_) => _submit(),
                decoration: const InputDecoration(labelText: 'New password again'),
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                'The new password is the one you will sign in with afterwards. The '
                "backup's own password is not recovered or reused.",
                style: TextStyle(fontSize: 11.5, height: 1.5, color: context.pip.textFaint),
              ),
              if (_error != null) ...[
                const SizedBox(height: AppSpacing.md),
                Text(_error!, style: TextStyle(fontSize: 12, color: context.pip.danger)),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: _submit, child: const Text('Check and stage')),
      ],
    );
  }
}
