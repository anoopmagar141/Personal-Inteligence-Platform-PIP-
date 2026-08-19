// PIP design system - "Terminal Trust" direction (dark, technical, precise).
// System fonts only (default UI font for body, generic monospace for
// data/labels) - no new package, no network font fetch.

import 'package:flutter/material.dart';

class AppColors {
  static const bg = Color(0xFF14161A);
  static const surface = Color(0xFF1C1F26);
  static const surfaceRaised = Color(0xFF262A33);
  static const border = Color(0xFF333844);
  static const text = Color(0xFFE6E8EC);
  static const textMuted = Color(0xFF8B93A1);
  static const textFaint = Color(0xFF4A4F5A);
  static const accent = Color(0xFF5EE6D0);
  static const accentOn = Color(0xFF0E1013);
  static const danger = Color(0xFFE5534B);
}

class AppSpacing {
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 16.0;
  static const lg = 24.0;
  static const xl = 32.0;
}

class AppRadius {
  static const sm = BorderRadius.all(Radius.circular(6));
  static const md = BorderRadius.all(Radius.circular(10));
  static const lg = BorderRadius.all(Radius.circular(14));
}

class AppTheme {
  static const mono = 'monospace';

  static ThemeData get dark {
    final base = ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: AppColors.bg,
      colorScheme: const ColorScheme.dark(
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
        hintStyle: const TextStyle(color: AppColors.textMuted, fontFamily: mono, fontSize: 13.5),
        labelStyle: const TextStyle(color: AppColors.textMuted),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        border: OutlineInputBorder(borderRadius: AppRadius.sm, borderSide: const BorderSide(color: AppColors.border)),
        enabledBorder: OutlineInputBorder(borderRadius: AppRadius.sm, borderSide: const BorderSide(color: AppColors.border)),
        focusedBorder: OutlineInputBorder(borderRadius: AppRadius.sm, borderSide: const BorderSide(color: AppColors.accent)),
        errorBorder: OutlineInputBorder(borderRadius: AppRadius.sm, borderSide: const BorderSide(color: AppColors.danger)),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.accent,
          foregroundColor: AppColors.accentOn,
          textStyle: const TextStyle(fontFamily: mono, fontWeight: FontWeight.w600, fontSize: 12.5, letterSpacing: 0.4),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: AppRadius.sm),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AppColors.accent,
          textStyle: const TextStyle(fontFamily: mono, fontSize: 12, fontWeight: FontWeight.w600),
        ),
      ),
      chipTheme: base.chipTheme.copyWith(
        backgroundColor: AppColors.surfaceRaised,
        labelStyle: const TextStyle(fontFamily: mono, fontSize: 12, color: AppColors.textMuted, letterSpacing: 0.3),
        side: const BorderSide(color: AppColors.border),
        shape: RoundedRectangleBorder(borderRadius: AppRadius.sm),
      ),
      dataTableTheme: DataTableThemeData(
        headingTextStyle: const TextStyle(fontFamily: mono, fontSize: 11, color: AppColors.textMuted, letterSpacing: 0.6, fontWeight: FontWeight.w600),
        dataTextStyle: const TextStyle(fontSize: 13.5, color: AppColors.text),
        dividerThickness: 1,
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(color: AppColors.accent),
    );
  }
}

/// Small uppercase monospace label, used throughout for section/status text
/// (matches the mockup's tab bar / side-panel-title / hint-row treatment).
class TagLabel extends StatelessWidget {
  final String text;
  final Color color;
  final double size;
  const TagLabel(this.text, {super.key, this.color = AppColors.textMuted, this.size = 11});

  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: TextStyle(fontFamily: AppTheme.mono, fontSize: size, color: color, letterSpacing: 0.6, fontWeight: FontWeight.w600),
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
        TagLabel(eyebrow, color: AppColors.accent),
        const SizedBox(height: AppSpacing.xs),
        Text(title, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: AppColors.text)),
        if (description != null) ...[
          const SizedBox(height: 4),
          Text(description!, style: const TextStyle(fontFamily: AppTheme.mono, fontSize: 12, color: AppColors.textMuted, height: 1.5)),
        ],
        const SizedBox(height: AppSpacing.lg),
      ],
    );
  }
}

/// A surface-colored card wrapper matching the mockup's rounded, bordered
/// panels (chat sidebar, onboarding card).
class SectionCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  const SectionCard({super.key, required this.child, this.padding = const EdgeInsets.all(AppSpacing.lg)});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(color: AppColors.surface, borderRadius: AppRadius.md, border: Border.all(color: AppColors.border)),
      child: child,
    );
  }
}

/// A small, uppercase-mono outlined action button, matching the mockup's
/// "Set active" / "Grant consent" treatment - lighter weight than FilledButton.
class GhostButton extends StatelessWidget {
  final String label;
  final VoidCallback? onTap;
  final Color color;
  const GhostButton({super.key, required this.label, required this.onTap, this.color = AppColors.accent});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: AppRadius.sm, side: BorderSide(color: onTap == null ? AppColors.border : color.withValues(alpha: 0.4))),
      child: InkWell(
        onTap: onTap,
        borderRadius: AppRadius.sm,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
          child: TagLabel(label, color: onTap == null ? AppColors.textFaint : color, size: 10.5),
        ),
      ),
    );
  }
}
