// What PIP has learned about you - and, now, the ability to fix it when it is
// wrong.
//
// The read half (GET /memory/profile) has been here since the first version.
// The write half was not: POST /memory/correct and DELETE
// /memory/profile/{field} existed on the backend with no caller, so a
// fabricated or outdated field could only be corrected by opening the
// database. That is the wrong place to leave it for this project in
// particular - the commit history is largely about PIP recording things that
// were not true, and the Review tab only governs memory PIP has not written
// yet. This governs what it already has.
//
// Deletion is soft (ADR-022: the row stays, its status flips), so these are
// retractions rather than erasures.
//
// Part 14.4 (frontend has zero intelligence) still holds: nothing here decides
// what is true, ranks a field, or edits a value on your behalf. What it does
// encode is which endpoint can service which row - API knowledge, the same
// kind this client already carries in every call it makes - and it is derived
// from the `table` the backend itself puts on each row rather than from a
// second copy of the backend's field list. Any mismatch still ends as the
// server's own 422 sentence, printed on the row that caused it.

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';

/// What the write endpoints can actually do with a row from this table.
///
/// This mirrors two backend functions rather than guessing:
///
///   * `correct_profile_field()` refuses name/language_preference/timezone
///     outright and otherwise routes the write to whichever table already
///     holds the field. It used to write to preference_memory unconditionally,
///     which is why "edit" was once offered on preferences alone: correcting a
///     skill would have filed a new preference of the same name and left the
///     skill untouched. Now that it dispatches properly, skills and goals are
///     editable too. The set-membership tables still are not - the field IS
///     the value there, so an in-place edit has no meaning and the backend
///     refuses it.
///   * `soft_delete_profile_field()` flips status on skill_memory,
///     preference_memory, preferred_tools, topic_interests,
///     document_access_patterns, and goal_memory (via its `goal:<id>` handle).
///     Nothing else is in its loop.
///
/// active_projects is deliberately in neither: projects have their own screen,
/// where archiving one is a status change rather than a memory retraction.
({bool canEdit, bool canDelete, bool hasHistory, String? note}) profileRowCapability(String table) {
  switch (table) {
    case 'identity':
      return (canEdit: false, canDelete: false, hasHistory: false, note: 'set at onboarding');
    case 'interaction_style':
      // The only row with a past. interaction_style_history gains a row on
      // every change and is the one audit trail the profile has.
      return (canEdit: true, canDelete: false, hasHistory: true, note: null);
    case 'preference_memory':
    case 'skill_memory':
    case 'goal_memory':
      return (canEdit: true, canDelete: true, hasHistory: false, note: null);
    case 'preferred_tools':
    case 'topic_interests':
    case 'document_access_patterns':
      // The field is the value here, so there is nothing to edit into - a
      // correction is a delete plus whatever PIP observes next.
      return (canEdit: false, canDelete: true, hasHistory: false, note: null);
    case 'active_projects':
      return (canEdit: false, canDelete: false, hasHistory: false, note: 'managed on Projects');
    default:
      // An unfamiliar table gets no write affordances rather than a guess. A
      // new profile table is a backend change, and this is the safe way to
      // find out about it.
      return (canEdit: false, canDelete: false, hasHistory: false, note: null);
  }
}

class ProfileView extends StatefulWidget {
  final ApiClient api;
  const ProfileView({super.key, required this.api});

  @override
  State<ProfileView> createState() => _ProfileViewState();
}

class _ProfileViewState extends State<ProfileView> {
  List<dynamic>? _fields;
  String? _error;

