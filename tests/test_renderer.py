# tests/test_renderer.py
import io
from pathlib import Path

import pytest
from PIL import Image

from catprint_bot.printing.renderer import (
    PAPER_WIDTH,
    render_text,
    render_image,
    compose,
    image_to_pbm,
)


def test_render_text_returns_correct_width():
    img = render_text("Hello, world!", font_size=14, width=384)
    assert img.width == 384
    assert img.mode == "1"
    assert img.height > 0


def test_render_text_wraps_long_text():
    long_text = "word " * 100
    img = render_text(long_text, font_size=14, width=384)
    # Should be taller than a single line
    assert img.height > 30


def test_render_text_empty_lines_preserved():
    text = "line1\n\nline3"
    img = render_text(text, font_size=14, width=384)
    assert img.height > 0


def test_render_image_scales_to_width(tmp_path):
    # Create a test image wider than paper
    src = Image.new("RGB", (800, 400), color="white")
    path = tmp_path / "test.png"
    src.save(path)

    result = render_image(str(path), width=384)
    assert result.width == 384
    assert result.mode == "1"


def test_compose_stacks_vertically():
    header = Image.new("1", (360, 20), 1)
    body = Image.new("1", (360, 50), 1)
    footer = Image.new("1", (360, 15), 1)

    result = compose(body, header=header, footer=footer, border_width=0)
    assert result.width == PAPER_WIDTH
    assert result.height == 20 + 50 + 15


def test_compose_with_border():
    body = Image.new("1", (370, 50), 1)
    result = compose(body, border_width=3)
    assert result.width == PAPER_WIDTH
    assert result.height > 50  # border + padding adds height


def test_image_to_pbm():
    img = Image.new("1", (384, 100), 1)
    buf = image_to_pbm(img)
    assert isinstance(buf, io.BytesIO)
    data = buf.read()
    assert len(data) > 0
    assert data[:2] == b"P4"  # PBM magic number
