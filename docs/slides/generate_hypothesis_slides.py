#!/usr/bin/env python3
"""Generate 5 different slide deck versions explaining hypothesis-driven evolution."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import os

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── Color palettes ────────────────────────────────────────────────────────────

# IBM-ish blues
DARK_BG = RGBColor(0x16, 0x16, 0x16)
DARK_BLUE = RGBColor(0x00, 0x2D, 0x5E)
MID_BLUE = RGBColor(0x00, 0x53, 0xA0)
LIGHT_BLUE = RGBColor(0x41, 0x78, 0xBE)
ACCENT_TEAL = RGBColor(0x00, 0xB3, 0x9E)
ACCENT_GREEN = RGBColor(0x24, 0xA1, 0x48)
ACCENT_RED = RGBColor(0xDA, 0x1E, 0x28)
ACCENT_ORANGE = RGBColor(0xFF, 0x83, 0x2B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF4, 0xF4, 0xF4)
MED_GRAY = RGBColor(0x8D, 0x8D, 0x8D)
DARK_GRAY = RGBColor(0x39, 0x39, 0x39)
BLACK = RGBColor(0x00, 0x00, 0x00)
CODE_BG = RGBColor(0x26, 0x26, 0x2E)
WARM_WHITE = RGBColor(0xFA, 0xFA, 0xF7)


# ─── Helper functions ──────────────────────────────────────────────────────────

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


def add_multiline_textbox(slide, left, top, width, height, lines,
                          font_size=16, color=BLACK, line_spacing=1.2,
                          bold_first=False, font_name="Arial", bullet=False):
    """lines is list of (text, bold, color_override) or just strings."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True

    for i, line in enumerate(lines):
        if isinstance(line, tuple):
            text, is_bold, clr = line
        else:
            text = line
            is_bold = (bold_first and i == 0)
            clr = color

        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()

        p.text = text
        p.font.size = Pt(font_size)
        p.font.color.rgb = clr
        p.font.bold = is_bold
        p.font.name = font_name
        p.space_after = Pt(font_size * 0.4)

    return txBox


def add_code_box(slide, left, top, width, height, code_text, font_size=11):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
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
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = line
        p.font.size = Pt(font_size)
        p.font.name = "Menlo"
        p.font.color.rgb = RGBColor(0xE0, 0xE0, 0xE0)
        p.space_after = Pt(1)

    return shape


def add_arrow_shape(slide, left, top, width, height, color=LIGHT_BLUE):
    shape = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def add_box(slide, left, top, width, height, text, fill_color, text_color=WHITE,
            font_size=14, bold=True, font_name="Arial"):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
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
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    # Vertically center
    tf.auto_size = None
    return shape


