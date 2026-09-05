// The launch screen's background: a field of dots warped into streams that
// converge on a bright waist and open out again.
//
// Written from the design, not ported from it. The component this follows
// (ThreeUI's "Gateway Flow", seen via 21st.dev) keeps its source behind a
// paywall on both sites, so nothing here is derived from their code - what was
// available was the picture and a one-line description, which is enough to
// build the same idea in a CustomPainter and no basis at all for claiming this
// is their implementation.
//
// WHY THE GRID IS WARPED RATHER THAN DRAWN AS CURVES
//
// The streams look like bezier paths and are cheaper than that. Every dot sits
// on a plain grid, and its row is pulled toward the centre line by how close
// its column is to the waist - at the waist the pull is total and every row
// collapses onto one point, far from it there is no pull at all. That single
// multiply produces the whole hourglass, with no path objects, no sampling
// along a curve, and no per-frame allocation beyond the point lists.
//
// WHY IT MATTERS THAT IT IS CHEAP
//
// This is on screen for about ten seconds while the backend starts, and that
// backend is opening SQLCipher, loading chromadb and warming an embedding
// model. An animation that competes with the startup it is reporting would be
// a poor trade for decoration. So the dots are drawn with drawPoints batched
// into a handful of brightness tiers - four or five draw calls a frame for
// roughly two thousand dots, instead of two thousand drawCircle calls.

import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

/// The stage colour. Deliberately fixed rather than themed - see the note on
/// [GatewayFlow] about why the launch screen is dark in both themes.
const _stage = Color(0xFF060608);

class GatewayFlow extends StatefulWidget {
  /// Drawn on top of the field.
  final Widget child;

  /// The accent used to tint the convergence. Defaults to PIP's indigo.
  final Color tint;

  const GatewayFlow({
    super.key,
    required this.child,
    this.tint = const Color(0xFF6D66F0),
  });

  @override
  State<GatewayFlow> createState() => _GatewayFlowState();
}

class _GatewayFlowState extends State<GatewayFlow> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  /// Where a tap landed and when, for the shockwave. Null until somebody taps.
  Offset? _rippleAt;
  double _rippleStartedAt = 0;

  @override
  void initState() {
    super.initState();
    // Long, because the drift should read as a current rather than as a loop.
    _controller = AnimationController(vsync: this, duration: const Duration(seconds: 24));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _ripple(Offset position) {
    setState(() {
      _rippleAt = position;
      _rippleStartedAt = _controller.value;
    });
  }

  @override
  Widget build(BuildContext context) {
    // Same rule the chat background follows: a viewer who has asked for less
    // motion gets the field without the drift, not a blank screen.
    final still = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (still) {
      if (_controller.isAnimating) _controller.stop();
    } else if (!_controller.isAnimating) {
      _controller.repeat();
    }

    return ColoredBox(
      color: _stage,
      child: GestureDetector(
        onTapDown: still ? null : (details) => _ripple(details.localPosition),
        child: Stack(
          children: [
            Positioned.fill(
              child: RepaintBoundary(
                child: AnimatedBuilder(
                  animation: _controller,
                  builder: (context, _) => CustomPaint(
                    painter: _GatewayPainter(
                      t: _controller.value,
                      tint: widget.tint,
                      rippleAt: _rippleAt,
                      // Wraps at 1.0, so a ripple started at 0.98 does not
                      // read as having happened in the future for the rest of
                      // the cycle.
                      rippleAge: _rippleAt == null
                          ? null
                          : (_controller.value - _rippleStartedAt + 1) % 1.0,
                    ),
                  ),
                ),
              ),
            ),
            widget.child,
          ],
        ),
      ),
    );
  }
}

class _GatewayPainter extends CustomPainter {
  final double t;
  final Color tint;
  final Offset? rippleAt;
  final double? rippleAge;

  _GatewayPainter({
    required this.t,
    required this.tint,
    this.rippleAt,
    this.rippleAge,
  });

