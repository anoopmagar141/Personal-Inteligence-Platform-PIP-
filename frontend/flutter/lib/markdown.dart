// A small Markdown renderer for assistant replies.
//
// Local models emit Markdown whether or not anyone asked them to - bold,
// inline code, fenced blocks, bullet and numbered lists - and the chat pane
// was printing the asterisks and backticks literally. That makes a correct
// answer look worse than it is, and a code block in particular becomes
// genuinely hard to read.
//
// WHY NOT A PACKAGE. flutter_markdown is discontinued and its replacements are
// third-party. This project's design system already carries the rule ("System
// fonts only - no new package, no network font fetch"), the constitution keeps
// a hard line about what leaves the machine, and pulling a transitive
// dependency tree into a privacy-first local app to bold some text is a poor
// trade. The subset below is what an 8B model actually produces; everything
// outside it renders as the text it was, which is exactly what happens today.
//
// STREAMING IS THE HARD PART, and it is why parsing is written to degrade
// rather than to be strict. Tokens arrive one at a time, so this parser is
// called on half-written Markdown many times per reply: a fence that has been
// opened and not yet closed, a `**` with no partner yet. An unclosed marker is
// therefore always treated as literal text rather than swallowing the rest of
// the reply, and an unterminated fence renders as the code it is so far. The
// alternative - text vanishing and reappearing as the model types - is worse
// than an asterisk showing for a few hundred milliseconds.
//
// Part 14.4 (frontend has zero intelligence) is untouched: this changes how
// the assistant's own bytes are drawn and never what they say. User messages
// are deliberately NOT parsed - see the note in MarkdownBody.

import 'package:flutter/material.dart';

import 'theme.dart';

// --- Model -------------------------------------------------------------------

/// One run of text with the emphasis that applies to it.
@immutable
class MdSpan {
  final String text;
  final bool bold;
  final bool italic;
  final bool code;
  const MdSpan(this.text, {this.bold = false, this.italic = false, this.code = false});

  @override
  bool operator ==(Object other) =>
      other is MdSpan &&
      other.text == text &&
      other.bold == bold &&
      other.italic == italic &&
      other.code == code;

  @override
  int get hashCode => Object.hash(text, bold, italic, code);

  @override
  String toString() =>
      'MdSpan("$text"${bold ? ' bold' : ''}${italic ? ' italic' : ''}${code ? ' code' : ''})';
}

sealed class MdBlock {
  const MdBlock();
}

class MdParagraph extends MdBlock {
  final String text;
  const MdParagraph(this.text);
}

class MdHeading extends MdBlock {
  final int level;
  final String text;
  const MdHeading(this.level, this.text);
}

/// One list item. [marker] is the number for an ordered item, null for a
/// bullet. Items are separate blocks rather than a grouped list because
/// nothing here needs the grouping and a half-streamed list has no end yet.
class MdListItem extends MdBlock {
  final String text;
  final String? marker;
  const MdListItem(this.text, {this.marker});
}

class MdCode extends MdBlock {
  final String code;
  final String? language;
  const MdCode(this.code, {this.language});
}

// --- Parsing -----------------------------------------------------------------

final _fence = RegExp(r'^\s*```(.*)$');
final _closingFence = RegExp(r'^\s*```\s*$');
final _heading = RegExp(r'^(#{1,6})\s+(.*)$');
final _bullet = RegExp(r'^\s*[-*+]\s+(.*)$');
final _numbered = RegExp(r'^\s*(\d{1,9})[.)]\s+(.*)$');

/// Splits [source] into blocks. Never throws and never drops input: anything
/// unrecognised comes back as a paragraph containing exactly its own text.
List<MdBlock> parseMarkdown(String source) {
  final blocks = <MdBlock>[];
  final lines = source.split('\n');
  final paragraph = <String>[];

  void flushParagraph() {
    if (paragraph.isEmpty) return;
    blocks.add(MdParagraph(paragraph.join('\n')));
    paragraph.clear();
  }

  var i = 0;
  while (i < lines.length) {
    final line = lines[i];

    final fence = _fence.firstMatch(line);
    if (fence != null) {
      flushParagraph();
      final language = fence.group(1)!.trim();
      final code = <String>[];
      i++;
      while (i < lines.length && !_closingFence.hasMatch(lines[i])) {
        code.add(lines[i]);
        i++;
      }
      // If the loop ended because we ran out of lines rather than on a closing
      // fence, the model is still typing. What it has written so far IS the
      // code block; printing a stray ``` and then reflowing everything once
      // the fence closes is the flicker this whole file is written to avoid.
      if (i < lines.length) i++;
      blocks.add(MdCode(code.join('\n'), language: language.isEmpty ? null : language));
      continue;
    }

    final heading = _heading.firstMatch(line);
    if (heading != null) {
      flushParagraph();
      blocks.add(MdHeading(heading.group(1)!.length, heading.group(2)!.trim()));
      i++;
      continue;
    }

    final numbered = _numbered.firstMatch(line);
    if (numbered != null) {
      flushParagraph();
      blocks.add(MdListItem(numbered.group(2)!, marker: numbered.group(1)!));
      i++;
      continue;
    }

    final bullet = _bullet.firstMatch(line);
    if (bullet != null) {
      flushParagraph();
      blocks.add(MdListItem(bullet.group(1)!));
      i++;
      continue;
    }

    if (line.trim().isEmpty) {
      flushParagraph();
      i++;
      continue;
    }

    paragraph.add(line);
    i++;
  }

  flushParagraph();
  return blocks;
}