def add_rect(slide, left, top, width, height, fill_color, border_color=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if border_color:
        shape.line.color.rgb = border_color
        shape.line.width = Pt(1)
    else:
        shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


# ═══════════════════════════════════════════════════════════════════════════════
# VERSION 1: "The Problem-Solution" — starts with what's missing, then the fix
# ═══════════════════════════════════════════════════════════════════════════════

def make_v1():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    W = prs.slide_width
    H = prs.slide_height

    # ── Slide 1: Title ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    set_slide_bg(slide, DARK_BLUE)

    add_textbox(slide, Inches(1), Inches(2.0), Inches(11), Inches(1.5),
                "Hypothesis-Driven Evolution", font_size=44, color=WHITE,
                bold=True)
    add_textbox(slide, Inches(1), Inches(3.5), Inches(11), Inches(0.8),
                "Making LLM-guided code evolution learn from its own experiments",
                font_size=22, color=LIGHT_BLUE)
    add_textbox(slide, Inches(1), Inches(5.5), Inches(11), Inches(0.5),
                "OpenEvolve  |  V3 Inline Results Architecture",
                font_size=16, color=MED_GRAY)

    # ── Slide 2: The Problem ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), DARK_BLUE)
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "The Problem: Blind Evolution", font_size=30, color=WHITE, bold=True)

    add_multiline_textbox(slide, Inches(0.8), Inches(1.3), Inches(5.5), Inches(5.5), [
        ("Standard OpenEvolve (No Hypotheses)", True, DARK_BLUE),
        "",
        "LLM generates code mutations",
        "Evaluator returns metrics (e.g., score = 0.72)",
        "LLM sees: parent code + score + top programs",
        "",
        ("What's missing:", True, ACCENT_RED),
        "LLM doesn't know WHY a change helped or hurt",
        "No causal reasoning is captured or shared",
        "Each iteration starts from scratch intellectually",
        "Successful strategies aren't explicitly documented",
        "Same failed approaches get re-attempted",
    ], font_size=17, color=DARK_GRAY)

    add_code_box(slide, Inches(7), Inches(1.3), Inches(5.8), Inches(2.5),
                 "# Normal evolution: just code, no reasoning\n"
                 "# EVOLVE-BLOCK-START\n"
                 "def solve(x):\n"
                 "    # some mutation...\n"
                 "    return result\n"
                 "# EVOLVE-BLOCK-END\n"
                 "\n"
                 "# Evaluator returns: {score: 0.72}\n"
                 "# LLM sees the score but has no idea\n"
                 "# what drove the improvement/regression",
                 font_size=12)

    add_textbox(slide, Inches(7), Inches(4.3), Inches(5.8), Inches(2.5),
                "The LLM is like a scientist running experiments without\n"
                "keeping a lab notebook. It can't learn from patterns\n"
                "across iterations.",
                font_size=17, color=DARK_GRAY)

    # ── Slide 3: The Solution ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), DARK_BLUE)
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "The Solution: Hypotheses as Code Comments", font_size=30, color=WHITE, bold=True)

    add_multiline_textbox(slide, Inches(0.8), Inches(1.3), Inches(5.5), Inches(5.5), [
        ("Hypothesis-Driven Evolution", True, DARK_BLUE),
        "",
        "LLM states WHY it expects a change to help",
        "Each hypothesis has 3 parts:",
        "  HYPOTHESIS-N:  the claim",
        "  MECHANISM-N:  causal reasoning",
        "  EXPECT-N:  testable prediction (metric + threshold)",
        "",
        "After evaluation, framework stamps the verdict:",
        "  RESULT-N: CONFIRMED / REFUTED / INCONCLUSIVE",
        "",
        ("Key insight:", True, ACCENT_TEAL),
        "Verdicts live IN the code, not a separate database",
        "OpenEvolve's existing mechanisms carry them forward",
    ], font_size=17, color=DARK_GRAY)

    add_code_box(slide, Inches(7), Inches(1.3), Inches(5.8), Inches(5.0),
                 "# EVOLVE-BLOCK-START\n"
                 "# HYPOTHESIS-1: Multi-start search escapes\n"
                 "#   local minima, improving combined_score\n"
                 "# MECHANISM-1: Random restarts cover more\n"
                 "#   basins in the search landscape\n"
                 "# EXPECT-1: combined_score > 0.8\n"
                 "# RESULT-1: CONFIRMED (actual=0.92)   <-- auto\n"
                 "#\n"
                 "# HYPOTHESIS-2: Larger step size finds\n"
                 "#   global optimum faster\n"
                 "# MECHANISM-2: Coarse search then refine\n"
                 "# EXPECT-2: distance_score > 0.9\n"
                 "# RESULT-2: REFUTED (actual=0.71)     <-- auto\n"
                 "\n"
                 "def solve(x):\n"
                 "    # evolved code here...\n"
                 "    return result\n"
                 "# EVOLVE-BLOCK-END",
                 font_size=12)

    # ── Slide 4: Pipeline Flow ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), DARK_BLUE)
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "How It Works: Step by Step", font_size=30, color=WHITE, bold=True)

    steps = [
        ("1  Config", "hypothesis_driven: true\nin YAML config", MID_BLUE),
        ("2  System Prompt", "HYPOTHESIS_INSTRUCTIONS\nappended to LLM prompt", MID_BLUE),
        ("3  LLM Writes", "HYPOTHESIS/MECHANISM/EXPECT\ncomments + evolved code", LIGHT_BLUE),
        ("4  Rescue", "rescue_hypotheses()\nrecovers comments lost\nin diff application", LIGHT_BLUE),
        ("5  Evaluate", "Evaluator runs code\nreturns metrics only\n(hypothesis-unaware)", ACCENT_TEAL),
        ("6  Stamp", "inject_result_comments()\nadds RESULT-N lines\nafter each EXPECT-N", ACCENT_GREEN),
        ("7  Store", "Code WITH results\nstored in database\n(MAP-Elites islands)", MID_BLUE),
        ("8  Next Iter", "Code shown as parent/\ntop/inspiration\nRESULTs visible to LLM", DARK_BLUE),
    ]

    box_w = Inches(1.35)
    box_h = Inches(1.6)
    start_x = Inches(0.5)
    y = Inches(1.5)
    gap = Inches(0.18)

    for i, (title, desc, color) in enumerate(steps):
        x = start_x + i * (box_w + gap)
        add_box(slide, x, y, box_w, Inches(0.5), title, color, WHITE, font_size=13, bold=True)
        add_textbox(slide, x + Pt(4), y + Inches(0.55), box_w - Pt(8), box_h - Inches(0.5),
                    desc, font_size=11, color=DARK_GRAY)

        # Arrow between boxes
        if i < len(steps) - 1:
            arrow_x = x + box_w + Pt(2)
            add_textbox(slide, arrow_x, y + Inches(0.1), Inches(0.15), Inches(0.4),
                        ">", font_size=22, color=MED_GRAY, bold=True)

    # Bottom: summary diagram
    add_code_box(slide, Inches(0.5), Inches(3.6), Inches(12.3), Inches(3.3),
                 "Iteration N:\n"
                 "  LLM sees:  system prompt (hypothesis instructions + RESULT-N docs)\n"
                 "           + parent code (with HYPOTHESIS/EXPECT/RESULT from parent's eval)\n"
                 "           + top programs (with their HYPOTHESIS/EXPECT/RESULT)\n"
                 "           + inspirations (with their HYPOTHESIS/EXPECT/RESULT)\n"
                 "\n"
                 "  LLM writes: evolved code with 1-3 HYPOTHESIS/MECHANISM/EXPECT comments\n"
                 "\n"
                 "  Framework:  rescue_hypotheses()     -- if diff mode lost comments\n"
                 "            > evaluator runs code     -- returns metrics (no hypothesis code)\n"
                 "            > inject_result_comments() -- stamps RESULT-N after EXPECT-N\n"
                 "            > stores code in database -- code carries its own verdicts\n"
                 "\n"
                 "Iteration N+1:\n"
                 "  This program may be selected as parent/top/inspiration\n"
                 "  > its code (with RESULT lines) is shown to the LLM > cycle continues",
                 font_size=12)

    # ── Slide 5: What OpenEvolve Provides ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), DARK_BLUE)
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "Zero Infrastructure: Leveraging OpenEvolve", font_size=30, color=WHITE, bold=True)

    add_multiline_textbox(slide, Inches(0.8), Inches(1.3), Inches(5.5), Inches(5.5), [
        ("What OpenEvolve already provides:", True, ACCENT_TEAL),
        "",
        "Parent selection  ->  parent's hypotheses + results shown",
        "Top programs      ->  best programs' strategies visible",
        "Inspirations      ->  diverse approaches visible",
        "Island isolation  ->  hypotheses stay within populations",
        "Migration         ->  strategies cross islands with code",
        "Checkpointing     ->  hypothesis history persists on resume",
        "",
        ("What we added (net ~40 lines):", True, ACCENT_GREEN),
        "",
        "inject_result_comments()  in hypothesis.py",
        "5 lines in iteration.py   (call after eval)",
        "5 lines in process_parallel.py (same in worker)",
        "Updated prompt template   (document RESULT-N)",
    ], font_size=17, color=DARK_GRAY)

    add_multiline_textbox(slide, Inches(7), Inches(1.3), Inches(5.8), Inches(5.5), [
        ("What we DON'T need:", True, ACCENT_RED),
        "",
        "No ledger file               (verdicts in code)",
        "No knowledge base generation (LLM reads code directly)",
        "No hypothesis artifacts      (evaluators unaware)",
        "No prompt-time queries       (code carries its history)",
        "No aggregation logic         (each program self-contained)",
        "No extra database fields     (just code + metrics)",
        "",
        ("Result:", True, DARK_BLUE),
        "~270 fewer lines vs V1 evaluator-based approach",
        "Evaluators are clean — just return metrics",
        "Works with any language (Python, Go, Rust, etc.)",
    ], font_size=17, color=DARK_GRAY)

    path = os.path.join(OUT_DIR, "hypothesis_v1_problem_solution.pptx")
    prs.save(path)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════════════════════
# VERSION 2: "Before/After" — side-by-side comparison focus
# ═══════════════════════════════════════════════════════════════════════════════

