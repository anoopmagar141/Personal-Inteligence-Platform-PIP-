"""Turns a chapter draft (Markdown) into HTML next to it, formatted to the LUC guide for pasting into Word.

The guide's rules applied: Times New Roman 12, line spacing 2.0, text left aligned; the chapter title in capitals,
centred; main titles (1.1 ...) bold capitals; sub-titles (1.3.1 ...) bold with the first letter of each word in
capitals. [Check: ...] notes are kept, in grey italics, so they are easy to find and delete before submitting.
Numbered lists ("1. ...") stay numbered lists. A line "[Figure 4.1: Caption (fig4-1_use_case.png)]" becomes that
picture from diagrams/png or screenshots/ with its caption under it; until the picture exists, a grey note says
where to save it. A
"Listing 5.1: ..." or "Algorithm 5.1: ..." line captions the ``` code block after it, which keeps its spacing in a
box, single-spaced. "[Include: table_6_1_test_cases.html]" places a table page built by its own script, whole.

Run: .venv/Scripts/python.exe -I notes/report/make_chapter_html.py notes/report/chapter1/chapter1_draft.md
"""
import os
import re
import sys
from html import escape

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
  body {{ font-family: "Times New Roman", serif; font-size: 12pt; line-height: 2; margin: 1in 1in 1in 1.5in;
         background: #fff; color: #000; text-align: left; }}
  h1 {{ font-size: 12pt; font-weight: bold; text-align: center; margin: 0 0 24pt 0; page-break-before: always; }}
  h1:first-of-type {{ page-break-before: auto; }}
  h2 {{ font-size: 12pt; font-weight: bold; margin: 24pt 0 12pt 0; }}
  h3 {{ font-size: 12pt; font-weight: bold; margin: 18pt 0 12pt 0; }}
  p {{ margin: 0 0 12pt 0; }}
  ol {{ margin: 0 0 12pt 0; padding-left: 0.4in; }}
  li {{ margin: 0 0 6pt 0; }}
  p.cap {{ margin: 12pt 0 6pt 0; }}
  table {{ border-collapse: collapse; width: 100%; line-height: 1.3; font-size: 11pt; margin-bottom: 12pt; }}
  th, td {{ border: 1px solid #000; padding: 4px 6px; vertical-align: top; text-align: left; }}
  th {{ background: #d9d9d9; }}
  .check {{ color: #777; font-style: italic; }}
  p.fig {{ margin: 12pt 0 0 0; text-align: center; line-height: 1; }}
  p.fig img {{ max-width: 100%; }}
  p.figcap {{ margin: 6pt 0 18pt 0; text-align: center; }}
  pre {{ font-family: Consolas, "Courier New", monospace; font-size: 9.5pt; line-height: 1.25; white-space: pre-wrap;
        border: 1px solid #000; background: #f5f5f5; padding: 6pt 8pt; margin: 0 0 12pt 0; }}
</style></head><body>
{body}
</body></html>
"""


def inline(text):
    out = escape(text)
    return re.sub(r"\[(Check[^\]]*)\]", r'<span class="check">[\1]</span>', out)


def title_words(text):
    num, _, rest = text.partition(" ")
    return num + " " + " ".join(w[:1].upper() + w[1:] for w in rest.split(" "))


REPORT = os.path.dirname(os.path.abspath(__file__))
FIGURE_DIRS = [os.path.join(REPORT, "diagrams", "png"), os.path.join(REPORT, "screenshots")]


def figure(line, out_dir):
    m = re.match(r"^\[Figure ([\d.]+): (.*) \(([\w.-]+\.png)\)\]$", line)
    if not m:
        return None
    num, caption, name = m.groups()
    found = [os.path.join(d, name) for d in FIGURE_DIRS if os.path.exists(os.path.join(d, name))]
    if not found:
        return (f'<p class="check">[Figure {num} to add: {escape(caption)}. Save it as '
                f'notes/report/screenshots/{escape(name)} and rebuild.]</p>')
    src = os.path.relpath(found[0], out_dir).replace(os.sep, "/")
    return (f'<p class="fig"><img src="{escape(src)}" alt="{escape(caption)}"></p>\n'
            f'<p class="figcap"><b>Figure {num}:</b> {escape(caption)}</p>')


def include(line, out_dir, n):
    """A table built by its own script (Table 6.1, 6.2), placed whole. Its styles are scoped to it, because two
    such pages each style every table and cell, and one's "no wrapping after the first column" would break the
    other's layout."""
    m = re.match(r"^\[Include: ([\w./-]+\.html)\]$", line)
    if not m:
        return None
    path = os.path.join(out_dir, m.group(1))
    if not os.path.exists(path):
        return f'<p class="check">[Missing: {escape(m.group(1))}. Run the script that builds it, then rebuild.]</p>'
    page = open(path, encoding="utf-8").read()
    style = re.search(r"<style>(.*?)</style>", page, re.S)
    rules = []
    for selectors, body in re.findall(r"([^{}]+)\{([^}]*)\}", style.group(1) if style else ""):
        if selectors.strip() == "body":
            continue
        scoped = ", ".join(f".incl{n} {s.strip()}" for s in selectors.split(","))
        rules.append(f"{scoped} {{{body}}}")
    content = re.search(r"<body>(.*)</body>", page, re.S).group(1).strip()
    return (f'<div class="incl{n}" style="font-size: 10pt; line-height: 1.3; margin: 12pt 0;">\n'
            f'<style>{" ".join(rules)}</style>\n{content}\n</div>')


def convert(md, out_dir):
    html, table, caption, items = [], [], None, []

    def flush():
        nonlocal table, caption, items
        if table:
            head, *rows = table
            if caption:
                html.append(f'<p class="cap"><b>{escape(caption)}</b></p>')
            html.append("<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr>")
            html.extend("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows)
            html.append("</table>")
            table, caption = [], None
        if items:
            html.append("<ol>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ol>")
            items = []

    code = None
    for line in md.split("\n"):
        if code is not None:
            if line.startswith("```"):
                if caption:
                    html.append(f'<p class="cap"><b>{escape(caption)}</b></p>')
                html.append("<pre>" + escape("\n".join(code)) + "</pre>")
                code, caption = None, None
            else:
                code.append(line)
            continue
        if line.startswith("```"):
            flush()
            code = []
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not all(set(c) <= {"-"} for c in cells):
                table.append(cells)
            continue
        m = re.match(r"^\d+\.\s+(.*)", line)
        if m:
            items.append(m.group(1))
            continue
        flush()
        if not line.strip():
            continue
        if line.startswith("# "):
            html.append(f"<h1>{escape(line[2:].upper())}</h1>")
        elif line.startswith("## "):
            html.append(f"<h2>{escape(line[3:].upper())}</h2>")
        elif line.startswith("### "):
            html.append(f"<h3>{escape(title_words(line[4:]))}</h3>")
        # The colon is what makes it a caption: "Table 3.2 lists ..." is a sentence, and was once dropped as one.
        elif re.match(r"^(Table|Listing|Algorithm) \d+(\.\d+)*:", line):
            caption = line
        elif figure(line, out_dir):
            html.append(figure(line, out_dir))
        elif include(line, out_dir, len(html)):
            html.append(include(line, out_dir, len(html)))
        else:
            html.append(f"<p>{inline(line)}</p>")
    flush()
    return "\n".join(html)


def main():
    src = os.path.abspath(sys.argv[1])
    md = open(src, encoding="utf-8").read()
    title = md.split("\n", 1)[0].lstrip("# ").strip().title()
    out = os.path.splitext(src)[0] + ".html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(PAGE.format(title=escape(title + " (draft)"), body=convert(md, os.path.dirname(out))))
    print("wrote", out)


if __name__ == "__main__":
    main()
