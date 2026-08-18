// Matches frontend/web/app.js's providers flow: table + consent grant/revoke.
// Same known simplification as the web client: "Grant consent" always
// requests "full_inference" scope regardless of provider type - a valid
// request (VALID_CONSENT_SCOPES accepts it), just not the most precise
// default. See docs/PIP_MASTER_REFERENCE.md's web client section for why
// this wasn't tightened up.

import 'package:flutter/material.dart';

import '../api_client.dart';

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
    if (_error != null) return Center(child: Text(_error!, style: const TextStyle(color: Colors.red)));
    if (_providers == null) return const Center(child: CircularProgressIndicator());

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Providers', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 4),
          const Text(
            'Local providers never need consent. Cloud providers are blocked until you explicitly consent (Stage 8, fail-closed).',
            style: TextStyle(color: Colors.grey),
          ),
          const SizedBox(height: 12),
          DataTable(
            columns: const [
              DataColumn(label: Text('Provider')),
              DataColumn(label: Text('Type')),
              DataColumn(label: Text('Consent')),
              DataColumn(label: Text('Scope')),
              DataColumn(label: Text('')),
            ],
            rows: [
              for (final provider in _providers!)
                DataRow(cells: [
                  DataCell(Text('${provider['provider_id']}')),
                  DataCell(Text(provider['is_cloud'] == true ? 'cloud' : 'local')),
                  DataCell(Text(_consentLabel(provider))),
                  DataCell(Text('${provider['consent_scope'] ?? '-'}')),
                  DataCell(_actionButton(provider)),
                ]),
            ],
          ),
        ],
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
      return const Text('n/a (local)', style: TextStyle(color: Colors.grey));
    }
    final consented = provider['user_consented'] == true && provider['revoked'] != true;
    final providerId = provider['provider_id'] as String;
    if (consented) {
      return TextButton(
        onPressed: () => _revoke(providerId),
        style: TextButton.styleFrom(foregroundColor: Colors.red),
        child: const Text('Revoke'),
      );
    }
    return TextButton(onPressed: () => _grant(providerId), child: const Text('Grant consent'));
  }
}
