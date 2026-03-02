#!/usr/bin/env python3
"""Generate 3 slide options for the Structured Threshold Tuning feature."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import os

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── Colors ───────────────────────────────────────────────────────────────────

DARK_BLUE = RGBColor(0x00, 0x2D, 0x5E)
MID_BLUE = RGBColor(0x00, 0x53, 0xA0)
LIGHT_BLUE = RGBColor(0x41, 0x78, 0xBE)
ACCENT_TEAL = RGBColor(0x00, 0xB3, 0x9E)
ACCENT_GREEN = RGBColor(0x24, 0xA1, 0x48)
ACCENT_RED = RGBColor(0xDA, 0x1E, 0x28)
ACCENT_ORANGE = RGBColor(0xFF, 0x83, 0x2B)
ACCENT_PURPLE = RGBColor(0x8A, 0x3F, 0xFC)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF4, 0xF4, 0xF4)
MED_GRAY = RGBColor(0x8D, 0x8D, 0x8D)
DARK_GRAY = RGBColor(0x39, 0x39, 0x39)
BLACK = RGBColor(0x00, 0x00, 0x00)
CODE_BG = RGBColor(0x26, 0x26, 0x2E)
WARM_WHITE = RGBColor(0xFA, 0xFA, 0xF7)
SOFT_BG = RGBColor(0xF0, 0xF4, 0xF8)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def set_slide_bg(slide, color):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_textbox(slide, left, top, width, height, text, font_size=18,
                color=BLACK, bold=False, alignment=PP_ALIGN.LEFT,
                font_name="Arial"):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font_name
    p.alignment = alignment
    return txBox


def add_multiline(slide, left, top, width, height, lines,
                  font_size=16, color=BLACK, font_name="Arial"):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, line in enumerate(lines):
        if isinstance(line, tuple):
            text, is_bold, clr = line
        else:
            text, is_bold, clr = line, False, color
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = text
        p.font.size = Pt(font_size)
        p.font.color.rgb = clr
        p.font.bold = is_bold
        p.font.name = font_name
        p.space_after = Pt(font_size * 0.3)
    return txBox


def add_box(slide, left, top, width, height, text, fill_color,
            text_color=WHITE, font_size=14, bold=True, font_name="Arial"):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                   left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.fill.background()
    shape.shadow.inherit = False
    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = Pt(8)
    tf.margin_right = Pt(8)
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = text_color
    p.font.bold = bold
    p.font.name = font_name
    p.alignment = PP_ALIGN.CENTER
    tf.auto_size = None
    return shape


def add_code_box(slide, left, top, width, height, code_text, font_size=11):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                   left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = CODE_BG
    shape.line.fill.background()
    shape.shadow.inherit = False
    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = Pt(12)
    tf.margin_right = Pt(12)
    tf.margin_top = Pt(8)
    tf.margin_bottom = Pt(8)
    for i, line in enumerate(code_text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.font.size = Pt(font_size)
        p.font.name = "Menlo"
        p.font.color.rgb = RGBColor(0xE0, 0xE0, 0xE0)
        p.space_after = Pt(1)
    return shape


def add_arrow(slide, left, top, width, height, color=LIGHT_BLUE,
              direction="down"):
    shape_type = {
        "down": MSO_SHAPE.DOWN_ARROW,
        "right": MSO_SHAPE.RIGHT_ARROW,
    }.get(direction, MSO_SHAPE.DOWN_ARROW)
    shape = slide.shapes.add_shape(shape_type, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def add_connector_line(slide, x1, y1, x2, y2, color=MED_GRAY, width=Pt(2)):
    connector = slide.shapes.add_connector(
        1, x1, y1, x2, y2  # 1 = straight connector
    )
    connector.line.color.rgb = color
    connector.line.width = width
    return connector


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 1: "The Problem & Pipeline" — clean vertical flow
# ═══════════════════════════════════════════════════════════════════════════════

def create_slide_v1():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    set_slide_bg(slide, WHITE)

    # ── Title ──
    add_textbox(slide, Inches(0.6), Inches(0.3), Inches(12), Inches(0.7),
                "Structured Threshold Tuning for OpenEvolve",
                font_size=32, color=DARK_BLUE, bold=True)
    add_textbox(slide, Inches(0.6), Inches(0.9), Inches(12), Inches(0.5),
                "Separate what the algorithm does from how its numbers are set",
                font_size=18, color=MED_GRAY)

    # ── Left: The Problem ──
    add_textbox(slide, Inches(0.6), Inches(1.7), Inches(4), Inches(0.5),
                "The Problem", font_size=22, color=ACCENT_RED, bold=True)
    add_multiline(slide, Inches(0.6), Inches(2.2), Inches(5.5), Inches(2.5), [
        "LLMs generate algorithms with hard-coded thresholds:",
        "",
        ('  if load < 0.4:  route_elsewhere()', False, DARK_GRAY),
        ('  if latency > 200:  scale_up()', False, DARK_GRAY),
        "",
        "These numbers are guesses. A brilliant algorithm",
        "with bad thresholds gets a bad score and is discarded.",
        "",
        ("The LLM can't search — it just picks numbers.", True, ACCENT_RED),
    ], font_size=15, color=DARK_GRAY)

    # ── Right: The Pipeline (vertical flow) ──
    add_textbox(slide, Inches(7), Inches(1.7), Inches(5.5), Inches(0.5),
                "The Solution: Let the optimizer handle numbers",
                font_size=22, color=ACCENT_GREEN, bold=True)

    # Step boxes
    bx = Inches(7.3)
    bw = Inches(5)
    bh = Inches(0.55)
    gap = Inches(0.15)  # between arrow and box

    y = Inches(2.4)
    add_box(slide, bx, y, bw, bh,
            "1. LLM generates code with @TUNE annotations",
            MID_BLUE, font_size=13)

    y += bh + gap
    add_arrow(slide, bx + Inches(2.2), y, Inches(0.5), Inches(0.35), LIGHT_BLUE)

    y += Inches(0.35) + gap
    add_box(slide, bx, y, bw, bh,
            "2. Parser extracts thresholds + ranges (max 3)",
            LIGHT_BLUE, font_size=13)

    y += bh + gap
    add_arrow(slide, bx + Inches(2.2), y, Inches(0.5), Inches(0.35), ACCENT_TEAL)

    y += Inches(0.35) + gap
    add_box(slide, bx, y, bw, bh,
            "3. Optuna (Bayesian) searches for best values",
            ACCENT_TEAL, font_size=13)

    y += bh + gap
    add_arrow(slide, bx + Inches(2.2), y, Inches(0.5), Inches(0.35), ACCENT_GREEN)

    y += Inches(0.35) + gap
    add_box(slide, bx, y, bw, bh,
            "4. Best values written back with @TUNED feedback",
            ACCENT_GREEN, font_size=13)

    y += bh + gap
    add_arrow(slide, bx + Inches(2.2), y, Inches(0.5), Inches(0.35), DARK_BLUE)

    y += Inches(0.35) + gap
    add_box(slide, bx, y, bw, bh,
            "5. Optimized code scored and stored in DB",
            DARK_BLUE, font_size=13)

    # ── Bottom: Code examples side by side ──
    add_textbox(slide, Inches(0.6), Inches(5.1), Inches(3), Inches(0.4),
                "LLM writes:", font_size=14, color=MID_BLUE, bold=True)
    add_code_box(slide, Inches(0.6), Inches(5.5), Inches(5.5), Inches(1.5),
                 'load_cutoff = 0.4  # @TUNE [0.0, 1.0]\n'
                 'batch_size = 32   # @TUNE [8, 128] int\n'
                 'strategy = "greedy"  # @TUNE {greedy, rr, weighted}',
                 font_size=12)

    add_textbox(slide, Inches(7), Inches(5.1), Inches(3), Inches(0.4),
                "After optimizer:", font_size=14, color=ACCENT_GREEN, bold=True)
    add_code_box(slide, Inches(7), Inches(5.5), Inches(5.8), Inches(1.5),
                 'load_cutoff = 0.67  # @TUNE [0.0, 1.0]\n'
                 '  @TUNED(was=0.4, gain=+0.12, best_impact=tp:+0.3)\n'
                 'batch_size = 64    # @TUNE [8, 128] int\n'
                 '  @TUNED(was=32, gain=+0.12, best_impact=lat:-20)',
                 font_size=12)

    prs.save(os.path.join(OUT_DIR, "tuning_v1_problem_pipeline.pptx"))
    print("Created: tuning_v1_problem_pipeline.pptx")


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 2: "Before / After" — two-column iteration comparison
# ═══════════════════════════════════════════════════════════════════════════════

def create_slide_v2():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    # ── Title ──
    add_textbox(slide, Inches(0.6), Inches(0.3), Inches(12), Inches(0.7),
                "Threshold Tuning: Before & After",
                font_size=32, color=DARK_BLUE, bold=True)
    add_textbox(slide, Inches(0.6), Inches(0.9), Inches(12), Inches(0.5),
                "Same algorithm, different thresholds = very different scores",
                font_size=18, color=MED_GRAY)

    # ── Divider line ──
    mid_x = Inches(6.666)

    # ── LEFT: Without Tuning ──
    add_textbox(slide, Inches(0.6), Inches(1.7), Inches(5.5), Inches(0.5),
                "Without Threshold Tuning", font_size=22, color=ACCENT_RED, bold=True)

    # Iteration flow boxes
    lx = Inches(0.8)
    lw = Inches(5.2)

    add_box(slide, lx, Inches(2.3), lw, Inches(0.5),
            "LLM generates: if load < 0.4 ...", MED_GRAY, font_size=13)
    add_arrow(slide, lx + Inches(2.3), Inches(2.85), Inches(0.4), Inches(0.3), MED_GRAY)
    add_box(slide, lx, Inches(3.2), lw, Inches(0.5),
            "Evaluate with guessed threshold", MED_GRAY, font_size=13)
    add_arrow(slide, lx + Inches(2.3), Inches(3.75), Inches(0.4), Inches(0.3), MED_GRAY)
    add_box(slide, lx, Inches(4.1), lw, Inches(0.5),
            "Score: 0.42 (bad threshold, good algorithm lost)",
            ACCENT_RED, font_size=13)

    # Sad outcome
    add_multiline(slide, Inches(0.8), Inches(4.9), Inches(5.2), Inches(2), [
        ("Problem:", True, ACCENT_RED),
        "The LLM must simultaneously invent the",
        "algorithm AND guess optimal numbers.",
        "",
        "Good algorithms with bad thresholds",
        "are discarded by evolution.",
    ], font_size=14, color=DARK_GRAY)

    # ── RIGHT: With Tuning ──
    add_textbox(slide, Inches(7), Inches(1.7), Inches(5.5), Inches(0.5),
                "With Threshold Tuning", font_size=22, color=ACCENT_GREEN, bold=True)

    rx = Inches(7.2)
    rw = Inches(5.2)

    add_box(slide, rx, Inches(2.3), rw, Inches(0.5),
            "LLM generates: load = 0.4  # @TUNE [0.0, 1.0]",
            MID_BLUE, font_size=13)
    add_arrow(slide, rx + Inches(2.3), Inches(2.85), Inches(0.4), Inches(0.3), ACCENT_TEAL)
    add_box(slide, rx, Inches(3.2), rw, Inches(0.5),
            "Optuna tries 25 values, finds 0.67 is best",
            ACCENT_TEAL, font_size=13)
    add_arrow(slide, rx + Inches(2.3), Inches(3.75), Inches(0.4), Inches(0.3), ACCENT_GREEN)
    add_box(slide, rx, Inches(4.1), rw, Inches(0.5),
            "Score: 0.54 (+0.12 gain from tuning alone)",
            ACCENT_GREEN, font_size=13)

    # Happy outcome
    add_multiline(slide, Inches(7.2), Inches(4.9), Inches(5.2), Inches(2), [
        ("Division of labor:", True, ACCENT_GREEN),
        "LLM focuses on algorithmic structure.",
        "Optimizer handles the numbers.",
        "",
        "Good algorithms survive evolution",
        "regardless of initial threshold guesses.",
    ], font_size=14, color=DARK_GRAY)

    # ── Bottom: Feedback loop ──
    add_textbox(slide, Inches(0.6), Inches(6.6), Inches(12), Inches(0.5),
                "Feedback loop: @TUNED(was=0.4, gain=+0.12) tells the LLM what the optimizer found"
                " — it learns what ranges matter and adjusts future generations.",
                font_size=15, color=MID_BLUE, bold=False)

    prs.save(os.path.join(OUT_DIR, "tuning_v2_before_after.pptx"))
    print("Created: tuning_v2_before_after.pptx")


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 3: "Lifecycle" — horizontal flow showing one annotation across iterations
# ═══════════════════════════════════════════════════════════════════════════════

def create_slide_v3():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)

    # ── Title ──
    add_textbox(slide, Inches(0.6), Inches(0.3), Inches(12), Inches(0.7),
                "How @TUNE Annotations Flow Through Evolution",
                font_size=32, color=DARK_BLUE, bold=True)
    add_textbox(slide, Inches(0.6), Inches(0.9), Inches(12), Inches(0.5),
                "LLM declares ranges, optimizer finds values, feedback informs next generation",
                font_size=18, color=MED_GRAY)

    # ── Three iteration columns ──
    col_w = Inches(3.7)
    col_gap = Inches(0.5)
    arrow_w = Inches(0.6)

    # Column 1: Iteration N
    c1x = Inches(0.5)
    add_box(slide, c1x, Inches(1.8), col_w, Inches(0.5),
            "Iteration N: LLM generates code",
            MID_BLUE, font_size=14)
    add_code_box(slide, c1x, Inches(2.5), col_w, Inches(1.8),
                 '# EVOLVE-BLOCK-START\n'
                 'load = 0.4  # @TUNE [0.0, 1.0]\n'
                 'batch = 32  # @TUNE [8, 128] int\n'
                 '\n'
                 'def route(req):\n'
                 '    if req.load < load:\n'
                 '        return fast_path(req)',
                 font_size=11)
    add_multiline(slide, c1x + Inches(0.2), Inches(4.5), col_w, Inches(1), [
        ("LLM picks the algorithm structure", True, MID_BLUE),
        "Declares 2 thresholds with ranges",
        "Doesn't need to guess exact values",
    ], font_size=13, color=DARK_GRAY)

    # Arrow 1→2
    add_arrow(slide, c1x + col_w + Inches(0.05), Inches(3.2),
              arrow_w, Inches(0.4), ACCENT_TEAL, direction="right")
    add_textbox(slide, c1x + col_w - Inches(0.1), Inches(3.6), Inches(0.9), Inches(0.4),
                "Optuna\nsearches", font_size=10, color=ACCENT_TEAL, bold=True,
                alignment=PP_ALIGN.CENTER)

    # Column 2: After Tuning
    c2x = c1x + col_w + arrow_w + Inches(0.1)
    add_box(slide, c2x, Inches(1.8), col_w, Inches(0.5),
            "After Tuning: optimized + annotated",
            ACCENT_GREEN, font_size=14)
    add_code_box(slide, c2x, Inches(2.5), col_w, Inches(1.8),
                 '# EVOLVE-BLOCK-START\n'
                 'load = 0.67  # @TUNE [0.0, 1.0]\n'
                 '  @TUNED(was=0.4, gain=+0.12)\n'
                 'batch = 64   # @TUNE [8, 128] int\n'
                 '  @TUNED(was=32, gain=+0.12)\n'
                 'def route(req):\n'
                 '    if req.load < load:',
                 font_size=11)
    add_multiline(slide, c2x + Inches(0.2), Inches(4.5), col_w, Inches(1), [
        ("Optimizer found better values", True, ACCENT_GREEN),
        "Values rewritten in-place",
        "@TUNED shows what changed & gain",
    ], font_size=13, color=DARK_GRAY)

    # Arrow 2→3
    add_arrow(slide, c2x + col_w + Inches(0.05), Inches(3.2),
              arrow_w, Inches(0.4), ACCENT_PURPLE, direction="right")
    add_textbox(slide, c2x + col_w - Inches(0.1), Inches(3.6), Inches(0.9), Inches(0.4),
                "Next\niteration", font_size=10, color=ACCENT_PURPLE, bold=True,
                alignment=PP_ALIGN.CENTER)

    # Column 3: Next Iteration
    c3x = c2x + col_w + arrow_w + Inches(0.1)
    add_box(slide, c3x, Inches(1.8), col_w, Inches(0.5),
            "Iteration N+1: LLM sees feedback",
            ACCENT_PURPLE, font_size=14)
    add_code_box(slide, c3x, Inches(2.5), col_w, Inches(1.8),
                 '# LLM sees parent code:\n'
                 'load = 0.67  # @TUNE [0.0, 1.0]\n'
                 '  @TUNED(was=0.4, gain=+0.12)\n'
                 '\n'
                 '# LLM learns:\n'
                 '# "load near 0.67 works well"\n'
                 '# May keep, adjust range, or add new',
                 font_size=11)
    add_multiline(slide, c3x + Inches(0.2), Inches(4.5), col_w, Inches(1), [
        ("LLM learns from optimizer", True, ACCENT_PURPLE),
        "Sees what values worked",
        "Can refine ranges or add new @TUNE",
    ], font_size=13, color=DARK_GRAY)

    # ── Bottom: Key properties ──
    y_bottom = Inches(5.7)
    prop_w = Inches(3.8)

    add_box(slide, Inches(0.5), y_bottom, prop_w, Inches(1.2),
            "Division of Labor\n\nLLM = algorithm structure\nOptimizer = threshold values",
            MID_BLUE, font_size=13, bold=False)

    add_box(slide, Inches(4.7), y_bottom, prop_w, Inches(1.2),
            "Lightweight Syntax\n\nJust add # @TUNE [min, max]\nMax 3 per program",
            ACCENT_TEAL, font_size=13, bold=False)

    add_box(slide, Inches(8.9), y_bottom, prop_w, Inches(1.2),
            "Works with Hypotheses\n\nBoth annotations coexist\nHypotheses = why, Tuning = how much",
            ACCENT_GREEN, font_size=13, bold=False)

    prs.save(os.path.join(OUT_DIR, "tuning_v3_lifecycle.pptx"))
    print("Created: tuning_v3_lifecycle.pptx")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    create_slide_v1()
    create_slide_v2()
    create_slide_v3()
    print("\nAll 3 slides generated in:", OUT_DIR)
