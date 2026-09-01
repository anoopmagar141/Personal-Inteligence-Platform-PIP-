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

  const ProjectsView({
    super.key,
    required this.api,
    required this.activeProjectId,
    required this.onActivate,
  });

  @override
  State<ProjectsView> createState() => _ProjectsViewState();
}

class _ProjectsViewState extends State<ProjectsView> {
  final _nameController = TextEditingController();
  final _descriptionController = TextEditingController();
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

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
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
              eyebrow: 'Context',
              title: 'Projects',
              description: "What you're working on right now, and what you've finished.",
            ),
            if (_error != null) Text(_error!, style: TextStyle(color: pip.danger)),
            if (_projects != null)
              if (_projects!.isEmpty)
                const EmptyState(
                  icon: Icons.folder_outlined,
                  title: 'No projects yet',
                  description: "Create one below to give PIP context on what you're working on.",
                )
              else
                Column(
                  children: [
                    for (final raw in _projects!) _projectCard(raw as Map<String, dynamic>),
                  ],
                ),
            const SizedBox(height: AppSpacing.lg),
            SectionCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TagLabel('New project', color: pip.text, size: 12),
                  const SizedBox(height: AppSpacing.md),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: TextField(controller: _nameController, decoration: const InputDecoration(labelText: 'Project name'))),
                      const SizedBox(width: AppSpacing.sm),
                      Expanded(child: TextField(controller: _descriptionController, decoration: const InputDecoration(labelText: 'Description'))),
                      const SizedBox(width: AppSpacing.sm),
                      FilledButton(onPressed: _create, child: const Text('Create')),
                    ],
                  ),
                  if (_createError != null) ...[
                    const SizedBox(height: AppSpacing.sm),
                    Text(_createError!, style: TextStyle(fontSize: 11.5, color: pip.danger)),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
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

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: SectionCard(
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
                              '${project['name']}',
                              style: TextStyle(
                                fontSize: 14.5,
                                fontWeight: FontWeight.w600,
                                // A shelved project is still readable, just
                                // visibly no longer in play.
                                color: isActive ? pip.text : pip.textMuted,
                              ),
                            ),
                          ),
                          if (isCurrent) ...[
                            const SizedBox(width: AppSpacing.sm),
                            TagLabel('in this chat', color: pip.accent),
                          ],
                        ],
                      ),
                      if (description.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Text(description, style: TextStyle(fontSize: 13, color: pip.textMuted)),
                      ],
                      const SizedBox(height: 6),
                      Text(
                        'status: $status · last active ${project['last_active']}',
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
                  const SizedBox(width: AppSpacing.sm),
                  GhostButton(
                    label: isActive ? 'Work in this' : 'Reopen',
                    // Reopening goes through /activate too: it is the one call
                    // that both restores 'active' and points the chat here,
                    // which is what "reopen" means from the user's side.
                    onTap: isCurrent && isActive ? null : () => _activate(projectId),
                  ),
                  if (isActive)
                    for (final entry in _statusVerb.entries) ...[
                      const SizedBox(width: AppSpacing.sm),
                      GhostButton(
                        label: entry.value,
                        color: pip.textMuted,
                        onTap: () => _setStatus(projectId, entry.key),
                      ),
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
