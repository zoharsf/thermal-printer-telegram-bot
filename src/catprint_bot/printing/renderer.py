"""Pure rendering pipeline: text/image → PBM for the thermal printer.

No BLE or I/O side effects.
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PAPER_WIDTH = 384
_PADDING = 10
_BORDER_INNER_PADDING = 6

_FONT_CANDIDATES = [
    # Linux / Raspberry Pi (Docker container)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    # macOS (for local dev)
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _wrap_text(text: str, max_width: int, font) -> list[str]:
    scratch = ImageDraw.Draw(Image.new("1", (1, 1)))
    lines: list[str] = []
    for paragraph in text.splitlines():
        if not paragraph.strip():
            lines.append("")
            continue
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}".strip()
            if scratch.textlength(candidate, font=font) <= max_width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
    return lines or [""]


def render_text(text: str, font_size: int, width: int) -> Image.Image:
    font = _load_font(font_size)
    lines = _wrap_text(text, width - 2 * _PADDING, font)
    line_height = font_size + 4
    height = line_height * len(lines) + 2 * _PADDING

    img = Image.new("1", (width, height), 1)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((_PADDING, _PADDING + i * line_height), line, font=font, fill=0)
    return img


def render_image(path: str, width: int) -> Image.Image:
    img = Image.open(path).convert("L")
    aspect = img.height / img.width
    new_height = max(int(width * aspect), 1)
    return img.resize((width, new_height), Image.LANCZOS).convert("1")


def compose(
    body: Image.Image,
    *,
    header: Image.Image | None = None,
    footer: Image.Image | None = None,
    border_width: int = 0,
) -> Image.Image:
    inner_pad = _BORDER_INNER_PADDING if border_width else 0
    offset = border_width + inner_pad

    parts = [p for p in (header, body, footer) if p is not None]
    total_height = sum(p.height for p in parts) + 2 * offset

    canvas = Image.new("1", (PAPER_WIDTH, total_height), 1)
    y = offset
    for part in parts:
        canvas.paste(part, (offset, y))
        y += part.height

    if border_width:
        draw = ImageDraw.Draw(canvas)
        half = border_width // 2
        draw.rectangle(
            [half, half, PAPER_WIDTH - half - 1, total_height - half - 1],
            outline=0,
            width=border_width,
        )

    return canvas


def image_to_pbm(img: Image.Image) -> io.BytesIO:
    buf = io.BytesIO()
    img.save(buf, format="PPM")
    buf.seek(0)
    return buf
