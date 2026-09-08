// Getting a model, on the one launch where not having one is the whole story.
//
// WHY THIS EXISTS WHEN model_browser.dart ALREADY DOES THIS
//
// It does not do this. The browser is a picker for somebody who already has
// PIP working and wants a different model: a curated list, a free-text field
// for anything in Ollama's library, VRAM warnings, the model currently in use.
// Every one of those is the right thing to show a person who knows what they
// are choosing between.
//
// A first run is not that. Before this screen existed, finishing onboarding
// dropped you into a chat that could not answer, because nothing had been
// downloaded and nothing had said so - you typed a message, it failed, and the
// way out was to find a settings screen you had no reason to know about and
// wait for 4.7 GB you were never warned about.
//
// So this asks one question with three or four answers, says what each costs
// in gigabytes, and downloads it in front of you. The browser stays where it
// is for every launch after this one.
//
// WHY IT IS ALWAYS SKIPPABLE
//
// Because the alternative is a first run that cannot be finished. Somebody on
// a metered connection, or a train, or a machine where Ollama will not install
// today, still owns their copy of PIP - and the rest of it (memory, projects,
// documents, the profile) works without a model. Trapping them here to protect
// them from an application that will not answer yet would be the worse of the
// two failures.

import 'dart:async';

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../logo.dart';
import '../theme.dart';

class ModelSetupScreen extends StatefulWidget {
  final ApiClient api;

  /// Called when this step is finished with - by downloading, or by skipping.
  /// The caller decides what comes next; this screen does not know.
  final VoidCallback onDone;

  const ModelSetupScreen({super.key, required this.api, required this.onDone});

  @override
  State<ModelSetupScreen> createState() => ModelSetupScreenState();
}

class ModelSetupScreenState extends State<ModelSetupScreen> {
  List<Map<String, dynamic>>? _models;

  /// Set when the catalogue could not reach Ollama. Not an error state for
  /// this screen - it is the OTHER thing this screen is for, and it has its
  /// own panel.
  bool _ollamaMissing = false;

  String? _error;
  bool _checking = false;

  /// The live pull, polled rather than streamed - see ApiClient.startPull.
  Map<String, dynamic>? _pull;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _checking = true;
      _error = null;
    });
    try {
      final catalog = await widget.api.getModelCatalog();
      if (!mounted) return;
      final models = (catalog['models'] as List<dynamic>? ?? [])
          .cast<Map<String, dynamic>>();
      setState(() {
        _models = models;
        // The catalogue is deliberately fail-open: it still lists what could
        // be pulled when Ollama is unreachable, and reports why in `error`.
        // That is what distinguishes "no models yet" from "no Ollama".
        _ollamaMissing = catalog['error'] != null;
        _checking = false;
      });
      // A pull may already be running - the backend keeps pulling across a
      // client restart, so this screen should pick one up rather than offer
      // to start a second.
      await _refreshPull();
      if (_pull?['status'] == 'pulling') _startPolling();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '$e';
        _checking = false;
      });
    }
  }

  Future<void> _refreshPull() async {
    try {
      final status = await widget.api.getPullStatus();
      if (mounted) setState(() => _pull = status);
    } catch (_) {
      // A progress reading that could not be taken is not worth a message on
      // this screen. The next tick tries again.
    }
  }

  void _startPolling() {
    _poll?.cancel();
    _poll = Timer.periodic(const Duration(seconds: 1), (_) async {
      await _refreshPull();
      if (_pull?['status'] != 'pulling') {
        _poll?.cancel();
        // The list carries `pulled`, which has just changed for one of them.
        if (_pull?['status'] == 'done') await _load();
      }
    });
  }

  Future<void> _download(String name) async {
    setState(() => _error = null);
    try {
      await widget.api.startPull(name);
      await _refreshPull();
      _startPolling();
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    }
  }

  bool get _isPulling => _pull?['status'] == 'pulling';
  bool get _hasModel => (_models ?? []).any((m) => m['pulled'] == true);

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;

    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const PipLogo(size: 48),
                const SizedBox(height: AppSpacing.lg),
                Text(
                  _ollamaMissing ? 'PIP needs Ollama' : 'Choose a model',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.w600, color: pip.text),
                ),
                const SizedBox(height: AppSpacing.sm),
                Text(
                  _ollamaMissing
                      ? 'PIP answers using a model running on this computer, and Ollama '
                          'is what runs it. Install it, then come back to this screen.'
                      : 'PIP answers using a model on this computer - nothing you type is '
                          'sent anywhere. Pick one to download now; you can change it later.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 13.5, height: 1.5, color: pip.textFaint),
                ),
                const SizedBox(height: AppSpacing.xl),

                if (_checking && _models == null)
                  const Center(child: Padding(
                    padding: EdgeInsets.all(AppSpacing.xl),
                    child: CircularProgressIndicator(),
                  ))
                else if (_ollamaMissing)
                  _OllamaMissing(onRecheck: _load, checking: _checking)
                else if (_isPulling)
                  _Progress(pull: _pull!)
                else
                  ..._choices(pip),

                if (_error != null) ...[
                  const SizedBox(height: AppSpacing.md),
                  Text(_error!, style: TextStyle(fontSize: 12.5, color: pip.danger)),
                ],

                const SizedBox(height: AppSpacing.xl),
                _continueRow(pip),
              ],
            ),
          ),
        ),
      ),
    );
  }

  List<Widget> _choices(PipPalette pip) {
    final models = _models ?? const [];
    if (models.isEmpty) {
      return [
        Text(
          'Ollama is running but has nothing to suggest.',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 13, color: pip.textFaint),
        ),
      ];
    }

    // Only what this machine can actually run, and only a few of them. `fits`
    // is null when VRAM could not be detected, which is not the same as false
    // - a machine with no NVIDIA card is one where this cannot tell, so those
    // are shown rather than hidden.
    final usable = models.where((m) => m['fits'] != false).toList();
    final shown = (usable.isEmpty ? models : usable).take(4).toList();

    return [
      for (final model in shown)
        Padding(
          padding: const EdgeInsets.only(bottom: AppSpacing.sm),
          child: _ModelChoice(
            model: model,
            onDownload: () => _download('${model['name']}'),
          ),
        ),
    ];
  }

  Widget _continueRow(PipPalette pip) {
    // "Continue" rather than "Skip" once a download is running, because the
    // download does not stop when this screen closes - it is server-side, and
    // it survives the client. Calling that button Skip would be a lie about
    // what happens next.
    final label = _hasModel
        ? 'Continue'
        : _isPulling
            ? 'Continue while it downloads'
            : 'Skip for now';

    return Column(
      children: [
        if (_hasModel)
          FilledButton(
            onPressed: widget.onDone,
            child: const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('Continue'),
            ),
          )
        else
          TextButton(onPressed: widget.onDone, child: Text(label)),
        if (!_hasModel && !_isPulling) ...[
          const SizedBox(height: AppSpacing.xs),
          Text(
            'PIP will work without a model, but it will not be able to answer you.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 11.5, color: pip.textFaint),
          ),
        ],
      ],
    );
  }
}

