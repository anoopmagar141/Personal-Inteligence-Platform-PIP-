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

  @override
  String toString() => 'ApiException($statusCode): $body';
}

class ApiClient {
  final String baseUrl; // e.g. http://127.0.0.1:8765/api/v1
  // Security fix: every /api/v1/* route now requires this (see
  // backend/core/auth.py) - PIP prints a ready-to-use token at startup.
  final String apiToken;

  ApiClient(this.baseUrl, {this.apiToken = ''});

  Uri _uri(String path, [Map<String, String>? query]) =>
      Uri.parse('$baseUrl$path').replace(queryParameters: query);

  Map<String, String> get _authHeaders => {'X-PIP-Token': apiToken};

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

  Future<List<dynamic>> searchDecisions([String query = '']) async {
    final result = await get('/decision/search', query: query.isEmpty ? null : {'q': query});
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
}
