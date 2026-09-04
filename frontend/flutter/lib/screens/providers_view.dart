// Providers: consent, scope, and which local model PIP runs.
//
// "Grant consent" used to send full_inference for every provider, in this
// client and in the web prototype before it. That was always a VALID request -
// backend/api/server.py's VALID_CONSENT_SCOPES accepts it - but it was the
// broadest of the four scopes rather than the narrowest one that would do, so
// a provider that only ever needed embeddings was consented for inference on
// your whole assembled context.
//
// The constitution puts a hard stop at stage_8_before_network_call and treats
// scope as the thing being enforced there. Sending one scope for everything
// left that machinery real but unused: the gate would faithfully enforce a
// permission nobody had actually chosen. Granting is now an explicit choice
// among the three scopes that mean something, with no preselection - picking
// a default here would be this screen making the least-privilege decision on
// the user's behalf, which is the decision the gate exists to leave to them.
//
// "none" is a valid scope and is deliberately not offered: it would set
// user_consented while consenting to nothing, which is what Revoke already
// says without the ambiguity.

import 'package:flutter/material.dart';

import '../api_client.dart';
import 'model_browser.dart';
import '../theme.dart';

class ProvidersView extends StatefulWidget {
  final ApiClient api;
  const ProvidersView({super.key, required this.api});

  @override
  State<ProvidersView> createState() => _ProvidersViewState();
}

class _ProvidersViewState extends State<ProvidersView> {
  List<dynamic>? _providers;

  /// "The provider list could not be loaded" - a page that has nothing to
  /// show. NOT where a failed grant goes: build() returns early on this, so
  /// putting an action's failure here replaces the whole screen, list and
  /// model picker included, with one sentence and no way back.
  String? _error;

  /// Keyed by provider_id, so a refusal appears on the provider that caused
  /// it. Consent is per provider and so is the reason it was refused.
  final Map<String, String> _rowErrors = {};
  final Set<String> _busy = {};

  List<dynamic>? _models; // null = loading, [] = loaded but empty (Ollama down or nothing pulled)
  String? _activeModel;
  String? _modelError;
  bool _switchingModel = false;

  @override
  void initState() {
    super.initState();
    _load();
    _loadModels();
  }

