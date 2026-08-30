// Everything PIP has learned but is not allowed to keep without asking.
//
// Mirrors the web client's Review tab (frontend/web/app.js), against the same
// endpoints: /memory/pending, /decision/pending and /proactive. Until these
// existed, the whole governance half of the system was reachable only by curl -
// the constitution gates several memory types behind prompt_confirm and Stage 13
// parks those candidates in memory_candidates_pending, the periodic memory check
// adds to the same queue every 30 sessions, and no screen displayed any of it.
//
// Part 14.4 (frontend has zero intelligence) is intact: the maps below turn a
// status code the server sent into a sentence a person can answer. Nothing is
// filtered, ranked, or judged here, and the lists render in the order the
// backend returned them.

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';

/// The question to put at the top of a memory candidate, chosen by where it
/// came from. "Should I remember this?" and "Do I still have this right?" are
/// genuinely different questions, which is what the origin column exists to
/// distinguish - one is about something not yet recorded, the other about
/// something recorded long ago and never confirmed.
const _memoryQuestion = <String, String>{
  'verification': 'Do I still have this right?',
  'observer': 'Should I remember this?',
};

const _memoryReason = <String, String>{
  'REQUIRES_CONFIRMATION': 'This is something PIP is not allowed to record without asking.',
  'TIER_2_REQUIRED': 'This disagrees with something already recorded confidently.',
  'PROMPT_RECONCILIATION': 'You stated one thing, and PIP has repeatedly observed another.',
};

const _tableLabel = <String, String>{
  'preference_memory': 'Preference',
  'skill_memory': 'Skill',
  'goal_memory': 'Goal',
  'active_projects': 'Project',
  'interaction_style': 'Answer style',
  'topic_interests': 'Topic',
  'identity': 'Identity',
};

class ReviewView extends StatefulWidget {
  final ApiClient api;

  /// Bumped by HomeShell each time this tab is selected. IndexedStack keeps
  /// every view alive, so initState runs once for the app's whole lifetime -
  /// without this, a queue filled by the session that just ended would show
  /// whatever was true when the app started.
  final int refreshToken;

  /// Lets the sidebar badge follow the queue without this view knowing the
  /// sidebar exists.
  final VoidCallback onQueueChanged;

  const ReviewView({
    super.key,
    required this.api,
    required this.refreshToken,
    required this.onQueueChanged,
  });

  @override
  State<ReviewView> createState() => _ReviewViewState();
}

class _ReviewViewState extends State<ReviewView> {
  List<dynamic>? _memory;
  List<dynamic>? _decisions;
  List<dynamic>? _proactive;
  String? _error;

