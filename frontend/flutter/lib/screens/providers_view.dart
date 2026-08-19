// Matches frontend/web/app.js's providers flow: table + consent grant/revoke.
// Same known simplification as the web client: "Grant consent" always
// requests "full_inference" scope regardless of provider type - a valid
// request (VALID_CONSENT_SCOPES accepts it), just not the most precise
// default. See docs/PIP_MASTER_REFERENCE.md's web client section for why
// this wasn't tightened up.

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

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final providers = await widget.api.getProviders();
      if (mounted) setState(() => _providers = providers);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
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
    if (_error != null) {
      return Center(child: Text(_error!, style: const TextStyle(fontFamily: AppTheme.mono, color: AppColors.danger)));
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
                      DataCell(TagLabel(provider['is_cloud'] == true ? 'cloud' : 'local', color: provider['is_cloud'] == true ? AppColors.textMuted : AppColors.accent)),
                      DataCell(Text(_consentLabel(provider))),
                      DataCell(Text('${provider['consent_scope'] ?? '-'}', style: const TextStyle(fontFamily: AppTheme.mono, fontSize: 12, color: AppColors.textMuted))),
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
    if (provider['is_cloud'] != true) {
      return const TagLabel('n/a (local)', color: AppColors.textFaint);
    }
    final consented = provider['user_consented'] == true && provider['revoked'] != true;
    final providerId = provider['provider_id'] as String;
    if (consented) {
      return GhostButton(label: 'Revoke', color: AppColors.danger, onTap: () => _revoke(providerId));
    }
    return GhostButton(label: 'Grant consent', onTap: () => _grant(providerId));
  }
}
