"""Grades recorded while reading grading/sheet.md blind (condition hidden). One letter per answer number:
C = CORRECT, D = DECLINES, W = WRONG, V = VAGUE."""
import json
from pathlib import Path

HERE = Path(__file__).parent
LETTER = {"C": "CORRECT", "D": "DECLINES", "W": "WRONG", "V": "VAGUE"}

GRADES_BY_NUMBER = (
    "1D 2D 3C 4D 5D 6C 7D 8W 9C 10C 11C 12V 13D 14C 15D 16D 17D 18D 19W 20D 21C 22D 23D 24C 25D 26D 27D 28D 29D 30D "
    "31D 32D 33W 34D 35C 36C 37C 38V 39D 40W 41D 42D 43D 44D 45D 46C 47D 48D 49D "
    "50D 51D 52D 53V 54D 55D 56W 57C 58D 59D 60D 61D 62D 63D 64D 65C 66C 67C 68C 69C 70V 71D 72W 73D 74C 75D 76C 77D 78C 79D "
    "80D 81D 82V 83D 84C 85D 86W 87C 88D 89W 90D 91D 92W 93D "
    "94C 95D 96D 97C 98D 99C 100V 101W 102D 103C 104W 105C 106D 107V 108D 109D 110W 111D 112D 113W 114V 115D 116D 117V 118D 119V "
    "120D 121W 122C 123D 124D 125D 126V 127D 128D 129W 130D 131W 132C 133D 134C 135C 136D 137C 138D 139D 140C"
).split()
nums = [int(t[:-1]) for t in GRADES_BY_NUMBER]
assert nums == list(range(1, 141)), "every answer number exactly once, in order"
GRADES = [t[-1] for t in GRADES_BY_NUMBER]


# Borderline calls: number -> (label I gave, strict reading, lenient reading)
BORDERLINE = {
    9: ("C", "W", "C"),     # file stays on disk (right) + invented rationale/cleanup
    72: ("W", "W", "C"),    # file stays on disk (right) + invented cleanup process that removes it
    76: ("C", "W", "C"),    # unopenable restored profile (right) but says it opens with the OLD password
    101: ("W", "W", "D"),   # "the cache does not give a TTL" then "I do not have that information"
    117: ("V", "V", "C"),   # right evidence, does not name the cause
    129: ("W", "W", "V"),   # right idea (dead process = stale), wrong rule, no creation time
    135: ("C", "V", "C"),   # names the Observer pass committing, not the sign-in catch-up
    137: ("C", "W", "C"),   # "constrain the mechanism; do not constrain the problem" (second half altered)
    70: ("V", "W", "V"),    # "cannot say... typically earliest to latest" (the opposite of the rule)
}

assert len(GRADES) == 140, len(GRADES)
main = {str(i + 1): LETTER[g] for i, g in enumerate(GRADES)}
for n, (given, strict, lenient) in BORDERLINE.items():
    assert GRADES[n - 1] == given, (n, GRADES[n - 1], given)
strict = dict(main)
lenient = dict(main)
for n, (_, s, l) in BORDERLINE.items():
    strict[str(n)] = LETTER[s]
    lenient[str(n)] = LETTER[l]
for name, g in (("grades", main), ("grades_strict", strict), ("grades_lenient", lenient)):
    json.dump(g, open(HERE / f"{name}.json", "w"), indent=0)
print("written; borderline calls:", sorted(BORDERLINE))
