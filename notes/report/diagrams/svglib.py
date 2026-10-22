"""Tiny SVG helper for the report diagrams. Standard library only.

Print style: white background, black lines, light grey fills, Times New Roman,
so the figures match the report's body font and survive black-and-white printing.
"""
from html import escape

FONT = "Times New Roman"
GREY = "#f0f0f0"
GREY2 = "#e2e2e2"
DARK = "#555"


class Svg:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.parts = []

    # -- primitives -------------------------------------------------------
    def rect(self, x, y, w, h, rx=0, fill="#fff", stroke="#000", sw=1.3, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"{d}/>'
        )

    def text(self, x, y, s, size=15, anchor="middle", weight="normal", style="normal",
             fill="#000", lh=1.22):
        """Text centred vertically on y; s may be a list of lines."""
        lines = s if isinstance(s, list) else [s]
        n = len(lines)
        top = y - (n - 1) * size * lh / 2
        for i, line in enumerate(lines):
            yy = top + i * size * lh + size * 0.34
            self.parts.append(
                f'<text x="{x}" y="{yy:.1f}" font-family="{FONT}" font-size="{size}" '
                f'text-anchor="{anchor}" font-weight="{weight}" font-style="{style}" '
                f'fill="{fill}">{escape(line)}</text>'
            )

    def line(self, x1, y1, x2, y2, end="arr", start=None, dash=None, sw=1.2, stroke="#000"):
        self.poly([(x1, y1), (x2, y2)], end=end, start=start, dash=dash, sw=sw, stroke=stroke)

    def poly(self, pts, end="arr", start=None, dash=None, sw=1.2, stroke="#000"):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        me = f' marker-end="url(#{end})"' if end else ""
        ms = f' marker-start="url(#{start}s)"' if start else ""
        p = " ".join(f"{x},{y}" for x, y in pts)
        self.parts.append(
            f'<polyline points="{p}" fill="none" stroke="{stroke}" stroke-width="{sw}"{d}{me}{ms}/>'
        )

    def ellipse(self, cx, cy, rx, ry, fill="#fff", stroke="#000", sw=1.3):
        self.parts.append(
            f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def circle(self, cx, cy, r, fill="#fff", stroke="#000", sw=1.3):
        self.parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def path(self, d, fill="none", stroke="#000", sw=1.3, dash=None):
        dd = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{dd}/>')

    def diamond(self, cx, cy, w, h, fill="#fff"):
        self.path(f"M{cx},{cy - h / 2} L{cx + w / 2},{cy} L{cx},{cy + h / 2} L{cx - w / 2},{cy} Z", fill=fill)

    # -- composites -------------------------------------------------------
    def box(self, x, y, w, h, label, size=15, rx=6, fill="#fff", weight="normal", dash=None, sw=1.3):
        self.rect(x, y, w, h, rx=rx, fill=fill, dash=dash, sw=sw)
        self.text(x + w / 2, y + h / 2, label, size=size, weight=weight)

    def cylinder(self, x, y, w, h, label, size=14, fill="#fff"):
        e = 9
        self.path(
            f"M{x},{y + e} L{x},{y + h - e} A{w / 2},{e} 0 0 0 {x + w},{y + h - e} "
            f"L{x + w},{y + e} A{w / 2},{e} 0 0 0 {x},{y + e} Z",
            fill=fill,
        )
        self.path(f"M{x},{y + e} A{w / 2},{e} 0 0 0 {x + w},{y + e}")
        self.text(x + w / 2, y + h / 2 + e / 2, label, size=size)

    # -- DFD symbols (Gane-Sarson) ----------------------------------------
    def process(self, x, y, w, h, num, label, size=14, fill="#fff"):
        """Rounded process box with its number in a top band."""
        self.rect(x, y, w, h, rx=10, fill=fill, sw=1.4)
        self.line(x, y + 22, x + w, y + 22, end=None, sw=1.1)
        self.text(x + w / 2, y + 11, num, size=13, weight="bold")
        self.text(x + w / 2, y + 22 + (h - 22) / 2, label, size=size)

    def store(self, x, y, w, h, sid, label, size=13, fill="#fff"):
        """Data store: open on the right, ID compartment on the left."""
        self.rect(x, y, w, h, fill=fill, stroke="none", sw=0)
        self.path(f"M{x + w},{y} L{x},{y} L{x},{y + h} L{x + w},{y + h}", sw=1.4)
        self.line(x + 40, y, x + 40, y + h, end=None, sw=1.1)
        self.text(x + 20, y + h / 2, sid, size=13, weight="bold")
        self.text(x + 48, y + h / 2, label, size=size, anchor="start")

    def external(self, x, y, w, h, label, size=14):
        self.rect(x, y, w, h, fill=GREY2, sw=1.6)
        self.text(x + w / 2, y + h / 2, label, size=size, weight="bold")

    def vtext(self, x, y, s, size=14, weight="bold"):
        """Text rotated to read bottom-to-top, centred on (x, y)."""
        self.parts.append(
            f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" text-anchor="middle" '
            f'font-weight="{weight}" transform="rotate(-90 {x} {y})">{escape(s)}</text>'
        )

    # -- ER (crow's foot) -------------------------------------------------
    def entity(self, x, y, w, name, attrs, rowh=17):
        """attrs: (key, column, type). key is PK, FK, PK FK, * or ''. Returns (x, y, w, h)."""
        h = 30 + len(attrs) * rowh + 8
        self.rect(x, y, w, h, fill="#fff", sw=1.4)
        self.rect(x, y, w, 28, fill=GREY2, sw=1.4)
        self.text(x + w / 2, y + 14, name, size=13, weight="bold")
        for i, (key, col, typ) in enumerate(attrs):
            yy = y + 34 + rowh * i + rowh / 2
            if key:
                self.text(x + 7, yy, key, size=10, anchor="start", weight="bold")
            self.text(x + 40, yy, col, size=12, anchor="start", weight="bold" if "PK" in key else "normal")
            if typ:
                self.text(x + w - 7, yy, typ, size=10, anchor="end", fill="#555")
        return (x, y, w, h)

    def cf_end(self, px, py, dx, dy, kind):
        """Crow's foot end at (px, py) on an entity edge; (dx, dy) points away from the entity.
        kind: one (||), zero_one (o|), one_many (|<), zero_many (o<)."""
        nx, ny = -dy, dx
        if kind.endswith("many"):
            qx, qy = px + dx * 14, py + dy * 14
            self.line(qx, qy, px + nx * 8, py + ny * 8, end=None, sw=1.3)
            self.line(qx, qy, px - nx * 8, py - ny * 8, end=None, sw=1.3)
            d = 19
        else:
            bx, by = px + dx * 9, py + dy * 9
            self.line(bx + nx * 7, by + ny * 7, bx - nx * 7, by - ny * 7, end=None, sw=1.3)
            d = 15
        if kind.startswith("zero"):
            self.circle(px + dx * (d + 5), py + dy * (d + 5), 5)
        else:
            bx, by = px + dx * (d + 2), py + dy * (d + 2)
            self.line(bx + nx * 7, by + ny * 7, bx - nx * 7, by - ny * 7, end=None, sw=1.3)

    def rel(self, pts, end1, end2, label=None, lpos=None, dash=None):
        """Relationship line through pts; end1 at pts[0], end2 at pts[-1]."""
        self.poly(pts, end=None, dash=dash, sw=1.3)
        for (p, q), kind in (((pts[0], pts[1]), end1), ((pts[-1], pts[-2]), end2)):
            if kind:
                dx, dy = q[0] - p[0], q[1] - p[1]
                n = (dx * dx + dy * dy) ** 0.5
                self.cf_end(p[0], p[1], dx / n, dy / n, kind)
        if label:
            self.label(lpos[0], lpos[1], label, size=12)

    # -- UML package and class --------------------------------------------
    def package(self, x, y, w, h, name, lines, size=12, fill="#fff"):
        """UML package: a name tab above the body; lines listed in the body."""
        tw = min(w - 20, len(name) * 7.3 + 24)
        self.rect(x, y, tw, 24, fill=GREY2, sw=1.4)
        self.text(x + 10, y + 12, name, size=13, anchor="start", weight="bold")
        self.rect(x, y + 24, w, h - 24, fill=fill, sw=1.4)
        top = y + 24 + 12
        for i, line in enumerate(lines):
            italic = line.startswith("uses ")
            self.text(x + 10, top + i * 17 + 8, line, size=size, anchor="start",
                      style="italic" if italic else "normal", fill="#444" if italic else "#000")

    def uml_class(self, x, y, w, name, stereo=None, attrs=(), ops=(), rowh=17, fill="#fff"):
        """UML class box: [stereotype] name / attributes / operations. Returns (x, y, w, h)."""
        head = 26 + (15 if stereo else 0)
        ha = len(attrs) * rowh + (10 if attrs else 6)
        ho = len(ops) * rowh + (10 if ops else 6)
        h = head + ha + ho
        self.rect(x, y, w, h, fill=fill, sw=1.4)
        self.rect(x, y, w, head, fill=GREY2, sw=1.4)
        if stereo:
            self.text(x + w / 2, y + 12, stereo, size=11, style="italic")
            self.text(x + w / 2, y + 29, name, size=13, weight="bold")
        else:
            self.text(x + w / 2, y + 13, name, size=13, weight="bold")
        self.line(x, y + head + ha, x + w, y + head + ha, end=None, sw=1.1)
        # SVG collapses runs of spaces; a continuation line keeps its indent as no-break spaces.
        attrs = [a[:len(a) - len(a.lstrip(" "))].replace(" ", " ") + a.lstrip(" ") for a in attrs]
        ops = [o[:len(o) - len(o.lstrip(" "))].replace(" ", " ") + o.lstrip(" ") for o in ops]
        for i, a in enumerate(attrs):
            self.text(x + 8, y + head + 5 + i * rowh + rowh / 2, a, size=12, anchor="start")
        for i, o in enumerate(ops):
            self.text(x + 8, y + head + ha + 5 + i * rowh + rowh / 2, o, size=12, anchor="start")
        return (x, y, w, h)

    def tri_end(self, px, py, dx, dy, size=13):
        """Hollow generalization triangle with its tip at (px, py); (dx, dy) points from the tip along the line."""
        nx, ny = -dy, dx
        bx, by = px + dx * size, py + dy * size
        self.path(f"M{px},{py} L{bx + nx * size * 0.6},{by + ny * size * 0.6} "
                  f"L{bx - nx * size * 0.6},{by - ny * size * 0.6} Z", fill="#fff", sw=1.3)

    def diamond_end(self, px, py, dx, dy, filled=True, size=11):
        """Composition (filled) or aggregation (hollow) diamond at the whole's end (px, py)."""
        nx, ny = -dy, dx
        mx, my = px + dx * size, py + dy * size
        ex, ey = px + dx * size * 2, py + dy * size * 2
        self.path(f"M{px},{py} L{mx + nx * size * 0.55},{my + ny * size * 0.55} L{ex},{ey} "
                  f"L{mx - nx * size * 0.55},{my - ny * size * 0.55} Z", fill="#000" if filled else "#fff", sw=1.3)

    def note(self, x, y, w, h, lines, size=12):
        """UML note: a rectangle with its top-right corner folded."""
        f = 12
        self.path(f"M{x},{y} L{x + w - f},{y} L{x + w},{y + f} L{x + w},{y + h} L{x},{y + h} Z", fill="#fffbe6", sw=1.2)
        self.path(f"M{x + w - f},{y} L{x + w - f},{y + f} L{x + w},{y + f}", sw=1.1)
        self.text(x + 8, y + h / 2, lines, size=size, anchor="start", style="italic")

    # -- UML activity -----------------------------------------------------
    def start_node(self, cx, cy):
        self.circle(cx, cy, 11, fill="#000")

    def end_node(self, cx, cy):
        self.circle(cx, cy, 13)
        self.circle(cx, cy, 8, fill="#000")

    def actor(self, cx, top, label, size=15):
        """UML stick figure; top is the top of the head."""
        self.circle(cx, top + 11, 11)
        self.line(cx, top + 22, cx, top + 52, end=None, sw=1.4)
        self.line(cx - 20, top + 32, cx + 20, top + 32, end=None, sw=1.4)
        self.line(cx, top + 52, cx - 16, top + 76, end=None, sw=1.4)
        self.line(cx, top + 52, cx + 16, top + 76, end=None, sw=1.4)
        self.text(cx, top + 92, label, size=size)

    def label(self, x, y, s, size=13, anchor="middle", style="italic", bg=True, weight="normal"):
        """A connector label on a white patch so it stays readable over lines."""
        lines = s if isinstance(s, list) else [s]
        if bg:
            wmax = max(len(l) for l in lines) * size * 0.47 + 6
            hh = len(lines) * size * 1.22 + 2
            xx = {"middle": x - wmax / 2, "start": x - 3, "end": x - wmax + 3}[anchor]
            self.rect(xx, y - hh / 2, wmax, hh, fill="#fff", stroke="none", sw=0)
        self.text(x, y, s, size=size, anchor=anchor, style=style, weight=weight)

    # -- output -----------------------------------------------------------
    def save(self, path):
        defs = """<defs>
<marker id="arr" viewBox="0 0 10 10" refX="9.5" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 Z" fill="#000"/></marker>
<marker id="arrs" viewBox="0 0 10 10" refX="9.5" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 Z" fill="#000"/></marker>
<marker id="open" viewBox="0 0 10 10" refX="9.5" refY="5" markerWidth="10" markerHeight="10" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10" fill="none" stroke="#000" stroke-width="1.3"/></marker>
<marker id="opens" viewBox="0 0 10 10" refX="9.5" refY="5" markerWidth="10" markerHeight="10" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10" fill="none" stroke="#000" stroke-width="1.3"/></marker>
</defs>"""
        body = "\n".join(self.parts)
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}">\n{defs}\n'
            f'<rect width="{self.w}" height="{self.h}" fill="#fff"/>\n{body}\n</svg>\n'
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
