// What PIP is doing, while it does it.
//
// Every line here is a `stage` event from the backend (shared/ws_spec.py),
// emitted by pipeline.run() as each stage finishes. Nothing on screen is
// invented by this widget: the label and the detail are the backend's own
// sentences, because it is the only side that knows a lookup found three
// passages or none.
//
// The Trace tab already showed all of this - afterwards, on a different
// screen, for a turn that had finished. This is the same information in the
// present tense, which is when somebody actually wants it.

import 'package:flutter/material.dart';

import '../theme.dart';
import 'thinking_orb.dart';

/// One completed step of the pipeline, exactly as the wire carries it.
class ReasoningStep {
  final String stage;
  final String label;
  final String detail;

  /// "ok" | "empty" | "skipped" | "error" - see StageData in ws_spec.py.
  final String status;

  const ReasoningStep({
    required this.stage,
    required this.label,
    required this.detail,
    required this.status,
  });

  factory ReasoningStep.fromEvent(Map<String, dynamic> data) => ReasoningStep(
        stage: '${data['stage'] ?? ''}',
        label: '${data['label'] ?? ''}',
        detail: '${data['detail'] ?? ''}',
        status: '${data['status'] ?? 'ok'}',
      );
}

class ReasoningStrip extends StatelessWidget {
  final List<ReasoningStep> steps;

  /// False once the answer is complete - the strip stays on screen for the
  /// turn it describes, but stops animating.
  final bool active;

  const ReasoningStrip({super.key, required this.steps, required this.active});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    if (steps.isEmpty) {
      // Before the first event lands there is nothing truthful to say, so the
      // orb turns without a claim beside it rather than asserting a stage that
      // may not have run.
      return _Pill(
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          ThinkingOrb(state: active ? OrbState.thinking : OrbState.idle, size: 32),
          const SizedBox(width: AppSpacing.sm),
          Text('Thinking', style: TextStyle(fontSize: 13.5, color: pip.textMuted)),
        ]),
      );
    }

    final current = steps.last;
    // Everything before the last line has finished; the last one is what is
    // happening now, which is why it gets the orb and they get a status dot.
    final finished = steps.sublist(0, steps.length - 1);

    return _Pill(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(mainAxisSize: MainAxisSize.min, children: [
            ThinkingOrb(
              state: active ? orbStateForStage(current.stage) : OrbState.idle,
              size: 32,
            ),
            const SizedBox(width: AppSpacing.sm),
            Flexible(
              child: Text(
                current.label,
                style: TextStyle(fontSize: 13.5, color: pip.text, fontWeight: FontWeight.w600),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            if (current.detail.isNotEmpty) ...[
              const SizedBox(width: AppSpacing.sm),
              Flexible(
                child: Text(
                  current.detail,
                  style: TextStyle(fontSize: 12.5, color: pip.textMuted),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ]),
          if (finished.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            for (final step in finished) _FinishedRow(step: step),
          ],
        ],
      ),
    );
  }
}

class _FinishedRow extends StatelessWidget {
  final ReasoningStep step;
  const _FinishedRow({required this.step});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    // "empty" is not an error and must not be dressed as one - a document
    // search that found nothing is a fact about the question, not a fault.
    // It is also not success, and colouring it like the rest would hide the
    // single most useful thing this strip can tell somebody about a wrong
    // answer.
    final empty = step.status == 'empty';
    final failed = step.status == 'error';
    final dot = failed
        ? pip.danger
        : empty
            ? pip.textFaint
            : pip.accent;

    return Padding(
      padding: const EdgeInsets.only(top: 3, left: 5),
      child: Row(children: [
        Container(
          width: 5,
          height: 5,
          margin: const EdgeInsets.only(right: AppSpacing.sm),
          decoration: BoxDecoration(color: dot, shape: BoxShape.circle),
        ),
        Flexible(
          child: Text(
            step.detail.isEmpty ? step.label : '${step.label} · ${step.detail}',
            style: TextStyle(
              fontSize: 12,
              color: empty ? pip.textFaint : pip.textMuted,
              fontStyle: empty ? FontStyle.italic : FontStyle.normal,
            ),
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ]),
    );
  }
}

class _Pill extends StatelessWidget {
  final Widget child;
  const _Pill({required this.child});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
        padding: const EdgeInsets.fromLTRB(9, 8, AppSpacing.md, 10),
        decoration: BoxDecoration(
          color: pip.surfaceRaised,
          borderRadius: AppRadius.lg,
          border: Border.all(color: pip.border),
        ),
        child: child,
      ),
    );
  }
}
