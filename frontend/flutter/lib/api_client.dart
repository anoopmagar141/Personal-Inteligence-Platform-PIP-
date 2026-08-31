// PIP - REST client for /api/v1/* (Part 14.2: REST for everything except
// chat; chat is WebSocket-only, see ws_chat_client.dart).
//
// Part 14.4: "Frontend has zero intelligence. All logic in PIP Core backend."
// This class does exactly one thing - turn a path + payload into an HTTP call
// and turn the JSON response into a Dart value. No caching, no retries, no
// client-side validation beyond what's needed to serialize the request -
// every value shown to the user comes straight from what the backend
// returned, matching the same "thin renderer" approach the web client
// (frontend/web/app.js) already uses and was live-validated against.

import 'dart:convert';

import 'package:http/http.dart' as http;

class ApiException implements Exception {
  final int statusCode;
  final String body;
  ApiException(this.statusCode, this.body);

  /// The server's own sentence, unwrapped from FastAPI's {"detail": "..."}
  /// envelope, falling back to the raw body when it is not shaped that way.
  ///
  /// That sentence is the entire point of some refusals rather than incidental
  /// detail - the memory review queue can reject a confirmation with 422
  /// because the candidate exists but cannot be applied, and "immutable
  /// identity fields cannot be edited after onboarding" is the only thing that
  /// tells a user why. Showing them a JSON envelope would throw it away.
  String get detail {
    try {
      final parsed = jsonDecode(body);
      if (parsed is Map && parsed['detail'] is String) return parsed['detail'] as String;
    } catch (_) {
      // Not JSON - fall through to the raw body.
    }
    return body;
  }

  @override
  String toString() => detail;
}

class ApiClient {
  final String baseUrl; // e.g. http://127.0.0.1:8765/api/v1
  // Security fix: every /api/v1/* route now requires this (see
  // backend/core/auth.py) - read from data/api_token.txt, never logged by
  // the server.
  final String apiToken;

  ApiClient(this.baseUrl, {this.apiToken = ''});

  Uri _uri(String path, [Map<String, String>? query]) =>
      Uri.parse('$baseUrl$path').replace(queryParameters: query);

  Map<String, String> get _authHeaders => {'Authorization': 'Bearer $apiToken'};

