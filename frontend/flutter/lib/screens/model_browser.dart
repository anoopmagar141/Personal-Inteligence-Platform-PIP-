// Choosing and downloading a model, without leaving PIP.
//
// WHY A CURATED LIST *AND* A TEXT FIELD
// ------------------------------------
// Ollama has no public library API, so PIP cannot show a live catalogue of
// everything available - and scraping ollama.com would make this screen depend
// on somebody else's HTML.
//
// A short curated list answers the question most people actually have ("which
// one should I pick?"), which a search box over thousands of names does not.
// The text field beneath it is what keeps the feature honest: the requirement
// is ANY open-source model, and a picker limited to seven names would be a
// worse product than the terminal it replaces. Anything Ollama can pull works,
// whether or not this file has heard of it.
//
// WHY IT WARNS INSTEAD OF REFUSING
// --------------------------------
// vram_gb from the backend is what the weights need resident, and it is
// approximate by nature - context length and KV cache push real usage above it.
// A number that cannot be exact must not be a gate. So a model too big for the
// card is marked, clearly, and still selectable: the user knows things about
// their machine that nvidia-smi does not, and being wrong in the direction of
// blocking somebody from their own hardware is the worse mistake.
//
// It also says nothing at all when VRAM could not be detected. A machine with
// no NVIDIA GPU is not one where every model fails; it is one where this cannot
// tell, and inventing a warning would train people to ignore the real ones.

import 'dart:async';

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';

class ModelBrowser extends StatefulWidget {
  final ApiClient api;

  /// Called when a pull finishes, so the caller can re-read its model list -
  /// the newly pulled model is only selectable once Ollama reports it.
  final VoidCallback onChanged;

  const ModelBrowser({super.key, required this.api, required this.onChanged});

  @override
  State<ModelBrowser> createState() => ModelBrowserState();
}

class ModelBrowserState extends State<ModelBrowser> {
  Map<String, dynamic>? _catalog;
  String? _error;

  final _nameController = TextEditingController();
  Timer? _poll;
  Map<String, dynamic>? _pull;

  @override
  void initState() {
    super.initState();
    _load();
    _refreshPullStatus();
  }