class _ModelChoice extends StatelessWidget {
  final Map<String, dynamic> model;
  final VoidCallback onDownload;

  const _ModelChoice({required this.model, required this.onDownload});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    final pulled = model['pulled'] == true;
    final sizeGb = model['size_gb'];

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: pip.surfaceRaised,
        border: Border.all(color: pip.border),
        borderRadius: AppRadius.md,
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    Text(
                      '${model['name']}',
                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: pip.text),
                    ),
                    if (sizeGb != null) ...[
                      const SizedBox(width: AppSpacing.sm),
                      // The number nobody is told until they are already
                      // waiting for it.
                      Text('$sizeGb GB', style: TextStyle(fontSize: 12, color: pip.textFaint)),
                    ],
                  ],
                ),
                if ('${model['note']}'.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(
                    '${model['note']}',
                    style: TextStyle(fontSize: 12, height: 1.4, color: pip.textFaint),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          if (pulled)
            Text('Ready', style: TextStyle(fontSize: 12.5, color: pip.accent))
          else
            FilledButton.tonal(onPressed: onDownload, child: const Text('Download')),
        ],
      ),
    );
  }
}

class _Progress extends StatelessWidget {
  final Map<String, dynamic> pull;
  const _Progress({required this.pull});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    final completed = (pull['completed'] as num?)?.toDouble() ?? 0;
    final total = (pull['total'] as num?)?.toDouble() ?? 0;
    // Indeterminate until Ollama has reported a total. It sends status changes
    // before it sends byte counts, and a bar sitting at 0% for the first few
    // seconds reads as stuck rather than starting.
    final fraction = total > 0 ? (completed / total).clamp(0.0, 1.0) : null;

    String size(double bytes) => '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Downloading ${pull['model']}',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: pip.text),
        ),
        const SizedBox(height: AppSpacing.md),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(value: fraction, minHeight: 8),
        ),
        const SizedBox(height: AppSpacing.sm),
        Text(
          total > 0
              ? '${size(completed)} of ${size(total)}'
              : '${pull['detail'] ?? 'starting'}...',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 12.5, color: pip.textFaint),
        ),
      ],
    );
  }
}

class _OllamaMissing extends StatelessWidget {
  final VoidCallback onRecheck;
  final bool checking;

  const _OllamaMissing({required this.onRecheck, required this.checking});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.all(AppSpacing.lg),
          decoration: BoxDecoration(
            color: pip.surfaceRaised,
            border: Border.all(color: pip.border),
            borderRadius: AppRadius.md,
          ),
          child: Column(
            children: [
              Text(
                'Download Ollama from',
                style: TextStyle(fontSize: 13, color: pip.textFaint),
              ),
              const SizedBox(height: AppSpacing.xs),
              // Selectable rather than a link: this window has no browser in
              // it, and a URL somebody can copy is more use than one they can
              // only look at.
              SelectableText(
                'https://ollama.com/download',
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: pip.accent),
              ),
              const SizedBox(height: AppSpacing.md),
              Text(
                'Install it, leave it running, then check again.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 12.5, color: pip.textFaint),
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        FilledButton.tonal(
          onPressed: checking ? null : onRecheck,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 10),
            child: Text(checking ? 'Checking...' : 'Check again'),
          ),
        ),
      ],
    );
  }
}
