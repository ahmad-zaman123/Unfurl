from pathlib import Path

CARD_WIDTH = 1200
CARD_HEIGHT = 630
MARGIN = 72

FONTS_DIR = Path(__file__).resolve().parent / "fonts"
FONT_REGULAR = str(FONTS_DIR / "DejaVuSans.ttf")
FONT_BOLD = str(FONTS_DIR / "DejaVuSans-Bold.ttf")

DEFAULT_ACCENT = "#2563eb"

# Per-theme surface and text colours. "brand" has no bg colour — it is a
# gradient derived from the accent at render time.
THEME_PALETTES = {
    "light": {"top": "#ffffff", "bottom": "#eef2f9", "text": "#101828", "muted": "#5b6472"},
    "dark": {"top": "#0f172a", "bottom": "#1e293b", "text": "#f8fafc", "muted": "#94a3b8"},
    "brand": {"text": "#ffffff", "muted": "#e6eefe"},
}

# Field length caps (basic guardrails; full hardening lands in a later phase).
MAX_TITLE_LEN = 200
MAX_LINE_LEN = 120

TITLE_MAX_SIZE = 84
TITLE_MIN_SIZE = 46
TITLE_MAX_LINES = 4
