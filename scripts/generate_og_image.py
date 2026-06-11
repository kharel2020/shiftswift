#!/usr/bin/env python3
"""Generate 1200×630 Open Graph preview image for ShiftSwift HR."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "assets" / "og-image.png"

W, H = 1200, 630
GREEN = (15, 110, 86)
GREEN_LIGHT = (93, 202, 165)
GREEN_PALE = (240, 250, 246)
INK = (17, 17, 17)
MUTED = (100, 100, 96)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_logo_mark(draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 120) -> None:
    r = 18
    draw.rounded_rectangle([x, y, x + size, y + size], radius=r, fill=GREEN)
    bar_h = 8
    draw.rounded_rectangle([x + 22, y + 22, x + 22 + 46, y + 22 + bar_h], radius=4, fill=GREEN_LIGHT)
    draw.rounded_rectangle([x + 22, y + 38, x + 22 + 32, y + 38 + bar_h], radius=4, fill=(159, 225, 203))
    draw.rounded_rectangle([x + 22, y + 54, x + 22 + 40, y + 54 + bar_h], radius=4, fill=GREEN_LIGHT)
    ay = y + size - 28
    draw.line([x + 22, ay, x + size - 22, ay], fill=(255, 255, 255), width=5)
    draw.polygon([(x + size - 38, ay - 12), (x + size - 18, ay), (x + size - 38, ay + 12)], fill=(255, 255, 255))


def main() -> None:
    img = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    for i in range(H):
        t = i / H
        r = int(255 - (255 - GREEN_PALE[0]) * t * 0.55)
        g = int(255 - (255 - GREEN_PALE[1]) * t * 0.55)
        b = int(255 - (255 - GREEN_PALE[2]) * t * 0.55)
        draw.line([(0, i), (W, i)], fill=(r, g, b))

    draw.rounded_rectangle([0, H - 8, W, H], radius=0, fill=GREEN)
    draw.ellipse([W - 280, -120, W + 80, 240], fill=(220, 240, 233))
    draw.ellipse([-100, H - 220, 320, H + 80], fill=(232, 248, 242))

    draw_logo_mark(draw, 80, 180, 120)

    title_font = load_font(72, bold=True)
    sub_font = load_font(32)
    pill_font = load_font(24, bold=True)
    url_font = load_font(26)

    draw.text((240, 195), "Shift", font=title_font, fill=INK)
    shift_w = draw.textlength("Shift", font=title_font)
    draw.text((240 + shift_w, 195), "Swift", font=title_font, fill=GREEN)
    swift_w = draw.textlength("Swift", font=title_font)
    badge_x = int(240 + shift_w + swift_w + 14)
    draw.rounded_rectangle([badge_x, 218, badge_x + 58, 252], radius=8, fill=GREEN)
    draw.text((badge_x + 29, 224), "HR", font=load_font(22, bold=True), fill=(255, 255, 255), anchor="mm")

    draw.text((240, 290), "UK HR & compliance software for SMEs", font=sub_font, fill=MUTED)
    draw.text(
        (240, 340),
        "Right-to-work · Day-9 absence alerts · Geofenced time clock",
        font=load_font(26),
        fill=(60, 60, 56),
    )

    pills = ["14-day free trial", "Sponsor licence tools", "Home Office audit exports"]
    px = 240
    py = 420
    for label in pills:
        tw = draw.textlength(label, font=pill_font) + 36
        draw.rounded_rectangle([px, py, px + tw, py + 44], radius=22, fill=(255, 255, 255), outline=GREEN, width=2)
        draw.text((px + 18, py + 8), label, font=pill_font, fill=GREEN)
        px += tw + 16

    draw.text((80, H - 56), "shiftswifthr.co.uk", font=url_font, fill=GREEN)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, format="PNG", optimize=True)
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