  static const _columns = 96;
  static const _rows = 24;

  /// Where the streams pinch, in fractions of the canvas.
  static const _waistX = 0.62;
  static const _waistY = 0.5;

  /// Dots are bucketed into this many brightness tiers, and each tier is one
  /// drawPoints call. More tiers is a smoother gradient and more draw calls;
  /// five is where the banding stops being visible.
  static const _tiers = 5;

  /// How long a shockwave lasts, as a fraction of the controller's cycle.
  static const _rippleLife = 0.06;

  @override
  void paint(Canvas canvas, Size size) {
    final phase = t * 2 * math.pi;
    final buckets = List.generate(_tiers, (_) => <Offset>[]);

    for (var c = 0; c < _columns; c++) {
      // Drift moves the SAMPLE along x rather than moving the dots, so nothing
      // ever leaves the canvas and no dot needs recycling - the field streams
      // without a particle system behind it.
      final x = ((c / _columns) + t * 0.15) % 1.0;

      // 0 at the waist, 1 at the far edge. Squared, so the pinch is tight at
      // the centre and the field stays open across most of the width - a
      // linear falloff makes an X rather than a gateway.
      final pinch = math.pow((x - _waistX).abs() / math.max(_waistX, 1 - _waistX), 2).toDouble();

      for (var r = 0; r < _rows; r++) {
        final row = r / (_rows - 1) - 0.5;

        // The whole shape, in one line.
        var y = _waistY + row * pinch * 1.15;

        // A slow vertical breathing, so the bands are not perfectly rigid.
        y += 0.012 * math.sin(phase + c * 0.15 + r * 0.4) * pinch;

        var point = Offset(x * size.width, y * size.height);

        // The shockwave: a ring expanding from the tap, pushing dots outward
        // as it passes and letting them settle behind it.
        if (rippleAt != null && rippleAge != null && rippleAge! < _rippleLife) {
          final progress = rippleAge! / _rippleLife;
          final delta = point - rippleAt!;
          final distance = delta.distance;
          final front = progress * size.width * 0.9;
          final band = size.width * 0.10;
          final closeness = 1 - ((distance - front).abs() / band).clamp(0.0, 1.0);
          if (closeness > 0 && distance > 0.001) {
            final push = closeness * (1 - progress) * 26;
            point += delta / distance * push;
          }
        }

        if (point.dy < -8 || point.dy > size.height + 8) continue;

        // Brightest at the waist, where the streams are densest.
        final brightness = (1 - pinch) * 0.85 + 0.15;
        buckets[(brightness * (_tiers - 1)).round().clamp(0, _tiers - 1)].add(point);
      }
    }

    for (var tier = 0; tier < _tiers; tier++) {
      if (buckets[tier].isEmpty) continue;
      final level = tier / (_tiers - 1);
      // Warm white at the edges, tinted toward the accent as it converges -
      // the reference is monochrome, and a PIP launch screen that is entirely
      // colourless would not read as this application's.
      final colour = Color.lerp(const Color(0xFFBFC4D8), tint, level * 0.75)!;
      canvas.drawPoints(
        ui.PointMode.points,
        buckets[tier],
        Paint()
          ..color = colour.withValues(alpha: 0.10 + level * 0.75)
          ..strokeWidth = 1.0 + level * 1.4
          ..strokeCap = StrokeCap.round,
      );
    }

    // The glow at the convergence, drawn last so it sits over the densest dots.
    final waist = Offset(size.width * _waistX, size.height * _waistY);
    canvas.drawCircle(
      waist,
      size.width * 0.09,
      Paint()
        ..shader = RadialGradient(
          colors: [tint.withValues(alpha: 0.30), tint.withValues(alpha: 0)],
        ).createShader(Rect.fromCircle(center: waist, radius: size.width * 0.09)),
    );
  }

  @override
  bool shouldRepaint(_GatewayPainter old) =>
      old.t != t || old.tint != tint || old.rippleAt != rippleAt || old.rippleAge != rippleAge;
}
