// Matches frontend/web/app.js's decisions flow: search box + list,
// GET /decision/search?q=, and a create form posting to /decision/create.

import 'package:flutter/material.dart';

import '../api_client.dart';

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
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Decision Log', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchController,
                  decoration: const InputDecoration(labelText: 'Search decisions…', border: OutlineInputBorder()),
                  onSubmitted: (_) => _search(),
                ),
              ),
              const SizedBox(width: 8),
              FilledButton(onPressed: _search, child: const Text('Search')),
            ],
          ),
          const SizedBox(height: 12),
          if (_error != null) Text(_error!, style: const TextStyle(color: Colors.red)),
          if (_decisions != null)
            if (_decisions!.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text('No decisions found.', style: TextStyle(color: Colors.grey)),
              )
            else
              for (final decision in _decisions!)
                Card(
                  margin: const EdgeInsets.symmetric(vertical: 4),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('${decision['decision_text']}'),
                        const SizedBox(height: 4),
                        Text(
                          'confidence ${(decision['confidence'] as num).toStringAsFixed(2)} · ${decision['state']} · ${decision['created_at']}',
                          style: const TextStyle(color: Colors.grey, fontSize: 12),
                        ),
                      ],
                    ),
                  ),
                ),
          const SizedBox(height: 24),
          Text('Log a new decision', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          TextField(controller: _textController, decoration: const InputDecoration(labelText: 'Decision')),
          const SizedBox(height: 8),
          TextField(controller: _reasoningController, decoration: const InputDecoration(labelText: 'Reasoning')),
          const SizedBox(height: 8),
          TextField(controller: _alternativesController, decoration: const InputDecoration(labelText: 'Alternatives considered')),
          const SizedBox(height: 8),
          FilledButton(
            onPressed: _creating ? null : _createDecision,
            child: _creating
                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Log decision'),
          ),
          if (_createResult != null) ...[
            const SizedBox(height: 8),
            Text(_createResult!, style: const TextStyle(color: Colors.grey)),
          ],
        ],
      ),
    );
  }
}
