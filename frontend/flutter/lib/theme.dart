// PIP design system - "Clarity", now in two skins.
// System fonts only - no new package, no network font fetch.
//
// The palette used to be a class of `static const` Colors, which is why the
// app was light-only: a compile-time constant cannot vary with the theme, and
// half the widget tree referenced those constants from inside `const`
// constructors. Dark mode was therefore not a matter of adding colors - it
// required the colors to become values that are looked up per build.
//
// So the palette is a ThemeExtension carried on ThemeData, read through
// `context.pip`. Two instances, one per brightness, with the same field names
// meaning the same things in both: `surface` is whatever a card sits on,
// `textMuted` is secondary text, `accentOn` is whatever is legible ON the
// accent. Nothing in the widget tree asks which mode it is in, and there is no
// `if (dark)` anywhere - a screen that needed one would mean the two palettes
// had stopped being the same design.

import 'package:flutter/material.dart';

@immutable
class PipPalette extends ThemeExtension<PipPalette> {
  final Color bg;
  final Color surface;
  final Color surfaceRaised;
  final Color border;
  final Color text;
  final Color textMuted;
  final Color textFaint;
  final Color accent;
  final Color accentSoft;
  final Color accentOn;
  final Color danger;
  final Color dangerSoft;

  const PipPalette({
    required this.bg,
    required this.surface,
    required this.surfaceRaised,
    required this.border,
    required this.text,
    required this.textMuted,
    required this.textFaint,
    required this.accent,
    required this.accentSoft,
    required this.accentOn,
    required this.danger,
    required this.dangerSoft,
  });

  /// Two values here are darker than the palette this started from, and the
  /// reason is measured rather than aesthetic (see test/theme_test.dart):
  ///
  ///   * textFaint was #A0A4B2, which is 2.49:1 on white - under even the 3:1
  ///     large-text minimum, on the timestamps and source labels that carry
  ///     the provenance of everything PIP claims to know.
  ///   * danger was #DC2626, which is 4.23:1 on its own soft tint - the exact
  ///     pairing used for refusal messages, i.e. the text that appears
  ///     precisely when something has gone wrong.
  static const light = PipPalette(
    bg: Color(0xFFF7F8FB),
    surface: Color(0xFFFFFFFF),
    surfaceRaised: Color(0xFFF0F1F6),
    border: Color(0xFFE3E6ED),
    text: Color(0xFF1A1D26),
    textMuted: Color(0xFF6B7080),
    textFaint: Color(0xFF8A8FA0),
    accent: Color(0xFF4F46E5),
    accentSoft: Color(0xFFEEF0FD),
    accentOn: Color(0xFFFFFFFF),
    danger: Color(0xFFC81E1E),
    dangerSoft: Color(0xFFFDECEC),
  );

  /// Not the light palette inverted. Two things are deliberately different in
  /// kind rather than in value:
  ///
  ///   * the accent is lightened, because the indigo that reads as emphasis on
  ///     white reads as almost-black on a dark ground;
  ///   * `accentOn` flips to a dark ink. White on a lightened indigo is the
  ///     weakest contrast pairing in the whole set, and it is used on the one
  ///     thing that must always be readable - the primary button.
  static const dark = PipPalette(
    bg: Color(0xFF0F1117),
    surface: Color(0xFF161922),
    surfaceRaised: Color(0xFF1E222D),
    border: Color(0xFF2A2F3D),
    text: Color(0xFFE8EAF0),
    textMuted: Color(0xFF9AA0B0),
    textFaint: Color(0xFF6B7080),
    accent: Color(0xFF8B8BF5),
    accentSoft: Color(0xFF232447),
    accentOn: Color(0xFF14162B),
    danger: Color(0xFFF87171),
    dangerSoft: Color(0xFF3A1F22),
  );

  @override
  PipPalette copyWith({
    Color? bg,
    Color? surface,
    Color? surfaceRaised,
    Color? border,
    Color? text,
    Color? textMuted,
    Color? textFaint,
    Color? accent,
    Color? accentSoft,
    Color? accentOn,
    Color? danger,
    Color? dangerSoft,
  }) {
    return PipPalette(
      bg: bg ?? this.bg,
      surface: surface ?? this.surface,
      surfaceRaised: surfaceRaised ?? this.surfaceRaised,
      border: border ?? this.border,
      text: text ?? this.text,
      textMuted: textMuted ?? this.textMuted,
      textFaint: textFaint ?? this.textFaint,
      accent: accent ?? this.accent,
      accentSoft: accentSoft ?? this.accentSoft,
      accentOn: accentOn ?? this.accentOn,
      danger: danger ?? this.danger,
      dangerSoft: dangerSoft ?? this.dangerSoft,
    );
  }