def make_v2():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # ── Slide 1: Title ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, RGBColor(0x0F, 0x24, 0x3E))

    add_textbox(slide, Inches(1), Inches(2.2), Inches(11), Inches(1.5),
                "Hypothesis-Driven Evolution", font_size=44, color=WHITE, bold=True)
    add_textbox(slide, Inches(1), Inches(3.7), Inches(11), Inches(0.6),
                "Teaching LLMs to reason about code improvements", font_size=22,
                color=ACCENT_TEAL)
    add_textbox(slide, Inches(1), Inches(5.0), Inches(11), Inches(0.5),
                "OpenEvolve  |  Inline Results (V3)", font_size=16, color=MED_GRAY)

    # ── Slide 2: Normal vs Hypothesis-Driven side-by-side ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, LIGHT_GRAY)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), DARK_BLUE)
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "Normal vs. Hypothesis-Driven Evolution", font_size=30, color=WHITE, bold=True)

    # Left panel: Normal
    add_rect(slide, Inches(0.5), Inches(1.2), Inches(5.9), Inches(5.8), WHITE, MED_GRAY)
    add_textbox(slide, Inches(0.8), Inches(1.4), Inches(5.3), Inches(0.5),
                "Normal Evolution", font_size=22, color=ACCENT_RED, bold=True)

    add_code_box(slide, Inches(0.8), Inches(2.1), Inches(5.3), Inches(2.2),
                 "# EVOLVE-BLOCK-START\n"
                 "def solve(x):\n"
                 "    result = random_search(x, n=100)\n"
                 "    return result\n"
                 "# EVOLVE-BLOCK-END\n"
                 "\n"
                 "# Metrics: {combined_score: 0.72}",
                 font_size=12)

    add_multiline_textbox(slide, Inches(0.8), Inches(4.5), Inches(5.3), Inches(2.3), [
        "LLM knows: the code + a score",
        "LLM doesn't know:",
        "  - Why this scored 0.72",
        "  - What strategies were tried before",
        "  - Which approaches failed",
        "  - What mechanism drives the score",
    ], font_size=15, color=DARK_GRAY)

    # Right panel: Hypothesis-Driven
    add_rect(slide, Inches(6.9), Inches(1.2), Inches(5.9), Inches(5.8), WHITE, ACCENT_TEAL)
    add_textbox(slide, Inches(7.2), Inches(1.4), Inches(5.3), Inches(0.5),
                "Hypothesis-Driven", font_size=22, color=ACCENT_TEAL, bold=True)

    add_code_box(slide, Inches(7.2), Inches(2.1), Inches(5.3), Inches(2.2),
                 "# EVOLVE-BLOCK-START\n"
                 "# HYPOTHESIS-1: Multi-start escapes local minima\n"
                 "# MECHANISM-1: Random restarts cover more basins\n"
                 "# EXPECT-1: combined_score > 0.8\n"
                 "# RESULT-1: CONFIRMED (actual=0.92)\n"
                 "def solve(x):\n"
                 "    result = multi_start_search(x, restarts=5)\n"
                 "    return result\n"
                 "# EVOLVE-BLOCK-END",
                 font_size=12)

    add_multiline_textbox(slide, Inches(7.2), Inches(4.5), Inches(5.3), Inches(2.3), [
        "LLM knows: the code + score + reasoning",
        "LLM also sees:",
        "  - What hypothesis was tested",
        "  - The causal mechanism proposed",
        "  - Whether the prediction held (CONFIRMED)",
        "  - Same info for top programs & inspirations",
    ], font_size=15, color=DARK_GRAY)

    # ── Slide 3: Lifecycle ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), DARK_BLUE)
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "Hypothesis Lifecycle", font_size=30, color=WHITE, bold=True)

    # Steps as boxes with arrows
    lifecycle = [
        ("GENERATED\nby LLM", "LLM writes HYPOTHESIS-N,\nMECHANISM-N, EXPECT-N\nas code comments", MID_BLUE),
        ("RESCUED\nif needed", "rescue_hypotheses()\nrecovers from diff\napplication edge cases", LIGHT_BLUE),
        ("TESTED\nby framework", "inject_result_comments()\ncompares EXPECT vs actual\nmetrics from evaluator", ACCENT_TEAL),
        ("STAMPED\nin code", "RESULT-N: CONFIRMED\nor REFUTED appended\nafter each EXPECT-N", ACCENT_GREEN),
        ("INHERITED\nnext iteration", "Parent/top/inspiration\ncode carries hypotheses\n+ results to next LLM", DARK_BLUE),
    ]

    box_w = Inches(2.15)
    box_h = Inches(0.7)
    start_x = Inches(0.6)
    y1 = Inches(1.3)
    y2 = Inches(2.2)
    gap = Inches(0.3)

    for i, (title, desc, color) in enumerate(lifecycle):
        x = start_x + i * (box_w + gap)
        add_box(slide, x, y1, box_w, box_h, title, color, WHITE, font_size=13, bold=True)
        add_textbox(slide, x + Pt(4), y2, box_w - Pt(8), Inches(1.3),
                    desc, font_size=12, color=DARK_GRAY)
        if i < len(lifecycle) - 1:
            ax = x + box_w + Pt(3)
            add_textbox(slide, ax, y1 + Pt(6), Inches(0.2), Inches(0.5),
                        ">", font_size=24, color=MED_GRAY, bold=True)

    # Where stored / when injected
    add_textbox(slide, Inches(0.6), Inches(3.8), Inches(12), Inches(0.5),
                "Where are hypotheses stored? When are they injected?",
                font_size=22, color=DARK_BLUE, bold=True)

    add_multiline_textbox(slide, Inches(0.8), Inches(4.5), Inches(5.5), Inches(2.5), [
        ("Stored:", True, ACCENT_TEAL),
        "In the code itself as comment lines",
        "Database stores code => stores hypotheses",
        "No separate ledger, no artifacts, no JSON files",
        "",
        ("Generated:", True, MID_BLUE),
        "By LLM at the start of each iteration",
        "Placed at TOP of EVOLVE-BLOCK, before code",
    ], font_size=16, color=DARK_GRAY)

    add_multiline_textbox(slide, Inches(7), Inches(4.5), Inches(5.5), Inches(2.5), [
        ("Injected (RESULT lines):", True, ACCENT_GREEN),
        "By framework AFTER evaluation returns metrics",
        "iteration.py and process_parallel.py call",
        "inject_result_comments(child_code, metrics)",
        "",
        ("Visible to next LLM when:", True, DARK_BLUE),
        "Code selected as parent, top program, or inspiration",
        "Carried by OpenEvolve's existing selection mechanisms",
    ], font_size=16, color=DARK_GRAY)

    # ── Slide 4: What we leverage from OpenEvolve ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), DARK_BLUE)
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "Leveraging OpenEvolve's Existing Architecture",
                font_size=30, color=WHITE, bold=True)

    # Two-column table-like layout
    features = [
        ("Parent Selection", "Parent code shown to LLM", "Parent's hypotheses + RESULT lines visible automatically"),
        ("Top Programs", "Best programs on island shown", "Top programs' confirmed/refuted strategies visible"),
        ("Inspirations", "Diverse programs from other islands", "Cross-island hypothesis intelligence travels with code"),
        ("Island Isolation", "Populations evolve independently", "Hypothesis strategies stay local until migration"),
        ("Migration", "Best programs cross islands", "Successful strategies spread with migrating code"),
        ("Checkpointing", "Full state persists to disk", "All hypothesis history preserved on resume"),
    ]

    y = Inches(1.2)
    for feat, desc, hypo_benefit in features:
        add_box(slide, Inches(0.5), y, Inches(2.3), Inches(0.5), feat, MID_BLUE, WHITE, font_size=13)
        add_textbox(slide, Inches(3.0), y + Pt(4), Inches(4.0), Inches(0.5),
                    desc, font_size=14, color=DARK_GRAY)
        add_textbox(slide, Inches(7.2), y + Pt(4), Inches(5.8), Inches(0.5),
                    hypo_benefit, font_size=14, color=ACCENT_TEAL)
        y += Inches(0.65)

    add_textbox(slide, Inches(0.5), y + Inches(0.3), Inches(12), Inches(0.5),
                "Result: hypothesis intelligence is a free rider on OpenEvolve's existing infrastructure",
                font_size=20, color=DARK_BLUE, bold=True)

    # Labels
    add_textbox(slide, Inches(3.0), Inches(0.95), Inches(4.0), Inches(0.3),
                "OpenEvolve Feature", font_size=13, color=MED_GRAY, bold=True)
    add_textbox(slide, Inches(7.2), Inches(0.95), Inches(5.8), Inches(0.3),
                "Hypothesis Benefit (zero extra code)", font_size=13, color=MED_GRAY, bold=True)

    path = os.path.join(OUT_DIR, "hypothesis_v2_before_after.pptx")
    prs.save(path)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════════════════════
