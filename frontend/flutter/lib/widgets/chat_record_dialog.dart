// A chat's "where we left off" record, seen and put right (BLUEPRINT #13 part 4).
//
// PIP's Observer - a model - writes one record per chat when the chat ends: its topic, open problems, decisions and
// next step. Every later chat in the same project is shown it, so a wrong record keeps coming back. Before this there
// was nowhere to see it: the user could neither check what PIP would carry forward nor correct it.
//
// So the dialog shows the record and says who wrote it and when ("it may be wrong" for PIP's own), what the chat
// produced (the decisions learned from it, and how its candidates came out - counts only, since the audit log keeps
// no text), and lets the user edit or clear it. A correction is the user's from then on: the backend marks it so,
// the prompt says so, and PIP's later passes over the chat leave it alone.
//
// The backend is the authority. A correction it refuses shows its own sentence and the form stays open, so a typo
// costs nothing; the client checks nothing itself beyond splitting the lines.

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';

class ChatRecordDialog extends StatefulWidget {
  /// GET /conversations/{id}/record: {"record": {...} or null, "links": {...}}.
  final Future<Map<String, dynamic>> Function() load;

  /// PUT /conversations/{id}/record with the user's fields; answers {"record": {...}}.
  final Future<Map<String, dynamic>> Function(Map<String, dynamic> fields) save;

  /// DELETE /conversations/{id}/record.
  final Future<void> Function() clear;

  const ChatRecordDialog({super.key, required this.load, required this.save, required this.clear});

  @override
  State<ChatRecordDialog> createState() => _ChatRecordDialogState();
}

class _ChatRecordDialogState extends State<ChatRecordDialog> {
  Map<String, dynamic>? _record;
  Map<String, dynamic> _links = const {};
  bool _loaded = false;
  bool _editing = false;
  bool _busy = false;
  String? _error;

