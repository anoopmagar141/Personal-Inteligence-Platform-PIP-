// Projects: list, create, choose which one PIP is working in, and - new here -
// move one out of the way when it is finished or shelved.
//
// PATCH /projects/{id}/status had no caller, which had a visible consequence:
// list_projects() returns every project regardless of status and orders the
// active ones first, so the backend was already prepared to show a finished
// project differently, and the screen rendered all of them the same way with
// no means of ever finishing one. A project list that only grows stops being
// a statement about what you are working on.
//
// Two verbs, deliberately kept apart because they are not the same act:
//
//   * "Work in this" (POST /activate) is about context - it marks the project
//     active AND tells the chat which project this session belongs to.
//   * Archive / Complete (PATCH /status) is about the project's own lifecycle
//     and says nothing about the current session.
//
// The one place they meet is handled below: shelving the project the chat is
// currently pointed at has to clear that pointer too, or PIP would keep
// attributing new work to a project you just put away.

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';

/// The three values active_projects.status is constrained to, with the verb
/// used to move a project into each.
const _statusVerb = <String, String>{
  'archived': 'Archive',
  'completed': 'Complete',
};

class ProjectsView extends StatefulWidget {
  final ApiClient api;
  final String? activeProjectId;

  /// Null clears the chat's project context - see the note above about
  /// shelving whatever the chat is currently pointed at.
  final ValueChanged<String?> onActivate;

  /// Open a new conversation in this project.
  ///
  /// Starting a chat about a project used to mean three steps in two places:
  /// select the project here, walk to Chat, press New chat. The project screen
  /// is where you are already thinking about the project, so the button is
  /// here and the shell does the rest.
  final ValueChanged<String> onStartChat;

  const ProjectsView({
    super.key,
    required this.api,
    required this.activeProjectId,
    required this.onActivate,
    required this.onStartChat,
  });

  @override
  State<ProjectsView> createState() => _ProjectsViewState();
}

class _ProjectsViewState extends State<ProjectsView> {
  final _nameController = TextEditingController();
  final _descriptionController = TextEditingController();

  /// Filters what is already loaded. Not a backend call - there is no project
  /// search endpoint, and inventing one to filter a list this size would be
  /// the wrong trade. Purely narrowing what is on screen, so it cannot
  /// disagree with what the server said.
  final _searchController = TextEditingController();
  String _query = '';
  List<dynamic>? _projects;
  String? _error;

  /// Belongs to the create form, not to the page: build() returns early on
  /// _error, so a rejected name would take the project list with it.
  String? _createError;

