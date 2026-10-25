"""Draws the Chameleon icon (a chameleon on a branch, its tail curled) and writes it to chameleon/assets/.

The generated files are committed, so this only needs to run after changing the
design. It needs Pillow (see requirements-dev.txt): ``python scripts/generate_icon.py``
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent.parent / "chameleon" / "assets"

CANVAS = 1024  # drawn large, then scaled down for smooth edges
BACKGROUND_TOP = (38, 150, 118)  # leaf green
BACKGROUND_BOTTOM = (12, 74, 64)
CREAM = (250, 236, 208)
GOLD = (240, 176, 64)
GOLD_DARK = (176, 116, 30)
BRANCH = (120, 74, 34)
BRANCH_DARK = (84, 50, 22)
INK = (40, 30, 24)
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]

BODY_CENTER = (530, 620)  # the body is an arch around this point
BODY_RADIUS = (210, 170)
OUTLINE = 14  # darker edge drawn around the gold shapes


def _rounded_background() -> tuple[Image.Image, Image.Image]:
    column = Image.new("RGBA", (1, CANVAS))
    column.putdata([
        tuple(round(a + (b - a) * y / (CANVAS - 1)) for a, b in zip(BACKGROUND_TOP, BACKGROUND_BOTTOM)) + (255,)
        for y in range(CANVAS)
    ])
    gradient = column.resize((CANVAS, CANVAS), Image.Resampling.NEAREST)
    mask = Image.new("L", (CANVAS, CANVAS), 0)
    ImageDraw.Draw(mask).rounded_rectangle((40, 40, CANVAS - 40, CANVAS - 40), radius=210, fill=255)
    background = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    background.paste(gradient, mask=mask)
    return background, mask


def _stroke(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], widths: list[float],
            fill: tuple[int, ...], grow: float = 0) -> None:
    """A smooth stroke of varying width: a disc stamped at every point."""
    for (x, y), width in zip(points, widths):
        radius = width / 2 + grow
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def _body_path(steps: int = 160) -> tuple[list[tuple[float, float]], list[float]]:
    """The spine from the base of the tail, over the arched back, to the neck, with the body's width."""
    cx, cy = BODY_CENTER
    rx, ry = BODY_RADIUS
    points, widths = [], []
    for index in range(steps + 1):
        t = index / steps
        angle = math.radians(170 - 140 * t)  # from the left (tail) round the top to the right (neck)
        points.append((cx + rx * math.cos(angle), cy - ry * math.sin(angle)))
        widths.append(110 + 120 * math.sin(math.pi * min(1.0, t * 1.15)))  # thickest just behind the middle
    return points, widths


def _tail_path(start: tuple[float, float], steps: int = 220) -> tuple[list[tuple[float, float]], list[float]]:
    """A spiral curling inwards below the start point, thinning to a point."""
    start_radius = 132
    center = (start[0], start[1] + start_radius)
    points, widths = [], []
    for index in range(steps + 1):
        t = index / steps
        turn = t * 2.3 * math.pi
        radius = start_radius * math.exp(-0.26 * turn)
        angle = -math.pi / 2 - turn  # start straight above the centre, curl anticlockwise (outwards then in)
        points.append((center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle)))
        widths.append(104 * (1 - t) ** 1.2 + 18)
    return points, widths


def _head(draw: ImageDraw.ImageDraw, neck: tuple[float, float], grow: float, fill: tuple[int, ...]) -> None:
    """Head with a pointed snout and the raised crest (casque) of a chameleon."""
    x, y = neck
    head = [(x - 40, y - 70), (x + 40, y - 150), (x + 90, y - 118), (x + 190, y - 30), (x + 210, y + 10),
            (x + 150, y + 60), (x + 30, y + 74), (x - 40, y + 60)]
    if grow:
        cx = sum(px for px, _ in head) / len(head)
        cy = sum(py for _, py in head) / len(head)
        head = [(px + (px - cx) * grow / 120, py + (py - cy) * grow / 120) for px, py in head]
    draw.polygon(head, fill=fill)


def draw_icon() -> Image.Image:
    background, mask = _rounded_background()
    figure = Image.new("RGBA", background.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(figure)

    body, body_widths = _body_path()
    tail, tail_widths = _tail_path(body[0])
    neck = body[-1]

    # Branch the chameleon grips, under its feet.
    branch_start, branch_end = (110, 808), (930, 736)
    draw.line([branch_start, branch_end], fill=BRANCH_DARK, width=70)
    draw.line([branch_start, branch_end], fill=BRANCH, width=50)

    # Legs, gripping the branch.
    for hip, knee, foot in (((430, 650), (372, 712), (404, 772)), ((650, 640), (712, 690), (694, 752))):
        for width, colour in ((70, GOLD_DARK), (46, GOLD)):
            draw.line([hip, knee, foot], fill=colour, width=width, joint="curve")
            draw.ellipse((knee[0] - width / 2, knee[1] - width / 2, knee[0] + width / 2, knee[1] + width / 2),
                         fill=colour)
        draw.ellipse((foot[0] - 46, foot[1] - 24, foot[0] + 46, foot[1] + 24), fill=GOLD_DARK)

    # Dark edge first, then the gold body, tail and head on top.
    _stroke(draw, tail, tail_widths, GOLD_DARK, grow=OUTLINE / 2)
    _stroke(draw, body, body_widths, GOLD_DARK, grow=OUTLINE / 2)
    _head(draw, neck, OUTLINE, GOLD_DARK)
    _stroke(draw, tail, tail_widths, GOLD)
    _stroke(draw, body, body_widths, GOLD)
    _head(draw, neck, 0, GOLD)

    # A cream stripe along the flank, the colour change chameleons are known for.
    flank = body[16:138]
    _stroke(draw, [(x, y + 40) for x, y in flank], [w * 0.16 for w in body_widths[16:138]], CREAM)

    # The turret eye: a cream ring with a dark pupil looking forward.
    eye_x, eye_y = neck[0] + 88, neck[1] - 46
    draw.ellipse((eye_x - 50, eye_y - 50, eye_x + 50, eye_y + 50), fill=GOLD_DARK)
    draw.ellipse((eye_x - 40, eye_y - 40, eye_x + 40, eye_y + 40), fill=CREAM)
    draw.ellipse((eye_x - 6, eye_y - 18, eye_x + 30, eye_y + 18), fill=INK)
    # Mouth line.
    draw.line([(neck[0] + 100, neck[1] + 24), (neck[0] + 196, neck[1] + 8)], fill=GOLD_DARK, width=12)

    clipped = Image.new("RGBA", background.size, (0, 0, 0, 0))
    clipped.paste(figure, mask=mask)  # keep everything inside the rounded tile
    background.alpha_composite(clipped)
    return background


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    master = draw_icon()
    master.resize((256, 256), Image.Resampling.LANCZOS).save(ASSETS / "chameleon.png")
    for size in (48, 64):
        master.resize((size, size), Image.Resampling.LANCZOS).save(ASSETS / f"chameleon-{size}.png")
    master.save(ASSETS / "chameleon.ico", sizes=[(s, s) for s in ICO_SIZES])
    print(f"Icons written to {ASSETS}")


if __name__ == "__main__":
    main()
