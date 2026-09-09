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
// THE CALLING NAME, AND WHY IT NEEDS A ROW THAT HOLDS NOTHING
//
// identity.preferred_name has been in the schema, in IDENTITY_FIELDS, in
// onboarding, and in correct_profile_field's routing since profiles had
// names - and it was unreachable to anybody who left the optional box blank
// at onboarding. get_profile() omits an unset one deliberately, so it does
// not put a blank "Preferred name:" line into the Identity section of every
// prompt; this screen renders what get_profile returns; so the field that
// was never set had no row, and a row is the only thing here that carries a
// button. Onboarding's "you can change any of this later from your profile"
// was true of every field except that one.
//
// Fixed on this side rather than by emitting the empty row from the backend,
// because the backend's reason for omitting it is a good one and applies to
// the prompt, not to this screen. So the placeholder is a presentation
// decision made where the presenting happens: one synthesised row, marked
// `unset`, offering "Set" instead of "Correct" and no confidence meter,
// because there is nothing yet to be confident about. Everything it sends is
// the ordinary correction endpoint - correct_profile_field already routes an
// unset identity field to the identity table precisely so that the first
// attempt to set a calling name does not create a preference of that name
// instead.
//
// TWO KINDS OF FACT, AND WHY THEY ARE NOW TWO SECTIONS
//
// Everything on this screen used to be one list, which put "your name is Anup
// Magar" and "PIP is 18% sure you prefer terse answers" in the same shape,
// under the same confidence meter, with the same Correct button. They are not
// the same kind of claim. One is something you stated and PIP is merely
// storing; the other is something PIP inferred and may have got wrong - and
// this screen's entire purpose is governing the second kind.
//
// So identity is lifted out into a profile card at the top: who you are, what
// PIP calls you, what language and timezone it works in, and the handful of
// counts PIP can honestly report about the relationship. It is edited as a
// unit, through one Edit button, because those four fields are answered
// together at onboarding and read together in every prompt - correcting them
// one dialog at a time was four round trips to change a name and the timezone
// it is greeted in.
//
// What remains below is what PIP has LEARNED. Every row there is inferred,
// carries a confidence, and can be retracted. That is the list this screen was
// built to govern, and it reads as one now that it is not interleaved with
// four rows nobody needs to govern at all.
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
({bool canEdit, bool canDelete, bool hasHistory, String? note}) profileRowCapability(
  String table, {
  String field = '',
}) {
  switch (table) {
    case 'identity':
      // Editable, and deletable in exactly one place. name,
      // language_preference and timezone are NOT NULL and are what PIP
      // addresses you by, so a correction has a meaning there and a
      // retraction does not.
      //
      // preferred_name is the exception, because it is the one identity
      // column that is optional to begin with: removing it means "go back to
      // calling me by my name", not "I have no name".
      // soft_delete_profile_field() gives it its own branch for that reason,
      // and offering no button for a delete the backend implements leaves the
      // only way to undo a calling name being to set it to something else.
      return (
        canEdit: true,
        canDelete: field == 'preferred_name',
        hasHistory: false,
        note: null,
      );
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
/// alphabetically or by table name: how they want to be spoken to, what they
/// are trying to do, then the smaller inferred material.
///
/// identity is deliberately absent. Those rows are drawn by the profile card
/// above the list rather than as a section in it, and removing them here
/// rather than filtering at the call site keeps one answer to "which tables
/// does the learned list show" - a future identity column is covered by it
/// without anybody having to remember.
const profileSections = <String, String>{
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

/// What the identity columns are called on screen.
///
/// Only where the humanised column name would be worse. "Name" and "Preferred
/// name" sitting next to each other do not say which is which - the first
/// reads as the general case and the second as a variation on it, when they
/// are a person's full name and what to call them. Onboarding already asks
/// for them as "Full name" and "What should PIP call you?", so this is the
/// same pair of questions given the same pair of names.
///
/// Scoped to identity rather than folded into humaniseFieldName(): a
/// preference legitimately called "name" is not somebody's full name, and a
/// humaniser is a spelling rule, not a glossary.
const identityLabels = <String, String>{
  'name': 'Full name',
  'preferred_name': 'Preferred name',
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

  // A field the profile does not hold yet, offered so that it can be. What
  // goes underneath is what PIP does in its absence - not a value, which is
  // the whole point of the row.
  if (row['unset'] == true) {
    return (title: _label(table, field), detail: row['note'] as String?);
  }

  if (_setMembershipTables.contains(table) || field == value) {
    return (title: field, detail: null);
  }

  return (title: _label(table, field), detail: value);
}

String _label(String table, String field) =>
    (table == 'identity' ? identityLabels[field] : null) ?? humaniseFieldName(field);

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

  /// Close the chat socket before an operation that ends this session.
  ///
  /// Passed in rather than reached for, because the socket belongs to the
  /// shell: this screen is one tab inside it and has no business owning the
  /// connection the chat tab is using.
  final VoidCallback onCloseChat;

  /// Return to the sign-in screen, after this profile has stopped existing.
  final VoidCallback onSignedOut;

  const ProfileView({
    super.key,
    required this.api,
    required this.onCloseChat,
    required this.onSignedOut,
  });

  @override
  State<ProfileView> createState() => _ProfileViewState();
}

class _ProfileViewState extends State<ProfileView> {
  List<dynamic>? _fields;
  Map<String, dynamic>? _status;
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

    // Second, and separately swallowed. The counts are the least important
    // thing on this screen and the profile is the most: a /status that failed
    // must cost the four small numbers in the card, not the page. The card
    // renders without them.
    try {
      final status = await widget.api.getStatus();
      if (mounted) setState(() => _status = status);
    } catch (_) {}
  }

  /// The identity columns as a plain map, for the card that draws them.
  ///
  /// Built from the same rows the list is built from rather than fetched
  /// separately - get_profile() is one call and already returned them, and a
  /// second endpoint for the same four values would be a second answer to
  /// what somebody's name is.
  Map<String, String> _identity() {
    final values = <String, String>{};
    for (final raw in _fields ?? const []) {
      if (raw is Map && raw['table'] == 'identity') {
        values['${raw['field']}'] = '${raw['value']}';
      }
    }
    return values;
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
    final unset = row['unset'] == true;
    final saved = await showDialog<String>(
      context: context,
      builder: (context) => _CorrectFieldDialog(
        field: field,
        // The label, not the column key. "Correct \"preferred_name\"" asks a
        // person to recognise an identifier they have never seen; the row
        // above the button already calls it Preferred name.
        label: profileRowContent(row).title,
        setting: unset,
        initialValue: unset ? '' : '${row['value']}',
        // A skill's value is skill_memory.level, a number. Saying so beats
        // letting someone type "expert" and meet a refusal for it - the
        // backend does reject it, but a hint is cheaper than a round trip.
        hint: row['table'] == 'skill_memory'
            ? 'A number from 0 to 1 - how well you know it.'
            : (field == 'preferred_name' ? 'What PIP should call you in conversation.' : null),
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
          // preferred_name is the one delete here that is not a retraction of
          // something PIP believed - the column is cleared outright, and what
          // happens next is that PIP uses the name it already has. Saying
          // "the record is kept and marked retracted" would describe
          // soft_delete_profile_field's loop, which this field never enters.
          field == 'preferred_name'
              ? 'PIP will go back to calling you by your full name. You can set a '
                  'preferred name again at any time.'
              : 'PIP will stop using "$field" straight away. The record is kept and marked '
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
            // Above the list rather than among it: everything below is
            // something PIP inferred and you may correct, and none of this is.
            // A picture was chosen, a name was stated - neither carries a
            // confidence, and there is nothing for the Observer to have been
            // wrong about.
            ProfileCard(
              api: widget.api,
              identity: _identity(),
              status: _status,
              learnedCount: _grouped().fold<int>(0, (sum, g) => sum + g.value.length),
              onChanged: _load,
            ),
            const SizedBox(height: AppSpacing.xl),
            Builder(builder: (context) {
              final groups = _grouped();
              if (groups.isEmpty) {
                return const EmptyState(
                  icon: Icons.psychology_outlined,
                  title: 'PIP has not learned anything yet',
                  // Not an error, and not a gap to apologise for: an
                  // installation that has only been onboarded has stated
                  // facts and inferred none, which is exactly right.
                  description: 'What you tell PIP directly is above. This fills in as it '
                      'notices patterns in what you work on.',
                );
              }
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.only(bottom: AppSpacing.md, left: 2),
                    child: Text(
                      'What PIP has learned',
                      style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: pip.text),
                    ),
                  ),
                  for (final group in groups) _section(group.key, group.value),
                ],
              );
            }),
            // Last, deliberately. Everything above is what PIP has of yours;
            // this is what you can do about the whole of it, and a page that
            // opened on a delete button would be a different page.
            const SizedBox(height: AppSpacing.xl),
            AccountCard(
              api: widget.api,
              onCloseChat: widget.onCloseChat,
              onSignedOut: widget.onSignedOut,
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
      // Drawn by the profile card instead. Skipped here rather than removed
      // after bucketing, so an identity column this build has never heard of
      // does not fall through to the unrecognised-table branch below and
      // reappear as a section called "identity".
      if (row['table'] == 'identity') continue;
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
    final capability = profileRowCapability(table, field: field);
    final unset = row['unset'] == true;
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
                    // "Correct" is the wrong verb for something PIP has never
                    // claimed. Nothing is being put right here; a question is
                    // being answered for the first time.
                    GhostButton(label: unset ? 'Set' : 'Correct', onTap: () => _edit(row)),
                  ],
                  // Never on a placeholder. The capability is a property of
                  // the FIELD - preferred_name is deletable - but this row
                  // holds nothing to delete, and the button would reach the
                  // backend only to be told there was no active record under
                  // that name to forget.
                  if (capability.canDelete && !unset) ...[
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

  /// What the row above the button calls this field.
  final String label;

  /// Whether this field is being answered for the first time rather than put
  /// right. Changes the verb and drops the sentence about outranking, which
  /// says nothing when there is nothing to outrank.
  final bool setting;

  /// What this particular field expects, when that is not obvious from the
  /// value already in the box. Null for the ordinary free-text case.
  final String? hint;
  const _CorrectFieldDialog({
    required this.field,
    required this.initialValue,
    required this.label,
    this.setting = false,
    this.hint,
  });

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
        widget.setting ? 'Set ${widget.label.toLowerCase()}' : 'Correct "${widget.label}"',
        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.setting
                ? 'You are telling PIP this directly, so it is recorded as explicit rather than inferred.'
                : 'This is recorded as your own correction, which outranks anything PIP inferred.',
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


/// Who you are, as opposed to what PIP thinks about you.
///
/// This is the half of the profile screen that is NOT governed memory. Every
/// value in it was stated - at onboarding, or here - so nothing carries a
/// confidence, nothing can be retracted, and there is no Observer to have
/// been wrong. Presenting it in the same row shape as an inferred preference
/// was the thing that made the old screen hard to read: a name and a hunch
/// looked identical.
///
/// It keeps its own error, and so did the picture row it replaces, for the
/// same reason. The screen's _error blanks the entire page - correct, since a
/// profile that would not load has nothing to show - and a picture that failed
/// to upload, or a rejected timezone, must not do that. The profile behind it
/// loaded fine.
class ProfileCard extends StatefulWidget {
  final ApiClient api;

  /// The identity columns, keyed by column name. Absent keys are absent
  /// values: preferred_name is optional, and get_profile() omits it when it
  /// has never been set.
  final Map<String, String> identity;

  /// /status, or null when it could not be read. Null costs the counts and
  /// nothing else.
  final Map<String, dynamic>? status;

  /// How many rows the learned list holds. Passed in rather than fetched:
  /// the screen has already grouped them, and counting them twice would be
  /// two answers to one question.
  final int learnedCount;

  final Future<void> Function() onChanged;

  const ProfileCard({
    super.key,
    required this.api,
    required this.identity,
    required this.status,
    required this.learnedCount,
    required this.onChanged,
  });

  @override
  State<ProfileCard> createState() => _ProfileCardState();
}

class _ProfileCardState extends State<ProfileCard> {
  bool _busy = false;
  String? _error;

  String? get _fullName => widget.identity['name'];
  String? get _callingName {
    final value = widget.identity['preferred_name'];
    return (value == null || value.trim().isEmpty) ? null : value;
  }

  Future<void> _run(Future<void> Function() work) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await work();
      await widget.onChanged();
    } catch (error) {
      // The server's own sentence. "Your timezone cannot be empty" is the
      // whole answer to why a save did not take, and a generic failure would
      // replace it with less.
      if (mounted) setState(() => _error = '$error');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _pickPicture() async {
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
      // drawn at 88 of them.
      final scaled = await downscaleForAvatar(Uint8List.fromList(original));
      await widget.api.setProfilePicture('avatar.png', scaled);
      await loadProfilePicture(widget.api);
    });
  }

  Future<void> _removePicture() => _run(() async {
        await widget.api.deleteProfilePicture();
        await loadProfilePicture(widget.api);
      });

  /// Edit all four identity fields at once.
  ///
  /// Only what CHANGED is sent, which is not an optimisation. Every write here
  /// is recorded as an explicit user correction and stamps source_label on the
  /// row; re-sending an untouched timezone would re-assert it as a fresh
  /// statement about a field the person did not look at.
  Future<void> _edit() async {
    final result = await showDialog<Map<String, String?>>(
      context: context,
      builder: (context) => _EditIdentityDialog(identity: widget.identity),
    );
    if (result == null) return;

    await _run(() async {
      for (final entry in result.entries) {
        final value = entry.value;
        if (value == null) {
          // Cleared, which only preferred_name can be - the dialog does not
          // offer it for the three NOT NULL columns, and the backend refuses
          // an empty value for them regardless. Deleting rather than writing
          // "" so that "no calling name" stays one state and not two.
          await widget.api.deleteProfileField(entry.key);
        } else {
          await widget.api.correctMemory(entry.key, value);
        }
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;

    return SectionCard(
      padding: const EdgeInsets.all(AppSpacing.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ValueListenableBuilder<Uint8List?>(
                valueListenable: profilePicture,
                builder: (context, picture, _) => Container(
                  width: 88,
                  height: 88,
                  alignment: Alignment.center,
                  clipBehavior: Clip.antiAlias,
                  decoration: BoxDecoration(
                    color: pip.surfaceRaised,
                    shape: BoxShape.circle,
                    border: Border.all(color: pip.border),
                  ),
                  child: picture != null
                      ? Image.memory(picture, fit: BoxFit.cover, width: 88, height: 88, gaplessPlayback: true)
                      : Text(
                          // Initials rather than a stock silhouette: they are
                          // already personal, and they make an empty state
                          // look deliberate rather than unfinished.
                          initialsFrom(_fullName),
                          style: TextStyle(fontSize: 30, fontWeight: FontWeight.w600, color: pip.textMuted),
                        ),
                ),
              ),
              const SizedBox(width: AppSpacing.lg),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    SelectableText(
                      _fullName ?? 'No name yet',
                      style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: pip.text, height: 1.2),
                    ),
                    const SizedBox(height: 4),
                    // The calling name gets its own line rather than a slot in
                    // the metadata run below, because it is the one fact here
                    // that changes what PIP says out loud. Absent when there
                    // is none: "PIP calls you Anup Magar" under the heading
                    // "Anup Magar" states the default twice.
                    if (_callingName != null)
                      Text(
                        'PIP calls you $_callingName',
                        style: TextStyle(fontSize: 13.5, color: pip.accent),
                      ),
                    const SizedBox(height: 6),
                    Wrap(
                      spacing: AppSpacing.sm,
                      runSpacing: 4,
                      children: [
                        for (final part in [
                          widget.identity['language_preference'],
                          widget.identity['timezone'],
                        ].whereType<String>())
                          Text(part, style: TextStyle(fontSize: 12.5, color: pip.textMuted)),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Row(
                      children: [
                        GhostButton(label: 'Change picture', onTap: _busy ? null : _pickPicture),
                        const SizedBox(width: AppSpacing.sm),
                        ValueListenableBuilder<Uint8List?>(
                          valueListenable: profilePicture,
                          // Offered only when there is one. A Remove that does
                          // nothing is the same class of bug as a Forget on a
                          // field that was never set.
                          builder: (context, picture, _) => picture == null
                              ? const SizedBox.shrink()
                              : GhostButton(
                                  label: 'Remove',
                                  color: pip.textMuted,
                                  onTap: _busy ? null : _removePicture,
                                ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              if (_busy)
                const Padding(
                  padding: EdgeInsets.only(left: AppSpacing.md),
                  child: SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
                )
              else
                GhostButton(label: 'Edit', onTap: _edit),
            ],
          ),
          if (_error != null) ...[
            const SizedBox(height: AppSpacing.md),
            Text(_error!, style: TextStyle(fontSize: 11.5, color: pip.danger)),
          ],
          const SizedBox(height: AppSpacing.lg),
          _Stats(status: widget.status, learnedCount: widget.learnedCount),
        ],
      ),
    );
  }
}

/// The four counts PIP can honestly report.
///
/// Every one is read from something the backend already maintains -
/// profile_meta's session counter and first_session_date, decision_log, and
/// the rows this screen is already displaying. Nothing here is derived,
/// estimated, or padded out to fill a fourth slot: a profile screen for a
/// product whose whole argument is that its claims are inspectable cannot
/// open with a statistic nobody can check.
class _Stats extends StatelessWidget {
  final Map<String, dynamic>? status;
  final int learnedCount;

  const _Stats({required this.status, required this.learnedCount});

  /// "2026-09-03T00:02:03Z" -> "3 Sep 2026". The stored value is an ISO
  /// timestamp because that is what everything else in this database stores;
  /// a date on a profile card is read, not sorted.
  static String? formatSince(String? iso) {
    if (iso == null || iso.isEmpty) return null;
    final parsed = DateTime.tryParse(iso);
    if (parsed == null) return null;
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    final local = parsed.toLocal();
    return '${local.day} ${months[local.month - 1]} ${local.year}';
  }

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    final since = formatSince(status?['first_session_date'] as String?);

    final tiles = <({String value, String label})>[
      (value: '${status?['session_count'] ?? '-'}', label: 'Sessions'),
      (value: since ?? '-', label: 'Known you since'),
      (value: '$learnedCount', label: 'Things learned'),
      (value: '${status?['active_decisions'] ?? '-'}', label: 'Decisions'),
    ];

    return Container(
      decoration: BoxDecoration(
        color: pip.surfaceRaised,
        borderRadius: AppRadius.md,
        border: Border.all(color: pip.border),
      ),
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
      child: Row(
        children: [
          for (var i = 0; i < tiles.length; i++) ...[
            if (i > 0)
              Container(width: 1, height: 30, color: pip.border),
            Expanded(
              child: Column(
                children: [
                  Text(
                    tiles[i].value,
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: pip.text),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    tiles[i].label,
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 11.5, color: pip.textMuted),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// All four identity fields in one form.
///
/// One dialog rather than four Correct buttons because these are answered
/// together at onboarding and read together in every prompt - changing a name
/// and the timezone it is greeted in was two dialogs and two round trips.
///
/// Returns only what changed, with null meaning "cleared". The caller turns a
/// null into a delete, which only preferred_name can be: the other three are
/// NOT NULL columns and the field marks them required rather than letting
/// somebody discover it from a 422.
class _EditIdentityDialog extends StatefulWidget {
  final Map<String, String> identity;
  const _EditIdentityDialog({required this.identity});

  @override
  State<_EditIdentityDialog> createState() => _EditIdentityDialogState();
}

class _EditIdentityDialogState extends State<_EditIdentityDialog> {
  late final _name = TextEditingController(text: widget.identity['name'] ?? '');
  late final _preferred = TextEditingController(text: widget.identity['preferred_name'] ?? '');
  late final _language = TextEditingController(text: widget.identity['language_preference'] ?? '');
  late final _timezone = TextEditingController(text: widget.identity['timezone'] ?? '');

  String? _complaint;

  @override
  void dispose() {
    _name.dispose();
    _preferred.dispose();
    _language.dispose();
    _timezone.dispose();
    super.dispose();
  }

  void _save() {
    final name = _name.text.trim();
    final language = _language.text.trim();
    final timezone = _timezone.text.trim();

    // Checked here as well as on the server, for the reason the sign-in screen
    // checks a password mismatch itself: the backend does refuse an empty
    // identity column, and being told so after a round trip is worse than
    // being told immediately by the field that is empty.
    if (name.isEmpty || language.isEmpty || timezone.isEmpty) {
      setState(() => _complaint = 'Full name, language and timezone cannot be empty.');
      return;
    }

    final preferred = _preferred.text.trim();
    final hadPreferred = (widget.identity['preferred_name'] ?? '').trim();

    final changed = <String, String?>{
      if (name != (widget.identity['name'] ?? '')) 'name': name,
      if (language != (widget.identity['language_preference'] ?? '')) 'language_preference': language,
      if (timezone != (widget.identity['timezone'] ?? '')) 'timezone': timezone,
      // Three cases, and only two of them are writes. Set to something new,
      // cleared when there was one (a delete), or emptied when there was none
      // - which is not a change at all and must not become a delete for a row
      // that does not exist.
      if (preferred != hadPreferred)
        'preferred_name': preferred.isEmpty ? null : preferred,
    };

    Navigator.of(context).pop(changed);
  }

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return AlertDialog(
      backgroundColor: pip.surface,
      title: const Text('Edit your profile', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
      content: SizedBox(
        width: 380,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'You are telling PIP this directly, so all of it is recorded as '
                'explicit rather than inferred.',
                style: TextStyle(fontSize: 12.5, color: pip.textMuted, height: 1.4),
              ),
              const SizedBox(height: AppSpacing.lg),
              TextField(
                controller: _name,
                autofocus: true,
                decoration: const InputDecoration(labelText: 'Full name'),
              ),
              const SizedBox(height: AppSpacing.md),
              TextField(
                controller: _preferred,
                decoration: const InputDecoration(
                  labelText: 'Preferred name',
                  helperText: 'What PIP calls you. Leave blank to be called by your full name.',
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              TextField(
                controller: _language,
                decoration: const InputDecoration(labelText: 'Primary language'),
              ),
              const SizedBox(height: AppSpacing.md),
              TextField(
                controller: _timezone,
                decoration: const InputDecoration(
                  labelText: 'Timezone',
                  helperText: 'e.g. Asia/Kathmandu',
                ),
                onSubmitted: (_) => _save(),
              ),
              if (_complaint != null) ...[
                const SizedBox(height: AppSpacing.md),
                Text(_complaint!, style: TextStyle(fontSize: 12, color: pip.danger)),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
        FilledButton(onPressed: _save, child: const Text('Save')),
      ],
    );
  }
}

/// The profile itself, as opposed to what is inside it.
///
/// WHY THIS IS ON THE PROFILE SCREEN AND NOT IN SETTINGS
///
/// Everything else here is what PIP has learned about a person. This is the
/// container that holds it: its name, its password, and the button that
/// destroys it. They belong on the same screen because they are answers to the
/// same question - "what does PIP have of mine, and what can I do about it" -
/// and putting the delete anywhere else would mean somebody reading a page of
/// inferences about themselves has no way to act on the whole of it from where
/// they are standing.
///
/// WHY ALL THREE ACTIONS ASK FOR SOMETHING
///
/// Renaming asks for a name, and changing or deleting asks for the password
/// again. Being signed in proves the database was opened at some point; it
/// does not prove who is at the keyboard now, and an unattended screen should
/// not be one click from either of the two operations nobody can undo.
class AccountCard extends StatefulWidget {
  final ApiClient api;

  /// Close the chat socket before the delete. The backend cannot erase a
  /// database file this client still has open.
  final VoidCallback onCloseChat;

  /// Back to the sign-in screen, once the profile is gone.
  final VoidCallback onSignedOut;

  const AccountCard({
    super.key,
    required this.api,
    required this.onCloseChat,
    required this.onSignedOut,
  });

  @override
  State<AccountCard> createState() => _AccountCardState();
}

class _AccountCardState extends State<AccountCard> {
  String? _slug;
  String? _name;
  bool _picturePublished = false;
  bool _busy = false;
  String? _error;
  String? _note;

  @override
  void initState() {
    super.initState();
    _load();
  }

  /// Which profile this is, and whether its picture is on the sign-in screen.
  ///
  /// From /auth/profiles rather than from a field on this screen, because the
  /// profile's name and the person's name are different things: identity.name
  /// is what PIP calls you, and this is the label on the database. They are
  /// usually the same word and are not the same fact - renaming the profile
  /// must not rewrite a memory, and correcting a memory must not rename a
  /// directory.
  Future<void> _load() async {
    try {
      final payload = await widget.api.authProfiles();
      final active = payload['active'] as String?;
      final listed = (payload['profiles'] as List<dynamic>? ?? [])
          .cast<Map<String, dynamic>>();
      final me = listed.where((p) => p['slug'] == active).firstOrNull;
      final published = await widget.api.signInPicturePublished();
      if (!mounted) return;
      setState(() {
        _slug = active;
        _name = me?['name'] as String? ?? active;
        _picturePublished = published;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = '$error');
    }
  }

  Future<void> _run(Future<void> Function() work) async {
    setState(() {
      _busy = true;
      _error = null;
      _note = null;
    });
    try {
      await work();
    } catch (error) {
      // The server's own sentence. "That is not your current password" and
      // "use at least 8 characters" are both complete answers, and a generic
      // failure would replace them with less.
      if (mounted) setState(() => _error = error is ApiException ? error.detail : '$error');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _rename() async {
    final slug = _slug;
    if (slug == null) return;
    final name = await showDialog<String>(
      context: context,
      builder: (context) => _RenameProfileDialog(current: _name ?? ''),
    );
    if (name == null) return;

    await _run(() async {
      await widget.api.renameProfile(slug, name);
      await _load();
      if (mounted) setState(() => _note = 'Renamed.');
    });
  }

  /// Publish or withdraw the copy the sign-in screen can read.
  ///
  /// The confirmation is on the way IN only. Turning it on writes an
  /// unencrypted copy of the picture beside the database, which is a real cost
  /// against the exact threat PIP encrypts for and is worth one sentence
  /// before it happens. Turning it off deletes that file, which needs no
  /// ceremony at all - nobody has ever regretted removing a copy of their own
  /// face from a disk.
  Future<void> _toggleSignInPicture(bool wanted) async {
    if (!wanted) {
      await _run(() async {
        await widget.api.unpublishSignInPicture();
        await _load();
        if (mounted) setState(() => _note = 'Removed from the sign-in screen.');
      });
      return;
    }

    final agreed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Show your picture before sign-in?'),
        content: const Text(
          'The sign-in screen appears before your password does, so it cannot '
          'read anything that needed one. Turning this on saves a second copy '
          'of your picture next to your data, NOT encrypted - anyone who can '
          'read this disk can see it.\n\n'
          'Nothing else leaves the encrypted database. Turning it off again '
          'deletes that copy.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Show it'),
          ),
        ],
      ),
    );
    if (agreed != true) return;

    await _run(() async {
      await widget.api.publishSignInPicture();
      await _load();
      if (mounted) setState(() => _note = 'Now shown on the sign-in screen.');
    });
  }

  Future<void> _changePassword() async {
    final result = await showDialog<List<String>>(
      context: context,
      builder: (context) => const _ChangePasswordDialog(),
    );
    if (result == null) return;

    await _run(() async {
      await widget.api.changePassword(result[0], result[1]);
      if (mounted) {
        setState(() => _note = 'Password changed. Your data has been re-encrypted.');
      }
    });
  }

  /// Erase this profile and leave.
  ///
  /// The socket closes before the request and the screen does not change until
  /// it has succeeded. A client that navigated away optimistically and then
  /// hit a 500 would have sent somebody to a sign-in screen for a profile that
  /// still exists, with no way to know whether their data was gone.
  Future<void> _delete() async {
    final slug = _slug;
    if (slug == null) return;

    final password = await showDialog<String>(
      context: context,
      builder: (context) => _DeleteProfileDialog(name: _name ?? slug),
    );
    if (password == null) return;

    setState(() {
      _busy = true;
      _error = null;
      _note = null;
    });

    widget.onCloseChat();
    try {
      await widget.api.deleteProfile(slug, password);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = error is ApiException ? error.detail : '$error';
      });
      return;
    }
    if (!mounted) return;
    widget.onSignedOut();
  }

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;

    return SectionCard(
      padding: const EdgeInsets.all(AppSpacing.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.shield_outlined, size: 18, color: pip.textMuted),
              const SizedBox(width: AppSpacing.sm),
              Text(
                'This profile',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: pip.text),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            'A profile is a separate, separately encrypted PIP. Its password is '
            'the only key to it, and there is no way to recover one that is '
            'forgotten.',
            style: TextStyle(fontSize: 12.5, height: 1.5, color: pip.textMuted),
          ),
          const SizedBox(height: AppSpacing.lg),

          _AccountRow(
            label: 'Name',
            value: _name ?? '...',
            // The label on the database, not the name PIP calls you - those
            // are two facts that are usually the same word, and only one of
            // them is a memory.
            description: 'Shown on the sign-in screen. Your data is not moved.',
            action: GhostButton(label: 'Rename', onTap: _busy ? null : _rename),
          ),
          Divider(height: AppSpacing.xl, color: pip.border),

          _AccountRow(
            label: 'Picture on the sign-in screen',
            value: _picturePublished ? 'Shown' : 'Hidden',
            description: _picturePublished
                ? 'A copy of your picture is saved unencrypted so the sign-in '
                    'screen can draw it. Turn this off to delete that copy.'
                : 'Off. Your picture stays inside the encrypted database, where '
                    'the sign-in screen cannot read it.',
            action: Switch(
              value: _picturePublished,
              onChanged: _busy ? null : _toggleSignInPicture,
            ),
          ),
          Divider(height: AppSpacing.xl, color: pip.border),

          _AccountRow(
            label: 'Password',
            value: 'Set',
            description: 'Changing it re-encrypts your database and your document '
                'index. Takes a few seconds.',
            action: GhostButton(label: 'Change', onTap: _busy ? null : _changePassword),
          ),
          Divider(height: AppSpacing.xl, color: pip.border),

          _AccountRow(
            label: 'Delete this profile',
            value: 'Permanent',
            description: 'Erases this profile\'s database, documents and search '
                'index from this machine. Other profiles are untouched. '
                'This cannot be undone.',
            action: GhostButton(
              label: 'Delete',
              color: pip.danger,
              onTap: _busy ? null : _delete,
            ),
          ),

          if (_busy) ...[
            const SizedBox(height: AppSpacing.md),
            Row(
              children: [
                const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2)),
                const SizedBox(width: AppSpacing.sm),
                Text('Working...', style: TextStyle(fontSize: 12, color: pip.textMuted)),
              ],
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: AppSpacing.md),
            Text(_error!, style: TextStyle(fontSize: 12, color: pip.danger)),
          ],
          if (_note != null) ...[
            const SizedBox(height: AppSpacing.md),
            Text(_note!, style: TextStyle(fontSize: 12, color: pip.accent)),
          ],
        ],
      ),
    );
  }
}

/// One setting: what it is, what it currently says, and the control.
class _AccountRow extends StatelessWidget {
  final String label;
  final String value;
  final String description;
  final Widget action;

  const _AccountRow({
    required this.label,
    required this.value,
    required this.description,
    required this.action,
  });

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(
                    label,
                    style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: pip.text),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Text(value, style: TextStyle(fontSize: 12.5, color: pip.textMuted)),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                description,
                style: TextStyle(fontSize: 12, height: 1.45, color: pip.textFaint),
              ),
            ],
          ),
        ),
        const SizedBox(width: AppSpacing.lg),
        action,
      ],
    );
  }
}