  final _topic = TextEditingController();
  final _problems = TextEditingController();
  final _decisions = TextEditingController();
  final _step = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    for (final c in [_topic, _problems, _decisions, _step]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final body = await widget.load();
      if (!mounted) return;
      setState(() {
        _record = body['record'] as Map<String, dynamic>?;
        _links = (body['links'] as Map<String, dynamic>?) ?? const {};
        _loaded = true;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _loaded = true;
      });
    }
  }

  List<String> _lines(dynamic value) => (value as List<dynamic>? ?? const []).map((e) => e.toString()).toList();

  void _startEditing() {
    final r = _record;
    _topic.text = (r?['topic'] as String?) ?? '';
    _problems.text = _lines(r?['open_problems']).join('\n');
    _decisions.text = _lines(r?['last_decisions']).join('\n');
    _step.text = (r?['suggested_next_step'] as String?) ?? '';
    setState(() {
      _editing = true;
      _error = null;
    });
  }

  List<String> _split(String text) => text.split('\n').map((l) => l.trim()).where((l) => l.isNotEmpty).toList();

  Future<void> _save() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final body = await widget.save({
        'topic': _topic.text,
        'open_problems': _split(_problems.text),
        'last_decisions': _split(_decisions.text),
        'suggested_next_step': _step.text.trim(),
      });
      if (!mounted) return;
      setState(() {
        _record = body['record'] as Map<String, dynamic>?;
        _editing = false;
        _busy = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.detail;
        _busy = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _busy = false;
      });
    }
  }

  Future<void> _confirmClear() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Clear this record?'),
        content: const Text(
          'PIP will no longer carry this summary into your next chats. The chat itself and what was learned from it '
          'stay; the next time this chat ends, PIP may write a new record.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text('Clear record')),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() => _busy = true);
    try {
      await widget.clear();
      if (!mounted) return;
      setState(() {
        _record = null;
        _busy = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _busy = false;
      });
    }
  }

  String _attribution(Map<String, dynamic> r) {
    final date = (r['record_date'] as String? ?? '');
    final day = date.length >= 10 ? date.substring(0, 10) : date;
    switch (r['source']) {
      case 'user':
        return 'Corrected by you, $day.';
      case 'earlier_note':
        return 'Carried over from PIP\'s earlier single note, $day; it may be wrong.';
      default:
        return 'Written by PIP when this chat ended, $day; it may be wrong.';
    }
  }

  String? _outcomes() {
    final o = (_links['outcomes'] as Map<String, dynamic>?) ?? const {};
    final parts = <String>[];
    for (final (key, label) in const [
      ('accepted', 'kept'),
      ('deferred', 'asked about'),
      ('rejected', 'not kept'),
      ('dismissed', 'dismissed by you'),
    ]) {
      final n = o[key];
      if (n is int && n > 0) parts.add('$n $label');
    }
    return parts.isEmpty ? null : parts.join(', ');
  }

  Widget _section(String label, List<String> items) {
    final pip = context.pip;
    if (items.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: TextStyle(fontSize: 12, color: pip.textMuted, fontWeight: FontWeight.w600)),
          for (final item in items) Text('•  $item', style: TextStyle(fontSize: 13.5, color: pip.text, height: 1.4)),
        ],
      ),
    );
  }

  Widget _view() {
    final pip = context.pip;
    final r = _record;
    if (r == null) {
      return Text(
        'No record of this chat yet. PIP writes one when a chat with something to summarise ends.',
        style: TextStyle(fontSize: 13.5, color: pip.textMuted, height: 1.4),
      );
    }
    final step = (r['suggested_next_step'] as String?) ?? '';
    final decisions = (_links['decisions'] as List<dynamic>? ?? const []).cast<Map<String, dynamic>>();
    final outcomes = _outcomes();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(r['topic'] as String? ?? '', style: TextStyle(fontSize: 15, color: pip.text, fontWeight: FontWeight.w600)),
        const SizedBox(height: AppSpacing.xs),
        Text(_attribution(r), style: TextStyle(fontSize: 12, color: pip.textFaint)),
        _section('Open problems', _lines(r['open_problems'])),
        _section('Decisions', _lines(r['last_decisions'])),
        if (step.isNotEmpty) _section('Next step', [step]),
        if (decisions.isNotEmpty || outcomes != null) ...[
          const SizedBox(height: AppSpacing.md),
          Divider(color: pip.border, height: 1),
          _section('Decisions PIP logged from this chat', [for (final d in decisions) d['decision_text'] as String]),
          if (outcomes != null)
            Padding(
              padding: const EdgeInsets.only(top: AppSpacing.sm),
              child: Text('What PIP did with what it noticed: $outcomes.',
                  style: TextStyle(fontSize: 12.5, color: pip.textMuted)),
            ),
        ],
      ],
    );
  }

  Widget _form() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        TextField(controller: _topic, decoration: const InputDecoration(labelText: 'Topic')),
        const SizedBox(height: AppSpacing.sm),
        TextField(
          controller: _problems,
          minLines: 2,
          maxLines: 5,
          decoration: const InputDecoration(labelText: 'Open problems (one per line)'),
        ),
        const SizedBox(height: AppSpacing.sm),
        TextField(
          controller: _decisions,
          minLines: 2,
          maxLines: 5,
          decoration: const InputDecoration(labelText: 'Decisions (one per line)'),
        ),
        const SizedBox(height: AppSpacing.sm),
        TextField(controller: _step, decoration: const InputDecoration(labelText: 'Next step')),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    final hasRecord = _record != null;
    return AlertDialog(
      title: const Text('Where we left off'),
      content: SizedBox(
        width: 520,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              if (!_loaded) const Center(child: Padding(padding: EdgeInsets.all(AppSpacing.md), child: CircularProgressIndicator()))
              else if (_editing) _form()
              else _view(),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.sm),
                  child: Text(_error!, style: TextStyle(color: pip.danger, fontSize: 13)),
                ),
            ],
          ),
        ),
      ),
      actions: _editing
          ? [
              TextButton(onPressed: _busy ? null : () => setState(() => _editing = false), child: const Text('Cancel')),
              FilledButton(onPressed: _busy ? null : _save, child: const Text('Save')),
            ]
          : [
              if (_loaded && hasRecord)
                TextButton(onPressed: _busy ? null : _confirmClear, child: const Text('Clear')),
              if (_loaded)
                TextButton(onPressed: _busy ? null : _startEditing, child: Text(hasRecord ? 'Edit' : 'Write it')),
              TextButton(onPressed: () => Navigator.of(context).maybePop(), child: const Text('Close')),
            ],
    );
  }
}
