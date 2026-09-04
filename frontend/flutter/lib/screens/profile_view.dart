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
// LAYOUT. This was one flat list of identical rows, each headed by the
// backend's own `field` key. That reads fine for a preference called
// answer_style and badly for everything else: goal_memory's key is the
// synthetic handle "goal:1", so the nine goals - the most substantial thing
// PIP knows - appeared as goal:1..goal:9 with their actual text squeezed into
// a value column and clipped. The set-membership tables were worse again,
// printing "data privacy" twice because for those the field IS the value.
//
// So rows are grouped by table under a heading a person would recognise, and
// each row renders in the shape its data actually has: a goal shows its text,
// a set-membership row shows its one word once, everything else shows a
// humanised label with the value under it. That is presentation only - no
// row is dropped, reordered within its group, or reinterpreted, and a table
// this build has never heard of still gets a section under its own raw name.
//
// Part 14.4 (frontend has zero intelligence) still holds: nothing here decides
// what is true, ranks a field, or edits a value on your behalf. What it does
// encode is which endpoint can service which row - API knowledge, the same
// kind this client already carries in every call it makes - and it is derived
// from the `table` the backend itself puts on each row rather than from a
// second copy of the backend's field list. Any mismatch still ends as the
// server's own 422 sentence, printed on the row that caused it.

import 'package:flutter/material.dart';

import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';

import '../api_client.dart';
import '../profile_picture.dart';
import '../theme.dart';

/// What the write endpoints can actually do with a row from this table.
///
/// This mirrors two backend functions rather than guessing:
///
///   * `correct_profile_field()` routes the write to whichever table already
///     holds the field, identity included - it passes allow_identity, which
///     the automated paths into that write deliberately do not, so the
///     Observer still cannot rename you from something it inferred. It used to
///     refuse name/language_preference/timezone outright, and used to write to
///     preference_memory unconditionally,
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
      // Editable, but never deletable: the columns are NOT NULL and they are
      // what PIP addresses you by, so a correction has a meaning here and a
      // retraction does not.
      return (canEdit: true, canDelete: false, hasHistory: false, note: null);
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

/// The order sections appear in, and what to call each one.
///
/// Ordered by how much it tells you about the person rather than
/// alphabetically or by table name: who they are, how they want to be spoken
/// to, what they are trying to do, then the smaller inferred material.
const profileSections = <String, String>{
  'identity': 'You',
  'interaction_style': 'How you like answers',
  'goal_memory': 'Goals',
  'active_projects': 'Projects',
  'skill_memory': 'Skills',
  'preference_memory': 'Preferences',
  'preferred_tools': 'Tools you use',
  'topic_interests': 'Topics you keep returning to',
  'document_access_patterns': 'Documents you lean on',
};

/// Tables whose `field` and `value` are the same string - membership in a set,
/// not a key with a value. Printing both is how "data privacy / data privacy"
/// happened.
const _setMembershipTables = {
  'topic_interests',
  'preferred_tools',
  'document_access_patterns',
};

/// What to show as a row's heading, and what (if anything) belongs under it.
///
/// Pure, so the decision can be tested without pumping a widget.
({String title, String? detail}) profileRowContent(Map<String, dynamic> row) {
  final table = '${row['table']}';
  final field = '${row['field']}';
  final value = '${row['value']}';

  // A goal's key is the synthetic "goal:<id>" handle get_profile() invents to
  // give the UI something stable to send back. It is addressing, not content -
  // the text is the goal.
  if (table == 'goal_memory') return (title: value, detail: null);

  if (_setMembershipTables.contains(table) || field == value) {
    return (title: field, detail: null);
  }

  return (title: humaniseFieldName(field), detail: value);
}

