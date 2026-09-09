"""
Turns installer/pip-mark.svg into every raster the product needs.

    .venv\\Scripts\\python.exe scripts\\make_icons.py

Writes:
    installer/pip.ico                                        the installer icon
    frontend/flutter/windows/runner/resources/app_icon.ico   the window icon
    frontend/flutter/assets/pip-logo.png                     in-app, light theme
    frontend/flutter/assets/pip-logo-dark.png                in-app, dark theme
    installer/wizard-small.bmp, -2x.bmp                      the wizard panel
    installer/pip-256.png                                    a preview to look at

WHY THE SHAPES ARE REDRAWN RATHER THAN THE FILE RENDERED

There is no SVG renderer in this environment - no cairosvg, no Pillow, no
ImageMagick, no Inkscape - and adding one to build an icon that changes about
once a year would be a heavy dependency for a rare job. requirements.txt is
already pinned to one exact grpcio build because a Windows policy rejected
another; it does not need a rasterizer too.

The mark happens to be arithmetic: a hub, six spokes at sixty-degree intervals,
six nodes on the ends. Circles and capsules are two inequalities, and numpy is
already installed under torch, so this evaluates them per pixel rather than
parsing anything.

That is only safe while the artwork stays this simple, and the SVG is checked
in beside this script so that stays checkable. Paths or gradients and the right
answer becomes exporting PNGs from a design tool.

WHY TWO THEMES AND NOT ONE FILE

The six nodes are the identity and never change. The hub and the spokes flip
with the background - a dark hub on a light ground, a light hub on a dark one -
because a single fixed pair loses one of them on half the surfaces PIP draws
on. The application picks by theme; the .ico cannot, so it gets a solid tile
(see build_icon_tile).

WHY THE .ICO IS WRITTEN BY HAND

Same reason, and it is a plainer format than it sounds: a header, one directory
entry per size, then the images. Sizes up to 128 are BMP because that is what
every consumer understands, including the resource compiler that links the icon
into the Flutter executable. 256 is PNG, because a 256x256 BMP entry costs a
quarter of a megabyte of pixels on its own.
"""

import struct
import sys
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SOURCE_SVG = ROOT / "installer" / "pip-mark.svg"

# The six nodes, clockwise from the top. Identity: identical in both themes.
NODES = [
    (90.0, "#C0392B"),    # red
    (30.0, "#D6336C"),    # pink
    (330.0, "#EFA02E"),   # amber
    (270.0, "#7CB342"),   # green
    (210.0, "#4BA3C9"),   # cyan
    (150.0, "#2547D8"),   # blue
]

# Everything else, per theme. `ground` is only used by the tile the .ico needs.
THEMES = {
    "light": {"hub": "#111111", "spoke": "#D9D6D0", "ground": "#FAFAF8"},
    "dark": {"hub": "#F7F7F5", "spoke": "#3D3D3D", "ground": "#0E0E0E"},
}

# Geometry, in the SVG's own 0-100 viewBox.
CENTRE = 50.0
NODE_ORBIT = 35.0     # distance from the hub to a node's centre
NODE_R = 8.0
HUB_R = 10.5
SPOKE_W = 4.5

# Every size Windows asks for. 16 is the taskbar and title bar, 32 the desktop,
# 48 medium icons, 256 the extra-large view.
SIZES = [16, 24, 32, 48, 64, 128, 256]

SUPERSAMPLE = 8       # per axis, so 64 samples per output pixel


def rgb(colour: str) -> tuple[float, float, float]:
    return tuple(int(colour[i : i + 2], 16) / 255.0 for i in (1, 3, 5))


def node_centre(degrees: float) -> tuple[float, float]:
    """
    Where a node sits, in viewBox coordinates.

    Negated on y because SVG's axis points down and the angles above are read
    the way somebody describes the mark out loud - 90 is the top.
    """
    radians = np.radians(degrees)
    return CENTRE + NODE_ORBIT * np.cos(radians), CENTRE - NODE_ORBIT * np.sin(radians)


def paint(canvas_rgb, canvas_a, mask, colour):
    """Lay `colour` over whatever is already there, wherever `mask` is true."""
    canvas_rgb[mask] = rgb(colour)
    canvas_a[mask] = 1.0