class _RenameProfileDialog extends StatefulWidget {
  final String current;
  const _RenameProfileDialog({required this.current});

  @override
  State<_RenameProfileDialog> createState() => _RenameProfileDialogState();
}

class _RenameProfileDialogState extends State<_RenameProfileDialog> {
  late final TextEditingController _name = TextEditingController(text: widget.current);

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  void _submit() {
    final name = _name.text.trim();
    if (name.isEmpty) return;
    Navigator.pop(context, name);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Rename this profile'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'This is the name on the sign-in screen. Nothing is moved and '
            'nothing PIP remembers about you changes.',
            style: TextStyle(fontSize: 13, height: 1.45),
          ),
          const SizedBox(height: AppSpacing.lg),
          TextField(
            controller: _name,
            autofocus: true,
            onSubmitted: (_) => _submit(),
            decoration: const InputDecoration(labelText: 'Name'),
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: _submit, child: const Text('Rename')),
      ],
    );
  }
}

/// Current password, new password, and the new one again.
///
/// The confirmation field is checked here rather than only on the server,
/// because a mismatch is the one error this side can be certain of - and the
/// round trip would cost a full re-encryption to report something that could
/// have been said immediately.
class _ChangePasswordDialog extends StatefulWidget {
  const _ChangePasswordDialog();