/// answer_style -> "Answer style", name -> "Name".
///
/// Anything carrying a path separator is left exactly as written: a document
/// path and a skill are the user's own text, not an identifier to prettify.
/// Capitalising is safe for the rest because a value that is already capital
/// ("Python") is unchanged by it - which is not true of the underscore
/// substitution, hence both rules rather than one.
String humaniseFieldName(String field) {
  if (field.isEmpty) return field;
  if (field.contains('/') || field.contains(r'\') || field.contains(':')) return field;
  final words = field.replaceAll('_', ' ').trim();
  if (words.isEmpty) return field;
  return words[0].toUpperCase() + words.substring(1);
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

  /// The name as the profile itself reports it, for the initials fallback.
  ///
  /// Read out of the rows already loaded rather than fetched separately: the
  /// value is being rendered a few lines below, and asking the backend again
  /// for it would be a second round trip for a first letter.
  String? _nameFromFields() {
    for (final row in _fields ?? const []) {
      if (row is Map && row['field'] == 'name') return '${row['value']}';
    }
    return null;
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
        // Bounded like every other screen here. Unbounded, a goal that runs to
        // two sentences was being set as one 1500px line, which is past the
        // width any prose stays readable at - and this screen is mostly prose.
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 820),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
            const PageHeader(
              eyebrow: 'Memory',
              title: 'Profile',
              description: 'What PIP has learned about you, and how confident it is. '
                  'Correct anything it has wrong - your correction outranks what it inferred.',
            ),
            // Above the fields rather than among them: everything below is
            // something PIP inferred and you may correct, and a picture is
            // neither. It was chosen, it carries no confidence, and there is
            // nothing for the Observer to have been wrong about.
            _PictureRow(api: widget.api, name: _nameFromFields()),
            _fields!.isEmpty
                ? const EmptyState(
                    icon: Icons.person_outline,
                    title: 'No profile fields yet',
                    description: 'PIP fills this in as it learns about you through conversation.',
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      for (final group in _grouped()) _section(group.key, group.value),
                    ],
                  ),
            ],
          ),
        ),
      ),
    );
  }

  /// Rows bucketed by table, in profileSections order, with anything
  /// unrecognised kept at the end under its own name. Order WITHIN a group is
  /// the backend's, untouched.
  List<MapEntry<String, List<Map<String, dynamic>>>> _grouped() {
    final buckets = <String, List<Map<String, dynamic>>>{};
    for (final raw in _fields!) {
      final row = raw as Map<String, dynamic>;
      buckets.putIfAbsent('${row['table']}', () => []).add(row);
    }

    final ordered = <MapEntry<String, List<Map<String, dynamic>>>>[];
    for (final table in profileSections.keys) {
      final rows = buckets.remove(table);
      if (rows != null && rows.isNotEmpty) ordered.add(MapEntry(table, rows));
    }
    // Whatever is left is a table added to the backend since this build. It
    // gets a section rather than vanishing - a profile screen that silently
    // omits part of the profile is the one thing it must never be.
    buckets.forEach((table, rows) => ordered.add(MapEntry(table, rows)));
    return ordered;
  }

  Widget _section(String table, List<Map<String, dynamic>> rows) {
    final pip = context.pip;
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.sm, left: 2),
            child: Row(
              children: [
                Text(
                  profileSections[table] ?? table,
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: pip.text),
                ),
                const SizedBox(width: AppSpacing.sm),
                Text('${rows.length}', style: TextStyle(fontSize: 11.5, color: pip.textFaint)),
              ],
            ),
          ),
          for (final row in rows) _row(row),
        ],
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
    final content = profileRowContent(row);
    final confidence = row['confidence'] is num ? (row['confidence'] as num).toDouble() : null;

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
                      // Selectable, and never truncated. A goal runs to a
                      // couple of sentences and is the most substantial thing
                      // on this screen; clipping it to keep rows a uniform
                      // height would hide the content to tidy the container.
                      SelectableText(
                        content.title,
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: pip.text,
                          height: 1.4,
                        ),
                      ),
                      if (content.detail != null) ...[
                        const SizedBox(height: 3),
                        SelectableText(
                          content.detail!,
                          style: TextStyle(fontSize: 13.5, color: pip.textMuted, height: 1.4),
                        ),
                      ],
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          if (confidence != null) ...[
                            _ConfidenceMeter(value: confidence),
                            const SizedBox(width: AppSpacing.sm),
                          ],
                          Flexible(
                            child: Text(
                              [
                                '${row['source_label'] ?? 'unknown source'}',
                                if (capability.note != null) capability.note!,
                              ].join(' · '),
                              style: TextStyle(fontSize: 11, color: pip.textFaint),
                            ),
                          ),
                        ],
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


