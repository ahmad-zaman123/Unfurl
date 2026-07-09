import io

from PIL import Image, ImageDraw, ImageFont

from apps.cards.services.fetch import UnsafeFetchError, fetch_image
from apps.cards.constants import (
    CARD_HEIGHT,
    CARD_WIDTH,
    DEFAULT_ACCENT,
    FONT_BOLD,
    FONT_REGULAR,
    MARGIN,
    THEME_PALETTES,
    TITLE_MAX_LINES,
    TITLE_MAX_SIZE,
    TITLE_MIN_SIZE,
)

CONTENT_WIDTH = CARD_WIDTH - 2 * MARGIN


def _hex_to_rgb(value):
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(channel * 2 for channel in value)
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _mix(rgb, target, factor):
    return tuple(round(channel + (target[channel_i] - channel) * factor) for channel_i, channel in enumerate(rgb))


def _darken(rgb, factor=0.35):
    return _mix(rgb, (0, 0, 0), factor)


def _lighten(rgb, factor=0.2):
    return _mix(rgb, (255, 255, 255), factor)


def _vertical_gradient(top_rgb, bottom_rgb):
    base = Image.new("RGB", (1, CARD_HEIGHT))
    for y in range(CARD_HEIGHT):
        ratio = y / (CARD_HEIGHT - 1)
        base.putpixel((0, y), _mix(top_rgb, bottom_rgb, ratio))
    return base.resize((CARD_WIDTH, CARD_HEIGHT))


def _font(path, size):
    return ImageFont.truetype(path, size)


def _text_width(font, text):
    return font.getlength(text)


def _wrap(font, text, max_width):
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = current + " " + word
            if _text_width(font, candidate) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _fit_title(text, max_width, max_height):
    size = TITLE_MAX_SIZE
    while size >= TITLE_MIN_SIZE:
        font = _font(FONT_BOLD, size)
        lines = _wrap(font, text, max_width)
        line_height = round(size * 1.16)
        total_height = line_height * len(lines)
        if len(lines) <= TITLE_MAX_LINES and total_height <= max_height:
            return font, lines, line_height
        size -= 4
    font = _font(FONT_BOLD, TITLE_MIN_SIZE)
    lines = _wrap(font, text, max_width)[:TITLE_MAX_LINES]
    return font, lines, round(TITLE_MIN_SIZE * 1.16)


def _draw_lines(draw, lines, x, y, font, line_height, fill):
    for index, line in enumerate(lines):
        draw.text((x, y + index * line_height), line, font=font, fill=fill)
    return y + len(lines) * line_height


def _background(theme, accent_rgb):
    if theme == "brand":
        return _vertical_gradient(_darken(accent_rgb, 0.32), _lighten(accent_rgb, 0.06))
    palette = THEME_PALETTES[theme]
    return _vertical_gradient(_hex_to_rgb(palette["top"]), _hex_to_rgb(palette["bottom"]))


def _colours(theme, accent_rgb):
    if theme == "brand":
        return (255, 255, 255), _hex_to_rgb(THEME_PALETTES["brand"]["muted"]), (255, 255, 255)
    palette = THEME_PALETTES[theme]
    return _hex_to_rgb(palette["text"]), _hex_to_rgb(palette["muted"]), accent_rgb


def render_card(
    *,
    template="generic",
    title="",
    subtitle="",
    eyebrow="",
    footer="",
    price="",
    date="",
    location="",
    theme="brand",
    accent=DEFAULT_ACCENT,
    logo="",
):
    accent_rgb = _hex_to_rgb(accent or DEFAULT_ACCENT)
    image = _background(theme, accent_rgb)
    draw = ImageDraw.Draw(image)
    text_rgb, muted_rgb, accent_text_rgb = _colours(theme, accent_rgb)

    # Accent bar down the left edge for a branded feel.
    draw.rectangle((0, 0, 10, CARD_HEIGHT), fill=accent_rgb)

    # Optional remote logo, pasted top-right. Fetch failures (including blocked
    # SSRF targets) are non-fatal — the card just renders without it.
    if logo:
        try:
            logo_image = fetch_image(logo)
            logo_image.thumbnail((120, 120))
            image.paste(
                logo_image,
                (CARD_WIDTH - MARGIN - logo_image.width, MARGIN),
                logo_image,
            )
        except UnsafeFetchError:
            pass

    # Eyebrow (site / brand / category) along the top.
    eyebrow_label = eyebrow or (template.upper() if template == "event" else "")
    top = MARGIN
    if eyebrow_label:
        eyebrow_font = _font(FONT_BOLD, 26)
        draw.text((MARGIN, top), eyebrow_label.upper(), font=eyebrow_font, fill=accent_text_rgb)
        top += 52

    # Bottom block (footer / price / date+location), measured first so the
    # title knows how much vertical room it has.
    bottom_lines = []
    if template == "product" and price:
        bottom_lines.append(("price", price))
    if template == "event":
        if date:
            bottom_lines.append(("meta", date))
        if location:
            bottom_lines.append(("meta", location))
    if footer:
        bottom_lines.append(("footer", footer))

    reserved_bottom = 0
    for kind, _ in bottom_lines:
        reserved_bottom += 64 if kind == "price" else 40
    bottom_anchor = CARD_HEIGHT - MARGIN - reserved_bottom

    # Subtitle reserves space under the title.
    subtitle_font = _font(FONT_REGULAR, 34)
    subtitle_lines = _wrap(subtitle_font, subtitle, CONTENT_WIDTH) if subtitle else []
    subtitle_height = round(34 * 1.3) * len(subtitle_lines) + (24 if subtitle_lines else 0)

    title_max_height = bottom_anchor - top - subtitle_height - 24
    title_font, title_lines, title_line_height = _fit_title(title or " ", CONTENT_WIDTH, title_max_height)
    y = _draw_lines(draw, title_lines, MARGIN, top, title_font, title_line_height, text_rgb)

    if subtitle_lines:
        y += 24
        _draw_lines(draw, subtitle_lines, MARGIN, y, subtitle_font, round(34 * 1.3), muted_rgb)

    # Render the bottom block, anchored to the card floor.
    by = bottom_anchor
    for kind, value in bottom_lines:
        if kind == "price":
            price_font = _font(FONT_BOLD, 54)
            draw.text((MARGIN, by), value, font=price_font, fill=accent_text_rgb)
            by += 64
        else:
            meta_font = _font(FONT_REGULAR, 28)
            draw.text((MARGIN, by), value, font=meta_font, fill=muted_rgb)
            by += 40

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