# VERSION 3: "Technical Deep-Dive" — more code, more implementation detail
# ═══════════════════════════════════════════════════════════════════════════════

def make_v3():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # ── Slide 1: Title ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, DARK_BG)

    add_textbox(slide, Inches(1), Inches(2.0), Inches(11), Inches(1.0),
                "Hypothesis-Driven Evolution", font_size=44, color=WHITE, bold=True)
    add_textbox(slide, Inches(1), Inches(3.2), Inches(11), Inches(0.6),
                "Technical Overview: Inline Results Architecture (V3)",
                font_size=22, color=ACCENT_TEAL)
    add_textbox(slide, Inches(1), Inches(5.5), Inches(11), Inches(0.5),
                "openevolve/hypothesis.py  |  openevolve/iteration.py  |  openevolve/prompt/templates.py",
                font_size=14, color=MED_GRAY, font_name="Menlo")

    # ── Slide 2: The Comment Protocol ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), DARK_BG)
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "The Comment Protocol", font_size=30, color=WHITE, bold=True)

    add_textbox(slide, Inches(0.6), Inches(1.1), Inches(6), Inches(0.4),
                "LLM writes (3 lines per hypothesis, max 3 hypotheses):",
                font_size=16, color=DARK_GRAY, bold=True)

    add_code_box(slide, Inches(0.6), Inches(1.6), Inches(6), Inches(1.5),
                 "# HYPOTHESIS-N: <one-line claim>\n"
                 "# MECHANISM-N:  <causal explanation>\n"
                 "# EXPECT-N:     <metric_name> <|> <threshold>",
                 font_size=14)

    add_textbox(slide, Inches(0.6), Inches(3.3), Inches(6), Inches(0.4),
                "Framework adds after evaluation:",
                font_size=16, color=DARK_GRAY, bold=True)

    add_code_box(slide, Inches(0.6), Inches(3.8), Inches(6), Inches(1.0),
                 "# RESULT-N: CONFIRMED (actual=3850.0)\n"
                 "# RESULT-N: REFUTED (actual=5200.0)\n"
                 "# RESULT-N: INCONCLUSIVE (metric not available)",
                 font_size=14)

    add_textbox(slide, Inches(0.6), Inches(5.0), Inches(6), Inches(0.4),
                "Works with any comment syntax:",
                font_size=16, color=DARK_GRAY, bold=True)

    add_code_box(slide, Inches(0.6), Inches(5.5), Inches(6), Inches(1.5),
                 "# Python/Ruby/Shell        (prefix: #)\n"
                 "// Go/C/Rust/JS            (prefix: //)\n"
                 "-- SQL/Lua/Haskell         (prefix: --)\n"
                 "\n"
                 "Regex: r\"(?://|#|--)\\s*HYPOTHESIS-\\d+:\"",
                 font_size=13)

    # Right side: complete example
    add_textbox(slide, Inches(7), Inches(1.1), Inches(6), Inches(0.4),
                "Complete example (Go):", font_size=16, color=DARK_GRAY, bold=True)

    add_code_box(slide, Inches(7), Inches(1.6), Inches(5.8), Inches(5.4),
                 "// EVOLVE-BLOCK-START\n"
                 "// HYPOTHESIS-1: Adaptive weight adjustment based\n"
                 "//   on input length reduces avg latency\n"
                 "// MECHANISM-1: Short requests have minimal cache\n"
                 "//   benefit; routing by load-balance improves\n"
                 "//   throughput for these requests\n"
                 "// EXPECT-1: cache_warmup_e2e_ms < 4200\n"
                 "// RESULT-1: CONFIRMED (actual=3850.0)\n"
                 "//\n"
                 "// HYPOTHESIS-2: Overload penalty prevents\n"
                 "//   hot-spotting under bursty traffic\n"
                 "// MECHANISM-2: Quadratic penalty on high-load\n"
                 "//   instances redistributes requests evenly\n"
                 "// EXPECT-2: load_spikes_e2e_ms < 3350\n"
                 "// RESULT-2: REFUTED (actual=4100.0)\n"
                 "\n"
                 "func route(req Request) int {\n"
                 "    // ... evolved routing logic ...\n"
                 "}\n"
                 "// EVOLVE-BLOCK-END",
                 font_size=12)

    # ── Slide 3: Implementation Details ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), DARK_BG)
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "Implementation: Key Functions", font_size=30, color=WHITE, bold=True)

    # rescue_hypotheses
    add_textbox(slide, Inches(0.5), Inches(1.1), Inches(6), Inches(0.4),
                "rescue_hypotheses(code, llm_response)", font_size=16,
                color=DARK_BLUE, bold=True, font_name="Menlo")
    add_textbox(slide, Inches(0.5), Inches(1.5), Inches(6), Inches(0.5),
                "When: After diff application, before evaluation\n"
                "Why: Some LLMs place hypotheses outside diff blocks",
                font_size=14, color=DARK_GRAY)
    add_code_box(slide, Inches(0.5), Inches(2.2), Inches(6), Inches(1.5),
                 "# In iteration.py (line ~125):\n"
                 "if config.hypothesis_driven:\n"
                 "    child_code = rescue_hypotheses(\n"
                 "        child_code, llm_response\n"
                 "    )",
                 font_size=12)

    # inject_result_comments
    add_textbox(slide, Inches(0.5), Inches(4.0), Inches(6), Inches(0.4),
                "inject_result_comments(code, actual_metrics)", font_size=16,
                color=ACCENT_TEAL, bold=True, font_name="Menlo")
    add_textbox(slide, Inches(0.5), Inches(4.4), Inches(6), Inches(0.5),
                "When: After evaluation returns metrics\n"
                "Why: Stamp verdicts into code before database storage",
                font_size=14, color=DARK_GRAY)
    add_code_box(slide, Inches(0.5), Inches(5.1), Inches(6), Inches(1.8),
                 "# In iteration.py (line ~160):\n"
                 "if config.hypothesis_driven and result.child_metrics:\n"
                 "    child_code = inject_result_comments(\n"
                 "        child_code, result.child_metrics\n"
                 "    )\n"
                 "# Same in process_parallel.py for workers",
                 font_size=12)

    # Right side: prompt injection
    add_textbox(slide, Inches(7), Inches(1.1), Inches(6), Inches(0.4),
                "HYPOTHESIS_INSTRUCTIONS_TEMPLATE", font_size=16,
                color=ACCENT_GREEN, bold=True, font_name="Menlo")
    add_textbox(slide, Inches(7), Inches(1.5), Inches(6), Inches(0.5),
                "When: System prompt construction (hypothesis_driven=true)\n"
                "Where: openevolve/prompt/templates.py",
                font_size=14, color=DARK_GRAY)
    add_code_box(slide, Inches(7), Inches(2.2), Inches(5.8), Inches(4.7),
                 "## Hypothesis-Driven Evolution\n"
                 "\n"
                 "You MUST include 1-3 hypotheses as comments\n"
                 "at the TOP of the EVOLVE-BLOCK.\n"
                 "\n"
                 "Format:\n"
                 "  # HYPOTHESIS-N: <claim>\n"
                 "  # MECHANISM-N:  <causal explanation>\n"
                 "  # EXPECT-N:     metric < threshold\n"
                 "\n"
                 "After evaluation, RESULT-N is auto-added:\n"
                 "  # RESULT-N: CONFIRMED (actual=3850.0)\n"
                 "  # RESULT-N: REFUTED (actual=5200.0)\n"
                 "\n"
                 "Rules:\n"
                 "- Look at RESULT lines in parent/top programs\n"
                 "- Build on CONFIRMED strategies\n"
                 "- Avoid REFUTED strategies\n"
                 "- Do NOT write RESULT lines yourself",
                 font_size=12)

    # ── Slide 4: Data Flow Diagram ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), DARK_BG)
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "Data Flow: Hypothesis Through the System", font_size=30, color=WHITE, bold=True)

    add_code_box(slide, Inches(0.5), Inches(1.2), Inches(12.3), Inches(5.8),
                 "                                    OPENEVOLVE FRAMEWORK\n"
                 "                    ┌──────────────────────────────────────────────────────────┐\n"
                 "                    │                                                          │\n"
                 " CONFIG             │   prompt/sampler.py          iteration.py                │\n"
                 " hypothesis_driven  │   ┌───────────────┐         ┌──────────────────────┐    │\n"
                 " : true             │   │ Append HYPO    │         │                      │    │\n"
                 "    ──────────────> │   │ INSTRUCTIONS   │──LLM──>│ rescue_hypotheses()  │    │\n"
                 "                    │   │ to system msg  │  call   │ (diff mode recovery) │    │\n"
                 "                    │   └───────────────┘         └──────────┬───────────┘    │\n"
                 "                    │                                         │                │\n"
                 "                    │                                         v                │\n"
                 "                    │                              ┌──────────────────────┐    │\n"
                 "                    │                              │ evaluator.evaluate()  │    │\n"
                 "                    │                              │ (hypothesis-UNAWARE)  │    │\n"
                 "                    │                              │ returns: {metrics}    │    │\n"
                 "                    │                              └──────────┬───────────┘    │\n"
                 "                    │                                         │                │\n"
                 "                    │                                         v                │\n"
                 "                    │                              ┌──────────────────────┐    │\n"
                 "                    │                              │inject_result_comments│    │\n"
                 "                    │                              │ EXPECT-1 vs metrics  │    │\n"
                 "                    │                              │  -> RESULT-1: ...    │    │\n"
                 "                    │                              └──────────┬───────────┘    │\n"
                 "                    │                                         │                │\n"
                 "                    │                                         v                │\n"
                 "                    │   database.py                ┌──────────────────────┐    │\n"
                 "                    │   ┌───────────────┐         │ Store child program   │    │\n"
                 "                    │   │ MAP-Elites    │<────────│ (code WITH RESULT-N)  │    │\n"
                 "                    │   │ Islands       │         └──────────────────────┘    │\n"
                 "                    │   │               │                                      │\n"
                 "                    │   │ parent/top/   │──> Next iteration LLM sees           │\n"
                 "                    │   │ inspiration   │    code with HYPOTHESIS + RESULT     │\n"
                 "                    │   └───────────────┘                                      │\n"
                 "                    │                                                          │\n"
                 "                    └──────────────────────────────────────────────────────────┘",
                 font_size=10)

    # ── Slide 5: Files changed ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), DARK_BG)
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "Files & Changes Summary", font_size=30, color=WHITE, bold=True)

    files = [
        ("openevolve/hypothesis.py", "+40 lines", "inject_result_comments() + HypothesisTracker", ACCENT_GREEN),
        ("openevolve/iteration.py", "+5 lines", "Call inject after eval, track stats", ACCENT_GREEN),
        ("openevolve/process_parallel.py", "+5 lines", "Same injection in worker process", ACCENT_GREEN),
        ("openevolve/prompt/templates.py", "~20 lines", "Updated HYPOTHESIS_INSTRUCTIONS_TEMPLATE", MID_BLUE),
        ("examples/*/evaluator.py (x4)", "-200 lines", "Removed all hypothesis pipeline boilerplate", ACCENT_RED),
    ]

    y = Inches(1.2)
    for fname, delta, desc, color in files:
        add_box(slide, Inches(0.5), y, Inches(4.5), Inches(0.5), fname, DARK_GRAY, WHITE, font_size=13, font_name="Menlo")
        add_box(slide, Inches(5.2), y, Inches(1.5), Inches(0.5), delta, color, WHITE, font_size=14)
        add_textbox(slide, Inches(7.0), y + Pt(4), Inches(6), Inches(0.5),
                    desc, font_size=14, color=DARK_GRAY)
        y += Inches(0.7)

    add_textbox(slide, Inches(0.5), y + Inches(0.5), Inches(12), Inches(0.5),
                "Net result: ~270 fewer lines of code, evaluators are hypothesis-free",
                font_size=20, color=DARK_BLUE, bold=True)

    # Tracking section
    add_textbox(slide, Inches(0.5), y + Inches(1.5), Inches(6), Inches(0.4),
                "Observability: HypothesisTracker", font_size=18, color=DARK_BLUE, bold=True)
    add_multiline_textbox(slide, Inches(0.5), y + Inches(2.1), Inches(12), Inches(2), [
        "Per-iteration stats: hypotheses generated, persisted, results injected, parent inheritance",
        "Aggregate rates: generation rate, persist rate, inject rate, inheritance rate",
        "Saved to JSON alongside checkpoints for experiment analysis",
    ], font_size=15, color=DARK_GRAY)

    path = os.path.join(OUT_DIR, "hypothesis_v3_technical.pptx")
    prs.save(path)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════════════════════
