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


# ── SVG output ───────────────────────────────────────────────────

_SVG_ESCAPE = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;"})


def _measure_monospace_ch(font_size: float) -> float:
    """Return the advance width of one character in DejaVu Sans Mono.

    We render a known string with Pillow and measure the exact pixel width
    so the SVG coordinates match real monospace metrics.
    """
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono.ttf",
            int(font_size),
        )
    except OSError:
        for path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
        ]:
            try:
                font = ImageFont.truetype(path, int(font_size))
                break
            except OSError:
                continue
        else:
            # Fallback: typical ratio for monospace at this size
            return font_size * 0.6

    tmp = Image.new("L", (1, 1))
    draw = ImageDraw.Draw(tmp)
    probe = "0" * 50
    bbox = draw.textbbox((0, 0), probe, font=font)
    return (bbox[2] - bbox[0]) / len(probe)


def grid_to_svg(
    grid: list[list[bool]],
    fg: str,
    bg: str,
    fcolor: str,
    bcolor: str,
    svg_background: str = "#ffffff",
) -> str:
    """Convert a boolean grid to a pure-SVG document.

    Uses <text> + <tspan> elements with a monospace font.  Character
    positions are computed from the measured advance width of DejaVu
    Sans Mono so the grid aligns perfectly in Inkscape, librsvg, and
    browsers alike.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0

    font_size = 14  # px
    cell_w = _measure_monospace_ch(font_size)
    cell_h = font_size * 1.2  # line height

    svg_w = cols * cell_w
    svg_h = rows * cell_h

    fg_esc = fg.translate(_SVG_ESCAPE)
    bg_esc = bg.translate(_SVG_ESCAPE)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {svg_w:.2f} {svg_h:.2f}" '
        f'width="{svg_w:.2f}" height="{svg_h:.2f}">',
        f'<rect width="100%" height="100%" fill="{svg_background}"/>',
    ]

    for r, row in enumerate(grid):
        y = cell_h * r + font_size  # baseline of this row
        run_fg: bool | None = None
        run_start_col = 0
        run_len = 0

        def _flush_run() -> None:
            nonlocal run_fg, run_start_col, run_len
            if run_len == 0:
                return
            color = fcolor if run_fg else bcolor
            char = fg_esc if run_fg else bg_esc
            text = char * run_len
            x = run_start_col * cell_w
            span_w = run_len * cell_w
            parts.append(
                f'<text x="{x:.2f}" y="{y:.2f}" '
                f'font-family="monospace" font-size="{font_size}px" '
                f'textLength="{span_w:.2f}" lengthAdjust="spacing" '
                f'fill="{color}" xml:space="preserve">{text}</text>'
            )
            run_len = 0

        for c, cell in enumerate(row):
            if cell != run_fg:
                _flush_run()
                run_fg = cell
                run_start_col = c
            run_len += 1
        _flush_run()

    parts.append("</svg>")
    return "\n".join(parts)


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
  %(prog)s --format svg -o output.svg CODE
  %(prog)s --format svg --fcolor '#e00' --bcolor '#ddd' -o art.svg HELLO
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
    p.add_argument(
        "-o",
        "--output",
        default=None,
        help="write output to a file instead of stdout",
    )
    p.add_argument(
        "--format",
        choices=["text", "svg"],
        default="text",
        help="output format: 'text' (default) or 'svg'",
    )
    p.add_argument(
        "--fcolor",
        default="#000000",
        help="foreground character colour in SVG as hex code (default: #000000)",
    )
    p.add_argument(
        "--bcolor",
        default="#cccccc",
        help="background character colour in SVG as hex code (default: #cccccc)",
    )
    p.add_argument(
        "--svg-background",
        default="#ffffff",
        help="SVG background colour as hex code (default: #ffffff)",
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

    if args.format == "svg":
        output = grid_to_svg(
            grid,
            fg,
            bg,
            fcolor=args.fcolor,
            bcolor=args.bcolor,
            svg_background=args.svg_background,
        )
    else:
        output = grid_to_string(grid, fg, bg)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(output)
            fh.write("\n")
    else:
        print(output)


if __name__ == "__main__":
    main()
