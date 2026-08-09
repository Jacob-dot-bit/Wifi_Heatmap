#!/usr/bin/env python3
"""Draw the synthetic floor plan shipped as data/plan.png.

The repository must not carry a picture of a real place, so the sample
background is generated instead. The layout is built around the sample
survey: a central service block, a corridor looping around it, and rooms
opening off that corridor. Colours stay light so the red-to-green heatmap
overlay remains readable on top.

Usage: python3 tools/make_sample_plan.py [output.png]
"""

import sys
from pathlib import Path
from PIL import Image, ImageDraw

WIDTH, HEIGHT = 489, 449

BACKDROP = (226, 223, 216)
FLOOR = (245, 243, 238)
CORRIDOR = (237, 234, 228)
SERVICE = (223, 228, 231)
WALL = (63, 63, 66)
FURNITURE = (196, 192, 185)
FIXTURE = (176, 190, 198)
LABEL = (138, 135, 130)

OUTER = (40, 40, 450, 410)
BLOCK = (205, 190, 315, 295)   # stairwell and services, never walked through
LEFT_WALL, RIGHT_WALL = 175, 345
UPPER, LOWER = 190, 295        # room splits in the side wings
BOTTOM = 350                   # bottom room split in the middle wing

THICK, THIN = 7, 5

ROOMS = [
    # (x0, y0, x1, y1, label)
    (40, 40, LEFT_WALL, UPPER, "BEDROOM 1"),
    (40, UPPER, LEFT_WALL, LOWER, "BEDROOM 2"),
    (40, LOWER, LEFT_WALL, 410, "BATH"),
    (RIGHT_WALL, 40, 450, UPPER, "OFFICE"),
    (RIGHT_WALL, UPPER, 450, LOWER, "BEDROOM 3"),
    (RIGHT_WALL, LOWER, 450, 410, "STORAGE"),
    (LEFT_WALL, BOTTOM, RIGHT_WALL, 410, "KITCHEN"),
]

# Wall segments as (x0, y0, x1, y1, thickness).
WALLS = [
    (OUTER[0], OUTER[1], OUTER[2], OUTER[1], THICK),
    (OUTER[0], OUTER[3], OUTER[2], OUTER[3], THICK),
    (OUTER[0], OUTER[1], OUTER[0], OUTER[3], THICK),
    (OUTER[2], OUTER[1], OUTER[2], OUTER[3], THICK),
    (LEFT_WALL, OUTER[1], LEFT_WALL, OUTER[3], THIN),
    (RIGHT_WALL, OUTER[1], RIGHT_WALL, OUTER[3], THIN),
    (OUTER[0], UPPER, LEFT_WALL, UPPER, THIN),
    (OUTER[0], LOWER, LEFT_WALL, LOWER, THIN),
    (RIGHT_WALL, UPPER, OUTER[2], UPPER, THIN),
    (RIGHT_WALL, LOWER, OUTER[2], LOWER, THIN),
    (LEFT_WALL, BOTTOM, RIGHT_WALL, BOTTOM, THIN),
    (BLOCK[0], BLOCK[1], BLOCK[2], BLOCK[1], THIN),
    (BLOCK[0], BLOCK[3], BLOCK[2], BLOCK[3], THIN),
    (BLOCK[0], BLOCK[1], BLOCK[0], BLOCK[3], THIN),
    (BLOCK[2], BLOCK[1], BLOCK[2], BLOCK[3], THIN),
]

# Door openings, painted back over the walls afterwards.
DOORS = [
    (LEFT_WALL, 95, LEFT_WALL, 140),
    (LEFT_WALL, 225, LEFT_WALL, 265),
    (LEFT_WALL, 320, LEFT_WALL, 355),
    (RIGHT_WALL, 100, RIGHT_WALL, 140),
    (RIGHT_WALL, 220, RIGHT_WALL, 260),
    (RIGHT_WALL, 320, RIGHT_WALL, 355),
    (225, BOTTOM, 285, BOTTOM),
    (BLOCK[0], 215, BLOCK[0], 255),
    (150, OUTER[3], 200, OUTER[3]),
]


def seg(draw, x0, y0, x1, y1, thickness, colour):
    half = thickness // 2
    draw.rectangle(
        [min(x0, x1) - half, min(y0, y1) - half,
         max(x0, x1) + half, max(y0, y1) + half],
        fill=colour,
    )


def draw_plan(path: Path) -> None:
    img = Image.new("RGB", (WIDTH, HEIGHT), BACKDROP)
    d = ImageDraw.Draw(img)

    d.rectangle(list(OUTER), fill=CORRIDOR)
    for x0, y0, x1, y1, _ in ROOMS:
        d.rectangle([x0, y0, x1, y1], fill=FLOOR)
    d.rectangle(list(BLOCK), fill=SERVICE)

    for x0, y0, x1, y1, thickness in WALLS:
        seg(d, x0, y0, x1, y1, thickness, WALL)
    for x0, y0, x1, y1 in DOORS:
        seg(d, x0, y0, x1, y1, THIN + 2, FLOOR if x0 != x1 or y0 != y1 else FLOOR)

    # Stairs inside the service block.
    for i, y in enumerate(range(202, 284, 11)):
        d.rectangle([218, y, 268, y + 8], fill=FURNITURE, outline=WALL, width=1)
    d.rectangle([278, 200, 306, 240], fill=FIXTURE, outline=WALL, width=1)
    d.ellipse([282, 250, 302, 276], fill=FIXTURE, outline=WALL, width=1)

    # Beds, desk and kitchen units, drawn as simple blocks.
    for x0, y0, x1, y1 in [(56, 58, 116, 122), (56, 206, 116, 270),
                           (362, 206, 428, 270)]:
        d.rectangle([x0, y0, x1, y1], fill=FURNITURE, outline=WALL, width=1)
        d.line([x0, y0 + 16, x1, y0 + 16], fill=WALL, width=1)
    d.rectangle([362, 58, 434, 92], fill=FURNITURE, outline=WALL, width=1)
    d.rectangle([56, 320, 100, 356], fill=FIXTURE, outline=WALL, width=1)
    d.ellipse([58, 372, 96, 398], fill=FIXTURE, outline=WALL, width=1)
    for x in range(190, 330, 46):
        d.rectangle([x, 366, x + 38, 398], fill=FURNITURE, outline=WALL, width=1)
    d.rectangle([364, 320, 432, 398], fill=FURNITURE, outline=WALL, width=1)

    # Sofa and table in the open area north of the service block.
    d.rectangle([214, 74, 306, 104], fill=FURNITURE, outline=WALL, width=1)
    d.rounded_rectangle([236, 122, 284, 158], radius=6,
                        fill=FURNITURE, outline=WALL, width=1)

    # Labels sit at the top of each room, clear of the furniture below.
    for x0, y0, x1, y1, label in ROOMS:
        d.text(((x0 + x1) // 2 - len(label) * 2.5, y0 + 9), label, fill=LABEL)
    d.text((186, 168), "LIVING", fill=LABEL)
    d.text((222, 301), "STAIRS", fill=LABEL)
    d.text((8, HEIGHT - 15), "sample floor plan - not a real building", fill=LABEL)

    img.save(path, "PNG")
    print(f"{path} written ({WIDTH}x{HEIGHT})")


if __name__ == "__main__":
    draw_plan(Path(sys.argv[1] if len(sys.argv) > 1 else "data/plan.png"))