  final Map<String, String> _rowErrors = {};
  final Set<String> _busy = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final projects = await widget.api.getProjects();
      if (mounted) {
        setState(() {
          _projects = projects;
          _error = null;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _create() async {
    if (_nameController.text.trim().isEmpty) return;
    try {
      await widget.api.createProject({
        'name': _nameController.text.trim(),
        'description': _descriptionController.text.trim(),
      });
      // Cleared only on success. Wiping the fields after a failed create
      // throws away what the user typed and leaves them nothing to retry
      // with, on top of not telling them it failed.
      _nameController.clear();
      _descriptionController.clear();
      setState(() => _createError = null);
      await _load();
    } catch (error) {
      if (mounted) setState(() => _createError = error.toString());
    }
  }

  Future<void> _act(String projectId, Future<void> Function() action) async {
    setState(() {
      _busy.add(projectId);
      _rowErrors.remove(projectId);
    });
    try {
      await action();
      await _load();
    } catch (error) {
      if (mounted) setState(() => _rowErrors[projectId] = error.toString());
    } finally {
      if (mounted) setState(() => _busy.remove(projectId));
    }
  }

  Future<void> _activate(String projectId) async {
    await _act(projectId, () async {
      await widget.api.activateProject(projectId);
      widget.onActivate(projectId);
    });
  }

  Future<void> _setStatus(String projectId, String status) async {
    await _act(projectId, () async {
      await widget.api.updateProjectStatus(projectId, status);
      // Archiving or completing the project the chat is pointed at has to let
      // go of it as well. Leaving the pointer behind would keep filing new
      // conversation against a project the user has just put away, which is
      // both wrong and invisible from the chat screen.
      if (projectId == widget.activeProjectId) widget.onActivate(null);
    });
  }

  /// Retract a project. Soft, like every other memory row - the backend keeps
  /// it at status 'deleted' so a decision or conversation filed against it
  /// still has something to point at.
  Future<void> _delete(Map<String, dynamic> project) async {
    final name = '${project['name']}';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete this project?', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
        content: Text(
          'PIP will stop offering "$name" and it will leave this list. Anything '
          'already filed against it - decisions, documents, conversations - is '
          'kept and still points at it, so nothing you have recorded is lost.',
          style: TextStyle(fontSize: 13, color: context.pip.textMuted, height: 1.5),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: context.pip.danger),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await _setStatus(project['project_id'] as String, 'deleted');
  }

  /// Point the chat at this project, then open a fresh conversation in it.
  ///
  /// Activation first and awaited: the new conversation is filed against
  /// whichever project the backend currently has active, so starting the chat
  /// before that lands would file it against the previous one.
  Future<void> _startChat(String projectId) async {
    await _activate(projectId);
    if (mounted) widget.onStartChat(projectId);
  }

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  /// Name and description are matched together because people search for
  /// either without thinking about which field they are in.
  List<Map<String, dynamic>> _visible() {
    final all = _projects!.cast<Map<String, dynamic>>();
    if (_query.trim().isEmpty) return all;
    final needle = _query.toLowerCase();
    return all
        .where((p) =>
            '${p['name']}'.toLowerCase().contains(needle) ||
            '${p['description'] ?? ''}'.toLowerCase().contains(needle))
        .toList();
  }

  Future<void> _openCreateDialog() async {
    // The controllers stay owned by this State rather than the dialog, so they
    // outlive the route being popped - the use-after-dispose that a
    // dialog-owned controller causes while the dialog animates out.
    setState(() => _createError = null);
    final created = await showDialog<bool>(
      context: context,
      builder: (context) => _NewProjectDialog(
        nameController: _nameController,
        descriptionController: _descriptionController,
      ),
    );
    if (created == true) await _create();
  }

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return LayoutBuilder(
      builder: (context, constraints) {
        // Two columns once there is room for two readable cards, one below
        // that.
        //
        // 700 LOGICAL pixels, which is the units LayoutBuilder reports in. The
        // first attempt used 900 and stayed stubbornly single-column on a
        // 1700px window, because a 150% display makes that 1133 logical - and
        // after the sidebar and padding, 853. Picking a breakpoint off the
        // physical window size is measuring in the wrong units.
        final available = constraints.maxWidth - (AppSpacing.xl * 2);
        final columns = available >= 700 ? 2 : 1;

        return SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _header(columns == 1),
              const SizedBox(height: AppSpacing.lg),
              if (_error != null) ...[
                Text(_error!, style: TextStyle(color: pip.danger)),
                const SizedBox(height: AppSpacing.md),
              ],
              if (_createError != null) ...[
                Text(_createError!, style: TextStyle(fontSize: 12.5, color: pip.danger)),
                const SizedBox(height: AppSpacing.md),
              ],
              if (_projects != null) _grid(columns),
            ],
          ),
        );
      },
    );
  }

  /// Title on the left, the two things you actually came to do on the right.
  ///
  /// The create form used to sit permanently at the bottom of the page, below
  /// every project, which put the least-used control furthest from the top and
  /// pushed the list itself down. It is a dialog now, behind a button that is
  /// always in the same place.
  Widget _header(bool stacked) {
    final pip = context.pip;
    final title = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        TagLabel('CONTEXT', color: pip.accent, size: 11),
        const SizedBox(height: AppSpacing.xs),
        Text(
          'Projects',
          style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: pip.text),
        ),
        const SizedBox(height: 4),
        Text(
          "What you're working on right now, and what you've finished.",
          style: TextStyle(fontSize: 13.5, color: pip.textMuted, height: 1.5),
        ),
      ],
    );

    final actions = Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          width: stacked ? 200 : 240,
          child: TextField(
            controller: _searchController,
            style: const TextStyle(fontSize: 13),
            decoration: const InputDecoration(
              hintText: 'Search projects...',
              prefixIcon: Icon(Icons.search, size: 18),
              isDense: true,
            ),
            onChanged: (value) => setState(() => _query = value),
          ),
        ),
        const SizedBox(width: AppSpacing.sm),
        FilledButton(onPressed: _openCreateDialog, child: const Text('New project')),
      ],
    );

    if (stacked) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [title, const SizedBox(height: AppSpacing.md), actions],
      );
    }
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [Expanded(child: title), actions],
    );
  }

  Widget _grid(int columns) {
    if (_projects!.isEmpty) {
      return EmptyState(
        icon: Icons.folder_outlined,
        title: 'No projects yet',
        description: "Create one to give PIP context on what you're working on.",
        actionLabel: 'New project',
        onAction: _openCreateDialog,
      );
    }

    final visible = _visible();
    if (visible.isEmpty) {
      // Distinct from having no projects at all - saying "no projects yet"
      // here would be a claim about the database rather than about the filter.
      return EmptyState(
        icon: Icons.search_off,
        title: 'Nothing matches "$_query"',
        description: 'Clear the search to see all ${_projects!.length} projects.',
      );
    }

    // Rows of IntrinsicHeight rather than a Wrap. Two reasons, and the first
    // is not cosmetic: a card ends with a Spacer so its footer sits at the
    // bottom, and Spacer needs a bounded height - inside a Wrap the height is
    // unbounded and it throws. IntrinsicHeight bounds it. The second is that
    // this also makes the cards in a row equal height, which is what stops a
    // grid of uneven cards looking like a mistake.
    final rows = <List<Map<String, dynamic>>>[];
    for (var i = 0; i < visible.length; i += columns) {
      rows.add(visible.sublist(i, (i + columns).clamp(0, visible.length)));
    }

    return Column(
      children: [
        for (final row in rows)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.md),
            child: IntrinsicHeight(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  for (var i = 0; i < columns; i++) ...[
                    if (i > 0) const SizedBox(width: AppSpacing.md),
                    Expanded(
                      // An empty cell keeps the last row's single card the
                      // same width as every other card, rather than letting it
                      // stretch across the whole grid.
                      child: i < row.length ? _projectCard(row[i]) : const SizedBox.shrink(),
                    ),
                  ],
                ],
              ),
            ),
          ),
      ],
    );
  }

  Widget _projectCard(Map<String, dynamic> project) {
    final pip = context.pip;
    final projectId = project['project_id'] as String;
    final status = '${project['status']}';
    final isActive = status == 'active';
    final isCurrent = projectId == widget.activeProjectId;
    final busy = _busy.contains(projectId);
    final rowError = _rowErrors[projectId];
    final description = '${project['description'] ?? ''}';

    return SectionCard(
      child: ConstrainedBox(
        // A floor, not a ceiling: cards line up in the grid without cropping a
        // long description to achieve it.
        constraints: const BoxConstraints(minHeight: 148),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Flexible(
                  child: Text(
                    '${project['name']}',
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      // A shelved project stays readable, just visibly no
                      // longer in play.
                      color: isActive ? pip.text : pip.textMuted,
                    ),
                  ),
                ),
                if (isCurrent) ...[
                  const SizedBox(width: AppSpacing.sm),
                  _Pill(text: 'in this chat', color: pip.accent),
                ],
                if (!isActive) ...[
                  const SizedBox(width: AppSpacing.sm),
                  _Pill(text: status, color: pip.textMuted),
                ],
              ],
            ),
            if (description.isNotEmpty) ...[
              const SizedBox(height: 6),
              // Truncated to keep the grid scannable, but the full text is on
              // the tooltip - a card is the only place a description appears,
              // so clipping it with no way to read the rest would lose it.
              Tooltip(
                message: description,
                child: Text(
                  description,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: 13, color: pip.textMuted, height: 1.45),
                ),
              ),
            ],
            const Spacer(),
            const SizedBox(height: AppSpacing.sm),
            Tooltip(
              message: 'last active ${project['last_active']}',
              child: Text(
                // The date only. The backend sends a full UTC stamp and this
                // takes the first ten characters of it - a truncation of a
                // known format, not a re-interpretation, so no timezone gets
                // silently shifted. The whole stamp is on the tooltip.
                'last active ${'${project['last_active']}'.split('T').first}',
                style: TextStyle(fontSize: 11, color: pip.textFaint),
              ),
            ),
            if (rowError != null) ...[
              const SizedBox(height: 6),
              Text(rowError, style: TextStyle(fontSize: 11.5, color: pip.danger)),
            ],
            const SizedBox(height: AppSpacing.sm),
            if (busy)
              const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
            else
              Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.sm,
                children: [
                  if (isActive)
                    GhostButton(label: 'New chat', onTap: () => _startChat(projectId)),
                  GhostButton(
                    label: isActive ? 'Work in this' : 'Reopen',
                    // Reopening goes through /activate too: it is the one call
                    // that both restores 'active' and points the chat here,
                    // which is what "reopen" means from the user's side.
                    onTap: isCurrent && isActive ? null : () => _activate(projectId),
                  ),
                  if (isActive)
                    for (final entry in _statusVerb.entries)
                      GhostButton(
                        label: entry.value,
                        color: pip.textMuted,
                        onTap: () => _setStatus(projectId, entry.key),
                      ),
                  GhostButton(
                    label: 'Delete',
                    color: pip.danger,
                    onTap: () => _delete(project),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

/// A small status chip. Reads at a glance in a grid, where a run of prose
/// ("status: archived · last active ...") did not.
class _Pill extends StatelessWidget {
  final String text;
  final Color color;
  const _Pill({required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: AppRadius.sm,
      ),
      child: Text(
        text,
        style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w600, color: color),
      ),
    );
  }
}

