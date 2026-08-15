"""Create the deterministic image used by the free multimodal ingress smoke."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1000, 500), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 960, 460), outline="black", width=8)
    draw.rectangle((70, 90, 280, 300), fill="red")
    draw.text((340, 90), "ALPHA CLAW", fill="black", stroke_width=1)
    draw.text((340, 175), "PERCEIVE -> SYMBOLIZE -> REASON", fill="blue")
    draw.text((340, 255), "MULTIMODAL IN. SYMBOLIC OUT.", fill="black")
    draw.text((340, 335), "FIXTURE 17", fill="black")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output, format="PNG")


if __name__ == "__main__":
    main()
