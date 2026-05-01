# [![ASCII-Block created from 0 and 1](https://raw.githubusercontent.com/jcubic/ascii-block/refs/heads/master/logo.svg)](https://github.com/jcubic/ascii-block)

[![pip](https://img.shields.io/badge/pip-0.1.0-blue.svg)](https://pypi.org/project/ascii-block/)
[![LICENSE MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](https://github.com/jcubic/ascii-block/blob/master/LICENSE)

ASCII-Block is a Python tool that renders text as binary art using a real font. The text is drawn
onto a Pillow canvas, each pixel is sampled, and the result is output as a character grid where one
character represents the letters and another fills the background.

## Installation

```bash
pip install ascii-block
```

Or install from source:

```bash
git clone https://github.com/jcubic/ascii-block.git
cd ascii-block
pip install .
```

### Requirements

- Python 3.10+
- [Pillow](https://pypi.org/project/Pillow/) (installed automatically)

A TrueType or OpenType font must be available on the system. The tool
auto-detects common fonts (DejaVu Sans Bold, FreeSans Bold, Helvetica, Arial)
or you can specify one explicitly with `--font`.

## Usage

```
block [options] [TEXT]
```

When run without arguments, `block` displays a banner with the version,
an ASCII-BLOCK art preview, and usage instructions. Pass `TEXT` to render
your own text.

## Options

| Short | Long | Default | Description |
|-------|------|---------|-------------|
| `-w` | `--width` | terminal width | Output width in characters. Detected via ANSI DSR escape, falling back to `shutil.get_terminal_size`, then 80. |
| `-h` | `--height` | width / 4 | Output height in characters (minimum 10). |
| `-f` | `--foreground` | `0` | Character(s) used for the text pixels. Supports ANSI escape codes. |
| `-b` | `--background` | `1` | Character(s) used for the background pixels. Supports ANSI escape codes. |
| `-p` | `--padding` | `0` | Padding in characters around the text on all four sides. |
| `-x` | `--font` | auto-detect | Path to a TrueType/OpenType font file. |
| `-o` | `--output` | stdout | Write output to a file instead of printing. |
| | `--format` | `text` | Output format: `text` or `svg`. |
| | `--fcolor` | `#000000` | Foreground character colour in SVG (hex code). |
| | `--bcolor` | `#cccccc` | Background character colour in SVG (hex code). |
| | `--svg-background` | `#ffffff` | SVG rectangle background colour (hex code). |
| `-v` | `--version` | | Show version number and exit. |
| | `--help` | | Show help message and exit. |

> **Note:** `-h` is used for `--height`, so help is only available via `--help`.

## ANSI Escape Codes

The `--foreground` and `--background` values support escape notations so you can
produce coloured terminal output. The following forms are recognised and
converted to the real escape character:

- `\033` or `\e` — ESC
- `\x1b` — hex byte
- `\u001b` — Unicode escape

Wrap the value in single quotes to prevent your shell from interpreting the
backslashes.

For a full reference on ANSI escape codes, see:
- [ANSI Escape Sequences — Gist by fnky](https://gist.github.com/fnky/458719343aabd01cfb17a3a4f7296797)
- [ANSI escape code — Wikipedia](https://en.wikipedia.org/wiki/ANSI_escape_code)

## Examples

### Basic usage

```bash
block CODE
```

```
11111111111001111111111111111001111111111111111111111111111111111111111111111111
11111110000000000111111110000000000111111110000000000001111111110000000000000111
11111000000000000011111100000000000001111110000000000000011111110000000000000111
11110000000000000011111000000000000000111110000000000000001111110000000000000111
11100000001111100011110000001111000000111110000011110000000111110000011111111111
11100000111111111111100000011111100000011110000011111100000011110000011111111111
11000000111111111111100000111111110000011110000011111110000011110000011111111111
11000001111111111111100000111111110000011110000011111110000001110000011111111111
11000001111111111111100000111111111000001110000011111111000001110000000000000111
11000001111111111111100000111111111000001110000011111111000001110000000000000111
11000001111111111111100000111111111000001110000011111111000001110000000000000111
11000001111111111111100000111111111000001110000011111111000001110000001111111111
11000001111111111111100000111111110000011110000011111110000001110000011111111111
11000000111111111111100000111111110000011110000011111110000011110000011111111111
11100000111111111111100000011111100000011110000011111100000011110000011111111111
11100000001111100011110000001111000000111110000011100000000111110000001111111111
11110000000000000011111000000000000000111110000000000000001111110000000000000011
11111000000000000011111100000000000001111110000000000000011111110000000000000011
11111110000000000111111110000000000111111110000000000001111111110000000000000011
11111111111001111111111111111001111111111111111111111111111111111111111111111111

```

### Custom characters

```bash
block -f '#' -b '.' HELLO
```

```
......................................................................#.........
..#####......####....###########....####..........####............########......
..#####......####....###########....####..........####...........###########....
..#####......####....###########....####..........####..........#############...
..#####......####....####...........####..........####.........#####....#####...
..#####......####....####...........####..........####.........####......#####..
..#####......####....####...........####..........####........#####.......####..
..#####......####....####...........####..........####........#####.......####..
..###############....##########.....####..........####........####........####..
..###############....##########.....####..........####........####........####..
..###############....##########.....####..........####........####........####..
..#####.....#####....####...........####..........####........####........####..
..#####......####....####...........####..........####........#####.......####..
..#####......####....####...........####..........####........#####.......####..
..#####......####....####...........####..........####.........####......#####..
..#####......####....####...........####..........####.........#####....#####...
..#####......####....###########....###########...###########...#############...
..#####......####....###########....###########...###########....###########....
..#####......####....###########....###########...###########.....########......
......................................................................#.........
```

### Coloured terminal output

```bash
# Red text on grey background
block -f '\033[31m0\033[0m' -b '\033[90m1\033[0m'

# Green block letters
block -f '\033[42m \033[0m' -b ' ' HELLO
```

### Explicit dimensions and padding

```bash
block -w 120 -h 30 HELLO
block -w 60 -h 15 -p 3 CODE
```

### Custom font

```bash
block -x /usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf CODE
```

### SVG output

```bash
# Default colours
block --format svg -o output.svg CODE

# Custom character and SVG colours
block --format svg \
  --fcolor '#e00' --bcolor '#ddd' \
  -f '#' -b '.' \
  -o art.svg HELLO

# Dark background
block --format svg \
  --svg-background '#1a1a2e' \
  --fcolor '#e00' --bcolor '#555' \
  -o dark.svg CODE
```

### Save text to file

```bash
block -o output.txt CODE
```

## License

Copyright (C) 2026 [Jakub T. Jankiewicz](https://jakub.jankiewicz.org)<br />
Released under MIT license
