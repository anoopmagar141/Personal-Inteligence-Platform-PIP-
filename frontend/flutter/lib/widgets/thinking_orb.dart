// An animated orb showing what PIP is doing right now.
//
// A Flutter port of the idea behind thinking-orbs (orbs.jakubantalik.com),
// written as a CustomPainter rather than pulled in: that package is a React
// canvas component on npm, and this application is Dart. What ports is the
// design - a cloud of dots whose motion differs per state - and it needs no
// dependency at all, because CustomPainter is the same primitive underneath.
//
// The states here are NOT decorative labels chosen by whoever renders it.
// Each maps to a real stage the backend reports as it happens (see
// pipeline._stage_event and shared/ws_spec.StageEvent), so the motion on
// screen is a readout of what the pipeline is doing rather than a spinner
// that means "busy".

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme.dart';

/// What the orb is depicting, resolved from the backend's stage identifier.
enum OrbState {
  /// Working out the question - a tight, deliberate rotation.
  thinking,

  /// Reaching outward: documents, the web. Dots sweep out and back.
  searching,

  /// Reading what PIP already holds - decisions, profile. Dots pulse inward.
  recalling,

  /// The long one: tokens are arriving. A steady, forward drift.
  writing,

  /// Nothing in flight.
  idle,
}

/// Maps a backend stage identifier onto a motion.
///
/// Lives here rather than in the backend because it is a rendering choice -
/// the wire carries `stage`, `label` and `detail`, and the label is the
/// backend's sentence. What that stage should LOOK like is this file's
/// business, and a client that wanted no animation at all would ignore it.
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

class ThinkingOrb extends StatefulWidget {
  final OrbState state;
  final double size;

  /// Null follows the accent colour, which is what almost every caller wants.
  final Color? color;

  const ThinkingOrb({
    super.key,
    required this.state,
    this.size = 28,
    this.color,
  });

  @override
  State<ThinkingOrb> createState() => _ThinkingOrbState();
}

class _ThinkingOrbState extends State<ThinkingOrb> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    // One long loop rather than a duration per state: the painter reads a
    // continuous clock and derives its own phase, so switching state mid-flight
    // changes the motion without restarting it. Re-running the controller on
    // every stage change would make the orb visibly stutter three times in the
    // first half second, which is exactly when the stages arrive.
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 6),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final color = widget.color ?? context.pip.accent;
    return RepaintBoundary(
      // The transcript above this can be long, and an animation repainting at
      // 60fps inside the same layer would drag every message with it.
      child: SizedBox(
        width: widget.size,
        height: widget.size,
        child: AnimatedBuilder(
          animation: _controller,
          builder: (context, _) => CustomPaint(
            painter: _OrbPainter(
              t: _controller.value,
              state: widget.state,
              color: color,
            ),
          ),
        ),
      ),
    );
  }
}

class _OrbPainter extends CustomPainter {
  final double t;
  final OrbState state;
  final Color color;

  _OrbPainter({required this.t, required this.state, required this.color});

  static const _dotCount = 14;

  @override
  void paint(Canvas canvas, Size size) {
    final centre = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2;
    final paint = Paint()..style = PaintingStyle.fill;

    for (var i = 0; i < _dotCount; i++) {
      // Golden-angle spacing, so the dots never line up into spokes the way an
      // even 2pi/n split does at small counts.
      final seed = i * 2.39996;
      final phase = t * 2 * math.pi;

      late final double distance;
      late final double angle;
      late final double scale;

      switch (state) {
        case OrbState.thinking:
          angle = seed + phase;
          distance = 0.42 + 0.10 * math.sin(phase * 2 + seed);
          scale = 0.75 + 0.25 * math.sin(phase + seed);
          break;
        case OrbState.searching:
          // Sweeping outward and back - reaching for something.
          angle = seed + phase * 0.6;
          distance = 0.28 + 0.52 * (0.5 + 0.5 * math.sin(phase + seed * 0.6));
          scale = 0.55 + 0.45 * math.sin(phase * 1.5 + seed);
          break;
        case OrbState.recalling:
          // Drawing inward - reading something already held.
          angle = seed - phase * 0.4;
          distance = 0.66 - 0.34 * (0.5 + 0.5 * math.sin(phase * 1.2 + seed));
          scale = 0.6 + 0.4 * math.cos(phase + seed);
          break;
        case OrbState.writing:
          // A steady forward drift, faster than the rest: this is the state
          // somebody watches for tens of seconds, so it has to look like
          // progress rather than like waiting.
          angle = seed + phase * 1.6;
          distance = 0.34 + 0.30 * math.sin(seed * 1.7);
          scale = 0.7 + 0.3 * math.sin(phase * 2 + seed);
          break;
        case OrbState.idle:
          angle = seed;
          distance = 0.44;
          scale = 0.5;
          break;
      }

      final offset = Offset(
        centre.dx + math.cos(angle) * distance * radius,
        centre.dy + math.sin(angle) * distance * radius,
      );
      // Opacity tracks scale so dots recede rather than pop.
      paint.color = color.withValues(alpha: (0.25 + 0.55 * scale).clamp(0.0, 1.0));
      canvas.drawCircle(offset, (radius * 0.12 * scale).clamp(0.5, radius), paint);
    }
  }

  @override
  bool shouldRepaint(_OrbPainter old) =>
      old.t != t || old.state != state || old.color != color;
}
