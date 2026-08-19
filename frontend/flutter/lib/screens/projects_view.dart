// Matches frontend/web/app.js's projects flow: list + create form +
// "Set active" per project, POST /projects/{id}/activate.

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';

class ProjectsView extends StatefulWidget {
  final ApiClient api;
  final String? activeProjectId;
  final ValueChanged<String> onActivate;
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

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final projects = await widget.api.getProjects();
      if (mounted) setState(() => _projects = projects);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _create() async {
    if (_nameController.text.trim().isEmpty) return;
    await widget.api.createProject({
      'name': _nameController.text.trim(),
      'description': _descriptionController.text.trim(),
    });
    _nameController.clear();
    _descriptionController.clear();
    await _load();
  }

  Future<void> _activate(String projectId) async {
    await widget.api.activateProject(projectId);
    widget.onActivate(projectId);
    await _load();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSpacing.xl),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 720),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const PageHeader(eyebrow: 'Context', title: 'Projects', description: 'What you\'re working on right now.'),
            if (_error != null) Text(_error!, style: const TextStyle(fontFamily: AppTheme.mono, color: AppColors.danger)),
            if (_projects != null)
              if (_projects!.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: AppSpacing.sm),
                  child: Text('No projects yet.', style: TextStyle(fontFamily: AppTheme.mono, fontSize: 12, color: AppColors.textFaint)),
                )
              else
                Column(
                  children: [
                    for (final project in _projects!)
                      Padding(
                        padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                        child: SectionCard(
                          child: Row(
                            children: [
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      children: [
                                        Text('${project['name']}', style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w600, color: AppColors.text)),
                                        if (project['project_id'] == widget.activeProjectId) ...[
                                          const SizedBox(width: AppSpacing.sm),
                                          const TagLabel('active', color: AppColors.accent),
                                        ],
                                      ],
                                    ),
                                    if ('${project['description'] ?? ''}'.isNotEmpty) ...[
                                      const SizedBox(height: 4),
                                      Text('${project['description']}', style: const TextStyle(fontSize: 13, color: AppColors.textMuted)),
                                    ],
                                    const SizedBox(height: 6),
                                    Text('status: ${project['status']}', style: const TextStyle(fontFamily: AppTheme.mono, fontSize: 11, color: AppColors.textFaint)),
                                  ],
                                ),
                              ),
                              GhostButton(label: 'Set active', onTap: () => _activate(project['project_id'] as String)),
                            ],
                          ),
                        ),
                      ),
                  ],
                ),
            const SizedBox(height: AppSpacing.lg),
            SectionCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const TagLabel('New project', color: AppColors.text, size: 12),
                  const SizedBox(height: AppSpacing.md),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: TextField(controller: _nameController, decoration: const InputDecoration(labelText: 'Project name'))),
                      const SizedBox(width: AppSpacing.sm),
                      Expanded(child: TextField(controller: _descriptionController, decoration: const InputDecoration(labelText: 'Description'))),
                      const SizedBox(width: AppSpacing.sm),
                      FilledButton(onPressed: _create, child: const Text('CREATE')),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
