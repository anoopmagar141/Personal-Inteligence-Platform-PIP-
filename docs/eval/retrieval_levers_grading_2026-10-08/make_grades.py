"""Grades recorded while reading grading/sheet.md blind (condition hidden), in five sittings (the part files).
C=CORRECT D=DECLINES W=WRONG V=VAGUE. Borderline calls carry a strict and a lenient reading."""
import json
from pathlib import Path

HERE = Path(__file__).parent
LETTER = {"C": "CORRECT", "D": "DECLINES", "W": "WRONG", "V": "VAGUE"}

PART5 = ("212W 213C 214W 215C 216D 217D 218C 219C 220D 221C 222D 223D 224W 225D 226C 227W 228C 229D 230C 231C 232C 233D "
         "234D 235D 236C 237W 238D 239D 240D 241D 242D 243D 244D 245D 246D 247W 248D 249D 250W 251D 252D 253D 254C 255C "
         "256D 257W 258D 259D 260W 261C 262D 263D 264D 265D 266W 267C 268D 269D 270C 271C 272C 273D")

tokens = []
for name in ("grades_part1.txt", "grades_part2.txt", "grades_part3.txt", "grades_part4.txt"):
    for line in (HERE / name).read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        tokens += line.split()
tokens += PART5.split()
numbers = [int(t[:-1]) for t in tokens]
assert numbers == list(range(1, 274)), "every answer number exactly once, in order"
GRADES = {n: t[-1] for n, t in zip(numbers, tokens)}

# number: (given, strict reading, lenient reading)
BORDERLINE = {
    5: ("V", "W", "V"), 22: ("C", "V", "C"), 27: ("C", "V", "C"), 47: ("C", "W", "C"),
    60: ("V", "V", "C"), 66: ("C", "V", "C"), 79: ("C", "W", "C"), 82: ("C", "W", "C"), 83: ("C", "W", "C"),
    86: ("W", "W", "V"), 98: ("V", "W", "V"),
    117: ("W", "W", "V"), 122: ("C", "V", "C"), 124: ("C", "V", "C"), 132: ("W", "W", "V"), 141: ("W", "W", "V"), 144: ("C", "V", "C"),
    165: ("W", "W", "D"), 168: ("V", "V", "C"), 176: ("V", "V", "C"), 187: ("V", "V", "C"), 190: ("C", "V", "C"),
    191: ("V", "W", "V"), 196: ("W", "W", "V"), 198: ("W", "W", "D"), 203: ("W", "W", "D"),
    214: ("W", "W", "V"), 226: ("C", "V", "C"), 237: ("W", "W", "C"), 272: ("C", "V", "C"),
}
for n, (given, _, _) in BORDERLINE.items():
    assert GRADES[n] == given, (n, GRADES[n], given)
main = {str(n): LETTER[g] for n, g in GRADES.items()}
strict, lenient = dict(main), dict(main)
for n, (_, s, l) in BORDERLINE.items():
    strict[str(n)] = LETTER[s]
    lenient[str(n)] = LETTER[l]
for name, g in (("grades", main), ("grades_strict", strict), ("grades_lenient", lenient)):
    json.dump(g, open(HERE / f"{name}.json", "w"))
print("written; borderline:", len(BORDERLINE))
