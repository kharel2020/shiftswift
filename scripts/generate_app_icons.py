#!/usr/bin/env python3
"""Generate Hastings-style ShiftSwift PWA app icons (Pillow only)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "frontend" / "assets"

GREEN = "#0F6E56"
GREEN_LIGHT = "#5DCAA5"
GREEN_SOFT = "#9FE1CB"
INK = "#111111"
WHITE = "#FFFFFF"


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_mark(draw: ImageDraw.ImageDraw, cx: int, top: int, scale: float = 1.0) -> None:
    size = int(96 * scale)
    left = cx - size // 2
    radius = int(20 * scale)
    draw.rounded_rectangle(
        (left, top, left + size, top + size),
        radius=radius,
        fill=GREEN,
    )
    bar_h = max(4, int(7 * scale))
    bar_rx = bar_h // 2
    bars = [
        (left + int(16 * scale), top + int(16 * scale), int(36 * scale), GREEN_LIGHT),
        (left + int(16 * scale), top + int(29 * scale), int(26 * scale), GREEN_SOFT),
        (left + int(16 * scale), top + int(42 * scale), int(32 * scale), GREEN_LIGHT),
    ]
    for x_off, y_off, width, color in bars:
        draw.rounded_rectangle(
            (x_off, y_off, x_off + width, y_off + bar_h),
            radius=bar_rx,
            fill=color,
        )
    y_line = top + int(65 * scale)
    x1 = left + int(16 * scale)
    x2 = left + int(80 * scale)
    sw = max(3, int(4 * scale))
    draw.line((x1, y_line, x2, y_line), fill=WHITE, width=sw)
    ax = left + int(63 * scale)
    ay = top + int(55 * scale)
    draw.line((ax, ay, x2, y_line), fill=WHITE, width=sw)
    draw.line((ax, top + int(75 * scale), x2, y_line), fill=WHITE, width=sw)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def render_icon(*, bottom_label: str, maskable: bool, size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), WHITE)
    draw = ImageDraw.Draw(img)

    pad = int(size * (0.14 if maskable else 0.06))
    draw.rounded_rectangle((pad, pad, size - pad, size - pad), radius=int(size * 0.21), fill=WHITE)

    cx = size // 2
    mark_top = int(size * (0.11 if maskable else 0.09))
    mark_scale = (0.98 if maskable else 1.08) * (size / 512)
    _draw_mark(draw, cx, mark_top, scale=mark_scale)

    mark_height = int(96 * mark_scale)
    mark_bottom = mark_top + mark_height

    word_size = int(size * 0.098)
    label_size = int(size * (0.052 if bottom_label == "HR" else 0.044))
    word_font = _font(word_size)
    label_font = _font(label_size)

    shift = "Shift"
    swift = "Swift"
    shift_w = _text_width(draw, shift, word_font)
    swift_w = _text_width(draw, swift, word_font)
    total_w = shift_w + swift_w
    word_y = mark_bottom + int(size * 0.028)
    x = cx - total_w // 2
    draw.text((x, word_y), shift, fill=INK, font=word_font)
    draw.text((x + shift_w, word_y), swift, fill=GREEN, font=word_font)

    word_box = draw.textbbox((x, word_y), shift + swift, font=word_font)
    word_bottom = word_box[3]
    label_y = word_bottom + int(size * 0.045)
    label_w = _text_width(draw, bottom_label, label_font)
    draw.text((cx - label_w // 2, label_y), bottom_label, fill=GREEN, font=label_font)

    return img


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    variants = [
        ("app-icon-hr", "HR", False),
        ("app-icon-hr-maskable", "HR", True),
        ("app-icon-clock", "CLOCK", False),
    ]
    for base, label, maskable in variants:
        for size in (180, 192, 512):
            out = ASSETS / f"{base}-{size}.png"
            render_icon(bottom_label=label, maskable=maskable, size=size).save(out, "PNG")
            print(f"wrote {out.relative_to(ROOT)}")

    aliases = {
        "app-icon-hr-512.png": "shiftswift-hr-app-icon.png",
        "app-icon-hr-maskable-512.png": "shiftswift-hr-app-icon-maskable.png",
        "app-icon-hr-192.png": "shiftswift-hr-app-icon-192.png",
        "app-icon-clock-512.png": "shiftswift-clock-app-icon.png",
        "app-icon-clock-192.png": "shiftswift-clock-app-icon-192.png",
        "app-icon-hr-180.png": "shiftswift-hr-app-icon-180.png",
        "app-icon-clock-180.png": "shiftswift-clock-app-icon-180.png",
    }
    for src, dest in aliases.items():
        target = ASSETS / dest
        target.write_bytes((ASSETS / src).read_bytes())
        print(f"wrote {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