  @override
  State<_ChangePasswordDialog> createState() => _ChangePasswordDialogState();
}

class _ChangePasswordDialogState extends State<_ChangePasswordDialog> {
  final _current = TextEditingController();
  final _next = TextEditingController();
  final _confirm = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _current.dispose();
    _next.dispose();
    _confirm.dispose();
    super.dispose();
  }

  void _submit() {
    if (_current.text.isEmpty) {
      setState(() => _error = 'Enter your current password.');
      return;
    }
    if (_next.text != _confirm.text) {
      setState(() => _error = 'Those two passwords are different.');
      return;
    }
    Navigator.pop(context, [_current.text, _next.text]);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Change your password'),
      content: SizedBox(
        width: 380,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Your database is re-encrypted with the new password. The old one '
              'stops working, and the new one cannot be recovered if you forget '
              'it - write it down somewhere that is not this machine.',
              style: TextStyle(fontSize: 13, height: 1.45),
            ),
            const SizedBox(height: AppSpacing.lg),
            TextField(
              controller: _current,
              obscureText: true,
              autofocus: true,
              decoration: const InputDecoration(labelText: 'Current password'),
            ),
            const SizedBox(height: AppSpacing.md),
            TextField(
              controller: _next,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'New password'),
            ),
            const SizedBox(height: AppSpacing.md),
            TextField(
              controller: _confirm,
              obscureText: true,
              onSubmitted: (_) => _submit(),
              decoration: const InputDecoration(labelText: 'New password again'),
            ),
            if (_error != null) ...[
              const SizedBox(height: AppSpacing.md),
              Text(_error!, style: TextStyle(fontSize: 12, color: context.pip.danger)),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: _submit, child: const Text('Change password')),
      ],
    );
  }
}

