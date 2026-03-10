#!/usr/bin/env python3
"""
Generate text as a binary art grid using a real font.

Renders the given text onto a Pillow canvas, samples each pixel,
and outputs a grid where foreground characters form the letters
and background characters fill the rest.

Supports ANSI escape codes in --foreground / --background values
(e.g. '\\033[31m0\\033[0m' for red zeros).

Default width is detected from the terminal via the ANSI DSR
(Device Status Report) escape sequence, falling back to
shutil.get_terminal_size, then to 80 columns.
"""

from __future__ import annotations

import argparse
import os
import re
import select
import shutil
import sys
import termios
import tty
from PIL import Image, ImageDraw, ImageFont

# ── Terminal size via ANSI escape codes ──────────────────────────


def _get_terminal_size_ansi() -> tuple[int, int] | None:
    """Query the terminal size using the ANSI DSR trick.

    1. Save cursor position          \\033[s
    2. Move cursor far bottom-right  \\033[9999;9999H
    3. Request cursor position (DSR)  \\033[6n
    4. Read response  \\033[<rows>;<cols>R
    5. Restore cursor position       \\033[u

    Returns (columns, rows) or None on failure.
    """
    # Only works when stdin is a real terminal
    if not os.isatty(sys.stdin.fileno()):
        return None

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        # save pos → jump far → request pos → restore pos
        sys.stdout.write("\033[s\033[9999;9999H\033[6n\033[u")
        sys.stdout.flush()

        # Read the response: \033[rows;colsR
        response = ""
        while True:
            if select.select([fd], [], [], 0.1)[0]:
                ch = os.read(fd, 1).decode("ascii", errors="ignore")
                response += ch
                if ch == "R":
                    break
            else:
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    m = re.search(r"\[(\d+);(\d+)R", response)
    if m:
        rows, cols = int(m.group(1)), int(m.group(2))
        return cols, rows
    return None


def get_terminal_width() -> int:
    """Return the terminal width in columns.

    Tries ANSI DSR first, then shutil.get_terminal_size, then 80.
    """
    try:
        result = _get_terminal_size_ansi()
        if result:
            cols, _rows = result
            if cols > 0:
                return cols
    except Exception:
        pass

    try:
        size = shutil.get_terminal_size(fallback=(80, 24))
        return size.columns
    except Exception:
        return 80


def get_terminal_height() -> int:
    """Return the terminal height in rows.

    Tries ANSI DSR first, then shutil.get_terminal_size, then 24.
    """
    try:
        result = _get_terminal_size_ansi()
        if result:
            _cols, rows = result
            if rows > 0:
                return rows
    except Exception:
        pass

    try:
        size = shutil.get_terminal_size(fallback=(80, 24))
        return size.lines
    except Exception:
        return 24


# ── Font helpers ─────────────────────────────────────────────────

_FONT_SEARCH_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",  # macOS
    "/System/Library/Fonts/SFNSMono.ttf",  # macOS
    "C:\\Windows\\Fonts\\arialbd.ttf",  # Windows
]


