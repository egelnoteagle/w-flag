#!/usr/bin/env python3
"""
LED matrix display handler for the 64x32 P6 HUB75 panel.
Uses the rpi-rgb-led-matrix library (https://github.com/hzeller/rpi-rgb-led-matrix).

Provides two functions:
  show_w_flag()  — render the W flag image on the matrix
  clear()        — blank the matrix
"""

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

# Path to the W flag image (64x32 PNG, pre-processed by prepare_image.py)
IMAGE_PATH = Path(__file__).parent / "w_flag_64x32.png"

# ---------------------------------------------------------------------------
# Try to import the real rgbmatrix bindings (only available on the Pi).
# Fall back to a stub so the rest of the code can be developed/tested off-Pi.
# ---------------------------------------------------------------------------
try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
    from PIL import Image
    _HW_AVAILABLE = True
except ImportError:
    _HW_AVAILABLE = False
    log.warning(
        "rgbmatrix library not found — running in stub mode (no display output)"
    )


def _build_matrix():
    """Configure and return an RGBMatrix instance."""
    options = RGBMatrixOptions()
    options.rows = 32
    options.cols = 64
    options.chain_length = 1
    options.parallel = 1
    options.hardware_mapping = "regular"   # standard HUB75 wiring
    options.scan_mode = 0                  # progressive
    options.pwm_bits = 11
    options.brightness = 80               # 0-100; tune to taste
    options.gpio_slowdown = 1             # Pi Zero may need 2 if flickering
    options.drop_privileges = True
    return RGBMatrix(options=options)


# Module-level matrix singleton so we don't re-initialise on every call.
_matrix = None


def _get_matrix():
    global _matrix
    if _matrix is None and _HW_AVAILABLE:
        _matrix = _build_matrix()
    return _matrix


def show_w_flag() -> None:
    """Display the W flag image on the LED matrix."""
    if not IMAGE_PATH.exists():
        log.error(
            "W flag image not found at %s — run prepare_image.py first", IMAGE_PATH
        )
        return

    if not _HW_AVAILABLE:
        log.info("[STUB] Would display W flag on LED matrix")
        return

    from PIL import Image

    matrix = _get_matrix()
    img = Image.open(IMAGE_PATH).convert("RGB")
    # Ensure correct size (should already be 64x32 after prepare_image.py)
    if img.size != (64, 32):
        img = img.resize((64, 32), Image.LANCZOS)

    canvas = matrix.CreateFrameCanvas()
    canvas.SetImage(img)
    matrix.SwapOnVSync(canvas)
    log.info("W flag displayed on LED matrix")


def clear() -> None:
    """Turn off all LEDs."""
    if not _HW_AVAILABLE:
        log.info("[STUB] Would clear LED matrix")
        return

    matrix = _get_matrix()
    matrix.Clear()
    log.info("LED matrix cleared")