def render(size: int, theme: str = "light", ground: str | None = None) -> np.ndarray:
    """
    The mark at `size` square, as straight (un-premultiplied) RGBA uint8.

    `ground` fills the whole canvas first, for the icon tile; omitted, the
    background stays transparent.

    Supersampled and box-filtered rather than analytically anti-aliased: at
    these sizes the difference is invisible and the arithmetic is one line.
    Compositing happens in PREMULTIPLIED space, because averaging straight
    colour across an edge blends the mark with the transparent background's
    undefined colour and leaves a dark fringe.
    """
    palette = THEMES[theme]
    n = size * SUPERSAMPLE
    axis = (np.arange(n) + 0.5) * (100.0 / n)   # pixel centres on the viewBox
    x, y = np.meshgrid(axis, axis)

    canvas_rgb = np.zeros((n, n, 3), dtype=np.float64)
    canvas_a = np.zeros((n, n), dtype=np.float64)

    if ground:
        canvas_rgb[:] = rgb(ground)
        canvas_a[:] = 1.0

    # Spokes first, so the hub and the nodes cover their ends - which is what
    # gives the round caps in the artwork without drawing any.
    for degrees, _ in NODES:
        nx, ny = node_centre(degrees)
        # Distance from each pixel to the segment hub->node: project onto it,
        # clamp to its length, measure. A capsule, in two lines.
        dx, dy = nx - CENTRE, ny - CENTRE
        length_sq = dx * dx + dy * dy
        t = np.clip(((x - CENTRE) * dx + (y - CENTRE) * dy) / length_sq, 0.0, 1.0)
        px, py = CENTRE + t * dx, CENTRE + t * dy
        paint(canvas_rgb, canvas_a,
              (x - px) ** 2 + (y - py) ** 2 <= (SPOKE_W / 2) ** 2,
              palette["spoke"])

    for degrees, colour in NODES:
        nx, ny = node_centre(degrees)
        paint(canvas_rgb, canvas_a, (x - nx) ** 2 + (y - ny) ** 2 <= NODE_R ** 2, colour)

    paint(canvas_rgb, canvas_a,
          (x - CENTRE) ** 2 + (y - CENTRE) ** 2 <= HUB_R ** 2,
          palette["hub"])

    premultiplied = canvas_rgb * canvas_a[..., None]
    shape = (size, SUPERSAMPLE, size, SUPERSAMPLE)
    down_rgb = premultiplied.reshape(shape + (3,)).mean(axis=(1, 3))
    down_a = canvas_a.reshape(shape).mean(axis=(1, 3))

    with np.errstate(invalid="ignore", divide="ignore"):
        straight = np.where(down_a[..., None] > 0, down_rgb / down_a[..., None], 0.0)

    out = np.zeros((size, size, 4), dtype=np.uint8)
    out[..., :3] = np.clip(straight * 255.0 + 0.5, 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(down_a * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return out


def to_png(image: np.ndarray) -> bytes:
    """Minimal RGBA PNG. zlib and struct are both standard library."""
    height, width = image.shape[:2]
    raw = b"".join(
        bytes(1) + image[row].tobytes()  # filter type 0 (None) per scanline
        for row in range(height)
    )

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    return (
        bytes([0x89]) + b"PNG\r\n" + bytes([0x1A]) + b"\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def to_bmp_entry(image: np.ndarray) -> bytes:
    """
    One icon image as a BITMAPINFOHEADER DIB, which is what an .ico entry is.

    Three things here are easy to get wrong and all three are load-bearing: the
    height in the header is DOUBLED (it covers the colour image plus a one-bit
    mask that follows), rows are stored BOTTOM-UP, and the channel order is
    BGRA rather than RGBA.

    The AND mask is all-zero - the pre-alpha way of saying "opaque". Everything
    modern ignores it in favour of the alpha channel, but it still has to be
    present and correctly sized, padded to a 32-bit boundary per row.
    """
    height, width = image.shape[:2]
    header = struct.pack(
        "<IiiHHIIiiII",
        40, width, height * 2, 1, 32, 0, 0, 0, 0, 0, 0,
    )
    pixels = image[::-1, :, [2, 1, 0, 3]].tobytes()
    mask_row_bytes = ((width + 31) // 32) * 4
    return header + pixels + bytes(mask_row_bytes * height)


def to_bmp_file(image: np.ndarray, background=(255, 255, 255)) -> bytes:
    """
    A standalone 24-bit .bmp, for Inno Setup's wizard artwork.

    Flattened onto a solid background rather than kept transparent: BMP alpha
    support is inconsistent and Inno's wizard does not rely on it, so a 32-bit
    file with alpha renders as a black box often enough not to risk it.

    Differs from the DIB inside an .ico in two ways that matter: it carries a
    BITMAPFILEHEADER, and it has no AND mask - so the height in the info header
    is the real height rather than double it.
    """
    height, width = image.shape[:2]
    alpha = image[..., 3:4].astype(np.float64) / 255.0
    flat = image[..., :3].astype(np.float64) * alpha + np.array(background) * (1 - alpha)
    bgr = np.clip(flat + 0.5, 0, 255).astype(np.uint8)[::-1, :, ::-1]

    padding = (-(width * 3)) % 4
    rows = b"".join(bgr[y].tobytes() + bytes(padding) for y in range(height))
    info = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, len(rows), 0, 0, 0, 0)
    return struct.pack("<2sIHHI", b"BM", 14 + len(info) + len(rows), 0, 0, 14 + len(info)) + info + rows


def build_ico(images: dict[int, np.ndarray]) -> bytes:
    """Assemble the multi-size .ico container."""
    entries, payloads, offset = [], [], 6 + 16 * len(images)
    for size in sorted(images):
        data = to_png(images[size]) if size > 128 else to_bmp_entry(images[size])
        payloads.append(data)
        entries.append(
            struct.pack(
                "<BBBBHHII",
                size if size < 256 else 0,   # 0 means 256 in this field
                size if size < 256 else 0,
                0, 0, 1, 32, len(data), offset,
            )
        )
        offset += len(data)
    return struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries) + b"".join(payloads)


def main() -> int:
    if not SOURCE_SVG.exists():
        print(f"ERROR: the artwork is missing: {SOURCE_SVG}", file=sys.stderr)
        print("       It is checked in beside this script so the icon stays", file=sys.stderr)
        print("       reproducible - restore it rather than editing shapes here.", file=sys.stderr)
        return 1

    print(f"  source   {SOURCE_SVG.relative_to(ROOT)}")
    print(f"  sizes    {', '.join(str(s) for s in SIZES)}")
    print()

    # The .ico is a solid tile, on the dark ground, because an icon cannot ask
    # what theme it is being drawn on. A transparent mark would lose its hub on
    # whichever taskbar colour did not match, and the hub is the middle of it.
    tile = {size: render(size, "dark", ground=THEMES["dark"]["ground"]) for size in SIZES}
    ico = build_ico(tile)
    for target in (
        ROOT / "installer" / "pip.ico",
        ROOT / "frontend" / "flutter" / "windows" / "runner" / "resources" / "app_icon.ico",
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(ico)
        print(f"  wrote    {target.relative_to(ROOT)}  ({len(ico) / 1024:.0f} KB)")

    # In the application the theme IS known, so both variants ship transparent
    # and lib/logo.dart picks. Written from here rather than copied by hand, so
    # the window icon, the installer and the picture inside the app cannot
    # drift apart - they all come from one run of this.
    assets = ROOT / "frontend" / "flutter" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for theme, name in (("light", "pip-logo.png"), ("dark", "pip-logo-dark.png")):
        (assets / name).write_bytes(to_png(render(256, theme)))
        print(f"  wrote    {(assets / name).relative_to(ROOT)}")

    preview = ROOT / "installer" / "pip-256.png"
    preview.write_bytes(to_png(render(256, "light")))
    print(f"  wrote    {preview.relative_to(ROOT)}")

    # Inno's wizard artwork. Two sizes because it picks by DPI, and one 55px
    # image upscaled is visibly soft on the one screen somebody watches while
    # waiting. On white, because that is what the modern wizard style puts
    # behind it.
    for size, name in ((55, "wizard-small.bmp"), (138, "wizard-small-2x.bmp")):
        target = ROOT / "installer" / name
        target.write_bytes(to_bmp_file(render(size, "light")))
        print(f"  wrote    {target.relative_to(ROOT)}")

    print()
    print("  Rebuild the app for the window icon and assets to change:")
    print("      cd frontend\\flutter; flutter build windows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
