// Tests for the assistant-reply Markdown renderer.
//
// Two groups matter more than the formatting itself:
//
//   * STREAMING. This parser runs on half-written Markdown many times per
//     reply, so an unclosed marker must stay literal. If a lone `**` swallowed
//     the rest of the text, every reply containing one would visibly lose its
//     tail and then get it back a second later.
//   * FALSE POSITIVES. This app talks about `file_path` and `2 * 3` all day. A
//     renderer that italicised the middle of an identifier would be wrong more
//     often than right, and wrong in a way that looks like the model said
//     something it did not.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pip_flutter_client/markdown.dart';

void main() {
  group('inline', () {
    test('reads bold, italic and code', () {
      expect(parseInline('a **b** c'), [
        const MdSpan('a '),
        const MdSpan('b', bold: true),
        const MdSpan(' c'),
      ]);
      expect(parseInline('a *b* c'), [
        const MdSpan('a '),
        const MdSpan('b', italic: true),
        const MdSpan(' c'),
      ]);
      expect(parseInline('run `pytest` now'), [
        const MdSpan('run '),
        const MdSpan('pytest', code: true),
        const MdSpan(' now'),
      ]);
    });

    test('carries emphasis into nested code', () {
      expect(parseInline('**use `-q`**'), [
        const MdSpan('use ', bold: true),
        const MdSpan('-q', code: true, bold: true),
      ]);
    });

    test('leaves an unclosed marker as text', () {
      // Mid-stream the closing marker has not arrived yet. Swallowing the rest
      // of the reply until it does is the failure this guards.
      expect(parseInline('this is **bol'), [const MdSpan('this is **bol')]);
      expect(parseInline('a `code'), [const MdSpan('a `code')]);
      expect(parseInline('half *ital'), [const MdSpan('half *ital')]);
    });

    test('does not treat underscores as emphasis', () {
      // preference_memory, stage_09_llm_streaming, file_path_enc.
      expect(parseInline('see stage_09_llm_streaming'), [
        const MdSpan('see stage_09_llm_streaming'),
      ]);
    });

    test('does not italicise arithmetic', () {
      expect(parseInline('2 * 3 * 4'), [const MdSpan('2 * 3 * 4')]);
    });

    test('leaves plain text exactly as it was', () {
      expect(parseInline('nothing to do here'), [const MdSpan('nothing to do here')]);
      expect(parseInline(''), isEmpty);
    });
  });

  group('blocks', () {
    test('splits paragraphs on blank lines', () {
      final blocks = parseMarkdown('first\n\nsecond');
      expect(blocks.length, 2);
      expect((blocks[0] as MdParagraph).text, 'first');
      expect((blocks[1] as MdParagraph).text, 'second');
    });

    test('reads headings, bullets and numbered items', () {
      final blocks = parseMarkdown('## Title\n- one\n- two\n1. first\n2) second');
      expect((blocks[0] as MdHeading).level, 2);
      expect((blocks[0] as MdHeading).text, 'Title');
      expect((blocks[1] as MdListItem).text, 'one');
      expect((blocks[1] as MdListItem).marker, isNull);
      expect((blocks[3] as MdListItem).marker, '1');
      expect((blocks[4] as MdListItem).marker, '2');
      expect((blocks[4] as MdListItem).text, 'second');
    });

    test('reads a fenced block and its language', () {
      final blocks = parseMarkdown('before\n```python\nprint(1)\nprint(2)\n```\nafter');
      final code = blocks.whereType<MdCode>().single;
      expect(code.language, 'python');
      expect(code.code, 'print(1)\nprint(2)');
      expect(blocks.whereType<MdParagraph>().map((p) => p.text), ['before', 'after']);
    });

    test('renders an unterminated fence as the code so far', () {
      // The model is still typing. Printing a stray ``` and then reflowing the
      // whole reply once it closes is the flicker this avoids.
      final blocks = parseMarkdown('here:\n```dart\nvoid main() {');
      final code = blocks.whereType<MdCode>().single;
      expect(code.language, 'dart');
      expect(code.code, 'void main() {');
    });

    test('a bare fence has no language rather than an empty one', () {
      final code = parseMarkdown('```\nx\n```').whereType<MdCode>().single;
      expect(code.language, isNull);
    });

    test('keeps text that is not Markdown at all, unchanged', () {
      const plain = 'You have one project recorded in your file: PIP.';
      final blocks = parseMarkdown(plain);
      expect(blocks.length, 1);
      expect((blocks.single as MdParagraph).text, plain);
    });

    test('never drops a line', () {
      // The property that matters most: whatever the model said reaches the
      // screen, formatted or not.
      const source = '# H\ntext\n- item\n\n```\ncode\n```\ntail';
      final rendered = parseMarkdown(source)
          .map((b) => switch (b) {
                MdParagraph(:final text) => text,
                MdHeading(:final text) => text,
                MdListItem(:final text) => text,
                MdCode(:final code) => code,
              })
          .join(' ');
      for (final fragment in ['H', 'text', 'item', 'code', 'tail']) {
        expect(rendered, contains(fragment));
      }
    });
  });

  group('rendering', () {
    testWidgets('shows the text without its markers', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              source: 'Run **now** with `-q`',
              baseStyle: TextStyle(fontSize: 14),
            ),
          ),
        ),
      );

      expect(find.textContaining('**'), findsNothing);
      expect(find.textContaining('now'), findsOneWidget);
    });

    testWidgets('a reply stays selectable', (tester) async {
      // An assistant reply is often the thing worth keeping. A renderer that
      // made replies un-copyable would be a downgrade dressed as an upgrade.
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              source: 'keep me\n\n```\ncode\n```',
              baseStyle: TextStyle(fontSize: 14),
            ),
          ),
        ),
      );

      expect(find.byType(SelectableText), findsWidgets);
    });
  });
}
