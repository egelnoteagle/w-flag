#!/usr/bin/env python3
"""
Resize and optimise the source W flag image for the 64x32 LED matrix.
Run once after cloning the repo (or any time you swap the source image).

Usage:
    python3 prepare_image.py [source_image]

If no source image is given, looks for w_flag_source.png in the same directory.
Output is always w_flag_64x32.png.
"""

import sys
from pathlib import Path

from PIL import Image, ImageEnhance

MATRIX_W, MATRIX_H = 64, 32
OUTPUT_PATH = Path(__file__).parent / "w_flag_64x32.png"
DEFAULT_SOURCE = Path(__file__).parent / "w_flag_source.png"


def prepare(source_path: Path) -> None:
    """Resize and centre source_path onto a white 64x32 canvas and save to OUTPUT_PATH."""
    img = Image.open(source_path).convert("RGB")

    # --- Crop to flag content (remove whitespace / pole hardware) ----------
    # The flag image is landscape; we want the W centred with minimal border.
    # PIL thumbnail keeps aspect ratio; we then paste onto a white 64x32 canvas
    # with the flag centred.
    img.thumbnail((MATRIX_W, MATRIX_H), Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (MATRIX_W, MATRIX_H), (255, 255, 255))
    x_off = (MATRIX_W - img.width) // 2
    y_off = (MATRIX_H - img.height) // 2
    canvas.paste(img, (x_off, y_off))

    # Boost contrast slightly — LED panels wash out at lower brightness
    canvas = ImageEnhance.Contrast(canvas).enhance(1.3)

    canvas.save(OUTPUT_PATH)
    print(f"Saved {OUTPUT_PATH}  ({MATRIX_W}x{MATRIX_H} px)")


def main() -> None:
    """Parse CLI argument and invoke prepare()."""
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    if not source.exists():
        print(f"Source image not found: {source}")
        print("Place your W flag image at w_flag_source.png or pass a path as an argument.")
        sys.exit(1)
    prepare(source)


if __name__ == "__main__":
    main()
