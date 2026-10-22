#!/usr/bin/env python3
"""生成云朵气泡样图（需要 Pillow；运行时桌宠本身仍然只用标准库）。

用法：
    python make_bubble_preview.py [输出路径]

几何和配色直接取自 bubble_shape.py，和桌宠实际绘制保持一致。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bubble_shape import BUBBLE_FILL, BUBBLE_STROKE, BUBBLE_TEXT, cloud_points

SCALE = 3
CANVAS_W, CANVAS_H = 760, 900
FONT_SIZE = 30
PAD_X, PAD_Y = 64, 58
MAX_TEXT_W = 360


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for ch in paragraph:
            trial = current + ch
            if draw.textlength(trial, font=font) <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = ch
        lines.append(current)
    return lines


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "bubble-preview.png"
    text = "又要我帮忙了吗？真是的。"

    image = Image.new("RGB", (CANVAS_W * SCALE, CANVAS_H * SCALE), "#f7f3fc")
    draw = ImageDraw.Draw(image)
    font_path = ROOT / "fonts" / "Yozai-0.868" / "Yozai-Regular.ttf"
    font = ImageFont.truetype(str(font_path), FONT_SIZE * SCALE)

    lines = wrap_text(draw, text, font, MAX_TEXT_W * SCALE)
    line_h = int(font.size * 1.35)
    text_w = max(draw.textlength(line, font=font) for line in lines)
    text_h = line_h * len(lines)

    bubble_w = text_w / SCALE + PAD_X * 2
    bubble_h = text_h / SCALE + PAD_Y * 2
    cx, cy = CANVAS_W / 2, 250
    points = cloud_points(cx, cy, bubble_w, bubble_h)
    draw.polygon(
        [(x * SCALE, y * SCALE) for x, y in points],
        fill=BUBBLE_FILL,
        outline=BUBBLE_STROKE,
        width=3 * SCALE,
    )

    ty = cy - (text_h / SCALE) / 2
    for line in lines:
        width = draw.textlength(line, font=font) / SCALE
        draw.text(
            ((cx - width / 2) * SCALE, ty * SCALE),
            line,
            font=font,
            fill=BUBBLE_TEXT,
        )
        ty += line_h / SCALE

    frame_path = ROOT / "frames" / "idle" / "00.png"
    frame = Image.open(frame_path).convert("RGB")
    pixels = frame.load()
    for y in range(frame.height):
        for x in range(frame.width):
            r, g, b = pixels[x, y]
            if g > 200 and r < 80 and b < 80:
                pixels[x, y] = (247, 243, 252)
    frame = frame.resize((frame.width * SCALE, frame.height * SCALE), Image.LANCZOS)
    image.paste(
        frame,
        (
            int((CANVAS_W * SCALE - frame.width) / 2),
            int(CANVAS_H * SCALE - frame.height - 20 * SCALE),
        ),
    )

    image = image.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    print(out)


if __name__ == "__main__":
    main()
