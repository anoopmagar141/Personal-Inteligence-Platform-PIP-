// Tests for the launch checklist.
//
// The screen this replaces chose between two sentences using a retry counter,
// so after eight seconds it said "Still preparing things" whether the database
// was decrypting or nothing was running at all. The tests that matter here are
// therefore about not repeating that in a new form: never claim progress that
// was not reported, never drop a phase this build does not recognise, and
// survive reading a file another process is currently writing.

import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/startup_progress.dart';

String line(String phase, [String detail = '']) =>
    '{"phase": "$phase", "detail": "$detail", "at": "2026-09-01T10:00:00Z"}';

StartupPhase phaseNamed(List<StartupPhase> phases, String id) =>
    phases.firstWhere((p) => p.id == id);

void main() {
  test('no file and no content means no information', () {
    // Deliberately empty rather than a checklist of pending steps: the app
    // cannot tell "nothing has started" from "nothing is reporting", and
    // drawing five hopeful rows would assert the first.
    expect(parseStartupProgress(''), isEmpty);
    expect(parseStartupProgress('   \n\n'), isEmpty);
  });

  test('marks what happened, what is happening, and what has not', () {
    final phases = parseStartupProgress([line('ollama', 'started'), line('profile')].join('\n'));

    expect(phaseNamed(phases, 'ollama').state, StartupPhaseState.done);
    expect(phaseNamed(phases, 'profile').state, StartupPhaseState.current);
    expect(phaseNamed(phases, 'backend').state, StartupPhaseState.pending);
    expect(phaseNamed(phases, 'ready').state, StartupPhaseState.pending);
  });

  test('keeps the detail, which is where "already running" lives', () {
    // The difference between a fast launch and a broken one.
    final phases = parseStartupProgress(line('ollama', 'already running'));
    expect(phaseNamed(phases, 'ollama').detail, 'already running');
  });

  test('drops a detail that only restates the label', () {
    // "Backend listening / backend listening" is how this first shipped, and
    // it was visible the moment the app was actually run. Three separate
    // writers produce these strings, so the guard lives with the labels.
    final phases = parseStartupProgress(line('ready', 'Backend listening'));
    expect(phaseNamed(phases, 'ready').detail, isEmpty);

    // A detail that adds something is kept.
    final kept = parseStartupProgress(line('ready', 'already listening'));
    expect(phaseNamed(kept, 'ready').detail, 'already listening');
  });

  test('orders by the canonical list, not by the order lines arrived', () {
    // Asserted as relative position rather than as a fixed prefix. The prefix
    // form broke the moment a phase was inserted between these two - which is a
    // change to the launch sequence, not to the property being tested here.
    final phases = parseStartupProgress([line('profile'), line('ollama')].join('\n'));
    final ids = phases.map((p) => p.id).toList();
    expect(ids.indexOf('ollama'), lessThan(ids.indexOf('profile')));
  });

  test('a skipped step is not left unresolved behind a later one', () {
    // The launcher omits the profile phase on a single-profile install, and
    // every phase when the backend was already running. ('key' used to be here:
    // the launcher no longer derives a key, the sign-in screen does.)
    // Those steps did happen - on the launch that started it - so the list
    // must not sit forever on a spinner for a step that will never report.
    final phases = parseStartupProgress([line('ollama'), line('ready')].join('\n'));

    expect(phaseNamed(phases, 'profile').state, StartupPhaseState.done);
    expect(phaseNamed(phases, 'backend').state, StartupPhaseState.done);
    expect(phaseNamed(phases, 'ready').state, StartupPhaseState.current);
  });

  test('survives a line being written while it is read', () {
    // Appending is not atomic. One torn line is not a reason to report
    // nothing - the phases before it are still true.
    final torn = '${line('ollama')}\n{"phase": "key", "det';
    final phases = parseStartupProgress(torn);

    expect(phaseNamed(phases, 'ollama').state, StartupPhaseState.current);
    expect(phases, isNotEmpty);
  });

  test('shows a phase this build has no label for', () {
    // A phase added to the backend and not here is a version skew, and a
    // launch screen is the worst place to hide one.
    final phases = parseStartupProgress([line('ollama'), line('migrating', 'schema v4')].join('\n'));

    final extra = phaseNamed(phases, 'migrating');
    expect(extra.label, 'migrating');
    expect(extra.detail, 'schema v4');
    expect(extra.state, StartupPhaseState.current);
  });

  test('ignores lines that are not phase records', () {
    final phases = parseStartupProgress(
      ['not json at all', '{"noise": 1}', '[]', line('ollama')].join('\n'),
    );
    expect(phaseNamed(phases, 'ollama').state, StartupPhaseState.current);
  });

  test('parses what PowerShell actually writes, CRLF and all', () {
    // The one seam nothing else covers: the launcher writes these lines from
    // PowerShell and this parser reads them in Dart. Captured verbatim from
    // `ConvertTo-Json -Compress` piped through Add-Content, which also means
    // CRLF line endings rather than the LF the Python side writes.
    const fromPowerShell =
        '{"phase":"ollama","detail":"already running","at":"2026-09-01T13:21:21Z"}\r\n'
        '{"phase":"profile","detail":"Work","at":"2026-09-01T13:21:21Z"}\r\n';

    final phases = parseStartupProgress(fromPowerShell);

    expect(phaseNamed(phases, 'ollama').detail, 'already running');
    expect(phaseNamed(phases, 'ollama').state, StartupPhaseState.done);
    expect(phaseNamed(phases, 'profile').state, StartupPhaseState.current);
  });

  group('startupIsReady', () {
    test('is true once the backend reports it is serving', () {
      expect(startupIsReady(parseStartupProgress(line('ready'))), isTrue);
    });

    test('is false while it is still coming up', () {
      expect(startupIsReady(parseStartupProgress(line('backend'))), isFalse);
      expect(startupIsReady(parseStartupProgress('')), isFalse);
    });
  });
}
