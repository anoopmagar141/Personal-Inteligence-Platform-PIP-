// What the launch screen shows instead of a spinner and a guess.
//
// The old screen picked between two sentences using a RETRY COUNTER: "Starting
// PIP..." for the first seven attempts, "Still preparing things - this can
// take a little longer on first launch..." after that. Neither came from
// anything happening. After eight seconds it said the same thing whether the
// database was being decrypted or nothing was running at all, which is the
// difference between "wait" and "this is broken".
//
// The real phases are written to data/startup.jsonl - by scripts/launch_pip.ps1
// for the parts that happen before uvicorn exists (Ollama, the password), and
// by backend/core/startup_progress.py from the instance lock onwards. A file
// rather than an endpoint because FastAPI's lifespan blocks serving until it
// finishes: nothing HTTP-shaped can report on a server that is not up yet.
// This app already polls a file on exactly this path for exactly this reason
// (data/api_token.txt), so it is reading a second file next to one it reads.
//
// Part 14.4 still holds. Nothing here decides anything: the backend says which
// phase it reached, and this turns a phase id into a sentence. An id it does
// not recognise is shown as itself rather than dropped, because an unfamiliar
// phase during a slow startup is exactly when someone needs to see it.

import 'dart:convert';

/// The phases a launch goes through, in order, with what to call each on
/// screen. Order is this list's, not the file's: the file records what
/// happened, and a launch that skipped a step should still show the step in
/// the place it would have occupied.
const startupPhaseLabels = <String, String>{
  'ollama': 'Local model service',
  'key': 'Unlocking your data',
  'backend': 'Starting PIP Core',
  'lock': 'Checking nothing else is running',
  'ready': 'Backend listening',
};

enum StartupPhaseState { done, current, pending }

class StartupPhase {
  final String id;
  final String label;
  final String detail;
  final StartupPhaseState state;
  const StartupPhase({
    required this.id,
    required this.label,
    required this.detail,
    required this.state,
  });
}

/// Parses the raw file into the ordered checklist to draw.
///
/// A phase earlier in the canonical order than the newest reported one is
/// shown complete even if its own line never arrived. That is not a guess
/// about the system: the launcher reports Ollama and the key on every path
/// where they are part of THIS launch, and omits them only when the backend
/// was already running - in which case they genuinely did happen, on the
/// launch that started it.
///
/// Returns an empty list for empty or unparseable input, which the caller
/// treats as "no information" rather than "nothing has happened".
List<StartupPhase> parseStartupProgress(String contents) {
  final reported = <String, String>{};
  final order = <String>[];

  for (final line in const LineSplitter().convert(contents)) {
    if (line.trim().isEmpty) continue;
    Object? decoded;
    try {
      decoded = jsonDecode(line);
    } catch (_) {
      // A reader can arrive mid-write. One torn line is not a reason to
      // report nothing - the phases before it are still true.
      continue;
    }
    if (decoded is! Map) continue;
    final id = decoded['phase'];
    if (id is! String || id.isEmpty) continue;
    final detail = '${decoded['detail'] ?? ''}';
    // A detail that merely restates the label is noise - "Backend listening /
    // backend listening" is how this first shipped. Dropped here rather than
    // only fixed at the writers, because there are three of them (this file's
    // labels, the PowerShell launcher, and the Python module) and nothing else
    // makes them agree.
    reported[id] =
        detail.toLowerCase() == (startupPhaseLabels[id] ?? '').toLowerCase() ? '' : detail;
    order.add(id);
  }

  if (order.isEmpty) return const [];

  final known = startupPhaseLabels.keys.toList();
  final latest = order.last;
  // An unknown phase id cannot be placed in the canonical order, so it is
  // treated as the furthest point reached and everything known is complete.
  final reachedIndex = known.indexOf(latest);

  final phases = <StartupPhase>[
    for (var i = 0; i < known.length; i++)
      StartupPhase(
        id: known[i],
        label: startupPhaseLabels[known[i]]!,
        detail: reported[known[i]] ?? '',
        state: reachedIndex < 0
            ? StartupPhaseState.done
            : i < reachedIndex
                ? StartupPhaseState.done
                : i == reachedIndex
                    ? StartupPhaseState.current
                    : StartupPhaseState.pending,
      ),
  ];

  // Anything the file reported that this build has no label for still gets a
  // row, under its own id. A phase added to the backend and not here is a
  // version skew, and the launch screen is the worst place to hide one.
  for (final id in order) {
    if (startupPhaseLabels.containsKey(id)) continue;
    phases.add(StartupPhase(
      id: id,
      label: id,
      detail: reported[id] ?? '',
      state: id == latest ? StartupPhaseState.current : StartupPhaseState.done,
    ));
  }

  return phases;
}

/// Whether the backend has reported that it is serving.
bool startupIsReady(List<StartupPhase> phases) =>
    phases.any((p) => p.id == 'ready' && p.state != StartupPhaseState.pending);