  /// Keyed by field name. A refusal belongs on the row that caused it - one
  /// field can be rejected for a reason that does not apply to any other, and
  /// a banner at the top of the page would not say which.
  final Map<String, String> _rowErrors = {};
  final Set<String> _busy = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final fields = await widget.api.getProfile();
      if (mounted) {
        setState(() {
          _fields = fields;
          _error = null;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _act(String field, Future<void> Function() action) async {
    setState(() {
      _busy.add(field);
      _rowErrors.remove(field);
    });
    try {
      await action();
      await _load();
    } catch (error) {
      // The server's sentence, not a generic failure - "immutable identity
      // fields cannot be edited after onboarding" is the entire answer to why
      // an edit did not take, and ApiException.detail exists to keep it.
      if (mounted) setState(() => _rowErrors[field] = error.toString());
    } finally {
      if (mounted) setState(() => _busy.remove(field));
    }
  }

  Future<void> _edit(Map<String, dynamic> row) async {
    final field = '${row['field']}';
    final saved = await showDialog<String>(
      context: context,
      builder: (context) => _CorrectFieldDialog(
        field: field,
        initialValue: '${row['value']}',
        // A skill's value is skill_memory.level, a number. Saying so beats
        // letting someone type "expert" and meet a refusal for it - the
        // backend does reject it, but a hint is cheaper than a round trip.
        hint: row['table'] == 'skill_memory' ? 'A number from 0 to 1 - how well you know it.' : null,
      ),
    );
    if (saved == null || saved.isEmpty) return;
    await _act(field, () => widget.api.correctMemory(field, saved));
  }

  Future<void> _delete(Map<String, dynamic> row) async {
    final field = '${row['field']}';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Forget this?', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
        content: Text(
          'PIP will stop using "$field" straight away. The record is kept and marked '
          'retracted rather than erased, so the history stays readable.',
          style: TextStyle(fontSize: 13, color: context.pip.textMuted, height: 1.5),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: context.pip.danger),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Forget it'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await _act(field, () async {
      final result = await widget.api.deleteProfileField(field);
      if (result['status'] == 'not_found') {
        // Reported rather than swallowed: a delete the backend could not match
        // means this row's handle is not one soft_delete_profile_field()
        // recognises, and silently reloading an unchanged table would look
        // like the button did nothing.
        throw Exception('PIP had no active record under "$field" to forget.');
      }
    });
  }

  /// interaction_style_history was written from three separate places in
  /// profile_store.py and read by nothing - "an audit trail that recorded
  /// every change and could not answer a single question about them", in that
  /// module's own words. A read function was added to fix that and still had
  /// no caller. This is the caller.
  Future<void> _showStyleHistory() async {
    List<dynamic>? history;
    String? failure;
    try {
      history = await widget.api.getInteractionStyleHistory();
    } catch (e) {
      failure = e.toString();
    }
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text(
          'How your answer style has changed',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
        ),
        content: SizedBox(
          width: 380,
          child: failure != null
              ? Text(failure, style: TextStyle(fontSize: 12.5, color: context.pip.danger))
              : history!.isEmpty
                  // Not an error, and worth saying plainly: the table only
                  // gains a row when the value CHANGES, so a style set once at
                  // onboarding and never revised genuinely has nothing to show.
                  ? Text(
                      'No changes recorded. PIP has had the same read on this since it was first set.',
                      style: TextStyle(fontSize: 13, color: context.pip.textMuted, height: 1.5),
                    )
                  : ListView(
                      shrinkWrap: true,
                      children: [
                        for (var i = 0; i < history.length; i++)
                          _HistoryRow(
                            value: '${history[i]['value']}',
                            changedAt: '${history[i]['changed_at']}',
                            // Newest first, per the backend's own ordering.
                            current: i == 0,
                          ),
                      ],
                    ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    if (_error != null) return Center(child: Text(_error!, style: TextStyle(color: pip.danger)));
    if (_fields == null) return const Center(child: CircularProgressIndicator());

    return RefreshIndicator(
      onRefresh: _load,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(AppSpacing.xl),
        physics: const AlwaysScrollableScrollPhysics(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const PageHeader(
              eyebrow: 'Memory',
              title: 'Profile',
              description: 'What PIP has learned about you, and how confident it is. '
                  'Correct anything it has wrong - your correction outranks what it inferred.',
            ),
            _fields!.isEmpty
                ? const EmptyState(
                    icon: Icons.person_outline,
                    title: 'No profile fields yet',
                    description: 'PIP fills this in as it learns about you through conversation.',
                  )
                : Column(
                    children: [
                      for (final raw in _fields!) _row(raw as Map<String, dynamic>),
                    ],
                  ),
          ],
        ),
      ),
    );
  }

  Widget _row(Map<String, dynamic> row) {
    final pip = context.pip;
    final table = '${row['table']}';
    final field = '${row['field']}';
    final capability = profileRowCapability(table);
    final busy = _busy.contains(field);
    final rowError = _rowErrors[field];
    final confidence = row['confidence'] != null ? (row['confidence'] as num).toStringAsFixed(2) : null;

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: SectionCard(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              field,
                              style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: pip.text),
                            ),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          TagLabel(table, color: pip.textFaint, size: 10.5),
                        ],
                      ),
                      const SizedBox(height: 4),
                      SelectableText(
                        '${row['value']}',
                        style: TextStyle(fontSize: 13.5, color: pip.textMuted, height: 1.4),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        [
                          if (confidence != null) 'confidence $confidence',
                          '${row['source_label'] ?? 'unknown source'}',
                          if (capability.note != null) capability.note!,
                        ].join(' · '),
                        style: TextStyle(fontSize: 11, color: pip.textFaint),
                      ),
                    ],
                  ),
                ),
                if (busy)
                  const Padding(
                    padding: EdgeInsets.only(left: AppSpacing.md),
                    child: SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
                  )
                else ...[
                  if (capability.canEdit) ...[
                    const SizedBox(width: AppSpacing.sm),
                    GhostButton(label: 'Correct', onTap: () => _edit(row)),
                  ],
                  if (capability.canDelete) ...[
                    const SizedBox(width: AppSpacing.sm),
                    GhostButton(label: 'Forget', color: pip.danger, onTap: () => _delete(row)),
                  ],
                  if (capability.hasHistory) ...[
                    const SizedBox(width: AppSpacing.sm),
                    GhostButton(label: 'History', color: pip.textMuted, onTap: _showStyleHistory),
                  ],
                ],
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

