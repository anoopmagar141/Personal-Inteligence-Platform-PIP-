// The decision log: search, create, and - new here - retract.
//
// PATCH /decision/{id}/state existed with no caller, so a decision could be
// logged but never taken back from any interface. That matters more in this
// project than the missing verb suggests: the Observer writes decisions on its
// own, it has written wrong ones before, and until now the only way to correct
// that was the database.
//
// Two things follow from ADR-022 (nothing is deleted) and shape this screen:
//
//   1. A retraction needs a reason, and the backend requires one. The log
//      outlives the retraction, so a later reader has to be able to tell "this
//      was a fabrication we cleaned up" from "this was real and we changed our
//      mind" - state alone cannot say which.
//   2. A retracted decision is still there, so it has to stay reachable. The
//      backend's list/search take exactly one state and default to 'active',
//      which means a screen that never passes one shows only live decisions -
//      and retracting through the UI would look indistinguishable from
//      deleting. Hence the state filter: three states, one query each, in the
//      order the backend returns them. There is no "all" here because the
//      backend has no such state and merging three responses client-side would
//      invent an ordering it never sent.

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';

/// The three states decision_log.state is constrained to, with the words the
/// screen uses for each. Kept in one place so the filter and the badges cannot
/// drift apart.
const _states = <String, String>{
  'active': 'Active',
  'superseded': 'Superseded',
  'abandoned': 'Retracted',
};

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
  String _state = 'active';

  final Map<int, String> _rowErrors = {};
  final Set<int> _busy = {};

  @override
  void initState() {
    super.initState();
    _search();
  }

  Future<void> _search() async {
    try {
      final decisions = await widget.api.searchDecisions(_searchController.text, _state);
      if (mounted) {
        setState(() {
          _decisions = decisions;
          _error = null;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  void _setState(String state) {
    if (state == _state) return;
    setState(() {
      _state = state;
      _decisions = null;
    });
    _search();
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
        _createResult = switch (status) {
          'logged' => 'Logged (confidence $confidence).',
          'duplicate' => 'Already in the log - PIP kept the existing entry.',
          _ => 'Confidence too low to auto-log ($confidence) - saved as a pending candidate.',
        };
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

  /// [requireReason] mirrors the backend exactly rather than exceeding it:
  /// update_decision_state() rejects an empty reason for 'superseded' and
  /// 'abandoned' and accepts one for 'active'. The prompt still asks in the
  /// reactivating case, because the reason is stored verbatim for every state
  /// and coming back to a decision is itself worth explaining.
  Future<void> _changeState(Map<String, dynamic> decision, String target) async {
    final id = (decision['id'] as num).toInt();
    final outcome = await showDialog<({String reason, int? supersededBy})>(
      context: context,
      builder: (context) => _StateChangeDialog(
        decisionText: '${decision['decision_text']}',
        target: target,
      ),
    );
    if (outcome == null) return;

    setState(() {
      _busy.add(id);
      _rowErrors.remove(id);
    });
    try {
      await widget.api.updateDecisionState(
        id,
        state: target,
        reason: outcome.reason,
        supersededBy: outcome.supersededBy,
      );
      await _search();
    } catch (error) {
      if (mounted) setState(() => _rowErrors[id] = error.toString());
    } finally {
      if (mounted) setState(() => _busy.remove(id));
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
    final pip = context.pip;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSpacing.xl),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 720),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const PageHeader(
              eyebrow: 'Memory',
              title: 'Decision Log',
              description: 'What PIP has decided on your behalf, and why. Retracting an entry '
                  'keeps it on the record with your reason attached.',
            ),
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
            Row(
              children: [
                for (final entry in _states.entries) ...[
                  _FilterChip(
                    label: entry.value,
                    selected: _state == entry.key,
                    onTap: () => _setState(entry.key),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                ],
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            if (_error != null) Text(_error!, style: TextStyle(color: pip.danger)),
            if (_decisions != null)
              if (_decisions!.isEmpty)
                EmptyState(
                  icon: Icons.fact_check_outlined,
                  title: _state == 'active' ? 'No decisions found' : 'Nothing ${_states[_state]!.toLowerCase()}',
                  description: _state == 'active'
                      ? 'Log one below, or clear your search to see everything.'
                      : 'Decisions you retract or supersede will show up here.',
                )
              else
                Column(
                  children: [
                    for (final raw in _decisions!) _decisionCard(raw as Map<String, dynamic>),
                  ],
                ),
            const SizedBox(height: AppSpacing.lg),
            SectionCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TagLabel('Log a new decision', color: pip.text, size: 12),
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
                        ? SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: pip.accentOn))
                        : const Text('Log decision'),
                  ),
                  if (_createResult != null) ...[
                    const SizedBox(height: AppSpacing.sm),
                    Text(_createResult!, style: TextStyle(fontSize: 11.5, color: pip.textMuted)),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _decisionCard(Map<String, dynamic> decision) {
    final pip = context.pip;
    final id = (decision['id'] as num).toInt();
    final state = '${decision['state']}';
    final reason = '${decision['state_reason'] ?? ''}';
    final busy = _busy.contains(id);
    final rowError = _rowErrors[id];

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: SectionCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${decision['decision_text']}', style: TextStyle(fontSize: 14.5, color: pip.text)),
            const SizedBox(height: 6),
            Text(
              'confidence ${(decision['confidence'] as num).toStringAsFixed(2)} · $state · ${decision['created_at']}'
              '${decision['superseded_by'] != null ? ' · replaced by #${decision['superseded_by']}' : ''}',
              style: TextStyle(color: pip.textMuted, fontSize: 11),
            ),
            // Only shown when the backend actually has one. It is NULL for
            // decisions still active and for any retracted before the column
            // existed, and an empty "Reason:" label would imply the record is
            // poorer than it is.
            if (reason.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.sm),
              Container(
                key: const Key('decision-state-reason'),
                padding: const EdgeInsets.only(left: AppSpacing.sm),
                decoration: BoxDecoration(
                  border: Border(left: BorderSide(color: pip.border, width: 2)),
                ),
                child: Text(
                  reason,
                  style: TextStyle(fontSize: 12, color: pip.textMuted, height: 1.4),
                ),
              ),
            ],
            const SizedBox(height: AppSpacing.md),
            if (busy)
              const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
            else
              Row(
                children: [
                  if (state == 'active') ...[
                    GhostButton(
                      label: 'Retract',
                      color: pip.danger,
                      onTap: () => _changeState(decision, 'abandoned'),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    GhostButton(label: 'Supersede', onTap: () => _changeState(decision, 'superseded')),
                  ] else
                    GhostButton(label: 'Reactivate', onTap: () => _changeState(decision, 'active')),
                ],
              ),
            if (rowError != null) ...[
              const SizedBox(height: AppSpacing.sm),
              Text(rowError, style: TextStyle(fontSize: 11.5, color: pip.danger)),
            ],
          ],
        ),
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _FilterChip({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Material(
      color: selected ? pip.accentSoft : pip.surface,
      shape: RoundedRectangleBorder(
        borderRadius: AppRadius.sm,
        side: BorderSide(color: selected ? pip.accent : pip.border),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: AppRadius.sm,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
          child: Text(
            label,
            style: TextStyle(
              fontSize: 12.5,
              fontWeight: FontWeight.w600,
              color: selected ? pip.accent : pip.textMuted,
            ),
          ),
        ),
      ),
    );
  }
}

/// The retract / supersede / reactivate prompt.
///
/// A widget rather than controllers created beside the showDialog() call,
/// because the dialog is still animating out when showDialog() returns and its
/// fields rebuild during that animation - disposing the controllers there is a
/// use-after-dispose. Owning them here ties their life to the route's.
class _StateChangeDialog extends StatefulWidget {
  final String decisionText;
  final String target;
  const _StateChangeDialog({required this.decisionText, required this.target});

  @override
  State<_StateChangeDialog> createState() => _StateChangeDialogState();
}

class _StateChangeDialogState extends State<_StateChangeDialog> {
  final _reason = TextEditingController();
  final _supersededBy = TextEditingController();

  @override
  void dispose() {
    _reason.dispose();
    _supersededBy.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    final requireReason = widget.target != 'active';
    final canSubmit = !requireReason || _reason.text.trim().isNotEmpty;
    return AlertDialog(
      backgroundColor: pip.surface,
      title: Text(
        switch (widget.target) {
          'abandoned' => 'Retract this decision?',
          'superseded' => 'Mark as superseded?',
          _ => 'Make this active again?',
        },
        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '"${widget.decisionText}"',
            style: TextStyle(fontSize: 13, color: pip.textMuted, height: 1.4),
          ),
          const SizedBox(height: AppSpacing.md),
          Text(
            'The entry is kept either way. The reason is what tells you later '
            'whether this was wrong or simply no longer true.',
            style: TextStyle(fontSize: 12, color: pip.textFaint, height: 1.4),
          ),
          const SizedBox(height: AppSpacing.md),
          TextField(
            key: const Key('state-reason-field'),
            controller: _reason,
            autofocus: true,
            onChanged: (_) => setState(() {}),
            decoration: InputDecoration(
              labelText: requireReason ? 'Reason (required)' : 'Reason',
            ),
          ),
          if (widget.target == 'superseded') ...[
            const SizedBox(height: AppSpacing.sm),
            TextField(
              key: const Key('superseded-by-field'),
              controller: _supersededBy,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Replaced by decision # (optional)'),
            ),
          ],
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
        FilledButton(
          style: widget.target == 'active' ? null : FilledButton.styleFrom(backgroundColor: pip.danger),
          onPressed: canSubmit
              ? () => Navigator.of(context).pop((
                  reason: _reason.text.trim(),
                  supersededBy: int.tryParse(_supersededBy.text.trim()),
                ))
              : null,
          child: Text(widget.target == 'active' ? 'Reactivate' : 'Confirm'),
        ),
      ],
    );
  }
}
