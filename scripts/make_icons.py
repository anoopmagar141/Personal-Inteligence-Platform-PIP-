"""
Turns installer/pip-iris-blue.svg into the .ico files Windows needs.

    .venv\\Scripts\\python.exe scripts\\make_icons.py

Writes:
    installer/pip.ico                                   the installer's icon
    frontend/flutter/windows/runner/resources/app_icon.ico   the window icon

WHY THE SHAPES ARE REDRAWN RATHER THAN THE FILE RENDERED

There is no SVG renderer in this environment - no cairosvg, no Pillow, no
ImageMagick, no Inkscape - and adding one to build an icon that changes about
once a year would be a heavy dependency for a rare job. requirements.txt is
already pinned to the exact grpcio build a Windows policy will accept; it does
not need a rasterizer too.

The mark happens to be arithmetic. Every blade is one circle minus another
circle minus a rotated half-plane, repeated six times at sixty-degree
intervals, and numpy is already installed as a dependency of torch. So this
evaluates those inequalities per pixel instead of parsing anything.

That is only safe because the shapes are simple and the SVG is checked in
beside this file: if the artwork is ever replaced with something involving
paths or gradients, this stops being appropriate and the right answer becomes
exporting PNGs from a design tool and assembling those.

WHY THE .ICO IS WRITTEN BY HAND

Same reason, and it is a simpler format than it sounds: a header, one directory
entry per size, then the images. Sizes up to 128 are written as BMP because
that is what every consumer of an .ico understands, including the resource
compiler that links the icon into the Flutter executable. 256 is written as PNG
because a 256x256 BMP entry costs 256 KB on its own and PNG entries have been
supported since Windows Vista.
"""

import struct
import sys
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SOURCE_SVG = ROOT / "installer" / "pip-iris-blue.svg"

# The six blade colours, in the order the SVG paints them - darkest first, so
# each blade sits in front of the one before it.
BLADE_COLOURS = ["#1B2E8C", "#2C4BE0", "#4B66E8", "#6B85FF", "#93A6FF", "#C2CCFF"]

# The mask geometry, in the SVG's own 0-100 viewBox units.
CENTRE = 50.0
OUTER_R = 45.0          # circle cx=50 cy=50 r=45, the blade's outer edge
INNER_R = 39.0          # circle cx=64 cy=50 r=39, cut out - the aperture
INNER_CX = 64.0
CUT_ANGLE = -18.0       # the half-plane rect, rotate(-18 50 50)

# Every size Windows asks for. 16 is the taskbar and title bar, 32 the desktop,
# 48 medium icons, 256 the extra-large view and the installer's own header.
SIZES = [16, 24, 32, 48, 64, 128, 256]

SUPERSAMPLE = 8         # per axis, so 64 samples per output pixel


def rotate(x, y, degrees):
    """
    Rotate about the mark's centre, in SVG's convention.

    SVG's y axis points down, so a positive angle turns clockwise on screen -
    which is why this is written out rather than reached for from a library
    that would use the mathematical convention and mirror the artwork.
    """
    radians = np.radians(degrees)
    cos, sin = np.cos(radians), np.sin(radians)
    dx, dy = x - CENTRE, y - CENTRE
    return CENTRE + dx * cos - dy * sin, CENTRE + dx * sin + dy * cos


def blade_mask(x, y):
    """The `blade` mask from the SVG: a circle, less a circle, less a wedge."""
    inside_outer = (x - CENTRE) ** 2 + (y - CENTRE) ** 2 <= OUTER_R ** 2
    inside_inner = (x - INNER_CX) ** 2 + (y - CENTRE) ** 2 <= INNER_R ** 2

    # The subtracted rect is x=50..100 over the full height, rotated -18 about
    # the centre. A device point is inside it if rotating it BACK by that angle
    # lands in the unrotated rectangle.
    rx, ry = rotate(x, y, -CUT_ANGLE)
    inside_cut = (rx >= 50.0) & (rx <= 100.0) & (ry >= 0.0) & (ry <= 100.0)

    return inside_outer & ~inside_inner & ~inside_cut


