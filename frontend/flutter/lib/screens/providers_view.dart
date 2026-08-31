// Matches frontend/web/app.js's providers flow: table + consent grant/revoke.
// Same known simplification as the web client: "Grant consent" always
// requests "full_inference" scope regardless of provider type. That is a
// valid request - backend/api/server.py's VALID_CONSENT_SCOPES accepts it -
// but it is the broadest of the four scopes rather than the narrowest one
// that would do, so a provider that only ever needs embeddings is consented
// for inference too. Still open; the scope picker this wants is a UI change,
// not a backend one.

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';

class ProvidersView extends StatefulWidget {
  final ApiClient api;
  const ProvidersView({super.key, required this.api});

  @override
  State<ProvidersView> createState() => _ProvidersViewState();
}

class _ProvidersViewState extends State<ProvidersView> {
  List<dynamic>? _providers;
  String? _error;

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

  Future<void> _grant(String providerId) async {
    await widget.api.grantConsent(providerId, 'full_inference');
    await _load();
  }

  Future<void> _revoke(String providerId) async {
    await widget.api.revokeConsent(providerId);
    await _load();
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
            const SizedBox(height: AppSpacing.lg),
            SectionCard(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
              child: DataTable(
                columns: const [
                  DataColumn(label: Text('PROVIDER')),
                  DataColumn(label: Text('TYPE')),
                  DataColumn(label: Text('CONSENT')),
                  DataColumn(label: Text('SCOPE')),
                  DataColumn(label: Text('')),
                ],
                rows: [
                  for (final provider in _providers!)
                    DataRow(cells: [
                      DataCell(Text('${provider['provider_id']}')),
                      DataCell(TagLabel(provider['is_cloud'] == true ? 'cloud' : 'local', color: provider['is_cloud'] == true ? pip.textMuted : pip.accent)),
                      DataCell(Text(_consentLabel(provider))),
                      DataCell(Text('${provider['consent_scope'] ?? '-'}', style: TextStyle(fontSize: 12, color: pip.textMuted))),
                      DataCell(_actionButton(provider)),
                    ]),
                ],
              ),
            ),
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
              'No models found. Is Ollama running, and have you pulled a model (e.g. `ollama pull llama3.1:8b`)?',
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