  /// Per-item, keyed "memory:3" / "decision:1". An error belongs on the row it
  /// came from - a confirmation can fail for a reason particular to one
  /// candidate, and a banner at the top of the page would not say which.
  final Map<String, String> _itemErrors = {};
  final Set<String> _busy = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(ReviewView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.refreshToken != widget.refreshToken) _load();
  }

  Future<void> _load() async {
    try {
      final results = await Future.wait([
        widget.api.getPendingMemory(),
        widget.api.getPendingDecisions(),
        widget.api.getProactive(),
      ]);
      if (!mounted) return;
      setState(() {
        _memory = results[0];
        _decisions = results[1];
        _proactive = results[2];
        _error = null;
      });
      widget.onQueueChanged();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  /// One shape for all four actions: disable the row, run the call, reload on
  /// success. On failure the reason goes on the row and the buttons come back -
  /// a confirmation that legitimately cannot be applied leaves the candidate in
  /// the queue, and the user must not be left guessing why nothing happened.
  Future<void> _act(String key, Future<void> Function() action) async {
    setState(() {
      _busy.add(key);
      _itemErrors.remove(key);
    });
    try {
      await action();
      await _load();
    } catch (error) {
      if (mounted) setState(() => _itemErrors[key] = error.toString());
    } finally {
      if (mounted) setState(() => _busy.remove(key));
    }
  }

  String _describeTrigger(Map<String, dynamic> trigger) {
    switch (trigger['trigger']) {
      case 'session_gap_exceeds_48h':
        final days = ((trigger['hours_elapsed'] as num) / 24).floor();
        return 'It has been about $days day(s) since your last session.';
      case 'goal_inactive_14_days':
        return 'Goal not mentioned in over ${trigger['threshold_days']} days: ${trigger['goal_text']}';
      default:
        return '${trigger['trigger']}';
    }
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _load,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const PageHeader(
                eyebrow: 'Governance',
                title: 'Review',
                description: 'PIP asks before writing anything the constitution gates, and before '
                    'trusting a memory it has never had confirmed. Nothing here is stored until you say so.',
              ),
              if (_error != null)
                Text(_error!, style: const TextStyle(color: AppColors.danger, fontSize: 12.5)),
              _sectionTitle('Memory'),
              _memorySection(),
              const SizedBox(height: AppSpacing.lg),
              _sectionTitle('Decisions PIP noticed'),
              _decisionSection(),
              const SizedBox(height: AppSpacing.lg),
              _sectionTitle('Worth knowing'),
              _proactiveSection(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _sectionTitle(String text) => Padding(
        padding: const EdgeInsets.only(bottom: AppSpacing.sm),
        child: TagLabel(text, color: AppColors.text, size: 13),
      );

  Widget _memorySection() {
    if (_memory == null) return const _Loading();
    if (_memory!.isEmpty) {
      return const EmptyState(
        icon: Icons.verified_outlined,
        title: 'Nothing waiting',
        description: 'PIP will ask here when it needs your decision on something.',
      );
    }
    return Column(
      children: [
        for (final raw in _memory!) _memoryCard(raw as Map<String, dynamic>),
      ],
    );
  }

  Widget _memoryCard(Map<String, dynamic> candidate) {
    final id = candidate['id'] as int;
    final key = 'memory:$id';
    final isCheck = candidate['origin'] == 'verification';
    final label = _tableLabel[candidate['target_table']] ?? '${candidate['target_table']}';
    final question = _memoryQuestion[candidate['origin']] ?? _memoryQuestion['observer']!;
    final evidence = '${candidate['evidence_text'] ?? ''}';

    // evidence_text means two different things by origin, and rendering both
    // the same way says something false. For an Observer candidate it is the
    // user's own words quoted back - which is what the quote styling is for.
    // For a periodic check it is a sentence the BACKEND wrote about its own
    // record, so quoting it would attribute PIP's note to the user. It also
    // explains itself better than the status map can: a check is
    // REQUIRES_CONFIRMATION for a different reason than a gated field is, so
    // the generic sentence read as a flat contradiction of the question above.
    final explanation = isCheck ? evidence : (_memoryReason[candidate['validation_status']] ?? '');

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: SectionCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TagLabel(question, color: AppColors.textMuted, size: 11.5),
            const SizedBox(height: 6),
            RichText(
              text: TextSpan(
                style: const TextStyle(fontSize: 14.5, color: AppColors.text),
                children: [
                  TextSpan(text: '$label · '),
                  TextSpan(
                    text: '${candidate['field_name']}',
                    style: const TextStyle(fontWeight: FontWeight.w700, color: AppColors.accent),
                  ),
                  TextSpan(text: ': ${candidate['proposed_value']}'),
                ],
              ),
            ),
            if (!isCheck && evidence.isNotEmpty) ...[
              const SizedBox(height: 8),
              _Quote(evidence),
            ],
            if (explanation.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(explanation, style: const TextStyle(fontSize: 11.5, color: AppColors.textMuted)),
            ],
            const SizedBox(height: AppSpacing.md),
            _actions(
              key: key,
              confirmLabel: 'Yes, keep it',
              onConfirm: () => widget.api.confirmPendingMemory(id),
              onReject: () => widget.api.dismissPendingMemory(id),
            ),
          ],
        ),
      ),
    );
  }

  Widget _decisionSection() {
    if (_decisions == null) return const _Loading();
    if (_decisions!.isEmpty) {
      return const EmptyState(
        icon: Icons.fact_check_outlined,
        title: 'No decision candidates waiting',
        description: 'PIP logs confident decisions on its own and asks about the rest.',
      );
    }
    return Column(
      children: [
        for (final raw in _decisions!) _decisionCard(raw as Map<String, dynamic>),
      ],
    );
  }

  Widget _decisionCard(Map<String, dynamic> candidate) {
    final id = candidate['id'] as int;
    final key = 'decision:$id';
    final quote = '${candidate['raw_quote'] ?? ''}';
    final signals = (candidate['signals_found'] as List<dynamic>? ?? []).join(', ');
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: SectionCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const TagLabel('Was this a decision you made?', color: AppColors.textMuted, size: 11.5),
            const SizedBox(height: 6),
            Text('${candidate['decision_text']}', style: const TextStyle(fontSize: 14.5, color: AppColors.text)),
            if (quote.isNotEmpty) ...[
              const SizedBox(height: 8),
              _Quote(quote),
            ],
            const SizedBox(height: 6),
            Text(
              'confidence ${(candidate['confidence'] as num).toStringAsFixed(2)} · '
              'signals: ${signals.isEmpty ? 'none' : signals}',
              style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
            ),
            const SizedBox(height: AppSpacing.md),
            _actions(
              key: key,
              confirmLabel: 'Log it',
              onConfirm: () => widget.api.promotePendingDecision(id),
              onReject: () => widget.api.dismissPendingDecision(id),
            ),
          ],
        ),
      ),
    );
  }

  Widget _proactiveSection() {
    if (_proactive == null) return const _Loading();
    if (_proactive!.isEmpty) {
      return const EmptyState(
        icon: Icons.notifications_none,
        title: 'Nothing to raise',
        description: 'Only a handful of fixed conditions ever appear here.',
      );
    }
    return Column(
      children: [
        for (final raw in _proactive!)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
            child: SectionCard(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.md),
              child: Row(
                children: [
                  const Icon(Icons.info_outline, size: 16, color: AppColors.accent),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(
                      _describeTrigger(raw as Map<String, dynamic>),
                      style: const TextStyle(fontSize: 13, color: AppColors.text),
                    ),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }

  Widget _actions({
    required String key,
    required String confirmLabel,
    required Future<void> Function() onConfirm,
    required Future<void> Function() onReject,
  }) {
    final busy = _busy.contains(key);
    final error = _itemErrors[key];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            FilledButton(
              onPressed: busy ? null : () => _act(key, onConfirm),
              child: busy
                  ? const SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.accentOn),
                    )
                  : Text(confirmLabel),
            ),
            const SizedBox(width: AppSpacing.sm),
            GhostButton(
              label: 'No',
              color: AppColors.textMuted,
              onTap: busy ? null : () => _act(key, onReject),
            ),
          ],
        ),
        if (error != null) ...[
          const SizedBox(height: AppSpacing.sm),
          Text(error, style: const TextStyle(fontSize: 11.5, color: AppColors.danger)),
        ],
      ],
    );
  }
}

/// The user's own words, quoted back. Only ever used for text that actually
/// came from them - see the note in _memoryCard.
class _Quote extends StatelessWidget {
  final String text;
  const _Quote(this.text);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.only(left: AppSpacing.sm),
      decoration: const BoxDecoration(
        border: Border(left: BorderSide(color: AppColors.border, width: 2)),
      ),
      child: Text(text, style: const TextStyle(fontSize: 12.5, color: AppColors.textMuted, height: 1.4)),
    );
  }
}

class _Loading extends StatelessWidget {
  const _Loading();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: AppSpacing.lg),
      child: Center(
        child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
      ),
    );
  }
}
