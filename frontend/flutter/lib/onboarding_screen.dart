// Matches frontend/web/app.js's submitOnboarding() payload shape exactly -
// same fields, same optional-vs-required split, same POST /onboarding/complete
// call.

import 'package:flutter/material.dart';

import 'api_client.dart';

List<String>? _parseCsv(String value, int limit) {
  if (value.trim().isEmpty) return null;
  final items = value.split(',').map((s) => s.trim()).where((s) => s.isNotEmpty).toList();
  return items.take(limit).toList();
}

class OnboardingScreen extends StatefulWidget {
  final ApiClient api;
  final VoidCallback onComplete;
  const OnboardingScreen({super.key, required this.api, required this.onComplete});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _language = TextEditingController(text: 'English');
  final _timezone = TextEditingController();
  final _projectName = TextEditingController();
  final _projectDescription = TextEditingController();
  final _skills = TextEditingController();
  final _preferredTools = TextEditingController();
  String _interactionStyle = '';
  bool _submitting = false;
  String? _error;

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _submitting = true;
      _error = null;
    });

    final payload = <String, dynamic>{
      'name': _name.text,
      'language_preference': _language.text,
      if (_timezone.text.trim().isNotEmpty) 'timezone': _timezone.text.trim(),
      if (_parseCsv(_skills.text, 3) != null) 'skills': _parseCsv(_skills.text, 3),
      if (_interactionStyle.isNotEmpty) 'interaction_style': _interactionStyle,
      if (_parseCsv(_preferredTools.text, 5) != null) 'preferred_tools': _parseCsv(_preferredTools.text, 5),
    };
    if (_projectName.text.trim().isNotEmpty) {
      payload['current_project'] = {
        'name': _projectName.text.trim(),
        'description': _projectDescription.text.trim(),
      };
    }

    try {
      await widget.api.completeOnboarding(payload);
      widget.onComplete();
    } catch (error) {
      setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _language.dispose();
    _timezone.dispose();
    _projectName.dispose();
    _projectDescription.dispose();
    _skills.dispose();
    _preferredTools.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('Welcome to PIP', style: Theme.of(context).textTheme.headlineSmall),
                  const SizedBox(height: 4),
                  const Text(
                    'A few questions before we start. Name, language, and timezone are locked once set.',
                    style: TextStyle(color: Colors.grey),
                  ),
                  const SizedBox(height: 20),
                  TextFormField(
                    controller: _name,
                    decoration: const InputDecoration(labelText: 'Name *'),
                    validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _language,
                    decoration: const InputDecoration(labelText: 'Primary language *', hintText: 'e.g. English'),
                    validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _timezone,
                    decoration: const InputDecoration(labelText: 'Timezone', hintText: 'defaults to system timezone'),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _projectName,
                    decoration: const InputDecoration(labelText: 'Current project name'),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _projectDescription,
                    decoration: const InputDecoration(labelText: 'Current project description'),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _skills,
                    decoration: const InputDecoration(
                      labelText: 'Skills (comma-separated, up to 3)',
                      hintText: 'Python, Docker, SQL',
                    ),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: _interactionStyle,
                    decoration: const InputDecoration(labelText: 'How do you prefer answers?'),
                    items: const [
                      DropdownMenuItem(value: '', child: Text("I'll specify each time (adaptive)")),
                      DropdownMenuItem(value: 'brief_summary_first', child: Text('Brief summary first, detail on request')),
                      DropdownMenuItem(value: 'full_detail', child: Text('Full detailed answer always')),
                    ],
                    onChanged: (v) => setState(() => _interactionStyle = v ?? ''),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _preferredTools,
                    decoration: const InputDecoration(
                      labelText: 'Tools you use most (comma-separated, up to 5)',
                      hintText: 'VS Code, Git, Ollama',
                    ),
                  ),
                  const SizedBox(height: 20),
                  FilledButton(
                    onPressed: _submitting ? null : _submit,
                    child: _submitting
                        ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Text('Complete setup'),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 8),
                    Text(_error!, style: const TextStyle(color: Colors.red)),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
