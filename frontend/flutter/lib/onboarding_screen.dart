// Sends only the identity and preference fields the first-run form asks for.
// The timezone comes from the local Windows account rather than asking the
// person to identify a setting their computer already knows.

import 'package:flutter/material.dart';

import 'api_client.dart';
import 'logo.dart';
import 'theme.dart';

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
  final _preferredName = TextEditingController();
  final _language = TextEditingController(text: 'English');
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
      if (_preferredName.text.trim().isNotEmpty) 'preferred_name': _preferredName.text.trim(),
      'language_preference': _language.text,
      'timezone': DateTime.now().timeZoneName,
      if (_parseCsv(_skills.text, 3) != null) 'skills': _parseCsv(_skills.text, 3),
      if (_interactionStyle.isNotEmpty) 'interaction_style': _interactionStyle,
      if (_parseCsv(_preferredTools.text, 5) != null) 'preferred_tools': _parseCsv(_preferredTools.text, 5),
    };
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
    _skills.dispose();
    _preferredTools.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 440),
            child: Container(
              padding: const EdgeInsets.all(AppSpacing.xl),
              decoration: BoxDecoration(
                color: pip.surface,
                borderRadius: AppRadius.lg,
                border: Border.all(color: pip.border),
              ),
              child: Form(
                key: _formKey,
                child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const PipLogo(size: 48),
                  const SizedBox(height: AppSpacing.md),
                  TagLabel('Setup', color: pip.accent),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    'Welcome to PIP',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: pip.text),
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    'Tell PIP a little about you. You can change these details later from your profile.',
                    style: TextStyle(fontSize: 12, color: pip.textMuted, height: 1.5),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  TextFormField(
                    controller: _name,
                    decoration: const InputDecoration(
                      labelText: 'Full name *',
                      hintText: 'your name as you would write it',
                    ),
                    validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _preferredName,
                    decoration: const InputDecoration(
                      labelText: 'What should PIP call you?',
                      hintText: 'leave blank to be called by the name above',
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _language,
                    decoration: const InputDecoration(labelText: 'Primary language *', hintText: 'e.g. English'),
                    validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
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
                    // A dropdown sizes itself to its widest ITEM, not to the
                    // space it has. "Brief summary first, detail on request"
                    // is wider than this card's 440px, so without this the row
                    // overflows by 268px - a real overflow at the width this
                    // screen declares for itself, found by a widget test
                    // rendering the form at exactly that width.
                    isExpanded: true,
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
                  const SizedBox(height: AppSpacing.lg),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: _submitting ? null : _submit,
                      child: _submitting
                          ? SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: pip.accentOn))
                          : const Text('Complete setup'),
                    ),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: AppSpacing.sm),
                    Text(_error!, style: TextStyle(fontSize: 12, color: pip.danger)),
                  ],
                ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
