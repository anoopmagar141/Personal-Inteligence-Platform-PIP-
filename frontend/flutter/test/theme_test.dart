// Tests for the two-palette design system.
//
// A dark mode is the one feature whose correctness cannot be argued from the
// code - it either reads or it does not, and nobody can see it from here. So
// the parts that ARE checkable are checked: that the palette actually varies
// with the theme (a copy-pasted dark palette would look fine in a diff and
// wrong on screen), and that every colour pairing the app relies on clears a
// measured contrast ratio rather than an opinion about it.
//
// Thresholds are WCAG 2.1: 4.5:1 for body text, 3:1 for the incidental
// metadata that is deliberately quiet. The faint pairings are held to the
// lower bar honestly rather than exempted - "it's only a timestamp" is how a
// 2.5:1 grey survives a review.

import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/theme.dart';

/// WCAG relative luminance.
double _luminance(Color color) {
  double channel(double v) => v <= 0.03928 ? v / 12.92 : math.pow((v + 0.055) / 1.055, 2.4).toDouble();
  return 0.2126 * channel(color.r) + 0.7152 * channel(color.g) + 0.0722 * channel(color.b);
}

/// WCAG contrast ratio, 1.0 (identical) to 21.0 (black on white).
double contrast(Color a, Color b) {
  final la = _luminance(a);
  final lb = _luminance(b);
  final lighter = math.max(la, lb);
  final darker = math.min(la, lb);
  return (lighter + 0.05) / (darker + 0.05);
}

void expectReadable(String what, Color fg, Color bg, double minimum) {
  final ratio = contrast(fg, bg);
  expect(
    ratio,
    greaterThanOrEqualTo(minimum),
    reason: '$what is ${ratio.toStringAsFixed(2)}:1, below the $minimum:1 minimum',
  );
}

void main() {
  group('palette', () {
    test('light and dark differ in every field', () {
      // A field left at its light value is invisible in review and obvious on
      // screen - usually as one white card in an otherwise dark app.
      final light = PipPalette.light;
      final dark = PipPalette.dark;
      final pairs = <String, List<Color>>{
        'bg': [light.bg, dark.bg],
        'surface': [light.surface, dark.surface],
        'surfaceRaised': [light.surfaceRaised, dark.surfaceRaised],
        'border': [light.border, dark.border],
        'text': [light.text, dark.text],
        'textMuted': [light.textMuted, dark.textMuted],
        'textFaint': [light.textFaint, dark.textFaint],
        'accent': [light.accent, dark.accent],
        'accentSoft': [light.accentSoft, dark.accentSoft],
        'accentOn': [light.accentOn, dark.accentOn],
        'danger': [light.danger, dark.danger],
        'dangerSoft': [light.dangerSoft, dark.dangerSoft],
      };
      pairs.forEach((name, colors) {
        expect(colors[0], isNot(colors[1]), reason: '$name is the same in both palettes');
      });
    });

    test('copyWith and lerp keep the extension contract', () {
      expect(PipPalette.light.copyWith(text: const Color(0xFF000000)).text, const Color(0xFF000000));
      expect(PipPalette.light.copyWith().surface, PipPalette.light.surface);
      expect(PipPalette.light.lerp(PipPalette.dark, 0).bg, PipPalette.light.bg);
      expect(PipPalette.light.lerp(PipPalette.dark, 1).bg, PipPalette.dark.bg);
    });
  });

  group('contrast', () {
    for (final entry in {'light': PipPalette.light, 'dark': PipPalette.dark}.entries) {
      final name = entry.key;
      final pip = entry.value;

      test('$name: body text is readable everywhere it is used', () {
        expectReadable('$name text on bg', pip.text, pip.bg, 4.5);
        expectReadable('$name text on surface', pip.text, pip.surface, 4.5);
        expectReadable('$name muted text on surface', pip.textMuted, pip.surface, 4.5);
        expectReadable('$name muted text on bg', pip.textMuted, pip.bg, 4.5);
      });

      test('$name: the primary button label is readable on the accent', () {
        // The weakest pairing in the set by construction, and on the one
        // control that must never be ambiguous.
        expectReadable('$name accentOn on accent', pip.accentOn, pip.accent, 4.5);
      });

      test('$name: errors and emphasis read against their own backgrounds', () {
        expectReadable('$name danger on surface', pip.danger, pip.surface, 4.5);
        expectReadable('$name danger on dangerSoft', pip.danger, pip.dangerSoft, 4.5);
        expectReadable('$name accent on accentSoft', pip.accent, pip.accentSoft, 4.5);
      });

      test('$name: faint metadata still clears the large-text minimum', () {
        expectReadable('$name faint text on surface', pip.textFaint, pip.surface, 3.0);
        expectReadable('$name faint text on bg', pip.textFaint, pip.bg, 3.0);
      });
    }
  });

  group('resolution', () {
    testWidgets('a widget under the dark theme gets the dark palette', (tester) async {
      late PipPalette resolved;
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.dark,
          home: Builder(
            builder: (context) {
              resolved = context.pip;
              return const SizedBox.shrink();
            },
          ),
        ),
      );
      expect(resolved.bg, PipPalette.dark.bg);
    });

    testWidgets('a widget under the light theme gets the light palette', (tester) async {
      late PipPalette resolved;
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light,
          home: Builder(
            builder: (context) {
              resolved = context.pip;
              return const SizedBox.shrink();
            },
          ),
        ),
      );
      expect(resolved.bg, PipPalette.light.bg);
    });

    testWidgets('a bare theme falls back to light rather than throwing', (tester) async {
      // Every screen test in this suite pumps a plain MaterialApp. They should
      // render, not die on a null assertion about a theme extension.
      late PipPalette resolved;
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) {
              resolved = context.pip;
              return const SizedBox.shrink();
            },
          ),
        ),
      );
      expect(resolved.bg, PipPalette.light.bg);
    });

    testWidgets('shared widgets follow the theme they are placed in', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.dark,
          home: const Scaffold(
            body: SectionCard(child: TagLabel('hello')),
          ),
        ),
      );

      final card = tester.widget<Container>(
        find.descendant(of: find.byType(SectionCard), matching: find.byType(Container)).first,
      );
      final decoration = card.decoration as BoxDecoration;
      expect(decoration.color, PipPalette.dark.surface);

      final label = tester.widget<Text>(find.text('hello'));
      expect(label.style?.color, PipPalette.dark.textMuted);
    });
  });
}