  dynamic _decode(http.Response response) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(response.statusCode, response.body);
    }
    if (response.body.isEmpty) return null;
    return jsonDecode(response.body);
  }

  Future<dynamic> get(String path, {Map<String, String>? query}) async {
    final response = await http.get(_uri(path, query), headers: _authHeaders);
    return _decode(response);
  }

  Future<dynamic> post(String path, [Map<String, dynamic>? body]) async {
    final response = await http.post(
      _uri(path),
      headers: {'Content-Type': 'application/json', ..._authHeaders},
      body: jsonEncode(body ?? {}),
    );
    return _decode(response);
  }

  Future<dynamic> patch(String path, [Map<String, dynamic>? body]) async {
    final response = await http.patch(
      _uri(path),
      headers: {'Content-Type': 'application/json', ..._authHeaders},
      body: jsonEncode(body ?? {}),
    );
    return _decode(response);
  }

  Future<dynamic> delete(String path) async {
    final response = await http.delete(_uri(path), headers: _authHeaders);
    return _decode(response);
  }

  // --- Domain calls, matching the exact endpoints validated for the web
  // client (frontend/web/app.js) - same API surface, per Part 14.1. ---

  Future<Map<String, dynamic>> getStatus() async => await get('/status') as Map<String, dynamic>;

  Future<void> completeOnboarding(Map<String, dynamic> payload) async {
    await post('/onboarding/complete', payload);
  }

  Future<List<dynamic>> getProfile() async => await get('/memory/profile') as List<dynamic>;

  /// [state] is an exact match on the backend side, not a filter that can be
  /// widened - list_decisions()/search_decisions() both take a single state and
  /// default to 'active'. Passing it explicitly is what makes a retracted
  /// decision reachable at all: without it the log silently shows only what is
  /// still active, and a decision retracted through the UI would appear to
  /// have been deleted by it.
  Future<List<dynamic>> searchDecisions([String query = '', String state = 'active']) async {
    final result = await get('/decision/search', query: {
      if (query.isNotEmpty) 'q': query,
      'state': state,
    });
    return result as List<dynamic>;
  }

  Future<Map<String, dynamic>> createDecision(Map<String, dynamic> payload) async =>
      await post('/decision/create', payload) as Map<String, dynamic>;

  Future<List<dynamic>> getProjects() async => await get('/projects') as List<dynamic>;

  Future<void> createProject(Map<String, dynamic> payload) async {
    await post('/projects', payload);
  }

  Future<void> activateProject(String projectId) async {
    await post('/projects/$projectId/activate');
  }

  Future<List<dynamic>> getProviders() async => await get('/providers') as List<dynamic>;

  Future<void> grantConsent(String providerId, String scope) async {
    await post('/providers/$providerId/consent', {'consent_scope': scope});
  }

  Future<void> revokeConsent(String providerId) async {
    await post('/providers/$providerId/revoke');
  }

  Future<List<dynamic>> getDocuments() async => await get('/rag/documents') as List<dynamic>;

  Future<void> deleteDocument(String filePath) async {
    await delete('/rag/documents/${Uri.encodeComponent(filePath)}');
  }

  // Multipart, not the json post() helper above - the backend writes the
  // picked file's bytes under its own sandboxed documents root (a desktop
  // file picker returns a path outside it, which the plain /rag/ingest
  // endpoint would reject) before ingesting it.
  Future<Map<String, dynamic>> uploadDocument(String filename, List<int> bytes, {String? projectId}) async {
    final request = http.MultipartRequest('POST', _uri('/rag/upload'))
      ..headers.addAll(_authHeaders)
      ..files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename));
    if (projectId != null) request.fields['project_id'] = projectId;
    final streamed = await request.send();
    final response = await http.Response.fromStream(streamed);
    return _decode(response) as Map<String, dynamic>;
  }

  Future<List<dynamic>> getLlmModels() async {
    final result = await get('/llm/models') as Map<String, dynamic>;
    return result['models'] as List<dynamic>;
  }

  Future<String> getActiveModel() async {
    final result = await get('/llm/active-model') as Map<String, dynamic>;
    return result['model_name'] as String;
  }

  Future<void> setActiveModel(String modelName) async {
    await post('/llm/active-model', {'model_name': modelName});
  }

  // --- Review queue -------------------------------------------------------
  // Everything PIP has learned but is not allowed to keep without asking:
  // constitution-gated candidates parked by Stage 13, and the periodic memory
  // check that adds to the same queue every 30 sessions.

  Future<List<dynamic>> getPendingMemory() async =>
      await get('/memory/pending') as List<dynamic>;

  Future<void> confirmPendingMemory(int candidateId) async {
    await post('/memory/pending/$candidateId/confirm');
  }

  Future<void> dismissPendingMemory(int candidateId) async {
    await post('/memory/pending/$candidateId/dismiss');
  }

  Future<List<dynamic>> getPendingDecisions() async =>
      await get('/decision/pending') as List<dynamic>;

  Future<void> promotePendingDecision(int candidateId) async {
    await post('/decision/pending/$candidateId/promote');
  }

  Future<void> dismissPendingDecision(int candidateId) async {
    await post('/decision/pending/$candidateId/dismiss');
  }

  /// Deterministic triggers only - the constitution forbids model judgment of
  /// relevance or urgency here, so this is a plain read of what is currently
  /// true, never a ranked feed.
  Future<List<dynamic>> getProactive() async => await get('/proactive') as List<dynamic>;

  // --- Profile editing ----------------------------------------------------
  // The read half of the profile has been here since the first version; these
  // are the write half. Both refuse the three identity fields server-side
  // (name / language_preference / timezone are settled at onboarding), and
  // both report that refusal as a 422 whose detail is the sentence explaining
  // it - which is why ApiException.detail exists and why these do not try to
  // pre-empt the rule client-side. Part 14.4: the backend decides.

  Future<void> correctMemory(String field, String value) async {
    await post('/memory/correct', {'field': field, 'value': value});
  }

  /// Soft delete - ADR-022 keeps the row and flips its status, so this is a
  /// retraction rather than an erasure. Returns the backend's own report of
  /// whether anything matched ({'status': 'deleted' | 'not_found'}).
  Future<Map<String, dynamic>> deleteProfileField(String field) async =>
      await delete('/memory/profile/${Uri.encodeComponent(field)}') as Map<String, dynamic>;

  // --- State transitions --------------------------------------------------

  /// [reason] is required by the backend for 'superseded' and 'abandoned' and
  /// is stored verbatim for every state including 'active': the log outlives
  /// the retraction, and state alone cannot tell a later reader "this was a
  /// fabrication we cleaned up" from "this was real and we changed our mind".
  Future<void> updateDecisionState(
    int decisionId, {
    required String state,
    required String reason,
    int? supersededBy,
  }) async {
    await patch('/decision/$decisionId/state', {
      'state': state,
      'reason': reason,
      'superseded_by': ?supersededBy,
    });
  }

  Future<void> updateProjectStatus(String projectId, String status) async {
    await patch('/projects/$projectId/status', {'status': status});
  }

  // --- Trace --------------------------------------------------------------
  // "Why did PIP reply like that" - which stages ran, what each retrieved,
  // where a run failed. The backend moved this out of a plaintext file and
  // into the database specifically so it could be read back; until now
  // nothing read it, so the answer was still unreachable from any interface.

  /// Summary rows, newest first: {trace_id, started_at, entries, errors}.
  Future<List<dynamic>> listTraces({int limit = 20}) async =>
      await get('/trace', query: {'limit': '$limit'}) as List<dynamic>;

  /// One run's stages in recorded order:
  /// {id, trace_id, timestamp, stage, status, message, error_detail}.
  Future<List<dynamic>> getTrace(String traceId) async =>
      await get('/trace/${Uri.encodeComponent(traceId)}') as List<dynamic>;

  Future<List<dynamic>> getConversations() async => await get('/conversations') as List<dynamic>;

  Future<List<dynamic>> getConversationMessages(String conversationId) async =>
      await get('/conversations/$conversationId/messages') as List<dynamic>;

  Future<void> deleteConversation(String conversationId) async {
    await delete('/conversations/$conversationId');
  }
}