# VERSION 4: "Minimal / Executive" — 4 slides, maximum clarity, minimal text
# ═══════════════════════════════════════════════════════════════════════════════

def make_v4():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # ── Slide 1: Title ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, DARK_BLUE)

    add_textbox(slide, Inches(2), Inches(2.5), Inches(9), Inches(1.0),
                "Hypothesis-Driven Evolution", font_size=48, color=WHITE,
                bold=True, alignment=PP_ALIGN.CENTER)
    add_textbox(slide, Inches(2), Inches(3.8), Inches(9), Inches(0.6),
                "LLMs that explain their mutations and learn from outcomes",
                font_size=22, color=LIGHT_BLUE, alignment=PP_ALIGN.CENTER)

    # ── Slide 2: One-slide explainer ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), DARK_BLUE)
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "What Is It?", font_size=30, color=WHITE, bold=True)

    # Three big boxes
    boxes = [
        ("CLAIM", "HYPOTHESIS-N:\nWhat will improve", MID_BLUE),
        ("REASON", "MECHANISM-N:\nWhy it should work", LIGHT_BLUE),
        ("PREDICTION", "EXPECT-N:\nmetric > threshold", ACCENT_TEAL),
    ]

    for i, (label, desc, color) in enumerate(boxes):
        x = Inches(0.8) + i * Inches(4.2)
        add_box(slide, x, Inches(1.3), Inches(3.8), Inches(1.6), f"{label}\n\n{desc}",
                color, WHITE, font_size=18)

    # Arrow down
    add_textbox(slide, Inches(5.5), Inches(3.1), Inches(2), Inches(0.5),
                "Evaluate code   >>   Compare to prediction", font_size=16,
                color=DARK_GRAY, alignment=PP_ALIGN.CENTER, bold=True)

    # Result boxes
    result_boxes = [
        ("CONFIRMED", "Prediction held\nStrategy works", ACCENT_GREEN),
        ("REFUTED", "Prediction failed\nAvoid this approach", ACCENT_RED),
    ]

    for i, (label, desc, color) in enumerate(result_boxes):
        x = Inches(2.5) + i * Inches(5.0)
        add_box(slide, x, Inches(3.8), Inches(3.8), Inches(1.2),
                f"RESULT-N: {label}\n\n{desc}", color, WHITE, font_size=16)

    add_textbox(slide, Inches(0.8), Inches(5.4), Inches(12), Inches(1.5),
                "Results are stamped INTO the code as comments.\n"
                "When this code is shown to the next LLM (as parent or top program),\n"
                "the LLM sees what worked and what failed — in context with the code.",
                font_size=18, color=DARK_GRAY, alignment=PP_ALIGN.CENTER)

    # ── Slide 3: The Flow (minimal) ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), DARK_BLUE)
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "How It Flows", font_size=30, color=WHITE, bold=True)

    flow_items = [
        ("1", "LLM writes code + hypotheses", MID_BLUE),
        ("2", "Evaluator runs code, returns metrics", ACCENT_TEAL),
        ("3", "Framework stamps RESULT into code", ACCENT_GREEN),
        ("4", "Code stored in database (MAP-Elites)", DARK_BLUE),
        ("5", "Next LLM sees code + results", MID_BLUE),
    ]

    for i, (num, text, color) in enumerate(flow_items):
        y = Inches(1.3) + i * Inches(1.1)
        add_box(slide, Inches(1), y, Inches(0.6), Inches(0.6), num, color, WHITE, font_size=24)
        add_textbox(slide, Inches(2.0), y + Pt(6), Inches(10), Inches(0.6),
                    text, font_size=22, color=DARK_GRAY)
        if i < len(flow_items) - 1:
            add_textbox(slide, Inches(1.15), y + Inches(0.65), Inches(0.4), Inches(0.4),
                        "|", font_size=18, color=MED_GRAY, alignment=PP_ALIGN.CENTER)

    add_textbox(slide, Inches(7), Inches(1.3), Inches(5.8), Inches(5.5),
                "Evaluators never touch hypotheses.\n\n"
                "No ledger. No knowledge base.\nNo artifacts. No extra infrastructure.\n\n"
                "Hypotheses travel with the code\nthrough OpenEvolve's existing\n"
                "parent/top-program/inspiration\nselection mechanisms.",
                font_size=20, color=DARK_BLUE)

    # ── Slide 4: What we leverage ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), DARK_BLUE)
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "Built On, Not Built From Scratch", font_size=30, color=WHITE, bold=True)

    # Left: what we use
    add_textbox(slide, Inches(0.8), Inches(1.3), Inches(5.5), Inches(0.5),
                "OpenEvolve provides:", font_size=22, color=ACCENT_TEAL, bold=True)
    items = [
        "Parent selection     (carries hypotheses)",
        "Top programs         (carries strategies)",
        "Inspirations         (carries diversity)",
        "Island isolation     (localizes learning)",
        "Migration            (spreads successes)",
        "Checkpointing        (persists everything)",
    ]
    for i, item in enumerate(items):
        y = Inches(2.0) + i * Inches(0.65)
        add_textbox(slide, Inches(1.2), y, Inches(5.5), Inches(0.5),
                    item, font_size=18, color=DARK_GRAY, font_name="Menlo")

    # Right: what we added
    add_textbox(slide, Inches(7), Inches(1.3), Inches(5.5), Inches(0.5),
                "We added ~40 lines:", font_size=22, color=ACCENT_GREEN, bold=True)
    adds = [
        "inject_result_comments()    hypothesis.py",
        "5 lines after eval          iteration.py",
        "5 lines after eval          process_parallel.py",
        "Prompt template update      templates.py",
    ]
    for i, item in enumerate(adds):
        y = Inches(2.0) + i * Inches(0.65)
        add_textbox(slide, Inches(7.4), y, Inches(5.5), Inches(0.5),
                    item, font_size=18, color=DARK_GRAY, font_name="Menlo")

    add_textbox(slide, Inches(0.8), Inches(5.5), Inches(12), Inches(1.0),
                "Deleted ~200 lines of evaluator boilerplate. Net: ~270 fewer lines.",
                font_size=20, color=DARK_BLUE, bold=True, alignment=PP_ALIGN.CENTER)

    path = os.path.join(OUT_DIR, "hypothesis_v4_executive.pptx")
    prs.save(path)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════════════════════