/// Splits one line's text into emphasis runs.
///
/// Underscores are NOT emphasis here. `_` is standard Markdown, but this app
/// spends its time discussing `file_path`, `preference_memory` and
/// `stage_09_llm_streaming`, and a renderer that italicised the middle of every
/// identifier would be wrong far more often than right.
List<MdSpan> parseInline(String source) => _parseInline(source);

List<MdSpan> _parseInline(String source, {bool bold = false, bool italic = false}) {
  final spans = <MdSpan>[];
  final buffer = StringBuffer();

  void flush() {
    if (buffer.isEmpty) return;
    spans.add(MdSpan(buffer.toString(), bold: bold, italic: italic));
    buffer.clear();
  }

  var i = 0;
  while (i < source.length) {
    if (source.startsWith('`', i)) {
      final end = source.indexOf('`', i + 1);
      if (end > i + 1) {
        flush();
        spans.add(MdSpan(source.substring(i + 1, end), code: true, bold: bold, italic: italic));
        i = end + 1;
        continue;
      }
    }

    if (source.startsWith('**', i)) {
      final end = source.indexOf('**', i + 2);
      if (end > i + 1 && _tightAround(source, i + 2, end)) {
        flush();
        spans.addAll(_parseInline(source.substring(i + 2, end), bold: true, italic: italic));
        i = end + 2;
        continue;
      }
    }

    if (source.startsWith('*', i)) {
      final end = source.indexOf('*', i + 1);
      if (end > i + 1 && _tightAround(source, i + 1, end)) {
        flush();
        spans.addAll(_parseInline(source.substring(i + 1, end), bold: bold, italic: true));
        i = end + 1;
        continue;
      }
    }

    buffer.write(source[i]);
    i++;
  }

  flush();
  return spans;
}

/// Whether the run from [start] to [end] is bounded by non-space, the usual
/// rule for treating a `*` as emphasis rather than as a character.
///
/// Without it "2 * 3 * 4" italicises " 3 ", which is a wrong answer produced
/// out of arithmetic - the kind of thing that is much more embarrassing on
/// screen than a stray asterisk would have been.
bool _tightAround(String source, int start, int end) {
  if (start >= end) return false;
  return source[start] != ' ' && source[end - 1] != ' ';
}

// --- Rendering ---------------------------------------------------------------

/// Renders [source] as Markdown, selectable throughout.
///
/// Selectable because an assistant reply is frequently the thing worth keeping
/// - a command, a snippet, an explanation to paste somewhere - and a renderer
/// that made replies un-copyable would be a downgrade dressed as an upgrade.
class MarkdownBody extends StatelessWidget {
  final String source;
  final TextStyle baseStyle;
  const MarkdownBody({super.key, required this.source, required this.baseStyle});

  @override
  Widget build(BuildContext context) {
    final blocks = parseMarkdown(source);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        for (var i = 0; i < blocks.length; i++)
          Padding(
            padding: EdgeInsets.only(top: i == 0 ? 0 : AppSpacing.sm),
            child: _block(context, blocks[i]),
          ),
      ],
    );
  }

  Widget _block(BuildContext context, MdBlock block) {
    final pip = context.pip;
    switch (block) {
      case MdParagraph(:final text):
        return SelectableText.rich(TextSpan(children: _spans(context, text)), style: baseStyle);

      case MdHeading(:final level, :final text):
        return SelectableText.rich(
          TextSpan(children: _spans(context, text)),
          style: baseStyle.copyWith(
            // Three steps is enough: nothing renders a level-6 heading
            // meaningfully at chat-bubble size, so deeper levels just stop
            // getting bigger rather than becoming illegibly small.
            fontSize: baseStyle.fontSize! + (level == 1 ? 5 : level == 2 ? 3 : 1),
            fontWeight: FontWeight.w700,
          ),
        );

      case MdListItem(:final text, :final marker):
        return Padding(
          padding: const EdgeInsets.only(left: AppSpacing.sm),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              SizedBox(
                width: 22,
                child: Text(
                  marker == null ? '•' : '$marker.',
                  style: baseStyle.copyWith(color: pip.textMuted),
                ),
              ),
              Flexible(
                child: SelectableText.rich(
                  TextSpan(children: _spans(context, text)),
                  style: baseStyle,
                ),
              ),
            ],
          ),
        );

      case MdCode(:final code, :final language):
        return Container(
          width: double.infinity,
          padding: const EdgeInsets.all(AppSpacing.sm),
          decoration: BoxDecoration(
            color: pip.surfaceRaised,
            borderRadius: AppRadius.sm,
            border: Border.all(color: pip.border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              if (language != null) ...[
                Text(language, style: TextStyle(fontSize: 10.5, color: pip.textFaint)),
                const SizedBox(height: 4),
              ],
              // Its own horizontal scroll: a long line must not widen the
              // bubble or force the whole page sideways.
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: SelectableText(
                  code,
                  style: baseStyle.copyWith(fontFamily: AppTheme.mono, fontSize: 12.5, height: 1.4),
                ),
              ),
            ],
          ),
        );
    }
  }

  List<InlineSpan> _spans(BuildContext context, String text) {
    final pip = context.pip;
    return [
      for (final span in parseInline(text))
        TextSpan(
          text: span.text,
          style: baseStyle.copyWith(
            fontWeight: span.bold ? FontWeight.w700 : null,
            fontStyle: span.italic ? FontStyle.italic : null,
            fontFamily: span.code ? AppTheme.mono : null,
            backgroundColor: span.code ? pip.surfaceRaised : null,
          ),
        ),
    ];
  }
}