  Future<void> _load() async {
    try {
      final providers = await widget.api.getProviders();
      if (mounted) setState(() => _providers = providers);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _loadModels() async {
    try {
      final results = await Future.wait([widget.api.getLlmModels(), widget.api.getActiveModel()]);
      if (mounted) {
        setState(() {
          _models = results[0] as List<dynamic>;
          _activeModel = results[1] as String;
          _modelError = null;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _modelError = error.toString());
    }
  }

  Future<void> _selectModel(String? modelName) async {
    if (modelName == null || modelName == _activeModel) return;
    setState(() => _switchingModel = true);
    try {
      await widget.api.setActiveModel(modelName);
      if (mounted) setState(() => _activeModel = modelName);
    } catch (error) {
      if (mounted) setState(() => _modelError = error.toString());
    } finally {
      if (mounted) setState(() => _switchingModel = false);
    }
  }

  /// One shape for both consent actions: mark the row busy, run the call,
  /// reload on success, and on failure put the server's own sentence on that
  /// row while leaving everything else on screen.
  Future<void> _act(String providerId, Future<void> Function() action) async {
    setState(() {
      _busy.add(providerId);
      _rowErrors.remove(providerId);
    });
    try {
      await action();
      await _load();
    } catch (error) {
      // The server names the scope it rejected and lists the ones it accepts.
      // That sentence is more use than "grant failed" ever is.
      if (mounted) setState(() => _rowErrors[providerId] = error.toString());
    } finally {
      if (mounted) setState(() => _busy.remove(providerId));
    }
  }

  Future<void> _grant(String providerId) async {
    final scope = await showDialog<String>(
      context: context,
      builder: (context) => _ScopeDialog(providerId: providerId),
    );
    if (scope == null) return;
    await _act(providerId, () => widget.api.grantConsent(providerId, scope));
  }

  Future<void> _revoke(String providerId) async {
    // Was unguarded: a failed revoke threw into nothing and the row simply did
    // not change, which reads exactly like a button that does not work. On a
    // consent screen that is the worst possible thing to be unsure about.
    await _act(providerId, () => widget.api.revokeConsent(providerId));
  }

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    if (_error != null) {
      return Center(child: Text(_error!, style: TextStyle(color: pip.danger)));
    }
    if (_providers == null) return const Center(child: CircularProgressIndicator());

    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSpacing.xl),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 720),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const PageHeader(
              eyebrow: 'Trust',
              title: 'Providers',
              description: 'Local providers never need consent. Cloud providers are blocked until you explicitly consent (Stage 8, fail-closed).',
            ),
            _buildModelPicker(),
            const SizedBox(height: AppSpacing.md),
            // Getting a model and choosing one are separate acts, so they are
            // separate cards: the picker above is about what PIP runs now, this
            // is about what is available to run at all.
            ModelBrowser(api: widget.api, onChanged: _loadModels),
            const SizedBox(height: AppSpacing.lg),
            // Cards, not a DataTable. Five columns plus an action button did
            // not fit the 720px this screen is constrained to, and the cell
            // holding the button ended up somewhere a tap could not reach it -
            // the control was visible and inert. Every other list in this app
            // is a card for the same reason, and it survives a narrow window.
            for (final provider in _providers!) _providerCard(provider as Map<String, dynamic>),
          ],
        ),
      ),
    );
  }

  Widget _providerCard(Map<String, dynamic> provider) {
    final pip = context.pip;
    final isCloud = provider['is_cloud'] == true;
    final scope = '${provider['consent_scope'] ?? ''}';
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: SectionCard(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.md),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          '${provider['provider_id']}',
                          style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: pip.text),
                        ),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      TagLabel(isCloud ? 'cloud' : 'local', color: isCloud ? pip.textMuted : pip.accent, size: 10.5),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    // The scope is the part worth reading: "granted" alone
                    // does not say what was granted.
                    scope.isEmpty ? _consentLabel(provider) : '${_consentLabel(provider)} - $scope',
                    style: TextStyle(fontSize: 12, color: pip.textMuted),
                  ),
                  if (_rowErrors[provider['provider_id']] != null) ...[
                    const SizedBox(height: 6),
                    Text(
                      _rowErrors[provider['provider_id']]!,
                      style: TextStyle(fontSize: 11.5, color: pip.danger),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            if (_busy.contains(provider['provider_id']))
              const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
            else
              _actionButton(provider),
          ],
        ),
      ),
    );
  }

  String _consentLabel(dynamic provider) {
    if (provider['is_cloud'] != true) return 'n/a';
    final consented = provider['user_consented'] == true && provider['revoked'] != true;
    if (consented) return 'granted';
    if (provider['revoked'] == true) return 'revoked';
    return 'not consented';
  }

  Widget _actionButton(dynamic provider) {
    final pip = context.pip;
    if (provider['is_cloud'] != true) {
      return TagLabel('n/a (local)', color: pip.textFaint);
    }
    final consented = provider['user_consented'] == true && provider['revoked'] != true;
    final providerId = provider['provider_id'] as String;
    if (consented) {
      return GhostButton(label: 'Revoke', color: pip.danger, onTap: () => _revoke(providerId));
    }
    return GhostButton(label: 'Grant consent', onTap: () => _grant(providerId));
  }

  Widget _buildModelPicker() {
    final pip = context.pip;
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: TagLabel('Local model', color: pip.text, size: 12),
              ),
              if (_switchingModel)
                const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2)),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'Which Ollama model PIP uses for chat and Observer (ADR-033: same model for both).',
            style: TextStyle(fontSize: 12.5, color: pip.textMuted),
          ),
          const SizedBox(height: AppSpacing.md),
          if (_modelError != null) ...[
            Text(_modelError!, style: TextStyle(fontSize: 12.5, color: pip.danger)),
            const SizedBox(height: AppSpacing.sm),
          ],
          if (_models == null)
            const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
          else if (_models!.isEmpty)
            Text(
              'No models pulled yet. Pick one below and PIP will download it.',
              style: TextStyle(fontSize: 12.5, color: pip.textFaint),
            )
          else
            DropdownButtonFormField<String>(
              initialValue: _models!.map((m) => m['name'] as String).contains(_activeModel) ? _activeModel : null,
              decoration: const InputDecoration(labelText: 'Active model'),
              items: [
                for (final model in _models!)
                  DropdownMenuItem(
                    value: model['name'] as String,
                    child: Text('${model['name']}${model['size'] != null ? ' (${_formatSize(model['size'] as int)})' : ''}'),
                  ),
              ],
              onChanged: _switchingModel ? null : _selectModel,
            ),
        ],
      ),
    );
  }

  String _formatSize(int bytes) {
    final gb = bytes / (1024 * 1024 * 1024);
    if (gb >= 0.1) return '${gb.toStringAsFixed(1)} GB';
    final mb = bytes / (1024 * 1024);
    return '${mb.toStringAsFixed(0)} MB';
  }
}

/// The consent prompt. One row per scope, each saying what actually leaves
/// this machine under it - the only detail that makes the choice a real one.
class _ScopeDialog extends StatefulWidget {
  final String providerId;
  const _ScopeDialog({required this.providerId});

  @override
  State<_ScopeDialog> createState() => _ScopeDialogState();
}

class _ScopeDialogState extends State<_ScopeDialog> {
  /// Nothing preselected on purpose - see the note at the top of this file.
  String? _scope;

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return AlertDialog(
      title: Text(
        'What may ${widget.providerId} receive?',
        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
      ),
      content: SizedBox(
        width: 420,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'This is a cloud provider, so it is blocked until you say otherwise. '
              'Pick the narrowest option that does what you need - PIP enforces it '
              'before any network call, and you can revoke it at any time.',
              style: TextStyle(fontSize: 12.5, color: pip.textMuted, height: 1.5),
            ),
            const SizedBox(height: AppSpacing.md),
            RadioGroup<String>(
              groupValue: _scope,
              onChanged: (value) => setState(() => _scope = value),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  for (final entry in ApiClient.consentScopes.entries)
                    RadioListTile<String>(
                      value: entry.key,
                      contentPadding: EdgeInsets.zero,
                      title: Text(
                        entry.key,
                        style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: pip.text),
                      ),
                      subtitle: Text(
                        entry.value,
                        style: TextStyle(fontSize: 12, color: pip.textMuted, height: 1.4),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
        FilledButton(
          onPressed: _scope == null ? null : () => Navigator.of(context).pop(_scope),
          child: const Text('Grant'),
        ),
      ],
    );
  }
}
