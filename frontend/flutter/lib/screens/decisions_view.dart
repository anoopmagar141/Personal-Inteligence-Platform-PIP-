// Matches frontend/web/app.js's decisions flow: search box + list,
// GET /decision/search?q=, and a create form posting to /decision/create.

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';

class DecisionsView extends StatefulWidget {
  final ApiClient api;
  final String? activeProjectId;
  const DecisionsView({super.key, required this.api, required this.activeProjectId});

  @override
  State<DecisionsView> createState() => _DecisionsViewState();
}

class _DecisionsViewState extends State<DecisionsView> {
  final _searchController = TextEditingController();
  final _textController = TextEditingController();
  final _reasoningController = TextEditingController();
  final _alternativesController = TextEditingController();

  List<dynamic>? _decisions;
  String? _error;
  String? _createResult;
  bool _creating = false;

  @override
  void initState() {
    super.initState();
    _search();
  }

  Future<void> _search() async {
    try {
      final decisions = await widget.api.searchDecisions(_searchController.text);
      if (mounted) setState(() => _decisions = decisions);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _createDecision() async {
    if (_textController.text.trim().isEmpty) return;
    setState(() {
      _creating = true;
      _createResult = null;
    });
    try {
      final result = await widget.api.createDecision({
        'text': _textController.text.trim(),
        if (_reasoningController.text.trim().isNotEmpty) 'reasoning': _reasoningController.text.trim(),
        if (_alternativesController.text.trim().isNotEmpty) 'alternatives': _alternativesController.text.trim(),
        if (widget.activeProjectId != null) 'project_id': widget.activeProjectId,
      });
      final status = result['status'];
      final confidence = (result['confidence'] as num).toStringAsFixed(2);
      setState(() {
        _createResult = status == 'logged'
            ? 'Logged (confidence $confidence).'
            : 'Confidence too low to auto-log ($confidence) - saved as a pending candidate.';
      });
      _textController.clear();
      _reasoningController.clear();
      _alternativesController.clear();
      await _search();
    } catch (error) {
      setState(() => _createResult = 'Error: $error');
    } finally {
      if (mounted) setState(() => _creating = false);
    }
  }

  @override
  void dispose() {
    _searchController.dispose();
    _textController.dispose();
    _reasoningController.dispose();
    _alternativesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSpacing.xl),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 720),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const PageHeader(eyebrow: 'Memory', title: 'Decision Log', description: 'What PIP has decided on your behalf, and why.'),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _searchController,
                    style: const TextStyle(fontSize: 13),
                    decoration: const InputDecoration(hintText: 'search decisions...'),
                    onSubmitted: (_) => _search(),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                FilledButton(onPressed: _search, child: const Text('Search')),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            if (_error != null) Text(_error!, style: const TextStyle(color: AppColors.danger)),
            if (_decisions != null)
              if (_decisions!.isEmpty)
                const EmptyState(
                  icon: Icons.fact_check_outlined,
                  title: 'No decisions found',
                  description: 'Log one below, or clear your search to see everything.',
                )
              else
                Column(
                  children: [
                    for (final decision in _decisions!)
                      Padding(
                        padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                        child: SectionCard(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('${decision['decision_text']}', style: const TextStyle(fontSize: 14.5, color: AppColors.text)),
                              const SizedBox(height: 6),
                              Text(
                                'confidence ${(decision['confidence'] as num).toStringAsFixed(2)} · ${decision['state']} · ${decision['created_at']}',
                                style: const TextStyle(color: AppColors.textMuted, fontSize: 11),
                              ),
                            ],
                          ),
                        ),
                      ),
                  ],
                ),
            const SizedBox(height: AppSpacing.lg),
            SectionCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const TagLabel('Log a new decision', color: AppColors.text, size: 12),
                  const SizedBox(height: AppSpacing.md),
                  TextField(controller: _textController, decoration: const InputDecoration(labelText: 'Decision')),
                  const SizedBox(height: AppSpacing.sm),
                  TextField(controller: _reasoningController, decoration: const InputDecoration(labelText: 'Reasoning')),
                  const SizedBox(height: AppSpacing.sm),
                  TextField(controller: _alternativesController, decoration: const InputDecoration(labelText: 'Alternatives considered')),
                  const SizedBox(height: AppSpacing.md),
                  FilledButton(
                    onPressed: _creating ? null : _createDecision,
                    child: _creating
                        ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.accentOn))
                        : const Text('Log decision'),
                  ),
                  if (_createResult != null) ...[
                    const SizedBox(height: AppSpacing.sm),
                    Text(_createResult!, style: const TextStyle(fontSize: 11.5, color: AppColors.textMuted)),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
