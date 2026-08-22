// PIP design system - "Clarity" direction (light, clean, modern SaaS).
// System fonts only - no new package, no network font fetch.

import 'package:flutter/material.dart';

class AppColors {
  static const bg = Color(0xFFF7F8FB);
  static const surface = Color(0xFFFFFFFF);
  static const surfaceRaised = Color(0xFFF0F1F6);
  static const border = Color(0xFFE3E6ED);
  static const text = Color(0xFF1A1D26);
  static const textMuted = Color(0xFF6B7080);
  static const textFaint = Color(0xFFA0A4B2);
  static const accent = Color(0xFF4F46E5);
  static const accentSoft = Color(0xFFEEF0FD);
  static const accentOn = Color(0xFFFFFFFF);
  static const danger = Color(0xFFDC2626);
  static const dangerSoft = Color(0xFFFDECEC);
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

  static ThemeData get light {
    final base = ThemeData(
      brightness: Brightness.light,
      scaffoldBackgroundColor: AppColors.bg,
      colorScheme: const ColorScheme.light(
        surface: AppColors.bg,
        primary: AppColors.accent,
        onPrimary: AppColors.accentOn,
        secondary: AppColors.accent,
        error: AppColors.danger,
      ),
      useMaterial3: true,
    );
    return base.copyWith(
      textTheme: base.textTheme.apply(
        bodyColor: AppColors.text,
        displayColor: AppColors.text,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.surface,
        foregroundColor: AppColors.text,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
      ),
      cardTheme: CardThemeData(
        color: AppColors.surface,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: AppRadius.md, side: const BorderSide(color: AppColors.border)),
        margin: EdgeInsets.zero,
      ),
      dividerTheme: const DividerThemeData(color: AppColors.border, space: 1),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.surface,
        hintStyle: const TextStyle(color: AppColors.textFaint, fontSize: 14),
        labelStyle: const TextStyle(color: AppColors.textMuted),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        border: OutlineInputBorder(borderRadius: AppRadius.sm, borderSide: const BorderSide(color: AppColors.border)),
        enabledBorder: OutlineInputBorder(borderRadius: AppRadius.sm, borderSide: const BorderSide(color: AppColors.border)),
        focusedBorder: OutlineInputBorder(borderRadius: AppRadius.sm, borderSide: const BorderSide(color: AppColors.accent, width: 1.5)),
        errorBorder: OutlineInputBorder(borderRadius: AppRadius.sm, borderSide: const BorderSide(color: AppColors.danger)),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.accent,
          foregroundColor: AppColors.accentOn,
          textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: AppRadius.sm),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AppColors.accent,
          textStyle: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600),
        ),
      ),
      chipTheme: base.chipTheme.copyWith(
        backgroundColor: AppColors.surfaceRaised,
        labelStyle: const TextStyle(fontSize: 12.5, color: AppColors.textMuted),
        side: const BorderSide(color: AppColors.border),
        shape: RoundedRectangleBorder(borderRadius: AppRadius.sm),
      ),
      dataTableTheme: DataTableThemeData(
        headingTextStyle: const TextStyle(fontSize: 11.5, color: AppColors.textMuted, letterSpacing: 0.3, fontWeight: FontWeight.w600),
        dataTextStyle: const TextStyle(fontSize: 13.5, color: AppColors.text),
        dividerThickness: 1,
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(color: AppColors.accent),
    );
  }
}

/// Small label used for section eyebrows and status text - sentence case,
/// soft-tinted pill when [color] is given, plain muted text otherwise.
class TagLabel extends StatelessWidget {
  final String text;
  final Color color;
  final double size;
  const TagLabel(this.text, {super.key, this.color = AppColors.textMuted, this.size = 12});

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: TextStyle(fontSize: size, color: color, fontWeight: FontWeight.w600),
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
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TagLabel(eyebrow.toUpperCase(), color: AppColors.accent, size: 11),
        const SizedBox(height: AppSpacing.xs),
        Text(title, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: AppColors.text)),
        if (description != null) ...[
          const SizedBox(height: 4),
          Text(description!, style: const TextStyle(fontSize: 13.5, color: AppColors.textMuted, height: 1.5)),
        ],
        const SizedBox(height: AppSpacing.lg),
      ],
    );
  }
}

/// A white, bordered, softly-shadowed card - the base surface for every
/// list item and form on a CRUD screen.
class SectionCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  const SectionCard({super.key, required this.child, this.padding = const EdgeInsets.all(AppSpacing.lg)});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: AppRadius.md,
        border: Border.all(color: AppColors.border),
        boxShadow: [
          BoxShadow(color: Colors.black.withValues(alpha: 0.03), blurRadius: 8, offset: const Offset(0, 2)),
        ],
      ),
      child: child,
    );
  }
}

/// Icon + message + optional action, for every "nothing here yet" spot
/// (matches 21st.dev's empty-state category - replaces what used to be a
/// single line of faint plain text on Documents/Projects/Decisions/Profile).
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
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xl, horizontal: AppSpacing.lg),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: AppRadius.md,
        border: Border.all(color: AppColors.border, style: BorderStyle.solid),
      ),
      child: Column(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: const BoxDecoration(color: AppColors.accentSoft, shape: BoxShape.circle),
            child: Icon(icon, size: 20, color: AppColors.accent),
          ),
          const SizedBox(height: AppSpacing.md),
          Text(title, style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w600, color: AppColors.text)),
          if (description != null) ...[
            const SizedBox(height: 4),
            Text(description!, textAlign: TextAlign.center, style: const TextStyle(fontSize: 12.5, color: AppColors.textMuted)),
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
  final Color color;
  const GhostButton({super.key, required this.label, required this.onTap, this.color = AppColors.accent});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: onTap == null ? Colors.transparent : color.withValues(alpha: 0.08),
      shape: RoundedRectangleBorder(borderRadius: AppRadius.sm, side: BorderSide(color: onTap == null ? AppColors.border : color.withValues(alpha: 0.3))),
      child: InkWell(
        onTap: onTap,
        borderRadius: AppRadius.sm,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          child: Text(label, style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: onTap == null ? AppColors.textFaint : color)),
        ),
      ),
    );
  }
}
