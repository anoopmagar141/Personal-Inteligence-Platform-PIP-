// "Why did PIP reply like that" - the pipeline trace, finally readable.
//
// backend/core/trace.py moved this out of a plaintext JSON file and into the
// SQLCipher database, and backend/api/server.py added /trace and /trace/{id}
// with an explicit reason: "it was being written to a file no interface read,
// so the answer existed and was unreachable; moving it into the database
// without a way to get it back out would only have changed where it was
// unreachable from." Both endpoints then shipped with no client - not in the
// web prototype either - so the answer stayed unreachable. This is the reader
// they were added for.
//
// Master-detail because the API is already shaped that way and says why:
// list_recent_traces() is "a listing rather than raw entries, because the
// question this answers is 'which run do I want to look at' - get_trace()
// answers the next one."
//
// Part 14.4 (frontend has zero intelligence) holds. Nothing here filters,
// ranks, or judges a run. Stage rows render in the order the backend returned
// them - which get_trace() orders by id precisely because timestamps tie - and
// every value is shown as sent. The one transformation is cosmetic: a stage
// key is split into its number and its words for the heading, and the exact
// key is kept on the row underneath so nothing is hidden behind the prettier
// version of itself.

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';

/// Splits "stage_09_llm_streaming" into ("09", "Llm streaming").
///
/// Deliberately total: "pipeline" and "response_cache" are also logged as
/// stages, and "stage_01" is logged with no name at all, so anything that is
/// not `stage_<digits>_<words>` keeps its own text and simply has no step
/// number. A trace is a diagnostic - a formatter that dropped or mangled an
/// unfamiliar stage key would break it exactly when something unfamiliar went
/// wrong.
({String? step, String label}) splitStageKey(String key) {
  final match = RegExp(r'^stage_(\d+)(?:_(.+))?$').firstMatch(key);
  if (match == null) return (step: null, label: _humanise(key));
  final rest = match.group(2);
  return (
    step: match.group(1),
    label: rest == null || rest.isEmpty ? 'Stage ${match.group(1)}' : _humanise(rest),
  );
}

String _humanise(String snake) {
  final words = snake.replaceAll('_', ' ').trim();
  if (words.isEmpty) return snake;
  return words[0].toUpperCase() + words.substring(1);
}

class TraceView extends StatefulWidget {
  final ApiClient api;

  /// Bumped by HomeShell on each tab selection - IndexedStack keeps this view
  /// alive for the app's lifetime, so initState runs exactly once and the list
  /// would otherwise show whichever runs existed at startup. Traces are
  /// written by every message, so that staleness would be immediate.
  final int refreshToken;

  const TraceView({super.key, required this.api, required this.refreshToken});

  @override
  State<TraceView> createState() => _TraceViewState();
}

class _TraceViewState extends State<TraceView> {
  List<dynamic>? _runs;
  String? _error;

  String? _selectedTraceId;
  List<dynamic>? _entries;
  String? _entriesError;
  bool _loadingEntries = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(TraceView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.refreshToken != widget.refreshToken) _load();
  }

  Future<void> _load() async {
    try {
      final runs = await widget.api.listTraces();
      if (!mounted) return;
      setState(() {
        _runs = runs;
        _error = null;
      });
      // Open the newest run rather than an empty right-hand pane. The most
      // recent one is what someone who just got a puzzling answer came here
      // for, and it saves a click on the overwhelmingly common path.
      if (runs.isNotEmpty) {
        final newest = (runs.first as Map<String, dynamic>)['trace_id'] as String;
        if (_selectedTraceId == null || !runs.any((r) => (r as Map)['trace_id'] == _selectedTraceId)) {
          await _select(newest);
        } else {
          await _select(_selectedTraceId!, force: true);
        }
      } else {
        setState(() {
          _selectedTraceId = null;
          _entries = null;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _select(String traceId, {bool force = false}) async {
    if (!force && traceId == _selectedTraceId) return;
    setState(() {
      _selectedTraceId = traceId;
      _entries = null;
      _entriesError = null;
      _loadingEntries = true;
    });
    try {
      final entries = await widget.api.getTrace(traceId);
      if (mounted) setState(() => _entries = entries);
    } catch (error) {
      // A trace can be purged between the listing and the click - retention is
      // real (trace.hard_delete_after_days) - so this is a normal outcome, not
      // a reason to blank the whole screen.
      if (mounted) setState(() => _entriesError = error.toString());
    } finally {
      if (mounted) setState(() => _loadingEntries = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Padding(
      padding: const EdgeInsets.all(AppSpacing.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Expanded(
                child: PageHeader(
                  eyebrow: 'Diagnostics',
                  title: 'Trace',
                  description: 'Why PIP replied the way it did: which stages ran, what each one '
                      'found, and where a run failed.',
                ),
              ),
              GhostButton(label: 'Refresh', onTap: _load),
            ],
          ),
          if (_error != null)
            Text(_error!, style: TextStyle(color: pip.danger, fontSize: 12.5))
          else
            Expanded(child: _body()),
        ],
      ),
    );
  }

  Widget _body() {
    if (_runs == null) {
      return const Center(child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)));
    }
    if (_runs!.isEmpty) {
      return const Align(
        alignment: Alignment.topCenter,
        child: EmptyState(
          icon: Icons.timeline_outlined,
          title: 'No runs traced yet',
          description: 'Every message you send records one. Ask PIP something, then come back.',
        ),
      );
    }
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(width: 260, child: _runList()),
        const SizedBox(width: AppSpacing.lg),
        Expanded(child: _detail()),
      ],
    );
  }

  Widget _runList() {
    return ListView.builder(
      itemCount: _runs!.length,
      itemBuilder: (context, index) {
        final run = _runs![index] as Map<String, dynamic>;
        final traceId = run['trace_id'] as String;
        final errors = ((run['errors'] ?? 0) as num).toInt();
        return Padding(
          padding: const EdgeInsets.only(bottom: AppSpacing.sm),
          child: _RunTile(
            startedAt: '${run['started_at']}',
            entries: ((run['entries'] ?? 0) as num).toInt(),
            errors: errors,
            selected: traceId == _selectedTraceId,
            onTap: () => _select(traceId),
          ),
        );
      },
    );
  }

  Widget _detail() {
    final pip = context.pip;
    if (_entriesError != null) {
      return SectionCard(
        child: Text(_entriesError!, style: TextStyle(color: pip.danger, fontSize: 12.5)),
      );
    }
    if (_loadingEntries || _entries == null) {
      return const Center(child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)));
    }
    return ListView(
      children: [
        SelectableText(
          'trace ${_selectedTraceId ?? ''}',
          style: TextStyle(fontSize: 11, color: pip.textFaint, fontFamily: AppTheme.mono),
        ),
        const SizedBox(height: AppSpacing.md),
        for (final raw in _entries!) _StageRow(entry: raw as Map<String, dynamic>),
      ],
    );
  }
}