  @override
  void dispose() {
    _poll?.cancel();
    _nameController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final catalog = await widget.api.getModelCatalog();
      if (mounted) setState(() { _catalog = catalog; _error = null; });
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  /// Read once on open, so a pull already running when this screen is opened
  /// shows its progress rather than an idle screen. The backend holds the
  /// state, not this widget, precisely so a download survives navigating away.
  Future<void> _refreshPullStatus() async {
    try {
      final status = await widget.api.getPullStatus();
      if (!mounted) return;
      setState(() => _pull = status);
      if (status['status'] == 'pulling') _startPolling();
    } catch (_) {
      // A backend that cannot answer is not worth an error on this screen -
      // the catalogue above it is the reason somebody opened it.
    }
  }

  void _startPolling() {
    _poll?.cancel();
    // One second: fast enough that a progress bar moves, slow enough that a
    // 5GB download does not spend the whole time answering status requests.
    _poll = Timer.periodic(const Duration(seconds: 1), (_) async {
      try {
        final status = await widget.api.getPullStatus();
        if (!mounted) return;
        setState(() => _pull = status);
        if (status['status'] != 'pulling') {
          _poll?.cancel();
          if (status['status'] == 'done') {
            await _load();
            widget.onChanged();
          }
        }
      } catch (_) {
        _poll?.cancel();
      }
    });
  }

  Future<void> _pullModel(String name) async {
    if (name.trim().isEmpty) return;
    setState(() => _error = null);
    try {
      await widget.api.startPull(name.trim());
      await _refreshPullStatus();
      _startPolling();
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  bool get _busy => _pull?['status'] == 'pulling';

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    final vram = _catalog?['vram_gb'];

    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TagLabel('Get a model', color: pip.text, size: 12),
          const SizedBox(height: 4),
          Text(
            vram == null
                ? 'Any model Ollama can pull. PIP could not read this machine’s VRAM, '
                    'so it has nothing to say about what will fit.'
                : 'Any model Ollama can pull. This machine has ${vram}GB of VRAM, '
                    'and models needing more are marked.',
            style: TextStyle(fontSize: 12.5, color: pip.textMuted, height: 1.5),
          ),
          const SizedBox(height: AppSpacing.md),

          if (_error != null) ...[
            Text(_error!, style: TextStyle(fontSize: 12.5, color: pip.danger)),
            const SizedBox(height: AppSpacing.sm),
          ],

          if (_pull != null && _pull!['status'] != 'idle') _progress(pip),

          // The spinner is suppressed once there is an error, because the two
          // together say "still loading" and "it failed" at the same time - and
          // an indicator that spins forever after a failed load is a hang as far
          // as anybody watching it is concerned.
          if (_catalog == null && _error == null)
            const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
          else if (_catalog != null)
            for (final model in (_catalog!['models'] as List<dynamic>))
              _row(pip, model as Map<String, dynamic>),

          const SizedBox(height: AppSpacing.md),
          Divider(color: pip.border, height: 1),
          const SizedBox(height: AppSpacing.md),

          Text(
            'Something else',
            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: pip.text),
          ),
          const SizedBox(height: 4),
          Text(
            'Any name from the Ollama library, or a Hugging Face GGUF reference. '
            'If it does not exist, Ollama says so.',
            style: TextStyle(fontSize: 12, color: pip.textFaint, height: 1.5),
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _nameController,
                  enabled: !_busy,
                  style: const TextStyle(fontSize: 13),
                  decoration: const InputDecoration(
                    hintText: 'e.g. qwen2.5:32b',
                    isDense: true,
                  ),
                  onSubmitted: _busy ? null : _pullModel,
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              FilledButton(
                onPressed: _busy ? null : () => _pullModel(_nameController.text),
                child: const Text('Download'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _progress(PipPalette pip) {
    final status = _pull!['status'] as String;
    final completed = (_pull!['completed'] as num?)?.toDouble() ?? 0;
    final total = (_pull!['total'] as num?)?.toDouble() ?? 0;
    final fraction = total > 0 ? (completed / total).clamp(0.0, 1.0) : null;

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            switch (status) {
              'pulling' => 'Downloading ${_pull!['model']}',
              'done' => 'Downloaded ${_pull!['model']}',
              _ => 'Could not download ${_pull!['model']}',
            },
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: status == 'error' ? pip.danger : pip.text,
            ),
          ),
          const SizedBox(height: 6),
          if (status == 'pulling') ...[
            // An indeterminate bar while total is unknown, rather than a bar
            // pinned at zero: Ollama sends manifest and verify statuses with no
            // byte counts, and a stuck bar reads as a hang.
            LinearProgressIndicator(value: fraction),
            const SizedBox(height: 4),
            Text(
              fraction == null
                  ? '${_pull!['detail']}'
                  : '${(fraction * 100).toStringAsFixed(0)}%  ${_gb(completed)} of ${_gb(total)}',
              style: TextStyle(fontSize: 11.5, color: pip.textFaint),
            ),
          ] else if (status == 'error')
            Text('${_pull!['error']}', style: TextStyle(fontSize: 12, color: pip.danger))
          else
            Text('Select it above to make it active.',
                style: TextStyle(fontSize: 12, color: pip.textMuted)),
        ],
      ),
    );
  }

  static String _gb(double bytes) => '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';

  Widget _row(PipPalette pip, Map<String, dynamic> model) {
    final name = model['name'] as String;
    final pulled = model['pulled'] == true;
    final fits = model['fits'];
    final note = '${model['note'] ?? ''}';
    final sizeGb = model['size_gb'];

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Icon(
              pulled ? Icons.check_circle_outline : Icons.cloud_download_outlined,
              size: 16,
              color: pulled ? pip.accent : pip.textFaint,
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(name,
                          style: TextStyle(
                              fontSize: 13, color: pip.text, fontFamily: AppTheme.mono)),
                    ),
                    if (sizeGb != null) ...[
                      const SizedBox(width: AppSpacing.sm),
                      Text('${sizeGb}GB',
                          style: TextStyle(fontSize: 11.5, color: pip.textMuted)),
                    ],
                    // Only for an explicit false. Null means VRAM is unknown,
                    // and a warning there would be a guess dressed as a fact.
                    if (fits == false) ...[
                      const SizedBox(width: AppSpacing.sm),
                      _Warn(text: 'needs ${model['vram_gb']}GB'),
                    ],
                  ],
                ),
                if (note.isNotEmpty)
                  Text(note,
                      style: TextStyle(fontSize: 11.5, color: pip.textFaint, height: 1.45)),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          if (!pulled)
            TextButton(
              onPressed: _busy ? null : () => _pullModel(name),
              child: const Text('Download'),
            ),
        ],
      ),
    );
  }
}

class _Warn extends StatelessWidget {
  final String text;
  const _Warn({required this.text});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
      decoration: BoxDecoration(color: pip.dangerSoft, borderRadius: AppRadius.sm),
      child: Text(text, style: TextStyle(fontSize: 10.5, color: pip.danger)),
    );
  }
}
