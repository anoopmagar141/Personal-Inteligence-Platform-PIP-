// Matches frontend/web/app.js's loadProfile(): GET /memory/profile, rendered
// as a read-only table exactly as the backend returns it - including
// skill_memory's value/confidence split, which is the backend's real data
// shape (verified live against the web client), not something to reinterpret
// here.

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';

class ProfileView extends StatefulWidget {
  final ApiClient api;
  const ProfileView({super.key, required this.api});

  @override
  State<ProfileView> createState() => _ProfileViewState();
}

class _ProfileViewState extends State<ProfileView> {
  List<dynamic>? _fields;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final fields = await widget.api.getProfile();
      if (mounted) setState(() => _fields = fields);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null) return Center(child: Text(_error!, style: const TextStyle(color: AppColors.danger)));
    if (_fields == null) return const Center(child: CircularProgressIndicator());

    return RefreshIndicator(
      onRefresh: _load,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(AppSpacing.xl),
        physics: const AlwaysScrollableScrollPhysics(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const PageHeader(eyebrow: 'Memory', title: 'Profile', description: 'What PIP has learned about you, and how confident it is.'),
            _fields!.isEmpty
                ? const EmptyState(
                    icon: Icons.person_outline,
                    title: 'No profile fields yet',
                    description: 'PIP fills this in as it learns about you through conversation.',
                  )
                : SectionCard(
                    padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                    child: DataTable(
                      columns: const [
                        DataColumn(label: Text('TABLE')),
                        DataColumn(label: Text('FIELD')),
                        DataColumn(label: Text('VALUE')),
                        DataColumn(label: Text('CONFIDENCE')),
                        DataColumn(label: Text('SOURCE')),
                      ],
                      rows: [
                        for (final field in _fields!)
                          DataRow(cells: [
                            DataCell(Text('${field['table']}')),
                            DataCell(Text('${field['field']}')),
                            DataCell(Text('${field['value']}')),
                            DataCell(Text(field['confidence'] != null ? (field['confidence'] as num).toStringAsFixed(2) : '-')),
                            DataCell(Text('${field['source_label'] ?? '-'}')),
                          ]),
                      ],
                    ),
                  ),
          ],
        ),
      ),
    );
  }
}
