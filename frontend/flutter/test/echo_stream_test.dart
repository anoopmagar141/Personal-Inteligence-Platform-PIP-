// Integration-style test for the spike's actual purpose: proving Dart can
// consume a live, asynchronously-arriving WebSocket token stream correctly,
// not just render a UI that looks right. Spins up the real
// scripts/fake_echo_server.py as a subprocess (same server the manual UI
// spike connects to), connects a real WebSocketChannel, sends a message, and
// asserts on the actual event sequence and timing - this is a stronger proof
// of "tests async stream handling" than eyeballing the rendered widget tree,
// which is why it exists alongside main.dart rather than instead of it.

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

void main() {
  late Process serverProcess;
  const port = 8767;

  setUpAll(() async {
    // frontend/flutter/test/ -> repo root is two levels up.
    final repoRoot = Directory.current.parent.parent.path;
    final pythonExe = Platform.isWindows
        ? '$repoRoot/.venv/Scripts/python.exe'
        : '$repoRoot/.venv/bin/python';

    serverProcess = await Process.start(
      pythonExe,
      ['-u', 'scripts/fake_echo_server.py', '--port', '$port'],
      workingDirectory: repoRoot,
    );

    final ready = Completer<void>();
    serverProcess.stdout.transform(utf8.decoder).listen((line) {
      if (line.contains('listening') && !ready.isCompleted) {
        ready.complete();
      }
    });
    serverProcess.stderr.transform(utf8.decoder).listen((line) => stderr.write('[echo-server] $line'));

    await ready.future.timeout(const Duration(seconds: 10));
  });

  tearDownAll(() {
    serverProcess.kill();
  });

  test('receives stage_hint, streamed tokens over time, then done', () async {
    final channel = WebSocketChannel.connect(Uri.parse('ws://127.0.0.1:$port'));
    await channel.ready;

    final events = <Map<String, dynamic>>[];
    final arrivalTimes = <DateTime>[];
    final doneCompleter = Completer<void>();

    final subscription = channel.stream.listen((raw) {
      events.add(jsonDecode(raw as String) as Map<String, dynamic>);
      arrivalTimes.add(DateTime.now());
      if (events.last['type'] == 'done' && !doneCompleter.isCompleted) {
        doneCompleter.complete();
      }
    });

    channel.sink.add(jsonEncode({'message': 'hello there dart client'}));
    await doneCompleter.future.timeout(const Duration(seconds: 10));
    await subscription.cancel();
    await channel.sink.close();

    // Shape: stage_hint first, then one token per word, then done last.
    expect(events.first['type'], 'stage_hint');
    expect(events.last['type'], 'done');

    final tokenEvents = events.where((e) => e['type'] == 'token').toList();
    expect(tokenEvents.length, 4); // "hello there dart client"
    final reassembled = tokenEvents.map((e) => e['data'] as String).join().trim();
    expect(reassembled, 'hello there dart client');

    // The actual thing being de-risked: tokens must arrive spread out over
    // real wall-clock time (the fake server sleeps 150ms between them), not
    // all buffered and delivered in one microtask burst. A broken/naive
    // stream consumer (e.g. one that accidentally buffers until the socket
    // closes) would make this span collapse to ~0.
    final firstTokenTime = arrivalTimes[events.indexOf(tokenEvents.first)];
    final lastTokenTime = arrivalTimes[events.indexOf(tokenEvents.last)];
    final spread = lastTokenTime.difference(firstTokenTime);
    expect(spread.inMilliseconds, greaterThan(300)); // 3 gaps * 150ms, minus scheduling slack
  });
}
