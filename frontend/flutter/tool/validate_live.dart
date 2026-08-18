// Scratch validation script, NOT part of the app or the committed test
// suite - drives the real ApiClient/WsChatClient code (the same classes
// lib/ uses) against a live PIP backend to prove the Flutter client's REST
// and WS logic actually works end-to-end, not just against a fake.
//
// Usage: dart run tool/validate_live.dart
// Requires: a real `uvicorn backend.api.server:app` already running and
// reachable at kApiBase/kWsUrl below.

// ignore_for_file: avoid_print

import 'dart:async';

import 'package:pip_flutter_client/api_client.dart';
import 'package:pip_flutter_client/ws_chat_client.dart';

const apiBase = 'http://127.0.0.1:8765/api/v1';
const wsUrl = 'ws://127.0.0.1:8765/ws/chat';

Future<void> main() async {
  final api = ApiClient(apiBase);
  var failures = 0;

  Future<void> check(String label, Future<void> Function() body) async {
    try {
      await body();
      print('PASS: $label');
    } catch (e, st) {
      failures++;
      print('FAIL: $label -> $e\n$st');
    }
  }

  await check('GET /status before onboarding', () async {
    final status = await api.getStatus();
    if (status['onboarding_complete'] != false) {
      throw StateError('expected onboarding_complete=false, got ${status['onboarding_complete']}');
    }
  });

  await check('POST /onboarding/complete', () async {
    await api.completeOnboarding({
      'name': 'Flutter Live Check',
      'language_preference': 'English',
      'timezone': 'UTC',
      'skills': ['Dart', 'Flutter'],
      'preferred_tools': ['VS Code'],
      'current_project': {'name': 'Flutter Client Validation', 'description': 'live check'},
    });
    final status = await api.getStatus();
    if (status['onboarding_complete'] != true) {
      throw StateError('expected onboarding_complete=true after completing onboarding');
    }
  });

  await check('GET /memory/profile has real fields', () async {
    final fields = await api.getProfile();
    if (fields.isEmpty) throw StateError('expected non-empty profile after onboarding');
    final names = fields.map((f) => f['field']).toList();
    if (!names.contains('name')) throw StateError('expected a "name" field, got $names');
  });

  String? projectId;
  await check('GET /projects has the onboarding project', () async {
    final projects = await api.getProjects();
    if (projects.isEmpty) throw StateError('expected at least one project from onboarding');
    projectId = projects.first['project_id'] as String;
  });

  await check('POST /projects creates a second project', () async {
    final before = (await api.getProjects()).length;
    await api.createProject({'name': 'Second Flutter Project', 'description': 'created live'});
    final after = await api.getProjects();
    if (after.length != before + 1) throw StateError('expected project count to increase by 1');
  });

  await check('POST /projects/{id}/activate', () async {
    if (projectId == null) throw StateError('no projectId from earlier check');
    await api.activateProject(projectId!);
  });

  await check('POST /decision/create then GET /decision/search finds it', () async {
    final result = await api.createDecision({
      'text': 'Use Riverpod for state management in the Flutter client',
      'reasoning': 'Keeps widget state predictable',
      'alternatives': 'Bare StatefulWidget, Provider',
    });
    if (result['status'] != 'logged') {
      throw StateError('expected status=logged, got ${result['status']}');
    }
    final found = await api.searchDecisions('What did we decide about Riverpod?');
    if (found.isEmpty) {
      throw StateError('FTS5 punctuation-tolerant search found nothing - regression check failed');
    }
  });

  await check('GET /providers lists ollama as local, no consent needed', () async {
    final providers = await api.getProviders();
    final ollama = providers.firstWhere((p) => p['provider_id'] == 'ollama', orElse: () => null);
    if (ollama == null) throw StateError('expected an "ollama" provider');
    if (ollama['is_cloud'] != false) throw StateError('expected ollama to be local');
  });

  await check('POST /providers/{id}/consent then /revoke for web_search', () async {
    await api.grantConsent('web_search', 'full_inference');
    final afterGrant = await api.getProviders();
    final webSearch = afterGrant.firstWhere((p) => p['provider_id'] == 'web_search');
    if (webSearch['user_consented'] != true) throw StateError('expected web_search consented after grant');

    await api.revokeConsent('web_search');
    final afterRevoke = await api.getProviders();
    final webSearchAfter = afterRevoke.firstWhere((p) => p['provider_id'] == 'web_search');
    if (webSearchAfter['revoked'] != true) throw StateError('expected web_search revoked after revoke');
  });

  await check('WS chat: real streamed response with stage hints', () async {
    final client = WsChatClient(wsUrl, reconnectDelay: const Duration(seconds: 999));
    final connected = Completer<void>();
    final done = Completer<void>();
    final tokens = StringBuffer();
    Map<String, dynamic>? stageHint;
    String? errorData;

    client.status.listen((s) {
      if (s == 'connected' && !connected.isCompleted) connected.complete();
    });
    client.events.listen((event) {
      switch (event.type) {
        case 'stage_hint':
          stageHint = event.data as Map<String, dynamic>?;
          break;
        case 'token':
          tokens.write(event.data as String);
          break;
        case 'done':
          if (!done.isCompleted) done.complete();
          break;
        case 'error':
          errorData = event.data as String?;
          if (!done.isCompleted) done.complete();
          break;
      }
    });

    client.connect();
    await connected.future.timeout(const Duration(seconds: 10));
    client.sendMessage('Say hello in exactly one short sentence.');
    // ADR-033: a cold Ollama model load measured ~130s; give real headroom
    // rather than a client-side timeout racing the server's own warm-up.
    await done.future.timeout(const Duration(seconds: 180));
    client.dispose();

    if (errorData != null) throw StateError('WS chat returned an error: $errorData');
    if (stageHint == null) throw StateError('expected a stage_hint event before done');
    if (tokens.isEmpty) throw StateError('expected non-empty streamed response text');
    print('  -> response: "${tokens.toString().trim()}"');
    print('  -> stage_hint: $stageHint');
  });

  print('\n${failures == 0 ? "ALL CHECKS PASSED" : "$failures CHECK(S) FAILED"}');
}
