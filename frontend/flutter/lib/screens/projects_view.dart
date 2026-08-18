// Matches frontend/web/app.js's projects flow: list + create form +
// "Set active" per project, POST /projects/{id}/activate.

import 'package:flutter/material.dart';

import '../api_client.dart';

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
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Projects', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 12),
          if (_error != null) Text(_error!, style: const TextStyle(color: Colors.red)),
          if (_projects != null)
            if (_projects!.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text('No projects yet.', style: TextStyle(color: Colors.grey)),
              )
            else
              for (final project in _projects!)
                Card(
                  margin: const EdgeInsets.symmetric(vertical: 4),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Text('${project['name']}'),
                                  if (project['project_id'] == widget.activeProjectId) ...[
                                    const SizedBox(width: 8),
                                    const Chip(label: Text('active'), visualDensity: VisualDensity.compact),
                                  ],
                                ],
                              ),
                              if ('${project['description'] ?? ''}'.isNotEmpty)
                                Text('${project['description']}', style: const TextStyle(color: Colors.grey)),
                              Text('status: ${project['status']}', style: const TextStyle(color: Colors.grey, fontSize: 12)),
                            ],
                          ),
                        ),
                        TextButton(
                          onPressed: () => _activate(project['project_id'] as String),
                          child: const Text('Set active'),
                        ),
                      ],
                    ),
                  ),
                ),
          const SizedBox(height: 24),
          Text('New project', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _nameController,
                  decoration: const InputDecoration(labelText: 'Project name'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: _descriptionController,
                  decoration: const InputDecoration(labelText: 'Description'),
                ),
              ),
              const SizedBox(width: 8),
              FilledButton(onPressed: _create, child: const Text('Create')),
            ],
          ),
        ],
      ),
    );
  }
}
