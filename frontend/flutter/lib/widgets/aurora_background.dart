// A slow drifting glow behind the chat.
//
// The reference this came from (a dark landing page with a bright purple arc)
// could not be lifted directly: it is a fixed background image on a hardcoded
// near-black page, and PIP ships light and dark and gets its colours from
// PipPalette. So the glow is painted from the accent colour at low alpha, and
// the two themes get different intensities - what reads as a soft wash on a
// near-white page is invisible, and what reads on black is a smear on white.
//
// Deliberately slow. This repaints continuously behind a scrolling transcript,
// on a desktop application somebody leaves open all day, so a 30-second cycle
// with three blurred circles is the whole budget - enough that the page is not
// static, cheap enough that nobody's fan notices. It is decoration and it is
// allowed to cost nothing.

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme.dart';

class AuroraBackground extends StatefulWidget {
  final Widget child;
  const AuroraBackground({super.key, required this.child});

  @override
  State<AuroraBackground> createState() => _AuroraBackgroundState();
}

class _AuroraBackgroundState extends State<AuroraBackground>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    // Started in build() rather than here, because whether it should run at
    // all depends on MediaQuery, which is not available yet.
    _controller = AnimationController(vsync: this, duration: const Duration(seconds: 30));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    final dark = Theme.of(context).brightness == Brightness.dark;

    // Somebody who has asked their operating system to reduce motion has
    // asked for exactly this: a decorative thing that moves forever behind
    // what they are reading. The glow stays - it is a colour wash, not an
    // animation - and simply stops drifting.
    //
    // It also makes this widget testable. A repeating controller means
    // pumpAndSettle can never settle, and dropping it into the chat screen
    // broke five existing tests that had every right to use it. Fixing that by
    // rewriting those tests would have been fixing the wrong thing.
    final still = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (still) {
      if (_controller.isAnimating) _controller.stop();
    } else if (!_controller.isAnimating) {
      _controller.repeat();
    }

    return Stack(
      children: [
        Positioned.fill(
          // The glow is its own layer, so the transcript scrolling above it
          // never repaints because of it and it never repaints because of the
          // transcript. Without this the two would share a layer and every
          // frame of a 30-second animation would redraw the whole message
          // list.
          child: RepaintBoundary(
            child: AnimatedBuilder(
              animation: _controller,
              builder: (context, _) => CustomPaint(
                painter: _AuroraPainter(
                  t: _controller.value,
                  color: pip.accent,
                  // Dark backgrounds swallow a wash that would be obvious on
                  // white, so the two are not the same number with a theme
                  // switch in front of them.
                  //
                  // 0.17 was too much, seen on a real screen rather than
                  // guessed at: over a near-black page it stopped reading as
                  // ambient light and started reading as a purple stain with
                  // an edge. Alpha also drives the banding - the fewer levels
                  // a gradient spans, the wider each band - so lowering it
                  // helps the same defect the extra gradient stops address.
                  strength: dark ? 0.10 : 0.07,
                ),
              ),
            ),
          ),
        ),
        widget.child,
      ],
    );
  }
}

class _AuroraPainter extends CustomPainter {
  final double t;
  final Color color;
  final double strength;

  _AuroraPainter({required this.t, required this.color, required this.strength});

  @override
  void paint(Canvas canvas, Size size) {
    final phase = t * 2 * math.pi;

    // Three blobs on slow, unequal orbits, so the pattern never visibly
    // repeats on the scale anybody watches it. Anchored low and wide: the
    // composer sits at the bottom of this area and the glow belongs behind
    // it, not behind the text somebody is reading.
    final blobs = <({Offset centre, double radius, double alpha})>[
      (
        centre: Offset(size.width * (0.5 + 0.16 * math.sin(phase)),
            size.height * (0.92 + 0.05 * math.cos(phase * 0.8))),
        radius: size.width * 0.58,
        alpha: strength,
      ),
      (
        centre: Offset(size.width * (0.22 + 0.10 * math.cos(phase * 0.7)),
            size.height * (0.78 + 0.06 * math.sin(phase * 1.1))),
        radius: size.width * 0.44,
        alpha: strength * 0.7,
      ),
      (
        centre: Offset(size.width * (0.80 + 0.09 * math.sin(phase * 1.3)),
            size.height * (0.70 + 0.07 * math.cos(phase))),
        radius: size.width * 0.38,
        alpha: strength * 0.55,
      ),
    ];

    for (final blob in blobs) {
      canvas.drawCircle(
        blob.centre,
        blob.radius,
        Paint()
          ..shader = RadialGradient(
            // Five stops approximating a gaussian falloff, not two.
            //
            // A two-stop gradient fades linearly, and a linear fade to zero
            // has a corner in it at the outer edge - the rate of change stops
            // dead. Over a large radius on a near-black page that corner is
            // visible as an arc, which is exactly what it looked like: a
            // smudge with a boundary rather than light with none. The extra
            // stops round that corner off so the falloff approaches zero
            // gradually instead of arriving there.
            colors: [
              color.withValues(alpha: blob.alpha),
              color.withValues(alpha: blob.alpha * 0.72),
              color.withValues(alpha: blob.alpha * 0.36),
              color.withValues(alpha: blob.alpha * 0.11),
              color.withValues(alpha: 0),
            ],
            stops: const [0.0, 0.28, 0.55, 0.78, 1.0],
          ).createShader(Rect.fromCircle(center: blob.centre, radius: blob.radius)),
      );
    }
  }

  @override
  bool shouldRepaint(_AuroraPainter old) =>
      old.t != t || old.color != color || old.strength != strength;
}