/// The correction prompt, as a widget that owns its own controller.
///
/// Not a controller created next to the showDialog() call and disposed when it
/// returns: the dialog is still animating out at that point and its TextField
/// rebuilds during the animation, so disposing there is a use-after-dispose
/// that throws. Tying the controller's life to the widget's is what makes the
/// timing correct rather than lucky.
class _CorrectFieldDialog extends StatefulWidget {
  final String field;
  final String initialValue;

  /// What this particular field expects, when that is not obvious from the
  /// value already in the box. Null for the ordinary free-text case.
  final String? hint;
  const _CorrectFieldDialog({required this.field, required this.initialValue, this.hint});

  @override
  State<_CorrectFieldDialog> createState() => _CorrectFieldDialogState();
}

class _CorrectFieldDialogState extends State<_CorrectFieldDialog> {
  late final TextEditingController _controller = TextEditingController(text: widget.initialValue);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return AlertDialog(
      backgroundColor: pip.surface,
      title: Text(
        'Correct "${widget.field}"',
        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'This is recorded as your own correction, which outranks anything PIP inferred.',
            style: TextStyle(fontSize: 12.5, color: pip.textMuted),
          ),
          const SizedBox(height: AppSpacing.md),
          TextField(
            controller: _controller,
            autofocus: true,
            decoration: InputDecoration(labelText: 'Value', helperText: widget.hint),
            onSubmitted: (value) => Navigator.of(context).pop(value.trim()),
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(_controller.text.trim()),
          child: const Text('Save'),
        ),
      ],
    );
  }
}

/// One recorded interaction-style value, and when it took effect.
class _HistoryRow extends StatelessWidget {
  final String value;
  final String changedAt;
  final bool current;
  const _HistoryRow({required this.value, required this.changedAt, required this.current});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 9),
      decoration: BoxDecoration(border: Border(bottom: BorderSide(color: pip.border))),
      child: Row(
        children: [
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 13,
                fontWeight: current ? FontWeight.w600 : FontWeight.w400,
                color: current ? pip.accent : pip.text,
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          Text(changedAt, style: TextStyle(fontSize: 11, color: pip.textFaint)),
        ],
      ),
    );
  }
}