def _load_font(
    size: int,
    font_path: str | None = None,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if font_path is not None:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            raise SystemExit(f"error: cannot load font: {font_path}")
    for path in _FONT_SEARCH_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ── Core rendering ───────────────────────────────────────────────


def render_text_to_grid(
    text: str,
    width: int,
    height: int,
    padding: int = 0,
    font_path: str | None = None,
) -> list[list[bool]]:
    """Render *text* into a width x height grid of booleans.

    True  = foreground (the letter pixels)
    False = background

    *padding* shrinks the renderable area by that many characters on
    every side while keeping the overall grid at width x height.
    """
    inner_w = max(width - 2 * padding, 1)
    inner_h = max(height - 2 * padding, 1)

    # Render text at a large size, then scale to fit the target grid.
    # This avoids the problem where font metrics (ascenders, descenders,
    # internal leading) leave the text much shorter than the canvas.

    # 1. Pick a large font and measure the tight bounding box.
    font_size = 200
    font = _load_font(font_size, font_path)
    tmp_img = Image.new("L", (1, 1))  # throwaway, just for measurement
    tmp_draw = ImageDraw.Draw(tmp_img)
    bbox = tmp_draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    if text_w == 0 or text_h == 0:
        # Degenerate case: empty text or whitespace-only
        return [[False] * width for _ in range(height)]

    # 2. Render the text tightly cropped onto an intermediate image.
    margin = 4  # small margin so anti-aliased edges aren't clipped
    render_w = int(text_w) + 2 * margin
    render_h = int(text_h) + 2 * margin
    big_img = Image.new("L", (render_w, render_h), color=255)
    big_draw = ImageDraw.Draw(big_img)
    big_draw.text((margin - bbox[0], margin - bbox[1]), text, font=font, fill=0)

    # 3. Scale the tight rendering to exactly fill the inner grid.
    scaled = big_img.resize((inner_w, inner_h), Image.Resampling.LANCZOS)

    # 4. Threshold each pixel.
    pixels = scaled.load()
    inner_grid: list[list[bool]] = []
    for row in range(inner_h):
        line: list[bool] = []
        for col in range(inner_w):
            line.append(pixels[col, row] < 128)  # type: ignore[index]
        inner_grid.append(line)

    # Wrap with padding (False = background)
    if padding <= 0:
        return inner_grid

    grid: list[list[bool]] = []
    pad_row = [False] * width
    for _ in range(padding):
        grid.append(pad_row[:])
    for inner_row in inner_grid:
        grid.append([False] * padding + inner_row + [False] * padding)
    for _ in range(padding):
        grid.append(pad_row[:])

    return grid


# ── ANSI-aware output ────────────────────────────────────────────


def decode_escape(s: str) -> str:
    r"""Interpret common escape notations so users can pass ANSI codes.

    Handles:
      \\033  \\e  \\x1b  \\x1B  \\u001b  →  ESC (0x1b)
      \\n \\t \\r  →  the usual C escapes
    """
    s = s.replace("\\033", "\033")
    s = s.replace("\\e", "\033")
    s = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)
    s = s.replace("\\n", "\n")
    s = s.replace("\\t", "\t")
    s = s.replace("\\r", "\r")
    return s


def grid_to_string(
    grid: list[list[bool]],
    fg: str,
    bg: str,
) -> str:
    lines: list[str] = []
    for row in grid:
        lines.append("".join(fg if cell else bg for cell in row))
    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Render text as binary art using a real font.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
        epilog="""\
examples:
  %(prog)s CODE
  %(prog)s -f 0 -b 1 CODE
  %(prog)s -w 120 -h 30 HELLO
  %(prog)s -f '\\033[31m#\\033[0m' -b . COOL
  %(prog)s -f '\\033[42m \\033[0m' -b ' ' HI
  %(prog)s -p 3 CODE
  %(prog)s -x /usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf CODE
""",
    )
    p.add_argument(
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help="show this help message and exit",
    )
    p.add_argument(
        "text",
        nargs="?",
        default="CODE",
        help="text to render (default: CODE)",
    )
    p.add_argument(
        "-w",
        "--width",
        type=int,
        default=None,
        help="output width in characters (default: terminal width)",
    )
    p.add_argument(
        "-h",
        "--height",
        type=int,
        default=None,
        help="output height in characters (default: width / 4)",
    )
    p.add_argument(
        "-f",
        "--foreground",
        default="0",
        help="character(s) for the text pixels (default: 0). "
        "Supports ANSI escapes like '\\\\033[31m#\\\\033[0m'.",
    )
    p.add_argument(
        "-b",
        "--background",
        default="1",
        help="character(s) for the background pixels (default: 1). "
        "Supports ANSI escapes like '\\\\033[31m.\\\\033[0m'.",
    )
    p.add_argument(
        "-p",
        "--padding",
        type=int,
        default=0,
        help="padding in characters around the text on all sides (default: 0)",
    )
    p.add_argument(
        "-x",
        "--font",
        default=None,
        help="path to a TrueType/OpenType font file (default: auto-detect system font)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    width = args.width if args.width is not None else get_terminal_width()
    height = args.height if args.height is not None else max(width // 4, 10)

    fg = decode_escape(args.foreground)
    bg = decode_escape(args.background)

    grid = render_text_to_grid(
        args.text,
        width,
        height,
        padding=args.padding,
        font_path=args.font,
    )
    print(grid_to_string(grid, fg, bg))


if __name__ == "__main__":
    main()
