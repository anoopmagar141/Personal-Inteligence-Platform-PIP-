// What PIP is doing, drawn as its own mark turning.
//
// This replaced a CustomPainter cloud of dots. The dots were a port of an idea
// from elsewhere and never looked like they belonged to this product - and
// once the six-node mark shipped everywhere else, a second, unrelated piece of
// motion beside it read as two applications sharing a window.
//
// So the thing that turns is the mark itself. Nothing else changes: the STATES
// below are unchanged and still resolve from the backend's own stage
// identifiers, so the motion is a readout of what the pipeline is doing rather
// than a spinner that means "busy". A spinner that means busy is the thing
// this is deliberately not.
//
// WHY THE ROTATION DOES NOT VARY WITH THE STATE
//
// It was going to: slow for recalling, fast for searching. An
// AnimationController cannot change speed without restarting its simulation,
// so every stage boundary would snap the mark back to zero degrees - and this
// mark has six differently coloured nodes, so that snap is plainly visible. A
// stutter several times per answer is a worse signal than a steady turn.
//
// The state still decides whether it turns AT ALL, which is the part that
// carries information: motion means working, stillness means finished. What
// PIP is actually doing is said in words beside it, by the backend, which is
// the only side that knows.

import 'package:flutter/material.dart';

import '../logo.dart';

/// What the mark is depicting, resolved from the backend's stage identifier.
enum OrbState {
  /// Working out the question.
  thinking,

  /// Reaching outside the machine.
  searching,

  /// Reading its own memory.
  recalling,

  /// Producing the answer.
  writing,

  /// Nothing is happening. The mark holds still rather than idling, because a
  /// thing that never stops turning stops meaning anything.
  idle,
}

/// The backend's stage identifier, mapped to what to draw.
///
/// Unrecognised and null both resolve to idle rather than to a guess: a stage
/// this build has never heard of is not an excuse to invent a state for it.
OrbState orbStateForStage(String? stage) {
  switch (stage) {
    case 'intent':
      return OrbState.thinking;
    case 'documents':
    case 'web':
      return OrbState.searching;
    case 'decisions':
    case 'profile':
    case 'cache':
      return OrbState.recalling;
    case 'writing':
      return OrbState.writing;
    default:
      return OrbState.idle;
  }
}

/// One word for what is happening, for the case where the backend has not sent
/// a label yet.
///
/// Only used before the first stage event lands. Once there is one, the label
/// on screen is the backend's own sentence - it is the only side that knows a
/// lookup found three passages or none, and inventing a friendlier word here
/// would be this widget claiming something it cannot see.
String defaultLabelFor(OrbState state) => switch (state) {
      OrbState.thinking => 'Thinking',
      OrbState.searching => 'Searching',
      OrbState.recalling => 'Remembering',
      OrbState.writing => 'Writing',
      OrbState.idle => 'Done',
    };

/// The mark, turning at a rate that depends on [state].
class ThinkingMark extends StatefulWidget {
  final OrbState state;
  final double size;

  const ThinkingMark({super.key, required this.state, this.size = 32});

  @override
  State<ThinkingMark> createState() => _ThinkingMarkState();
}

class _ThinkingMarkState extends State<ThinkingMark> with SingleTickerProviderStateMixin {
  /// One turn every 1.6s - fast enough to read as working, slow enough that it
  /// is not competing with the tokens arriving beside it.
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1600),
  );

  @override
  void initState() {
    super.initState();
    _apply();
  }

  @override
  void didUpdateWidget(ThinkingMark old) {
    super.didUpdateWidget(old);
    if (old.state != widget.state) _apply();
  }

  /// Turning or still - the only thing the state decides here.
  ///
  /// Stopped rather than reset on idle: the mark holds the angle it reached,
  /// so a finished answer leaves it parked wherever it got to instead of
  /// snapping upright and drawing the eye back to a turn that has ended.
  void _apply() {
    if (widget.state == OrbState.idle) {
      _controller.stop();
    } else if (!_controller.isAnimating) {
      _controller.repeat();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // RepaintBoundary because this turns continuously beside a transcript that
    // is appending tokens - without it the rotation marks the whole strip
    // dirty on every frame.
    return RepaintBoundary(
      child: RotationTransition(
        turns: _controller,
        child: PipLogo(size: widget.size),
      ),
    );
  }
}