def render(size: int) -> np.ndarray:
    """
    The mark at `size` square, as straight (un-premultiplied) RGBA uint8.

    Supersampled and box-filtered rather than analytically anti-aliased: at
    these sizes the difference is invisible and the arithmetic is one line.
    Compositing happens in PREMULTIPLIED space, because averaging straight
    colour across an edge blends the blade's blue with the transparent
    background's undefined colour and leaves a dark fringe.
    """
    n = size * SUPERSAMPLE
    # Pixel centres, mapped onto the SVG's 0-100 viewBox.
    axis = (np.arange(n) + 0.5) * (100.0 / n)
    x, y = np.meshgrid(axis, axis)

    rgb = np.zeros((n, n, 3), dtype=np.float64)
    alpha = np.zeros((n, n), dtype=np.float64)

    for index, colour in enumerate(BLADE_COLOURS):
        # Each blade is the base mask rotated into place. A device point
        # belongs to blade k if rotating it back by k*60 lands in the mask.
        bx, by = rotate(x, y, -60.0 * index)
        covered = blade_mask(bx, by)

        r = int(colour[1:3], 16) / 255.0
        g = int(colour[3:5], 16) / 255.0
        b = int(colour[5:7], 16) / 255.0

        # Painted in order, so a later blade replaces an earlier one where they
        # overlap - which is what the SVG's stacking does.
        rgb[covered] = (r, g, b)
        alpha[covered] = 1.0

    # Premultiply, box-filter down, then un-premultiply.
    premultiplied = rgb * alpha[..., None]
    shape = (size, SUPERSAMPLE, size, SUPERSAMPLE)
    down_rgb = premultiplied.reshape(shape + (3,)).mean(axis=(1, 3))
    down_a = alpha.reshape(shape).mean(axis=(1, 3))

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
        b"\x00" + image[row].tobytes()  # filter type 0 (None) per scanline
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
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def to_bmp_entry(image: np.ndarray) -> bytes:
    """
    One icon image as a BITMAPINFOHEADER DIB, which is what an .ico entry is.

    Three things about this format are easy to get wrong and all three are
    load-bearing: the height in the header is DOUBLED (it covers the colour
    image plus a one-bit mask that follows it), the rows are stored BOTTOM-UP,
    and the channel order is BGRA rather than RGBA.

    The AND mask is written as all-zero. It is the pre-alpha way of saying
    "opaque", and it is ignored in favour of the alpha channel by everything
    modern - but it still has to be present and correctly sized, padded to a
    32-bit boundary per row.
    """
    height, width = image.shape[:2]

    header = struct.pack(
        "<IiiHHIIiiII",
        40,             # header size
        width,
        height * 2,     # colour data + AND mask
        1,              # planes
        32,             # bits per pixel
        0,              # BI_RGB, uncompressed
        0, 0, 0, 0, 0,  # sizes and palette counts, unused at 32bpp
    )

    bgra = image[::-1, :, [2, 1, 0, 3]]  # bottom-up, BGRA
    pixels = bgra.tobytes()

    mask_row_bytes = ((width + 31) // 32) * 4
    and_mask = b"\x00" * (mask_row_bytes * height)

    return header + pixels + and_mask


def to_bmp_file(image: np.ndarray, background=(255, 255, 255)) -> bytes:
    """
    A standalone 24-bit .bmp, for Inno Setup's wizard artwork.

    Flattened onto a solid background rather than kept transparent: BMP's
    alpha support is inconsistent and Inno's wizard does not rely on it, so a
    32-bit file with alpha renders as a black box often enough not to risk it.
    White, because that is what the modern wizard style puts behind it.

    Differs from the DIB inside an .ico in two ways that matter: it carries a
    BITMAPFILEHEADER, and it has no AND mask - so the height in the info
    header is the real height rather than double it.
    """
    height, width = image.shape[:2]

    alpha = image[..., 3:4].astype(np.float64) / 255.0
    flat = image[..., :3].astype(np.float64) * alpha + np.array(background) * (1 - alpha)
    bgr = np.clip(flat + 0.5, 0, 255).astype(np.uint8)[::-1, :, ::-1]  # bottom-up, BGR

    # Every row is padded to a 4-byte boundary.
    row_bytes = width * 3
    padding = (-row_bytes) % 4
    rows = b"".join(bgr[y].tobytes() + bytes(padding) for y in range(height))

    info = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, len(rows), 0, 0, 0, 0)
    size = 14 + len(info) + len(rows)
    file_header = struct.pack("<2sIHHI", b"BM", size, 0, 0, 14 + len(info))
    return file_header + info + rows