class _RunTile extends StatelessWidget {
  final String startedAt;
  final int entries;
  final int errors;
  final bool selected;
  final VoidCallback onTap;
  const _RunTile({
    required this.startedAt,
    required this.entries,
    required this.errors,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Material(
      color: selected ? pip.accentSoft : pip.surface,
      borderRadius: AppRadius.md,
      child: InkWell(
        onTap: onTap,
        borderRadius: AppRadius.md,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.md),
          decoration: BoxDecoration(
            borderRadius: AppRadius.md,
            border: Border.all(color: selected ? pip.accent : pip.border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                startedAt,
                style: TextStyle(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w600,
                  color: selected ? pip.accent : pip.text,
                ),
              ),
              const SizedBox(height: 4),
              Row(
                children: [
                  Text('$entries stages', style: TextStyle(fontSize: 11.5, color: pip.textMuted)),
                  if (errors > 0) ...[
                    const SizedBox(width: AppSpacing.sm),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                      decoration: BoxDecoration(color: pip.dangerSoft, borderRadius: AppRadius.sm),
                      child: Text(
                        errors == 1 ? '1 error' : '$errors errors',
                        style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, color: pip.danger),
                      ),
                    ),
                  ],
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StageRow extends StatelessWidget {
  final Map<String, dynamic> entry;
  const _StageRow({required this.entry});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    final key = '${entry['stage']}';
    final parts = splitStageKey(key);
    final status = '${entry['status']}';
    // 'ok' and 'error' are the only statuses the backend writes today, but an
    // unrecognised one renders neutrally rather than being forced into either
    // bucket - a trace must not editorialise about a status it does not know.
    final isError = status == 'error';
    final isOk = status == 'ok';
    final message = '${entry['message'] ?? ''}';
    final errorDetail = '${entry['error_detail'] ?? ''}';

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: SectionCard(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.md),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 30,
              height: 30,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: isError ? pip.dangerSoft : pip.accentSoft,
                shape: BoxShape.circle,
              ),
              child: Text(
                parts.step ?? '·',
                style: TextStyle(
                  fontSize: 11.5,
                  fontWeight: FontWeight.w700,
                  color: isError ? pip.danger : pip.accent,
                ),
              ),
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          parts.label,
                          style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: pip.text),
                        ),
                      ),
                      Text(
                        status,
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                          color: isError
                              ? pip.danger
                              : isOk
                                  ? pip.accent
                                  : pip.textMuted,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '$key · ${entry['timestamp']}',
                    style: TextStyle(fontSize: 10.5, color: pip.textFaint, fontFamily: AppTheme.mono),
                  ),
                  if (message.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    SelectableText(
                      message,
                      style: TextStyle(fontSize: 12.5, color: pip.textMuted, height: 1.4),
                    ),
                  ],
                  if (errorDetail.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(AppSpacing.sm),
                      decoration: BoxDecoration(color: pip.dangerSoft, borderRadius: AppRadius.sm),
                      child: SelectableText(
                        errorDetail,
                        style: TextStyle(fontSize: 11.5, color: pip.danger, height: 1.4),
                      ),
                    ),
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