/// The one dialog in PIP that asks somebody to type something they cannot get
/// back.
///
/// Two obstacles rather than one, and they test different things. The password
/// proves the person asking is the person who owns the data. The typed name
/// proves they read which profile they are about to erase - which the password
/// alone does not, and which matters most on a machine where several people
/// each have one.
class _DeleteProfileDialog extends StatefulWidget {
  final String name;
  const _DeleteProfileDialog({required this.name});

  @override
  State<_DeleteProfileDialog> createState() => _DeleteProfileDialogState();
}

class _DeleteProfileDialogState extends State<_DeleteProfileDialog> {
  final _password = TextEditingController();
  final _typedName = TextEditingController();
  String? _error;

  bool get _nameMatches =>
      _typedName.text.trim().toLowerCase() == widget.name.trim().toLowerCase();

  @override
  void initState() {
    super.initState();
    _typedName.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _password.dispose();
    _typedName.dispose();
    super.dispose();
  }

  void _submit() {
    if (!_nameMatches) return;
    if (_password.text.isEmpty) {
      setState(() => _error = 'Enter your password.');
      return;
    }
    Navigator.pop(context, _password.text);
  }

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return AlertDialog(
      title: Text('Delete ${widget.name}?'),
      content: SizedBox(
        width: 400,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'This erases this profile from this machine: every conversation, '
              'everything PIP has learned about you, your decisions, your '
              'documents and the search index over them.',
              style: TextStyle(fontSize: 13, height: 1.45, color: pip.text),
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              'There is no undo and no backup unless you made one yourself. '
              'Other profiles on this machine are not affected.',
              style: TextStyle(fontSize: 13, height: 1.45, color: pip.danger),
            ),
            const SizedBox(height: AppSpacing.lg),
            TextField(
              controller: _typedName,
              autofocus: true,
              decoration: InputDecoration(
                labelText: 'Type ${widget.name} to confirm',
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            TextField(
              controller: _password,
              obscureText: true,
              onSubmitted: (_) => _submit(),
              decoration: const InputDecoration(labelText: 'Your password'),
            ),
            if (_error != null) ...[
              const SizedBox(height: AppSpacing.md),
              Text(_error!, style: TextStyle(fontSize: 12, color: pip.danger)),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(
          // Dead until the name has been typed. A destructive button that is
          // clickable before its confirmation is satisfied is a confirmation
          // in name only.
          onPressed: _nameMatches ? _submit : null,
          style: FilledButton.styleFrom(backgroundColor: pip.danger),
          child: const Text('Delete permanently'),
        ),
      ],
    );
  }
}
