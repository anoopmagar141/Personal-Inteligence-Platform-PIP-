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
import 'dart:typed_data';

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

  /// [body] is sent when given, which HTTP allows on DELETE and which one
  /// route here needs: deleting a profile is confirmed by re-typing its
  /// password, and a password does not belong in a query string - those are
  /// logged, kept in history, and visible in a URL bar.
  Future<dynamic> delete(String path, [Map<String, dynamic>? body]) async {
    final request = http.Request('DELETE', _uri(path))
      ..headers.addAll(_authHeaders);
    if (body != null) {
      request.headers['Content-Type'] = 'application/json';
      request.body = jsonEncode(body);
    }
    final response = await http.Response.fromStream(await request.send());
    return _decode(response);
  }

  // --- Domain calls, matching the exact endpoints validated for the web
  // client (frontend/web/app.js) - same API surface, per Part 14.1. ---

  // --- signing in ----------------------------------------------------
  //
  // The only calls that work before the database is open. Everything else
  // answers 423 until unlock() or completeSetup() has succeeded, which is why
  // AppRoot asks authState() first and getStatus() second.

  /// Which of setup / locked / needs_migration / unlocked this install is in.
  Future<String> authState() async =>
      (await get('/auth/state') as Map<String, dynamic>)['state'] as String;

  /// Who this installation can be signed in as.
  ///
  /// Each entry carries `slug`, `name`, and `exists` - the last being whether
  /// the profile has been created or only registered, which is what lets the
  /// sign-in screen say "Choose a password" for one name and "Welcome back"
  /// for another without opening anything.
  Future<Map<String, dynamic>> authProfiles() async =>
      await get('/auth/profiles') as Map<String, dynamic>;

  /// Point the backend at another profile, and get back the state it is in.
  ///
  /// Refused with 409 while unlocked, which is not a limitation to work
  /// around: the key in the server's memory belongs to the profile it was
  /// derived for. Switching is something the sign-in screen does, and signing
  /// out is how you get back to it.
  Future<String> selectProfile(String slug) async =>
      (await post('/auth/profile', {'slug': slug}) as Map<String, dynamic>)['state'] as String;

  /// Open the database with [password]. Throws on a wrong one - the message
  /// carries the server's own sentence, which is more specific than anything
  /// the caller could infer from a status code.
  ///
  /// [profile] is sent even though selectProfile() has normally already been
  /// called, so that the password and the profile it is meant for arrive
  /// together. A selection in one request and a password in the next leaves a
  /// window between them; nobody should be able to reach "typed one profile's
  /// password at another's database" by timing.
  Future<void> unlock(String password, {String? profile}) async {
    await post('/auth/unlock', {
      'password': password,
      'profile': ?profile,
    });
  }

  /// Choose the first password on a profile that has never had one.
  Future<void> completeSetup(String password, {String? profile}) async {
    await post('/auth/setup', {
      'password': password,
      'profile': ?profile,
    });
  }

  /// Sign out: the server persists whatever the open sessions were saying,
  /// then forgets the key. Every route answers 423 afterwards, so the caller's
  /// next job is to show the sign-in screen.
  Future<void> lock() async {
    await post('/auth/lock', {});
  }

  // --- managing profiles ----------------------------------------------
  //
  // Creating one happens on the sign-in screen and so works while locked; the
  // other three happen from inside a profile and are refused otherwise. That
  // split is the only ownership test this application has - there is no
  // account server and no recovery, so the sole way to tell the owner of a
  // profile from anyone else with the disk is that the owner can turn a
  // password into a key that opens it.

  /// Register a new profile and point the backend at it, ready for
  /// [completeSetup] to choose its password.
  ///
  /// Two calls rather than one, matching the backend: this creates a directory
  /// and a registry entry, and the password arrives separately. Sending both
  /// together would mean a password travelling with a request that is served
  /// while locked, for no gain.
  Future<Map<String, dynamic>> createProfile(String name) async =>
      await post('/auth/profiles', {'name': name}) as Map<String, dynamic>;

  /// Change the name shown on the sign-in screen. The directory is untouched.
  Future<Map<String, dynamic>> renameProfile(String slug, String name) async =>
      await patch('/auth/profiles/$slug', {'name': name}) as Map<String, dynamic>;

  /// Change this profile's password, re-encrypting its database to match.
  ///
  /// The current password is required even though the caller is already
  /// signed in: the session proves the database was opened, not who is at the
  /// keyboard now. Takes seconds - two PBKDF2 derivations and a full
  /// re-encryption - so callers should show that it is working.
  Future<void> changePassword(String currentPassword, String newPassword) async {
    await post('/auth/password', {
      'current_password': currentPassword,
      'new_password': newPassword,
    });
  }

  /// Erase this profile's data and sign out. There is no undo.
  ///
  /// The password is sent again for the same reason the change needs it, with
  /// more at stake. Close the WebSocket before calling: the backend cannot
  /// delete a database file this client still has open.
  Future<Map<String, dynamic>> deleteProfile(String slug, String password) async =>
      await delete('/auth/profiles/$slug', {'password': password}) as Map<String, dynamic>;

  // --- the picture on the sign-in screen -------------------------------
  //
  // The avatar lives inside the encrypted database. The sign-in screen draws
  // profiles that are locked, so a picture shown there cannot come from
  // inside it - publishing writes a second, unencrypted copy beside the
  // profile's database, which is a real cost against the threat the
  // encryption exists for. Hence off by default, and un-publishing deletes
  // the file rather than merely hiding it.

  /// Whether this profile's picture is currently shown on the sign-in screen.
  Future<bool> signInPicturePublished() async =>
      ((await get('/profile/picture/sign-in')) as Map<String, dynamic>)['published'] as bool;

  /// Publish a copy of the stored picture where the locked screen can read it.
  Future<void> publishSignInPicture() async {
    await post('/profile/picture/sign-in', {});
  }

  /// Delete that copy. The picture inside the database is left alone.
  Future<void> unpublishSignInPicture() async {
    await delete('/profile/picture/sign-in');
  }

  /// A profile's published picture, or null when it has not published one.
  ///
  /// The one call that reads a per-profile file without a password, and it can
  /// only ever return what that profile's owner chose to publish for this
  /// screen. 404 is "no picture", which the switcher draws initials for.
  Future<Uint8List?> getSignInPicture(String slug) async {
    final response = await http.get(_uri('/auth/profiles/$slug/picture'), headers: _authHeaders);
    if (response.statusCode != 200) return null;
    return response.bodyBytes;
  }

  // --- restoring a backup ----------------------------------------------
  //
  // A restore is two things and only one of them is blocked by the app being
  // open. Converting the backup into a live database happens now, while both
  // passwords are in memory; the swap into place happens at the next start,
  // because a file that is open cannot be renamed. Nothing is recorded until
  // the converted database has been proven to open.

  /// Whether a restore is staged and waiting for a restart.
  Future<Map<String, dynamic>> restoreStatus() async =>
      await get('/backup/restore') as Map<String, dynamic>;

  /// Verify a .pipbak and stage it to replace this profile at the next start.
  ///
  /// The path rather than the bytes: a .pipbak is the whole profile and runs
  /// to hundreds of megabytes, and the backend is on this same machine.
  Future<Map<String, dynamic>> stageRestore({
    required String path,
    required String backupPassword,
    required String newPassword,
  }) async =>
      await post('/backup/restore', {
        'path': path,
        'backup_password': backupPassword,
        'new_password': newPassword,
      }) as Map<String, dynamic>;

  /// Discard a staged restore and the temporary files it wrote.
  Future<void> cancelRestore() async {
    await delete('/backup/restore');
  }

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

  /// The scopes backend/api/server.py's VALID_CONSENT_SCOPES accepts, narrowest
  /// first. 'none' is a valid scope but is deliberately absent: granting
  /// "none" sets user_consented while consenting to nothing, which is what
  /// revoke already says without the ambiguity.
  static const consentScopes = <String, String>{
    'embedding_only': 'Embeddings only - text is sent to be turned into vectors, and nothing else.',
    'web_search_only': 'Web search only - search queries leave this machine, your conversation does not.',
    'full_inference': 'Full inference - your prompts and assembled context are sent to the provider.',
  };

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

  // --- the profile picture --------------------------------------------
  //
  // The one endpoint pair that does not speak JSON. An image encoded into a
  // JSON field would be base64 - a third larger, hand-decoded on both sides,
  // and no longer something Image.memory can be handed directly.

  /// The stored picture, or null when none is set.
  ///
  /// 404 is translated to null rather than thrown, because "there is no
  /// picture" is an answer and not a failure - it is what makes the initials
  /// appear. Every other status still throws.
  Future<Uint8List?> getProfilePicture() async {
    final response = await http.get(_uri('/profile/picture'), headers: _authHeaders);
    if (response.statusCode == 404) return null;
    if (response.statusCode != 200) {
      throw Exception('GET /profile/picture failed: ${response.statusCode} ${response.body}');
    }
    return response.bodyBytes;
  }

  Future<void> setProfilePicture(String filename, List<int> bytes) async {
    final request = http.MultipartRequest('POST', _uri('/profile/picture'))
      ..headers.addAll(_authHeaders)
      ..files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename));
    final response = await http.Response.fromStream(await request.send());
    _decode(response);
  }

  Future<void> deleteProfilePicture() async {
    await delete('/profile/picture');
  }

  Future<List<dynamic>> getLlmModels() async {
    final result = await get('/llm/models') as Map<String, dynamic>;
    return result['models'] as List<dynamic>;
  }

  Future<String> getActiveModel() async {
    final result = await get('/llm/active-model') as Map<String, dynamic>;
    return result['model_name'] as String;
  }

  /// What can be chosen: pulled models, suggested ones, and what fits.
  ///
  /// One call rather than three, because "what can I run" is one question and
  /// answering it from three endpoints would put the joining logic here, where
  /// a second client would have to reimplement it.
  Future<Map<String, dynamic>> getModelCatalog() async {
    return await get('/llm/catalog') as Map<String, dynamic>;
  }

  /// Start a download. Progress comes from polling pullStatus(), not a stream:
  /// ADR-028 keeps every streaming path on the one WebSocket, and a progress
  /// bar is not worth a second transport.
  Future<void> startPull(String modelName) async {
    await post('/llm/pull', {'model_name': modelName});
  }

  /// Ask the running download to stop.
  ///
  /// Returns as soon as the backend has asked, not when it has stopped - the
  /// puller notices between lines of Ollama's response. The status this screen
  /// already polls reports 'cancelled' when it really has, so there is no
  /// second mechanism to keep working.
  ///
  /// Nothing is wasted: the blobs already written stay in Ollama's store, so
  /// pulling the same model again resumes rather than starting over.
  Future<void> cancelPull() async {
    await delete('/llm/pull');
  }

  /// Remove a pulled model from Ollama's store, freeing its weights on disk.
  ///
  /// Refused for the model PIP is currently using, and for one being
  /// downloaded right now - both come back as the server's own sentence.
  Future<void> deleteModel(String modelName) async {
    await delete('/llm/models', {'model_name': modelName});
  }

  Future<Map<String, dynamic>> getPullStatus() async {
    return await get('/llm/pull') as Map<String, dynamic>;
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

  /// How the recorded interaction style has changed over time, newest first:
  /// {value, changed_at}.
  ///
  /// interaction_style is the only profile field with any history at all -
  /// every other table keeps its current value and nothing else - which makes
  /// this the one place PIP can show that a setting was once something else
  /// rather than just asserting what it is now.
  Future<List<dynamic>> getInteractionStyleHistory({int limit = 50}) async =>
      await get('/memory/interaction-style/history', query: {'limit': '$limit'}) as List<dynamic>;

  /// {similarity_threshold, top_k_results} - the settings a /rag/query with no
  /// threshold is answered at, straight from config/settings.json.
  ///
  /// Fetched rather than assumed. These are backend configuration, so any copy
  /// kept on this side is correct only until someone edits the file, and no
  /// build or test would catch the day it stops being.
  Future<Map<String, dynamic>> getRagDefaults() async =>
      await get('/rag/defaults') as Map<String, dynamic>;

  /// What RAG would actually retrieve for [query], without asking PIP anything:
  /// {chunk_text, file_path, chunk_index, similarity}, already filtered by
  /// [threshold] server-side.
  ///
  /// [threshold] is exposed rather than left at the backend's own default
  /// because the question people actually bring here is "why did PIP not use
  /// my document" - and an empty result at 0.6 with near-misses at 0.3 is the
  /// answer, where an empty result alone is not.
  ///
  /// Omitting it is meaningful: the backend then resolves
  /// rag.similarity_threshold itself, which is what a caller wanting "whatever
  /// Stage 5 would have used" should send. Callers that want to show that
  /// number before searching read it from [getRagDefaults].
  Future<List<dynamic>> queryRag(String query, {double? threshold, String? projectId}) async =>
      await post('/rag/query', {
        'query': query,
        'threshold': ?threshold,
        'project_id': ?projectId,
      }) as List<dynamic>;

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

  /// [projectId] narrows the list to one project's conversations.
  ///
  /// The backend has always supported it (list_conversations takes a
  /// project_id) and this never passed one, so the sidebar was a single flat
  /// pile no matter what you were working on. Null means every conversation,
  /// which is a real choice rather than a fallback - a chat started with no
  /// project selected belongs to no project, and has to stay reachable.
  Future<List<dynamic>> getConversations({String? projectId}) async {
    final result = await get(
      '/conversations',
      query: projectId == null ? null : {'project_id': projectId},
    );
    return result as List<dynamic>;
  }

  Future<List<dynamic>> getConversationMessages(String conversationId) async =>
      await get('/conversations/$conversationId/messages') as List<dynamic>;

  Future<void> deleteConversation(String conversationId) async {
    await delete('/conversations/$conversationId');
  }
}