def build_ico(images: dict[int, np.ndarray]) -> bytes:
    """Assemble the multi-size .ico container."""
    entries, payloads, offset = [], [], 6 + 16 * len(images)

    for size in sorted(images):
        image = images[size]
        # PNG above 128: a 256x256 BMP entry is 256 KB of pixels on its own,
        # and PNG entries have been understood since Vista. Below that, BMP,
        # because the resource compiler that links this into the executable is
        # the least forgiving consumer in the chain.
        data = to_png(image) if size > 128 else to_bmp_entry(image)
        payloads.append(data)
        entries.append(
            struct.pack(
                "<BBBBHHII",
                size if size < 256 else 0,   # 0 means 256 in this field
                size if size < 256 else 0,
                0,       # palette colours
                0,       # reserved
                1,       # colour planes
                32,      # bits per pixel
                len(data),
                offset,
            )
        )
        offset += len(data)

    return struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries) + b"".join(payloads)


def main() -> int:
    if not SOURCE_SVG.exists():
        print(f"ERROR: the artwork is missing: {SOURCE_SVG}", file=sys.stderr)
        print("       It is checked in beside this script so the icon stays", file=sys.stderr)
        print("       reproducible - restore it rather than editing sizes here.", file=sys.stderr)
        return 1

    print(f"  source   {SOURCE_SVG.relative_to(ROOT)}")
    print(f"  sizes    {', '.join(str(s) for s in SIZES)}")

    images = {size: render(size) for size in SIZES}
    ico = build_ico(images)

    targets = [
        ROOT / "installer" / "pip.ico",
        ROOT / "frontend" / "flutter" / "windows" / "runner" / "resources" / "app_icon.ico",
    ]
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(ico)
        print(f"  wrote    {target.relative_to(ROOT)}  ({len(ico) / 1024:.0f} KB)")

    # The same artwork as a flat PNG, twice: once beside the .ico for looking
    # at, and once as the application's own asset. Written from here rather
    # than copied by hand so the window icon, the installer and the picture
    # inside the app cannot drift apart - they all come from one run of this.
    for preview in (
        ROOT / "installer" / "pip-256.png",
        ROOT / "frontend" / "flutter" / "assets" / "pip-logo.png",
    ):
        preview.parent.mkdir(parents=True, exist_ok=True)
        preview.write_bytes(to_png(images[256]))
        print(f"  wrote    {preview.relative_to(ROOT)}")

    # Inno Setup's wizard artwork. Two sizes because it picks by DPI, and a
    # single 55px image upscaled on a high-DPI display is visibly soft on the
    # one screen somebody looks at while waiting.
    for size, name in ((55, "wizard-small.bmp"), (138, "wizard-small-2x.bmp")):
        target = ROOT / "installer" / name
        target.write_bytes(to_bmp_file(render(size)))
        print(f"  wrote    {target.relative_to(ROOT)}")

    print()
    print("  Rebuild the app for the window icon to change:")
    print("      cd frontend\\flutter; flutter build windows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
