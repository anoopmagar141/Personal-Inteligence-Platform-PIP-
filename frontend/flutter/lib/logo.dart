// The iris, wherever PIP introduces itself.
//
// One widget rather than an Image.asset at each call site, because the same
// three decisions were being made at every one of them: how big, how much room
// underneath, and what to do when the asset cannot be loaded. A shared widget
// makes the first two consistent and the third correct in one place.
//
// WHERE IT BELONGS, AND WHERE IT DOES NOT
//
// It goes on the screens where somebody is being introduced to the
// application: the launch screen, signing in, choosing a model, onboarding.
// Those are the moments a person is deciding what this thing is.
//
// It does not go in the chat, the profile, or any of the working screens. A
// logo above a conversation is a logo somebody has to look past every time
// they use the product, and PIP already says its name in the window title and
// the taskbar. Branding that repeats stops being branding and becomes
// furniture.

import 'package:flutter/material.dart';

/// The mark, at [size] logical pixels square.
///
/// Falls back to nothing at all - not a placeholder, not a broken-image icon -
/// if the asset is missing. Every screen that uses this says who it is in
/// words directly underneath, so a missing decoration should cost the layout a
/// gap and nothing else. A broken-image glyph on the sign-in screen would look
/// like the application itself was damaged.
class PipLogo extends StatelessWidget {
  final double size;

  const PipLogo({super.key, this.size = 64});

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      'assets/pip-logo.png',
      width: size,
      height: size,
      // The source is 256px square, so it is only ever scaled DOWN. filterQuality
      // medium is what keeps the blade edges clean at 48 and 64.
      filterQuality: FilterQuality.medium,
      errorBuilder: (context, error, stack) => SizedBox(width: size, height: size),
    );
  }
}