/// How confident PIP is in one row, as a bar plus the number.
///
/// The number stays because this project's whole argument is that its
/// confidence is inspectable rather than vibes - "0.18" is a claim someone
/// may want to challenge, and a bar alone cannot be challenged. The bar is
/// there because a column of bare floats is not scannable, which is what the
/// screen looked like before.
class _ConfidenceMeter extends StatelessWidget {
  final double value;
  const _ConfidenceMeter({required this.value});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    final clamped = value.clamp(0.0, 1.0);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 34,
          height: 4,
          decoration: BoxDecoration(color: pip.surfaceRaised, borderRadius: BorderRadius.circular(2)),
          child: FractionallySizedBox(
            alignment: Alignment.centerLeft,
            widthFactor: clamped,
            child: Container(
              decoration: BoxDecoration(
                // Low confidence is stated, not coloured as an error - an
                // inferred 0.18 is PIP being honest, not something wrong.
                color: pip.accent.withValues(alpha: clamped < 0.4 ? 0.45 : 1.0),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
        ),
        const SizedBox(width: 6),
        Text(
          clamped.toStringAsFixed(2),
          style: TextStyle(fontSize: 11, color: pip.textFaint, fontFamily: AppTheme.mono),
        ),
      ],
    );
  }
}


/// The profile picture, with the two things anybody wants to do to one.
///
/// Its own widget rather than more of _ProfileViewState, and it keeps its own
/// error. The screen's _error blanks the entire page - correctly, since a
/// profile that could not be loaded has nothing to show - and a picture that
/// failed to upload must not do that. The profile behind it loaded fine.
class _PictureRow extends StatefulWidget {
  final ApiClient api;
  final String? name;

  const _PictureRow({required this.api, required this.name});

  @override
  State<_PictureRow> createState() => _PictureRowState();
}

class _PictureRowState extends State<_PictureRow> {
  bool _busy = false;
  String? _error;

  Future<void> _run(Future<void> Function() work) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await work();
      await loadProfilePicture(widget.api);
    } catch (error) {
      if (mounted) setState(() => _error = '$error');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _pick() async {
    final picked = await FilePicker.pickFile(
      type: FileType.custom,
      allowedExtensions: ['png', 'jpg', 'jpeg'],
    );
    if (picked == null) return;

    await _run(() async {
      final original = await picked.readAsBytes();
      // Scaled here rather than on the server: what travels is what gets
      // stored, decrypted on every read and decoded on every frame - and a
      // camera-roll photograph is several megabytes of pixels for something
      // drawn at 26 of them.
      final scaled = await downscaleForAvatar(Uint8List.fromList(original));
      await widget.api.setProfilePicture('avatar.png', scaled);
    });
  }

  Future<void> _remove() => _run(() => widget.api.deleteProfilePicture());

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;

    return ValueListenableBuilder<Uint8List?>(
      valueListenable: profilePicture,
      builder: (context, picture, _) {
        return Padding(
          padding: const EdgeInsets.only(bottom: AppSpacing.xl),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 72,
                height: 72,
                alignment: Alignment.center,
                clipBehavior: Clip.antiAlias,
                decoration: BoxDecoration(
                  color: pip.surfaceRaised,
                  shape: BoxShape.circle,
                  border: Border.all(color: pip.border),
                ),
                child: picture != null
                    ? Image.memory(picture, fit: BoxFit.cover, width: 72, height: 72, gaplessPlayback: true)
                    : Text(
                        // Initials rather than a stock silhouette: they are
                        // already personal, and they make an empty state look
                        // deliberate rather than unfinished.
                        initialsFrom(widget.name),
                        style: TextStyle(fontSize: 24, fontWeight: FontWeight.w600, color: pip.textMuted),
                      ),
              ),
              const SizedBox(width: AppSpacing.lg),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'Profile picture',
                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: pip.text),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'PNG or JPEG, kept inside your encrypted database rather than as a loose file.',
                      style: TextStyle(fontSize: 12.5, height: 1.4, color: pip.textFaint),
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Row(
                      children: [
                        TextButton(
                          onPressed: _busy ? null : _pick,
                          child: Text(picture == null ? 'Choose a picture' : 'Change'),
                        ),
                        if (picture != null)
                          TextButton(
                            onPressed: _busy ? null : _remove,
                            child: const Text('Remove'),
                          ),
                        if (_busy) ...[
                          const SizedBox(width: AppSpacing.sm),
                          const SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        ],
                      ],
                    ),
                    if (_error != null)
                      Text(_error!, style: TextStyle(fontSize: 12, color: pip.danger)),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