  @override
  PipPalette lerp(ThemeExtension<PipPalette>? other, double t) {
    if (other is! PipPalette) return this;
    return PipPalette(
      bg: Color.lerp(bg, other.bg, t)!,
      surface: Color.lerp(surface, other.surface, t)!,
      surfaceRaised: Color.lerp(surfaceRaised, other.surfaceRaised, t)!,
      border: Color.lerp(border, other.border, t)!,
      text: Color.lerp(text, other.text, t)!,
      textMuted: Color.lerp(textMuted, other.textMuted, t)!,
      textFaint: Color.lerp(textFaint, other.textFaint, t)!,
      accent: Color.lerp(accent, other.accent, t)!,
      accentSoft: Color.lerp(accentSoft, other.accentSoft, t)!,
      accentOn: Color.lerp(accentOn, other.accentOn, t)!,
      danger: Color.lerp(danger, other.danger, t)!,
      dangerSoft: Color.lerp(dangerSoft, other.dangerSoft, t)!,
    );
  }
}

extension PipThemeContext on BuildContext {
  /// The palette for the theme in force at this point in the tree.
  ///
  /// Falls back to the light palette rather than throwing when no theme
  /// carries the extension - a widget pumped bare in a test should render, not
  /// crash on a null assertion that says nothing about what the test was for.
  PipPalette get pip => Theme.of(this).extension<PipPalette>() ?? PipPalette.light;
}

class AppSpacing {
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 16.0;
  static const lg = 24.0;
  static const xl = 32.0;
}

class AppRadius {
  static const sm = BorderRadius.all(Radius.circular(8));
  static const md = BorderRadius.all(Radius.circular(12));
  static const lg = BorderRadius.all(Radius.circular(18));
}

class AppTheme {
  // Kept for call sites that still reference a monospace treatment (rare,
  // used only for literal IDs/paths now) - the system default elsewhere.
  static const mono = 'monospace';

  static ThemeData get light => _build(Brightness.light, PipPalette.light);
  static ThemeData get dark => _build(Brightness.dark, PipPalette.dark);

  /// One builder for both, taking the palette as an argument. Two hand-written
  /// ThemeDatas would drift: the light one has been tuned repeatedly, and a
  /// dark twin maintained beside it would quietly stop matching.
  static ThemeData _build(Brightness brightness, PipPalette pip) {
    final base = ThemeData(
      brightness: brightness,
      scaffoldBackgroundColor: pip.bg,
      colorScheme: ColorScheme.fromSeed(
        seedColor: pip.accent,
        brightness: brightness,
      ).copyWith(
        surface: pip.bg,
        primary: pip.accent,
        onPrimary: pip.accentOn,
        secondary: pip.accent,
        error: pip.danger,
      ),
      useMaterial3: true,
    );
    return base.copyWith(
      extensions: [pip],
      textTheme: base.textTheme.apply(
        bodyColor: pip.text,
        displayColor: pip.text,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: pip.surface,
        foregroundColor: pip.text,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: pip.surface,
        surfaceTintColor: Colors.transparent,
      ),
      cardTheme: CardThemeData(
        color: pip.surface,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: AppRadius.md, side: BorderSide(color: pip.border)),
        margin: EdgeInsets.zero,
      ),
      dividerTheme: DividerThemeData(color: pip.border, space: 1),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: pip.surface,
        hintStyle: TextStyle(color: pip.textFaint, fontSize: 14),
        labelStyle: TextStyle(color: pip.textMuted),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        border: OutlineInputBorder(borderRadius: AppRadius.sm, borderSide: BorderSide(color: pip.border)),
        enabledBorder: OutlineInputBorder(borderRadius: AppRadius.sm, borderSide: BorderSide(color: pip.border)),
        focusedBorder: OutlineInputBorder(borderRadius: AppRadius.sm, borderSide: BorderSide(color: pip.accent, width: 1.5)),
        errorBorder: OutlineInputBorder(borderRadius: AppRadius.sm, borderSide: BorderSide(color: pip.danger)),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: pip.accent,
          foregroundColor: pip.accentOn,
          textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: AppRadius.sm),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: pip.accent,
          textStyle: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600),
        ),
      ),
      chipTheme: base.chipTheme.copyWith(
        backgroundColor: pip.surfaceRaised,
        labelStyle: TextStyle(fontSize: 12.5, color: pip.textMuted),
        side: BorderSide(color: pip.border),
        shape: RoundedRectangleBorder(borderRadius: AppRadius.sm),
      ),
      dataTableTheme: DataTableThemeData(
        headingTextStyle: TextStyle(fontSize: 11.5, color: pip.textMuted, letterSpacing: 0.3, fontWeight: FontWeight.w600),
        dataTextStyle: TextStyle(fontSize: 13.5, color: pip.text),
        dividerThickness: 1,
      ),
      progressIndicatorTheme: ProgressIndicatorThemeData(color: pip.accent),
    );
  }
}