# VERSION 5: "Analogy-Driven" — uses scientist/lab notebook analogy
# ═══════════════════════════════════════════════════════════════════════════════

def make_v5():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # ── Slide 1: Title ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, RGBColor(0x1A, 0x1A, 0x2E))

    add_textbox(slide, Inches(1), Inches(1.8), Inches(11), Inches(1.5),
                "Hypothesis-Driven Evolution", font_size=44, color=WHITE, bold=True)
    add_textbox(slide, Inches(1), Inches(3.3), Inches(11), Inches(1.0),
                "Turning a trial-and-error loop\ninto a scientific method",
                font_size=24, color=ACCENT_TEAL)
    add_textbox(slide, Inches(1), Inches(5.5), Inches(11), Inches(0.5),
                "OpenEvolve  |  V3 Architecture", font_size=16, color=MED_GRAY)

    # ── Slide 2: The Analogy ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), RGBColor(0x1A, 0x1A, 0x2E))
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "From Trial-and-Error to Scientific Method", font_size=30, color=WHITE, bold=True)

    # Left: trial and error
    add_rect(slide, Inches(0.5), Inches(1.2), Inches(5.9), Inches(5.8), LIGHT_GRAY, MED_GRAY)
    add_textbox(slide, Inches(0.8), Inches(1.4), Inches(5.3), Inches(0.5),
                "Trial-and-Error Scientist", font_size=22, color=ACCENT_RED, bold=True)

    add_multiline_textbox(slide, Inches(0.8), Inches(2.1), Inches(5.3), Inches(4.5), [
        '"I\'ll try adding more heat"',
        "  Result: 72% yield",
        "",
        '"I\'ll try a different catalyst"',
        "  Result: 68% yield",
        "",
        '"I\'ll try more heat again"   <-- repeats!',
        "  Result: 71% yield",
        "",
        ("Problems:", True, ACCENT_RED),
        "No record of reasoning",
        "Repeats failed experiments",
        "Can't build on successes systematically",
        "Colleagues can't learn from notes",
    ], font_size=16, color=DARK_GRAY)

    # Right: scientific method
    add_rect(slide, Inches(6.9), Inches(1.2), Inches(5.9), Inches(5.8), RGBColor(0xF0, 0xFA, 0xF0), ACCENT_TEAL)
    add_textbox(slide, Inches(7.2), Inches(1.4), Inches(5.3), Inches(0.5),
                "Hypothesis-Driven Scientist", font_size=22, color=ACCENT_TEAL, bold=True)

    add_multiline_textbox(slide, Inches(7.2), Inches(2.1), Inches(5.3), Inches(4.5), [
        '"H1: More heat increases yield because it',
        '  accelerates the rate-limiting step"',
        "  Predict: yield > 80%",
        "  Result: CONFIRMED (actual=85%)",
        "",
        '"H2: Catalyst X reduces side-reactions"',
        "  Predict: purity > 95%",
        "  Result: REFUTED (actual=88%)",
        "",
        ("Benefits:", True, ACCENT_TEAL),
        "Each experiment has a stated prediction",
        "Outcomes recorded next to reasoning",
        "Others read the notebook and build on it",
        "Failed paths documented, not repeated",
    ], font_size=16, color=DARK_GRAY)

    # ── Slide 3: Mapping to OpenEvolve ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), RGBColor(0x1A, 0x1A, 0x2E))
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "Mapping to OpenEvolve", font_size=30, color=WHITE, bold=True)

    mappings = [
        ("Scientist", "LLM", "Generates mutations (experiments)"),
        ("Hypothesis", "HYPOTHESIS-N comment", "One-line claim about what improves"),
        ("Reasoning", "MECHANISM-N comment", "Causal explanation of why"),
        ("Prediction", "EXPECT-N comment", "metric_name < or > threshold"),
        ("Lab notebook", "The code itself", "Comments live in code, travel with it"),
        ("Experiment result", "RESULT-N comment", "CONFIRMED / REFUTED / INCONCLUSIVE"),
        ("Colleagues reading notes", "Next LLM iteration", "Sees parent + top programs' results"),
        ("Research group", "MAP-Elites islands", "Independent populations with migration"),
    ]

    y = Inches(1.2)
    add_textbox(slide, Inches(0.5), y, Inches(2.5), Inches(0.4),
                "Scientific Method", font_size=14, color=MED_GRAY, bold=True)
    add_textbox(slide, Inches(3.2), y, Inches(3.5), Inches(0.4),
                "OpenEvolve Equivalent", font_size=14, color=MED_GRAY, bold=True)
    add_textbox(slide, Inches(7.0), y, Inches(6), Inches(0.4),
                "What It Does", font_size=14, color=MED_GRAY, bold=True)
    y += Inches(0.45)

    for sci, oe, desc in mappings:
        add_box(slide, Inches(0.5), y, Inches(2.5), Inches(0.5), sci, LIGHT_GRAY, DARK_GRAY, font_size=13)
        add_box(slide, Inches(3.2), y, Inches(3.5), Inches(0.5), oe, MID_BLUE, WHITE, font_size=12, font_name="Menlo")
        add_textbox(slide, Inches(7.0), y + Pt(5), Inches(6), Inches(0.4),
                    desc, font_size=14, color=DARK_GRAY)
        y += Inches(0.58)

    add_textbox(slide, Inches(0.5), y + Inches(0.3), Inches(12), Inches(0.5),
                "The \"lab notebook\" IS the code. No separate storage needed.",
                font_size=20, color=DARK_BLUE, bold=True, alignment=PP_ALIGN.CENTER)

    # ── Slide 4: The Pipeline ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), RGBColor(0x1A, 0x1A, 0x2E))
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "The Experiment Cycle", font_size=30, color=WHITE, bold=True)

    # Circular flow shown as a code box
    add_code_box(slide, Inches(0.5), Inches(1.2), Inches(7), Inches(5.8),
                 "# Iteration N:\n"
                 "#\n"
                 "# 1. FORM HYPOTHESIS\n"
                 "#    LLM reads: system prompt + parent code\n"
                 "#    (with RESULT lines from prior experiments)\n"
                 "#    + top programs (with their RESULTs)\n"
                 "#    LLM writes: HYPOTHESIS + MECHANISM + EXPECT\n"
                 "#\n"
                 "# 2. RUN EXPERIMENT\n"
                 "#    Evaluator runs evolved code\n"
                 "#    Returns metrics (hypothesis-unaware)\n"
                 "#\n"
                 "# 3. RECORD OUTCOME\n"
                 "#    Framework compares EXPECT vs actual\n"
                 "#    Stamps RESULT-N into the code\n"
                 "#    Code stored in database\n"
                 "#\n"
                 "# 4. SHARE FINDINGS\n"
                 "#    Code (with results) may become:\n"
                 "#    - Parent for next iteration\n"
                 "#    - Top program (visible to all on island)\n"
                 "#    - Inspiration (visible cross-island)\n"
                 "#\n"
                 "# Iteration N+1:\n"
                 "#    LLM sees prior results -> forms better hypotheses\n"
                 "#    -> cycle continues",
                 font_size=13)

    # Right: what's free
    add_textbox(slide, Inches(8), Inches(1.3), Inches(5), Inches(0.5),
                "What OpenEvolve gives us for free:", font_size=20, color=ACCENT_TEAL, bold=True)

    free_items = [
        ("Parent selection", "Carries hypotheses to child"),
        ("Top programs", "Best strategies visible"),
        ("Inspirations", "Diverse approaches shared"),
        ("Islands", "Local experimentation"),
        ("Migration", "Spread winning strategies"),
        ("Checkpoints", "Full experiment history"),
    ]

    y = Inches(2.0)
    for item, benefit in free_items:
        add_box(slide, Inches(8), y, Inches(2.2), Inches(0.45), item, MID_BLUE, WHITE, font_size=13)
        add_textbox(slide, Inches(10.4), y + Pt(4), Inches(2.8), Inches(0.4),
                    benefit, font_size=14, color=DARK_GRAY)
        y += Inches(0.6)

    add_textbox(slide, Inches(8), Inches(5.8), Inches(5), Inches(1.0),
                "Total new code: ~40 lines\nDeleted evaluator boilerplate: ~200 lines\nNet: -270 lines",
                font_size=17, color=DARK_BLUE, bold=True)

    # ── Slide 5: Code Example ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WHITE)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.9), RGBColor(0x1A, 0x1A, 0x2E))
    add_textbox(slide, Inches(0.6), Inches(0.15), Inches(12), Inches(0.6),
                "What The LLM Actually Sees", font_size=30, color=WHITE, bold=True)

    add_textbox(slide, Inches(0.5), Inches(1.1), Inches(6), Inches(0.4),
                "Parent program (from previous iteration):", font_size=16, color=DARK_BLUE, bold=True)

    add_code_box(slide, Inches(0.5), Inches(1.6), Inches(6), Inches(5.3),
                 "# EVOLVE-BLOCK-START\n"
                 "# HYPOTHESIS-1: Multi-start search escapes\n"
                 "#   local minima\n"
                 "# MECHANISM-1: Random restarts sample more\n"
                 "#   basins in the landscape\n"
                 "# EXPECT-1: combined_score > 0.8\n"
                 "# RESULT-1: CONFIRMED (actual=0.92)\n"
                 "#\n"
                 "# HYPOTHESIS-2: Larger step size speeds\n"
                 "#   convergence\n"
                 "# MECHANISM-2: Coarse-to-fine search\n"
                 "# EXPECT-2: distance_score > 0.9\n"
                 "# RESULT-2: REFUTED (actual=0.71)\n"
                 "\n"
                 "def solve(x):\n"
                 "    best = None\n"
                 "    for _ in range(5):  # multi-start\n"
                 "        candidate = local_search(x)\n"
                 "        if best is None or f(candidate) > f(best):\n"
                 "            best = candidate\n"
                 "    return best\n"
                 "# EVOLVE-BLOCK-END",
                 font_size=12)

    add_textbox(slide, Inches(7), Inches(1.1), Inches(6), Inches(0.4),
                "What the LLM learns from this:", font_size=16, color=ACCENT_TEAL, bold=True)

    add_multiline_textbox(slide, Inches(7.2), Inches(1.7), Inches(5.5), Inches(5.0), [
        ("From RESULT-1: CONFIRMED", True, ACCENT_GREEN),
        "Multi-start search works!",
        "The mechanism (random restarts) was correct",
        "Build on this: maybe try more restarts?",
        "",
        ("From RESULT-2: REFUTED", True, ACCENT_RED),
        "Larger step size did NOT help distance_score",
        "The coarse-to-fine mechanism failed",
        "Don't repeat this; try alternative approaches",
        "",
        ("The LLM's next mutation can be smarter:", True, DARK_BLUE),
        "",
        "Keep multi-start (CONFIRMED)",
        "Fix or replace the step-size strategy (REFUTED)",
        "Form new hypotheses about distance_score",
        "Set thresholds 5-10% beyond current actuals",
    ], font_size=16, color=DARK_GRAY)

    path = os.path.join(OUT_DIR, "hypothesis_v5_analogy.pptx")
    prs.save(path)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Generating 5 hypothesis-driven evolution slide decks...\n")
    make_v1()
    make_v2()
    make_v3()
    make_v4()
    make_v5()
    print("\nDone! All 5 versions saved to docs/slides/")
