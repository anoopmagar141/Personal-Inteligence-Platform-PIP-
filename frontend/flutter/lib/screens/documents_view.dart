// Matches the backend's /rag/* surface (backend/api/server.py): list what's
// been ingested, upload a new file (multipart -> /rag/upload, which copies
// the picked file into DOCUMENTS_ROOT before ingesting - see that route's
// docstring for why a plain /rag/ingest call can't take an arbitrary picked
// path directly), and delete an ingested document.

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';

class DocumentsView extends StatefulWidget {
  final ApiClient api;
  final String? activeProjectId;
  const DocumentsView({super.key, required this.api, required this.activeProjectId});

  @override
  State<DocumentsView> createState() => _DocumentsViewState();
}

class _DocumentsViewState extends State<DocumentsView> {
  List<dynamic>? _documents;
  String? _error;
  bool _uploading = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final documents = await widget.api.getDocuments();
      if (mounted) setState(() => _documents = documents);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _pickAndUpload() async {
    final picked = await FilePicker.pickFile(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'md', 'txt', 'py', 'json', 'html'],
    );
    if (picked == null) return;

    setState(() {
      _uploading = true;
      _error = null;
    });
    try {
      final bytes = await picked.readAsBytes();
      await widget.api.uploadDocument(picked.name, bytes, projectId: widget.activeProjectId);
      await _load();
    } catch (error) {
      setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  Future<void> _delete(String filePath) async {
    await widget.api.deleteDocument(filePath);
    await _load();
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
              eyebrow: 'Memory',
              title: 'Documents',
              description: 'Files PIP has read into its memory (RAG). Supported: PDF, Markdown, text, Python, JSON, HTML.',
            ),
            if (_error != null) ...[
              Text(_error!, style: TextStyle(color: pip.danger, fontSize: 12.5)),
              const SizedBox(height: AppSpacing.sm),
            ],
            if (_documents != null)
              if (_documents!.isEmpty)
                EmptyState(
                  icon: Icons.description_outlined,
                  title: 'No documents yet',
                  description: 'Upload a file below and PIP will read it into memory.',
                  actionLabel: 'Upload a file',
                  onAction: _pickAndUpload,
                )
              else
                Column(
                  children: [
                    for (final doc in _documents!)
                      Padding(
                        padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                        child: SectionCard(
                          child: Row(
                            children: [
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      _fileName('${doc['file_path']}'),
                                      style: TextStyle(fontSize: 14.5, fontWeight: FontWeight.w600, color: pip.text),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      '${doc['chunk_count']} chunks · ingested ${doc['ingested_at']}',
                                      style: TextStyle(fontSize: 12, color: pip.textMuted),
                                    ),
                                  ],
                                ),
                              ),
                              GhostButton(
                                label: 'Remove',
                                color: pip.danger,
                                onTap: () => _delete('${doc['file_path']}'),
                              ),
                            ],
                          ),
                        ),
                      ),
                  ],
                ),
            const SizedBox(height: AppSpacing.lg),
            SectionCard(
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      'Add a document for PIP to remember.',
                      style: TextStyle(fontSize: 13.5, color: pip.textMuted),
                    ),
                  ),
                  FilledButton(
                    onPressed: _uploading ? null : _pickAndUpload,
                    child: _uploading
                        ? SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: pip.accentOn))
                        : const Text('Upload'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _fileName(String path) => path.split(RegExp(r'[\\/]')).last;
}