/// Small label used for section eyebrows and status text - sentence case,
/// muted by default.
///
/// [color] is nullable rather than defaulting to a constant: a default
/// argument must be a compile-time constant, which is exactly what a
/// theme-dependent color cannot be. Null means "the palette's muted text".
class TagLabel extends StatelessWidget {
  final String text;
  final Color? color;
  final double size;
  const TagLabel(this.text, {super.key, this.color, this.size = 12});

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: TextStyle(fontSize: size, color: color ?? context.pip.textMuted, fontWeight: FontWeight.w600),
    );
  }
}

/// Shared page header (a small accent eyebrow + title + optional description)
/// used at the top of every CRUD view for a consistent rhythm across screens.
class PageHeader extends StatelessWidget {
  final String eyebrow;
  final String title;
  final String? description;
  const PageHeader({super.key, required this.eyebrow, required this.title, this.description});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TagLabel(eyebrow.toUpperCase(), color: pip.accent, size: 11),
        const SizedBox(height: AppSpacing.xs),
        Text(title, style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: pip.text)),
        if (description != null) ...[
          const SizedBox(height: 4),
          Text(description!, style: TextStyle(fontSize: 13.5, color: pip.textMuted, height: 1.5)),
        ],
        const SizedBox(height: AppSpacing.lg),
      ],
    );
  }
}

/// A bordered, softly-shadowed card - the base surface for every list item and
/// form on a CRUD screen.
class SectionCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  const SectionCard({super.key, required this.child, this.padding = const EdgeInsets.all(AppSpacing.lg)});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: pip.surface,
        borderRadius: AppRadius.md,
        border: Border.all(color: pip.border),
        boxShadow: [
          // Heavier in dark mode: a 3%-black shadow is invisible against a
          // dark ground, so the card would lose the lift the border alone
          // does not give it.
          BoxShadow(
            color: Colors.black.withValues(alpha: Theme.of(context).brightness == Brightness.dark ? 0.25 : 0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: child,
    );
  }
}

/// Icon + message + optional action, for every "nothing here yet" spot.
class EmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? description;
  final String? actionLabel;
  final VoidCallback? onAction;
  const EmptyState({
    super.key,
    required this.icon,
    required this.title,
    this.description,
    this.actionLabel,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xl, horizontal: AppSpacing.lg),
      decoration: BoxDecoration(
        color: pip.surface,
        borderRadius: AppRadius.md,
        border: Border.all(color: pip.border),
      ),
      child: Column(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(color: pip.accentSoft, shape: BoxShape.circle),
            child: Icon(icon, size: 20, color: pip.accent),
          ),
          const SizedBox(height: AppSpacing.md),
          Text(title, style: TextStyle(fontSize: 14.5, fontWeight: FontWeight.w600, color: pip.text)),
          if (description != null) ...[
            const SizedBox(height: 4),
            Text(description!, textAlign: TextAlign.center, style: TextStyle(fontSize: 12.5, color: pip.textMuted)),
          ],
          if (actionLabel != null && onAction != null) ...[
            const SizedBox(height: AppSpacing.md),
            GhostButton(label: actionLabel!, onTap: onAction),
          ],
        ],
      ),
    );
  }
}

/// A small outlined action button - lighter weight than FilledButton, for
/// secondary actions like "Set active" / "Revoke".
class GhostButton extends StatelessWidget {
  final String label;
  final VoidCallback? onTap;

  /// Null means the palette's accent - see the note on [TagLabel.color].
  final Color? color;
  const GhostButton({super.key, required this.label, required this.onTap, this.color});

  @override
  Widget build(BuildContext context) {
    final pip = context.pip;
    final tint = color ?? pip.accent;
    return Material(
      color: onTap == null ? Colors.transparent : tint.withValues(alpha: 0.08),
      shape: RoundedRectangleBorder(
        borderRadius: AppRadius.sm,
        side: BorderSide(color: onTap == null ? pip.border : tint.withValues(alpha: 0.3)),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: AppRadius.sm,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          child: Text(
            label,
            style: TextStyle(
              fontSize: 12.5,
              fontWeight: FontWeight.w600,
              color: onTap == null ? pip.textFaint : tint,
            ),
          ),
        ),
      ),
    );
  }
}