/// The create form, moved off the page and behind the button.
///
/// The controllers belong to ProjectsView's State, not to this dialog: a
/// dialog-owned controller is disposed while the route is still animating out
/// and its TextField is still rebuilding, which throws.
class _NewProjectDialog extends StatefulWidget {
  final TextEditingController nameController;
  final TextEditingController descriptionController;
  const _NewProjectDialog({required this.nameController, required this.descriptionController});

  @override
  State<_NewProjectDialog> createState() => _NewProjectDialogState();
}

class _NewProjectDialogState extends State<_NewProjectDialog> {
  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    final canCreate = widget.nameController.text.trim().isNotEmpty;
    return AlertDialog(
      title: const Text('New project', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
      content: SizedBox(
        width: 420,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Telling PIP what you are working on is what lets it file decisions '
              'and documents against the right thing.',
              style: TextStyle(fontSize: 12.5, color: pip.textMuted, height: 1.5),
            ),
            const SizedBox(height: AppSpacing.md),
            TextField(
              controller: widget.nameController,
              autofocus: true,
              decoration: const InputDecoration(labelText: 'Project name'),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: AppSpacing.sm),
            TextField(
              controller: widget.descriptionController,
              decoration: const InputDecoration(labelText: 'Description'),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Cancel')),
        FilledButton(
          onPressed: canCreate ? () => Navigator.of(context).pop(true) : null,
          child: const Text('Create'),
        ),
      ],
    );
  }
}
