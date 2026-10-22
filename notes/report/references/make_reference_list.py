"""Writes the report's one reference list (APA 6th edition) from the checked sources in chapter2/make_references.py,
and checks it against every chapter: each in-text citation must have a reference, and each reference must be cited
somewhere. A grey [Check: ...] note in a draft is not a citation, so a source named only there (Nepal's Privacy Act)
stays out until the text cites it.

Run: .venv/Scripts/python.exe -I notes/report/references/make_reference_list.py
"""
import importlib.util
import os
import re
import sys
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.dirname(HERE)

spec = importlib.util.spec_from_file_location("ch2refs", os.path.join(REPORT, "chapter2", "make_references.py"))
ch2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ch2)

# How each source is named in running text: the first author's surname (or the group or law), and its year.
NAMES = {
    "packer2023": ("Packer", "2023"), "park2023": ("Park", "2023"), "zhong2024": ("Zhong", "2024"),
    "chhikara2025": ("Chhikara", "2025"), "zhang2024": ("Zhang", "2024"), "lewis2020": ("Lewis", "2020"),
    "reimers2019": ("Reimers", "2019"), "wang2020": ("Wang", "2020"), "liu2024": ("Liu", "2024"),
    "ji2023": ("Ji", "2023"), "bai2022": ("Bai", "2022"), "greshake2023": ("Greshake", "2023"),
    "turan2010": ("Turan", "2010"), "gdpr2016": ("2016/679", "2016"), "qwen2024": ("Qwen Team", "2024"),
    "nepal2018": ("Privacy Act, 2075", "2018"), "cavoukian2009": ("Cavoukian", "2009"),
}


def chapter_texts():
    for n in range(1, 8):
        path = os.path.join(REPORT, f"chapter{n}", f"chapter{n}_draft.md")
        text = open(path, encoding="utf-8").read()
        text = re.sub(r"```.*?```", "", text, flags=re.S)
        text = re.sub(r"\[Check:[^\]]*\]", "", text)
        yield n, text


def cited_in(name, year, text):
    for m in re.finditer(re.escape(name), text):
        if year in text[m.start():m.start() + 160]:
            return True
    return False


def citations(text):
    """Every citation with a year, each with the words around it: "(Name, 2023)" and "Name et al. (2023)".
    Table rows are skipped (a "Dates (2026)" column heading is not a citation), and so is a bracket whose year does
    not follow a comma ("(329 commits by 22 October 2026)")."""
    text = "\n".join(line for line in text.split("\n") if not line.startswith("|"))
    found = [m.group(0) for m in re.finditer(
        r"\([^()]*[A-Z][^()]*,\s(?:19|20)\d\d[a-z]?(?:, Art\. \d+)?(?:;[^()]*)?\)", text)]
    found += [text[max(0, m.start() - 100):m.end()] for m in re.finditer(
        r"[A-Z][A-Za-z'’-]+(?: et al\.)? \((?:19|20)\d\d[a-z]?\)", text)]
    return found


def main():
    all_sources = {s[0]: s for s in ch2.SOURCES + ch2.OPTIONAL}
    texts = list(chapter_texts())
    used = {}
    for key, (name, year) in NAMES.items():
        chapters = [n for n, t in texts if cited_in(name, year, t)]
        if chapters:
            used[key] = chapters

    problems = []
    for n, t in texts:
        for c in citations(t):
            if not any(name in c for name, _ in NAMES.values()):
                problems.append(f"chapter {n}: citation with no reference: {c[-120:]!r}")
    for s in ch2.SOURCES:
        if s[0] not in used:
            problems.append(f"reference never cited: {s[0]}")

    refs = sorted((all_sources[k] for k in used), key=ch2.sort_key)
    items = "\n".join(f'<p class="ref">{ch2.html_ref(s[2])}</p>' for s in refs)
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>References</title>
<style>
  body {{ font-family: "Times New Roman", serif; font-size: 12pt; margin: 1in 1in 1in 1.5in; background: #fff;
         color: #000; }}
  h1 {{ font-size: 12pt; text-align: center; font-weight: bold; margin: 0 0 24pt 0; }}
  p.ref {{ padding-left: 0.5in; text-indent: -0.5in; margin: 0; line-height: 2; }}
</style></head><body>
<h1>REFERENCES</h1>
{items}
</body></html>
"""
    open(os.path.join(HERE, "references.html"), "w", encoding="utf-8").write(html)

    lines = ["# REFERENCES", ""] + [re.sub(r"\*(.+?)\*", r"*\1*", s[2]) + "\n" for s in refs]
    lines += ["", "<!-- Where each is cited (not part of the list): -->"]
    lines += [f"<!-- {k}: chapter(s) {', '.join(map(str, used[k]))} -->" for k in sorted(used)]
    open(os.path.join(HERE, "references.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

    print(f"{len(refs)} references written; cited in chapters:",
          ", ".join(f"{k} {used[k]}" for k in sorted(used)))
    left_out = [k for k in all_sources if k not in used]
    print("not cited, so left out:", ", ".join(left_out) or "none")
    if problems:
        print("PROBLEMS:\n  " + "\n  ".join(problems))
        sys.exit(1)
    print("every citation has a reference, and every reference is cited")


if __name__ == "__main__":
    main()
