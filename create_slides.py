"""Generate a 5-slide PowerPoint deck comparing Claude-driven ADRS vs Scientific ADRS tools."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import math

# ── Color palettes ──────────────────────────────────────────────────────────
# Palette 1: Deep blue / coral
P1 = {
    "bg": RGBColor(0x0F, 0x17, 0x2A),        # dark navy bg
    "top_box": RGBColor(0x3B, 0x82, 0xF6),    # blue
    "top_light": RGBColor(0x60, 0xA5, 0xFA),  # lighter blue
    "bot_box": RGBColor(0xF9, 0x73, 0x16),    # orange
    "bot_light": RGBColor(0xFB, 0x92, 0x3C),  # lighter orange
    "text_w": RGBColor(0xFF, 0xFF, 0xFF),
    "text_d": RGBColor(0xFF, 0xFF, 0xFF),
    "accent": RGBColor(0x94, 0xA3, 0xB8),     # slate
    "divider": RGBColor(0x33, 0x40, 0x55),
    "green": RGBColor(0x22, 0xC5, 0x5E),
    "red": RGBColor(0xEF, 0x44, 0x44),
    "yellow": RGBColor(0xFA, 0xCC, 0x15),
    "pill_top": RGBColor(0x1E, 0x3A, 0x5F),
    "pill_bot": RGBColor(0x3D, 0x27, 0x0A),
}

# Palette 2: White / teal-purple
P2 = {
    "bg": RGBColor(0xF8, 0xFA, 0xFC),
    "top_box": RGBColor(0x6D, 0x28, 0xD9),    # purple
    "top_light": RGBColor(0x8B, 0x5C, 0xF6),
    "bot_box": RGBColor(0x05, 0x96, 0x69),     # teal
    "bot_light": RGBColor(0x34, 0xD3, 0x99),
    "text_w": RGBColor(0xFF, 0xFF, 0xFF),
    "text_d": RGBColor(0x1E, 0x29, 0x3B),
    "accent": RGBColor(0x64, 0x74, 0x8B),
    "divider": RGBColor(0xCB, 0xD5, 0xE1),
    "green": RGBColor(0x16, 0xA3, 0x4A),
    "red": RGBColor(0xDC, 0x26, 0x26),
    "yellow": RGBColor(0xEA, 0xB3, 0x08),
    "pill_top": RGBColor(0xED, 0xE9, 0xFE),
    "pill_bot": RGBColor(0xD1, 0xFA, 0xE5),
}

# Palette 3: Dark charcoal / green-pink
P3 = {
    "bg": RGBColor(0x18, 0x18, 0x1B),
    "top_box": RGBColor(0xEC, 0x48, 0x99),     # pink
    "top_light": RGBColor(0xF4, 0x72, 0xB6),
    "bot_box": RGBColor(0x10, 0xB9, 0x81),     # emerald
    "bot_light": RGBColor(0x34, 0xD3, 0x99),
    "text_w": RGBColor(0xFF, 0xFF, 0xFF),
    "text_d": RGBColor(0xFF, 0xFF, 0xFF),
    "accent": RGBColor(0x71, 0x71, 0x7A),
    "divider": RGBColor(0x3F, 0x3F, 0x46),
    "green": RGBColor(0x22, 0xC5, 0x5E),
    "red": RGBColor(0xFB, 0x71, 0x85),
    "yellow": RGBColor(0xFD, 0xE0, 0x47),
    "pill_top": RGBColor(0x35, 0x1C, 0x2E),
    "pill_bot": RGBColor(0x0A, 0x2E, 0x22),
}

# Palette 4: Warm cream / blue-terracotta
P4 = {
    "bg": RGBColor(0xFF, 0xFA, 0xF0),
    "top_box": RGBColor(0x25, 0x63, 0xEB),     # blue
    "top_light": RGBColor(0x3B, 0x82, 0xF6),
    "bot_box": RGBColor(0xC2, 0x41, 0x0C),     # terracotta
    "bot_light": RGBColor(0xEA, 0x58, 0x0C),
    "text_w": RGBColor(0xFF, 0xFF, 0xFF),
    "text_d": RGBColor(0x29, 0x1D, 0x0E),
    "accent": RGBColor(0x78, 0x71, 0x6C),
    "divider": RGBColor(0xD6, 0xD3, 0xD1),
    "green": RGBColor(0x16, 0xA3, 0x4A),
    "red": RGBColor(0xDC, 0x26, 0x26),
    "yellow": RGBColor(0xCA, 0x8A, 0x04),
    "pill_top": RGBColor(0xDB, 0xEA, 0xFE),
    "pill_bot": RGBColor(0xFF, 0xED, 0xD5),
}

# Palette 5: Gradient slate / cyan-amber
P5 = {
    "bg": RGBColor(0x0F, 0x17, 0x2A),
    "top_box": RGBColor(0x06, 0xB6, 0xD4),     # cyan
    "top_light": RGBColor(0x22, 0xD3, 0xEE),
    "bot_box": RGBColor(0xF5, 0x9E, 0x0B),     # amber
    "bot_light": RGBColor(0xFB, 0xBF, 0x24),
    "text_w": RGBColor(0xFF, 0xFF, 0xFF),
    "text_d": RGBColor(0xFF, 0xFF, 0xFF),
    "accent": RGBColor(0x94, 0xA3, 0xB8),
    "divider": RGBColor(0x33, 0x40, 0x55),
    "green": RGBColor(0x22, 0xC5, 0x5E),
    "red": RGBColor(0xEF, 0x44, 0x44),
    "yellow": RGBColor(0xFA, 0xCC, 0x15),
    "pill_top": RGBColor(0x0C, 0x29, 0x33),
    "pill_bot": RGBColor(0x35, 0x2A, 0x05),
}

PALETTES = [P1, P2, P3, P4, P5]

W = Inches(13.333)
H = Inches(7.5)


def _add_bg(slide, color):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def _box(slide, left, top, width, height, fill_color, border_color=None, radius=None):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
        left, top, width, height,
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if border_color:
        shape.line.color.rgb = border_color
        shape.line.width = Pt(1.5)
    else:
        shape.line.fill.background()
    if radius:
        shape.adjustments[0] = radius
    return shape


def _text_box(slide, left, top, width, height, text, font_size, color,
              bold=False, align=PP_ALIGN.LEFT, font_name="Calibri"):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font_name
    p.alignment = align
    return txBox


def _arrow(slide, start_left, start_top, end_left, end_top, color, width=Pt(2)):
    connector = slide.shapes.add_connector(
        1,  # straight connector
        start_left, start_top, end_left, end_top,
    )
    connector.line.color.rgb = color
    connector.line.width = width
    return connector


def _pill(slide, left, top, width, height, fill_color, text, font_size, text_color, font_name="Calibri"):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.fill.background()
    shape.adjustments[0] = 0.5
    tf = shape.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = text_color
    p.font.bold = True
    p.font.name = font_name
    p.alignment = PP_ALIGN.CENTER
    tf.paragraphs[0].space_before = Pt(0)
    tf.paragraphs[0].space_after = Pt(0)
    return shape


def _icon_circle(slide, left, top, size, fill_color, text, text_color, font_size=14):
    shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, left, top, size, size)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.fill.background()
    tf = shape.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = text_color
    p.font.bold = True
    p.alignment = PP_ALIGN.CENTER
    tf.paragraphs[0].space_before = Pt(0)
    tf.paragraphs[0].space_after = Pt(0)
    return shape


def _check_x(slide, left, top, is_check, pal):
    """Draw a small check or X icon."""
    color = pal["green"] if is_check else pal["red"]
    symbol = "\u2713" if is_check else "\u2717"
    _text_box(slide, left, top, Inches(0.3), Inches(0.3), symbol, 16, color, bold=True)


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 1: Horizontal split — two wide panels top/bottom
# ═══════════════════════════════════════════════════════════════════════════
def slide_1(prs):
    pal = PALETTES[0]
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    _add_bg(slide, pal["bg"])

    # Title
    _text_box(slide, Inches(0.5), Inches(0.2), Inches(12), Inches(0.6),
              "Two Paradigms for Algorithm Discovery", 28, pal["text_w"], bold=True,
              align=PP_ALIGN.CENTER, font_name="Calibri Light")
    _text_box(slide, Inches(0.5), Inches(0.7), Inches(12), Inches(0.35),
              "Version 1  |  Horizontal Split", 12, pal["accent"],
              align=PP_ALIGN.CENTER)

    # ── TOP PANEL: Claude-driven ADRS ──
    top_y = Inches(1.2)
    panel_h = Inches(2.6)
    _box(slide, Inches(0.4), top_y, Inches(12.5), panel_h, pal["pill_top"],
         border_color=pal["top_box"], radius=0.05)

    # Header bar
    _pill(slide, Inches(0.6), top_y + Inches(0.15), Inches(3.2), Inches(0.45),
          pal["top_box"], "Claude-Driven ADRS", 14, pal["text_w"])

    # Three property boxes
    props_top = [
        ("Principles &\nHypothesis Structure", "\u2713  Well-defined"),
        ("Process\nReproducibility", "\u2717  Black-box / Agentic"),
        ("Algorithm\nReproducibility", "\u2713  Results may match"),
    ]
    bx = Inches(0.8)
    for i, (title, desc) in enumerate(props_top):
        x = bx + i * Inches(4.0)
        _box(slide, x, top_y + Inches(0.85), Inches(3.4), Inches(1.5),
             pal["bg"], border_color=pal["top_light"], radius=0.08)
        _text_box(slide, x + Inches(0.2), top_y + Inches(0.95), Inches(3.0), Inches(0.6),
                  title, 13, pal["top_light"], bold=True, align=PP_ALIGN.CENTER)
        color = pal["green"] if "\u2713" in desc else pal["red"]
        _text_box(slide, x + Inches(0.2), top_y + Inches(1.65), Inches(3.0), Inches(0.4),
                  desc, 11, color, align=PP_ALIGN.CENTER)

    # Divider with "VS"
    div_y = top_y + panel_h + Inches(0.15)
    _box(slide, Inches(2), div_y, Inches(9.3), Pt(1.5), pal["divider"])
    _pill(slide, Inches(5.9), div_y - Inches(0.18), Inches(1.5), Inches(0.38),
          pal["bg"], "VS", 13, pal["accent"])

    # ── BOTTOM PANEL: Scientific ADRS ──
    bot_y = div_y + Inches(0.4)
    _box(slide, Inches(0.4), bot_y, Inches(12.5), panel_h, pal["pill_bot"],
         border_color=pal["bot_box"], radius=0.05)

    _pill(slide, Inches(0.6), bot_y + Inches(0.15), Inches(3.8), Inches(0.45),
          pal["bot_box"], "Scientific ADRS  (OpenEvolve, GEPA)", 13, pal["text_w"])

    props_bot = [
        ("Evolutionary Algorithms\n+ LLMs", "\u2713  Principled methods"),
        ("Process\nReproducibility", "\u2713  Seed, temperature, config"),
        ("Algorithm\nReproducibility", "\u2713  Results match across runs"),
    ]
    for i, (title, desc) in enumerate(props_bot):
        x = bx + i * Inches(4.0)
        _box(slide, x, bot_y + Inches(0.85), Inches(3.4), Inches(1.5),
             pal["bg"], border_color=pal["bot_light"], radius=0.08)
        _text_box(slide, x + Inches(0.2), bot_y + Inches(0.95), Inches(3.0), Inches(0.6),
                  title, 13, pal["bot_light"], bold=True, align=PP_ALIGN.CENTER)
        color = pal["green"] if "\u2713" in desc else pal["red"]
        _text_box(slide, x + Inches(0.2), bot_y + Inches(1.65), Inches(3.0), Inches(0.4),
                  desc, 11, color, align=PP_ALIGN.CENTER)


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 2: Two-column comparison with icon badges
# ═══════════════════════════════════════════════════════════════════════════
def slide_2(prs):
    pal = PALETTES[1]
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_bg(slide, pal["bg"])

    _text_box(slide, Inches(0.5), Inches(0.2), Inches(12), Inches(0.6),
              "Two Paradigms for Algorithm Discovery", 28, pal["text_d"], bold=True,
              align=PP_ALIGN.CENTER, font_name="Calibri Light")
    _text_box(slide, Inches(0.5), Inches(0.7), Inches(12), Inches(0.35),
              "Version 2  |  Side-by-Side Columns", 12, pal["accent"],
              align=PP_ALIGN.CENTER)

    col_w = Inches(5.8)
    col_h = Inches(5.6)
    left_x = Inches(0.5)
    right_x = Inches(7.0)
    col_y = Inches(1.2)

    # Left column - Claude
    _box(slide, left_x, col_y, col_w, col_h, pal["pill_top"],
         border_color=pal["top_box"], radius=0.04)
    _pill(slide, left_x + Inches(0.3), col_y + Inches(0.2), Inches(3.5), Inches(0.5),
          pal["top_box"], "Claude-Driven ADRS", 15, pal["text_w"])

    # Icon + text rows
    items_left = [
        ("\u2699", "Principles & Hypothesis", "Clearly defined structure", True),
        ("\u26A0", "Process Reproducibility", "Hard — Claude is a black box", False),
        ("\u2699", "Agentic Workflow", "Non-deterministic reasoning", False),
        ("\u2713", "Algorithm Output", "May reproduce across users", True),
    ]
    for i, (icon, title, desc, good) in enumerate(items_left):
        iy = col_y + Inches(1.0) + i * Inches(1.1)
        c = pal["green"] if good else pal["red"]
        _icon_circle(slide, left_x + Inches(0.4), iy, Inches(0.45), c,
                     icon, pal["text_w"], font_size=16)
        _text_box(slide, left_x + Inches(1.05), iy - Inches(0.02), Inches(4.2), Inches(0.35),
                  title, 14, pal["text_d"], bold=True)
        _text_box(slide, left_x + Inches(1.05), iy + Inches(0.3), Inches(4.2), Inches(0.3),
                  desc, 11, pal["accent"])

    # Right column - Scientific
    _box(slide, right_x, col_y, col_w, col_h, pal["pill_bot"],
         border_color=pal["bot_box"], radius=0.04)
    _pill(slide, right_x + Inches(0.3), col_y + Inches(0.2), Inches(4.2), Inches(0.5),
          pal["bot_box"], "Scientific ADRS  (OpenEvolve, GEPA)", 14, pal["text_w"])

    items_right = [
        ("\u2699", "Evolutionary + LLM", "Principled algorithm design", True),
        ("\u2713", "Process Reproducibility", "Seed, temperature, config", True),
        ("\u2713", "Deterministic Pipeline", "Same inputs \u2192 same outputs", True),
        ("\u2713", "Algorithm Output", "Reproducible across users", True),
    ]
    for i, (icon, title, desc, good) in enumerate(items_right):
        iy = col_y + Inches(1.0) + i * Inches(1.1)
        c = pal["green"] if good else pal["red"]
        _icon_circle(slide, right_x + Inches(0.4), iy, Inches(0.45), c,
                     icon, pal["text_w"], font_size=16)
        _text_box(slide, right_x + Inches(1.05), iy - Inches(0.02), Inches(4.2), Inches(0.35),
                  title, 14, pal["text_d"], bold=True)
        _text_box(slide, right_x + Inches(1.05), iy + Inches(0.3), Inches(4.2), Inches(0.3),
                  desc, 11, pal["accent"])

    # Center divider label
    _text_box(slide, Inches(6.0), Inches(3.7), Inches(1.3), Inches(0.4),
              "VS", 20, pal["accent"], bold=True, align=PP_ALIGN.CENTER)


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 3: Flow diagram — process arrows top and bottom
# ═══════════════════════════════════════════════════════════════════════════
def slide_3(prs):
    pal = PALETTES[2]
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_bg(slide, pal["bg"])

    _text_box(slide, Inches(0.5), Inches(0.15), Inches(12), Inches(0.55),
              "Two Paradigms for Algorithm Discovery", 28, pal["text_w"], bold=True,
              align=PP_ALIGN.CENTER, font_name="Calibri Light")
    _text_box(slide, Inches(0.5), Inches(0.6), Inches(12), Inches(0.3),
              "Version 3  |  Process Flow", 12, pal["accent"],
              align=PP_ALIGN.CENTER)

    # ── TOP FLOW: Claude-driven ──
    flow_y_top = Inches(1.15)
    _pill(slide, Inches(0.4), flow_y_top, Inches(2.8), Inches(0.4),
          pal["top_box"], "Claude-Driven ADRS", 13, pal["text_w"])

    steps_top = [
        ("Define\nPrinciples", pal["top_box"]),
        ("Set\nHypotheses", pal["top_box"]),
        ("Claude\nAgent\n(black box)", pal["pill_top"]),
        ("Generate\nAlgorithm", pal["top_box"]),
        ("Evaluate\nResults", pal["top_box"]),
    ]
    box_w = Inches(1.9)
    box_h = Inches(1.5)
    start_x = Inches(0.4)
    step_y = flow_y_top + Inches(0.6)
    gap = Inches(0.45)

    for i, (label, color) in enumerate(steps_top):
        x = start_x + i * (box_w + gap)
        border = pal["red"] if "black box" in label else pal["top_light"]
        _box(slide, x, step_y, box_w, box_h, color, border_color=border, radius=0.1)
        _text_box(slide, x + Inches(0.1), step_y + Inches(0.25), box_w - Inches(0.2), box_h - Inches(0.3),
                  label, 12, pal["text_w"], bold=True, align=PP_ALIGN.CENTER)
        if i < len(steps_top) - 1:
            _text_box(slide, x + box_w, step_y + Inches(0.55), gap, Inches(0.35),
                      "\u25B6", 18, pal["top_light"], align=PP_ALIGN.CENTER)

    # Reproducibility badges for top
    _pill(slide, Inches(4.95), step_y + box_h + Inches(0.1), Inches(2.4), Inches(0.35),
          pal["red"], "\u2717  Process: NOT reproducible", 10, pal["text_w"])
    _pill(slide, Inches(9.0), step_y + box_h + Inches(0.1), Inches(2.8), Inches(0.35),
          pal["green"], "\u2713  Algorithm output: may match", 10, pal["text_w"])

    # ── Divider ──
    div_y = step_y + box_h + Inches(0.7)
    _box(slide, Inches(1.5), div_y, Inches(10.3), Pt(1), pal["divider"])
    _pill(slide, Inches(5.9), div_y - Inches(0.17), Inches(1.5), Inches(0.35),
          pal["bg"], "VS", 12, pal["accent"])

    # ── BOTTOM FLOW: Scientific ──
    flow_y_bot = div_y + Inches(0.25)
    _pill(slide, Inches(0.4), flow_y_bot, Inches(3.8), Inches(0.4),
          pal["bot_box"], "Scientific ADRS  (OpenEvolve, GEPA)", 13, pal["text_w"])

    steps_bot = [
        ("Configure\nSeed / Temp", pal["bot_box"]),
        ("Evolutionary\nAlgorithm", pal["bot_box"]),
        ("LLM\nMutations\n(controlled)", pal["pill_bot"]),
        ("Evaluate\n& Select", pal["bot_box"]),
        ("Best\nAlgorithm", pal["bot_box"]),
    ]
    step_y_b = flow_y_bot + Inches(0.6)

    for i, (label, color) in enumerate(steps_bot):
        x = start_x + i * (box_w + gap)
        _box(slide, x, step_y_b, box_w, box_h, color, border_color=pal["bot_light"], radius=0.1)
        _text_box(slide, x + Inches(0.1), step_y_b + Inches(0.25), box_w - Inches(0.2), box_h - Inches(0.3),
                  label, 12, pal["text_w"], bold=True, align=PP_ALIGN.CENTER)
        if i < len(steps_bot) - 1:
            _text_box(slide, x + box_w, step_y_b + Inches(0.55), gap, Inches(0.35),
                      "\u25B6", 18, pal["bot_light"], align=PP_ALIGN.CENTER)

    _pill(slide, Inches(4.95), step_y_b + box_h + Inches(0.1), Inches(2.4), Inches(0.35),
          pal["green"], "\u2713  Process: reproducible", 10, pal["text_w"])
    _pill(slide, Inches(9.0), step_y_b + box_h + Inches(0.1), Inches(2.8), Inches(0.35),
          pal["green"], "\u2713  Algorithm output: matches", 10, pal["text_w"])


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 4: Matrix / scorecard grid
# ═══════════════════════════════════════════════════════════════════════════
def slide_4(prs):
    pal = PALETTES[3]
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_bg(slide, pal["bg"])

    _text_box(slide, Inches(0.5), Inches(0.2), Inches(12), Inches(0.6),
              "Two Paradigms for Algorithm Discovery", 28, pal["text_d"], bold=True,
              align=PP_ALIGN.CENTER, font_name="Calibri Light")
    _text_box(slide, Inches(0.5), Inches(0.7), Inches(12), Inches(0.35),
              "Version 4  |  Scorecard Matrix", 12, pal["accent"],
              align=PP_ALIGN.CENTER)

    # Grid layout
    grid_x = Inches(1.0)
    grid_y = Inches(1.4)
    col_label_w = Inches(3.5)
    col_val_w = Inches(4.2)
    row_h = Inches(1.0)

    # Column headers
    _box(slide, grid_x + col_label_w, grid_y, col_val_w, Inches(0.6),
         pal["top_box"])
    _text_box(slide, grid_x + col_label_w + Inches(0.1), grid_y + Inches(0.1),
              col_val_w - Inches(0.2), Inches(0.4),
              "Claude-Driven ADRS", 14, pal["text_w"], bold=True, align=PP_ALIGN.CENTER)

    _box(slide, grid_x + col_label_w + col_val_w, grid_y, col_val_w, Inches(0.6),
         pal["bot_box"])
    _text_box(slide, grid_x + col_label_w + col_val_w + Inches(0.1), grid_y + Inches(0.1),
              col_val_w - Inches(0.2), Inches(0.4),
              "Scientific ADRS", 14, pal["text_w"], bold=True, align=PP_ALIGN.CENTER)

    rows = [
        ("Methodology", "LLM agent (agentic)", "Evolutionary algorithms + LLMs"),
        ("Principles & Structure", "\u2713  Well-defined", "\u2713  Well-defined"),
        ("Process\nReproducibility", "\u2717  Non-deterministic\n     (black-box agent)", "\u2713  Deterministic\n     (seed, temp, config)"),
        ("Algorithm Output\nReproducibility", "\u2713  May reproduce\n     across users", "\u2713  Reproduces\n     across users"),
        ("Examples", "Claude + ADRS prompts", "OpenEvolve, GEPA"),
    ]

    for i, (label, val_left, val_right) in enumerate(rows):
        ry = grid_y + Inches(0.6) + i * row_h
        bg = pal["bg"] if i % 2 == 0 else RGBColor(0xF0, 0xE7, 0xD8)

        # Label cell
        _box(slide, grid_x, ry, col_label_w, row_h, bg, border_color=pal["divider"])
        _text_box(slide, grid_x + Inches(0.2), ry + Inches(0.15),
                  col_label_w - Inches(0.4), row_h - Inches(0.2),
                  label, 12, pal["text_d"], bold=True)

        # Left value
        _box(slide, grid_x + col_label_w, ry, col_val_w, row_h, bg, border_color=pal["divider"])
        c_left = pal["green"] if "\u2713" in val_left else (pal["red"] if "\u2717" in val_left else pal["text_d"])
        _text_box(slide, grid_x + col_label_w + Inches(0.2), ry + Inches(0.15),
                  col_val_w - Inches(0.4), row_h - Inches(0.2),
                  val_left, 11, c_left)

        # Right value
        _box(slide, grid_x + col_label_w + col_val_w, ry, col_val_w, row_h, bg, border_color=pal["divider"])
        c_right = pal["green"] if "\u2713" in val_right else (pal["red"] if "\u2717" in val_right else pal["text_d"])
        _text_box(slide, grid_x + col_label_w + col_val_w + Inches(0.2), ry + Inches(0.15),
                  col_val_w - Inches(0.4), row_h - Inches(0.2),
                  val_right, 11, c_right)


# ═══════════════════════════════════════════════════════════════════════════
# SLIDE 5: Stacked cards with big icons
# ═══════════════════════════════════════════════════════════════════════════
def slide_5(prs):
    pal = PALETTES[4]
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_bg(slide, pal["bg"])

    _text_box(slide, Inches(0.5), Inches(0.15), Inches(12), Inches(0.55),
              "Two Paradigms for Algorithm Discovery", 28, pal["text_w"], bold=True,
              align=PP_ALIGN.CENTER, font_name="Calibri Light")
    _text_box(slide, Inches(0.5), Inches(0.6), Inches(12), Inches(0.3),
              "Version 5  |  Card Layout with Icons", 12, pal["accent"],
              align=PP_ALIGN.CENTER)

    # ── TOP CARD ──
    card_x = Inches(0.5)
    card_w = Inches(12.3)
    card_h = Inches(2.7)
    card_y_top = Inches(1.1)

    _box(slide, card_x, card_y_top, card_w, card_h, pal["pill_top"],
         border_color=pal["top_box"], radius=0.04)

    # Left: big icon area
    _icon_circle(slide, card_x + Inches(0.5), card_y_top + Inches(0.6),
                 Inches(1.4), pal["top_box"], "\u2728", pal["text_w"], font_size=32)
    _text_box(slide, card_x + Inches(0.15), card_y_top + Inches(2.1), Inches(2.0), Inches(0.4),
              "Claude-Driven\nADRS", 12, pal["top_light"], bold=True, align=PP_ALIGN.CENTER)

    # Right: three attribute columns
    attrs_top = [
        ("\u2713", "Principles\nDefined", "Hypotheses &\nprocesses clear", True),
        ("\u2717", "Process\nRepro", "Agentic black-box\nnon-deterministic", False),
        ("\u2713", "Algorithm\nRepro", "Output algorithms\nmay match", True),
    ]
    attr_start_x = card_x + Inches(2.5)
    attr_w = Inches(3.1)
    for i, (sym, title, desc, good) in enumerate(attrs_top):
        ax = attr_start_x + i * attr_w
        ay = card_y_top + Inches(0.3)
        color = pal["green"] if good else pal["red"]

        _text_box(slide, ax + Inches(0.1), ay, Inches(0.4), Inches(0.4),
                  sym, 22, color, bold=True, align=PP_ALIGN.CENTER)
        _text_box(slide, ax + Inches(0.5), ay + Inches(0.02), Inches(2.3), Inches(0.45),
                  title, 14, pal["text_w"], bold=True)
        # Separator line
        _box(slide, ax + Inches(0.1), ay + Inches(0.6), Inches(2.7), Pt(1), pal["divider"])
        _text_box(slide, ax + Inches(0.1), ay + Inches(0.7), Inches(2.7), Inches(1.2),
                  desc, 11, pal["accent"])

    # ── VS bar ──
    vs_y = card_y_top + card_h + Inches(0.15)
    _pill(slide, Inches(5.9), vs_y, Inches(1.5), Inches(0.35),
          pal["bg"], "VS", 13, pal["accent"])

    # ── BOTTOM CARD ──
    card_y_bot = vs_y + Inches(0.5)

    _box(slide, card_x, card_y_bot, card_w, card_h, pal["pill_bot"],
         border_color=pal["bot_box"], radius=0.04)

    _icon_circle(slide, card_x + Inches(0.5), card_y_bot + Inches(0.6),
                 Inches(1.4), pal["bot_box"], "\u2699", pal["text_w"], font_size=32)
    _text_box(slide, card_x + Inches(0.0), card_y_bot + Inches(2.1), Inches(2.3), Inches(0.4),
              "Scientific ADRS\n(OpenEvolve, GEPA)", 11, pal["bot_light"], bold=True, align=PP_ALIGN.CENTER)

    attrs_bot = [
        ("\u2713", "Principled\nMethods", "Evolutionary algs\n+ LLM mutations", True),
        ("\u2713", "Process\nRepro", "Seed, temperature,\nfull config control", True),
        ("\u2713", "Algorithm\nRepro", "Same results\nacross users", True),
    ]
    for i, (sym, title, desc, good) in enumerate(attrs_bot):
        ax = attr_start_x + i * attr_w
        ay = card_y_bot + Inches(0.3)
        color = pal["green"]

        _text_box(slide, ax + Inches(0.1), ay, Inches(0.4), Inches(0.4),
                  sym, 22, color, bold=True, align=PP_ALIGN.CENTER)
        _text_box(slide, ax + Inches(0.5), ay + Inches(0.02), Inches(2.3), Inches(0.45),
                  title, 14, pal["text_w"], bold=True)
        _box(slide, ax + Inches(0.1), ay + Inches(0.6), Inches(2.7), Pt(1), pal["divider"])
        _text_box(slide, ax + Inches(0.1), ay + Inches(0.7), Inches(2.7), Inches(1.2),
                  desc, 11, pal["accent"])


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════
def main():
    prs = Presentation()
    prs.slide_width = W
    prs.slide_height = H

    slide_1(prs)
    slide_2(prs)
    slide_3(prs)
    slide_4(prs)
    slide_5(prs)

    out = "adrs_paradigms_comparison.pptx"
    prs.save(out)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
