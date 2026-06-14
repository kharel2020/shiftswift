#!/usr/bin/env python3
"""Generate 1200×630 Open Graph preview — hero-style with top selling points."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "assets" / "og-image.png"

W, H = 1200, 630
GREEN = (15, 110, 86)
GREEN_DARK = (8, 80, 65)
GREEN_LIGHT = (93, 202, 165)
GREEN_PALE = (225, 245, 238)
GREEN_SOFT = (241, 249, 246)
GOLD = (212, 160, 23)
INK = (17, 17, 17)
MUTED = (95, 94, 90)
WHITE = (255, 255, 255)
WARN = (180, 83, 9)
OK = (15, 110, 86)


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


def draw_logo_mark(draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 72) -> None:
    draw.rounded_rectangle([x, y, x + size, y + size], radius=14, fill=GREEN)
    bar_h = 5
    draw.rounded_rectangle([x + 14, y + 14, x + 14 + 28, y + 14 + bar_h], radius=2, fill=GREEN_LIGHT)
    draw.rounded_rectangle([x + 14, y + 24, x + 14 + 20, y + 24 + bar_h], radius=2, fill=(159, 225, 203))
    draw.rounded_rectangle([x + 14, y + 34, x + 14 + 24, y + 34 + bar_h], radius=2, fill=GREEN_LIGHT)
    ay = y + size - 18
    draw.line([x + 14, ay, x + size - 14, ay], fill=WHITE, width=3)
    draw.polygon([(x + size - 28, ay - 8), (x + size - 14, ay), (x + size - 28, ay + 8)], fill=WHITE)


def draw_text_block(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    lines: list[str],
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    line_gap: int = 8,
) -> int:
    cy = y
    for line in lines:
        draw.text((x, cy), line, font=font, fill=fill)
        bbox = draw.textbbox((x, cy), line, font=font)
        cy = bbox[3] + line_gap
    return cy


def draw_pill(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    label: str,
    font: ImageFont.ImageFont,
    *,
    fill: tuple[int, int, int] = GREEN,
    text_fill: tuple[int, int, int] = WHITE,
    outline: tuple[int, int, int] | None = None,
    pad_x: int = 16,
    pad_y: int = 8,
) -> int:
    tw = draw.textlength(label, font=font)
    w = int(tw + pad_x * 2)
    h = int(font.size + pad_y * 2)
    draw.rounded_rectangle(
        [x, y, x + w, y + h],
        radius=h // 2,
        fill=fill,
        outline=outline or fill,
        width=2 if outline else 0,
    )
    draw.text((x + pad_x, y + pad_y - 1), label, font=font, fill=text_fill)
    return w


def draw_dashboard_mock(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int) -> None:
    shadow = 6
    draw.rounded_rectangle([x + shadow, y + shadow, x + w + shadow, y + h + shadow], radius=20, fill=(0, 0, 0, 20))
    draw.rounded_rectangle([x, y, x + w, y + h], radius=20, fill=WHITE, outline=(211, 209, 199), width=2)

    bar_h = 44
    draw.rounded_rectangle([x, y, x + w, y + bar_h], radius=20, fill=GREEN_SOFT)
    draw.rectangle([x, y + bar_h - 20, x + w, y + bar_h], fill=GREEN_SOFT)
    for i, cx in enumerate([x + 22, x + 38, x + 54]):
        draw.ellipse([cx, y + 16, cx + 10, y + 26], fill=(180, 178, 170) if i else (255, 120, 120))
    draw.text((x + 72, y + 12), "ShiftSwift HR · Live dashboard", font=load_font(18, bold=True), fill=MUTED)

    stats_y = y + bar_h + 20
    stat_w = (w - 56) // 3
    labels = [("Active staff", "18", INK), ("RTW due", "3", WARN), ("Day-9", "Clear", OK)]
    for i, (label, value, color) in enumerate(labels):
        sx = x + 20 + i * (stat_w + 8)
        draw.rounded_rectangle([sx, stats_y, sx + stat_w, stats_y + 78], radius=12, fill=GREEN_SOFT)
        draw.text((sx + 12, stats_y + 10), label, font=load_font(15), fill=MUTED)
        draw.text((sx + 12, stats_y + 34), value, font=load_font(28, bold=True), fill=color)

    list_y = stats_y + 98
    draw.text((x + 20, list_y), "This week", font=load_font(16, bold=True), fill=INK)
    rows = [
        ("Geofenced clock-in", "✓ On site"),
        ("Hours export", "Ready for accountant"),
        ("Sponsor audit pack", "1-click export"),
    ]
    ry = list_y + 28
    for title, sub in rows:
        draw.rounded_rectangle([x + 20, ry, x + w - 20, ry + 52], radius=10, fill=GREEN_SOFT)
        draw.text((x + 32, ry + 8), title, font=load_font(17, bold=True), fill=INK)
        draw.text((x + 32, ry + 28), sub, font=load_font(14), fill=GREEN)
        ry += 58


def main() -> None:
    img = Image.new("RGB", (W, H), GREEN_SOFT)
    draw = ImageDraw.Draw(img)

    for i in range(H):
        t = i / max(H - 1, 1)
        r = int(GREEN_SOFT[0] + (WHITE[0] - GREEN_SOFT[0]) * (1 - t) * 0.35)
        g = int(GREEN_SOFT[1] + (WHITE[1] - GREEN_SOFT[1]) * (1 - t) * 0.35)
        b = int(GREEN_SOFT[2] + (WHITE[2] - GREEN_SOFT[2]) * (1 - t) * 0.35)
        draw.line([(0, i), (W, i)], fill=(r, g, b))

    draw.ellipse([720, -140, 1180, 300], fill=GREEN_PALE)
    draw.ellipse([-80, 380, 360, 720], fill=(232, 248, 242))
    draw.rounded_rectangle([0, 0, W, 6], radius=0, fill=GREEN)

    draw_logo_mark(draw, 64, 52, 72)
    brand_font = load_font(42, bold=True)
    draw.text((152, 58), "Shift", font=brand_font, fill=INK)
    sw = draw.textlength("Shift", font=brand_font)
    draw.text((152 + sw, 58), "Swift", font=brand_font, fill=GREEN)
    sw2 = draw.textlength("Swift", font=brand_font)
    bx = int(152 + sw + sw2 + 10)
    draw.rounded_rectangle([bx, 72, bx + 46, 98], radius=6, fill=GREEN)
    draw.text((bx + 23, 78), "HR", font=load_font(16, bold=True), fill=WHITE, anchor="mm")

    tagline_font = load_font(26)
    draw.text(
        (64, 148),
        "UK HR & sponsor compliance recording tools",
        font=tagline_font,
        fill=MUTED,
    )

    feature_font = load_font(24, bold=True)
    features = [
        "RTW evidence · Day-9 alerts ·",
        "Time clock · Audit export packs",
    ]
    draw_text_block(draw, 64, 198, features, feature_font, INK, line_gap=6)

    pill_font = load_font(20, bold=True)
    py = 310
    w1 = draw_pill(draw, 64, py, "14-day free trial", pill_font, fill=GOLD, text_fill=INK, pad_x=16, pad_y=9)
    draw_pill(
        draw,
        64 + w1 + 14,
        py,
        "Compliance recording tools",
        pill_font,
        fill=WHITE,
        text_fill=GREEN,
        outline=GREEN,
        pad_x=16,
        pad_y=9,
    )
    draw_pill(
        draw,
        64,
        py + 52,
        "You act on Home Office duties",
        pill_font,
        fill=WHITE,
        text_fill=GREEN,
        outline=GREEN,
        pad_x=16,
        pad_y=9,
    )

    sub_font = load_font(22)
    draw.text(
        (64, 430),
        "Built for UK SMEs & sponsor licence holders",
        font=sub_font,
        fill=MUTED,
    )

    draw_dashboard_mock(draw, 680, 88, 480, 480)

    draw.rounded_rectangle([0, H - 52, W, H], radius=0, fill=GREEN)
    draw.text((64, H - 38), "shiftswifthr.co.uk", font=load_font(24, bold=True), fill=WHITE)
    draw.text(
        (W - 64, H - 38),
        "Free 14-day trial · From £9/mo ex VAT",
        font=load_font(18, bold=True),
        fill=GREEN_LIGHT,
        anchor="rm",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, format="PNG", optimize=True)
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
