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

  final _searchController = TextEditingController();
  List<dynamic>? _matches; // null = never searched, [] = searched and found nothing
  String? _searchError;
  bool _searching = false;

  /// The similarity floor sent to /rag/query. The backend defaults to 0.6, and
  /// this is a control rather than a constant because the question people
  /// bring to this screen is "why did PIP not use my document" - nothing at
  /// 0.6 with near-misses at 0.3 answers that, where nothing at 0.6 alone does
  /// not. Starts at the backend's own default, so the first result set is what
  /// a real question would actually have retrieved.
  double _threshold = 0.6;

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
    // Was unguarded. This screen already prints _error inline above the list
    // rather than returning early on it, so a failure here is reportable
    // without costing the page - it just had nowhere to go.
    try {
      await widget.api.deleteDocument(filePath);
      setState(() => _error = null);
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  /// Runs retrieval on its own, without asking PIP anything.
  ///
  /// This is the half the Trace tab cannot show. A trace records that Stage 5
  /// ran and how many chunks came back; it does not record which chunks, or
  /// how close they were. POST /rag/query answers both and had no caller in
  /// either client - so "is my document actually reachable" was a question the
  /// system could answer and no interface would ask.
  Future<void> _search() async {
    final query = _searchController.text.trim();
    if (query.isEmpty) return;
    setState(() {
      _searching = true;
      _searchError = null;
    });
    try {
      final matches = await widget.api.queryRag(query, threshold: _threshold);
      if (mounted) setState(() => _matches = matches);
    } catch (error) {
      if (mounted) setState(() => _searchError = error.toString());
    } finally {
      if (mounted) setState(() => _searching = false);
    }
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
            _searchCard(),
            const SizedBox(height: AppSpacing.lg),
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

  Widget _searchCard() {
    final pip = context.pip;
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TagLabel('What would PIP find?', color: pip.text, size: 12),
          const SizedBox(height: 4),
          Text(
            'Runs retrieval on its own, without asking PIP anything. Shows the '
            'passages a question would actually pull in, and how close each one is.',
            style: TextStyle(fontSize: 12.5, color: pip.textMuted),
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchController,
                  style: const TextStyle(fontSize: 13),
                  decoration: const InputDecoration(
                    hintText: 'Ask something your documents should answer...',
                  ),
                  onSubmitted: (_) => _search(),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              FilledButton(
                onPressed: _searching ? null : _search,
                child: _searching
                    ? SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2, color: pip.accentOn),
                      )
                    : const Text('Search'),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              Text('Minimum similarity', style: TextStyle(fontSize: 12, color: pip.textMuted)),
              Expanded(
                child: Slider(
                  value: _threshold,
                  max: 0.9,
                  divisions: 18,
                  label: _threshold.toStringAsFixed(2),
                  onChanged: (value) => setState(() => _threshold = value),
                  // Re-runs only once the drag settles, and only if a search
                  // has already been made - dragging the slider before asking
                  // anything has nothing to re-run.
                  onChangeEnd: (_) {
                    if (_matches != null) _search();
                  },
                ),
              ),
              SizedBox(
                width: 36,
                child: Text(
                  _threshold.toStringAsFixed(2),
                  style: TextStyle(fontSize: 12, color: pip.textMuted, fontFamily: AppTheme.mono),
                ),
              ),
            ],
          ),
          if (_searchError != null) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(_searchError!, style: TextStyle(fontSize: 12, color: pip.danger)),
          ],
          if (_matches != null) ...[
            const SizedBox(height: AppSpacing.sm),
            if (_matches!.isEmpty)
              Text(
                'Nothing above ${_threshold.toStringAsFixed(2)}. Lower the threshold to see what '
                'came closest - if the answer is in a document at all, it will surface further down.',
                style: TextStyle(fontSize: 12.5, color: pip.textFaint, height: 1.5),
              )
            else
              for (final raw in _matches!) _MatchRow(match: raw as Map<String, dynamic>),
          ],
        ],
      ),
    );
  }
}

/// One retrieved passage: where it came from, how close it was, and the text
/// itself. The score is shown because the point of this panel is that
/// retrieval is a threshold, not a yes or no.
class _MatchRow extends StatelessWidget {
  final Map<String, dynamic> match;
  const _MatchRow({required this.match});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    final similarity = (match['similarity'] as num).toDouble();
    final path = '${match['file_path']}';
    final name = path.split(RegExp(r'[\\/]')).last;
    return Container(
      margin: const EdgeInsets.only(top: AppSpacing.sm),
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(color: pip.surfaceRaised, borderRadius: AppRadius.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  '$name . chunk ${match['chunk_index']}',
                  style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: pip.text),
                ),
              ),
              Text(
                similarity.toStringAsFixed(3),
                style: TextStyle(
                  fontSize: 11.5,
                  fontWeight: FontWeight.w700,
                  color: pip.accent,
                  fontFamily: AppTheme.mono,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          SelectableText(
            '${match['chunk_text']}',
            style: TextStyle(fontSize: 12.5, color: pip.textMuted, height: 1.45),
          ),
        ],
      ),
    );
  }
}
