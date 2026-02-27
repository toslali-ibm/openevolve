"""
Generate a PowerPoint deck with 5 different slide versions,
each explaining the OpenEvolve pipeline in a distinct visual style.
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import math

# ── colour palette ──────────────────────────────────────────────
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
BLACK      = RGBColor(0x00, 0x00, 0x00)
DARK_BG    = RGBColor(0x1A, 0x1A, 0x2E)
DARK_BG2   = RGBColor(0x16, 0x21, 0x3E)
ACCENT1    = RGBColor(0x00, 0x96, 0xD6)  # blue
ACCENT2    = RGBColor(0x00, 0xC9, 0xA7)  # teal
ACCENT3    = RGBColor(0xFF, 0x6B, 0x6B)  # coral
ACCENT4    = RGBColor(0xFF, 0xD9, 0x3D)  # gold
ACCENT5    = RGBColor(0xA8, 0x5C, 0xFF)  # purple
LIGHT_GRAY = RGBColor(0xE8, 0xE8, 0xE8)
MED_GRAY   = RGBColor(0x99, 0x99, 0x99)
SOFT_WHITE = RGBColor(0xF0, 0xF0, 0xF5)
WARM_BG    = RGBColor(0xFD, 0xF6, 0xE3)
CLEAN_BG   = RGBColor(0xF8, 0xF9, 0xFA)
NAVY       = RGBColor(0x0B, 0x1D, 0x51)
DEEP_BLUE  = RGBColor(0x1B, 0x2A, 0x4A)
GREEN      = RGBColor(0x2E, 0xCC, 0x71)
ORANGE     = RGBColor(0xF3, 0x9C, 0x12)
SOFT_BLUE  = RGBColor(0xE3, 0xF2, 0xFD)
SOFT_GREEN = RGBColor(0xE8, 0xF5, 0xE9)
SOFT_CORAL = RGBColor(0xFF, 0xEB, 0xEE)
SOFT_GOLD  = RGBColor(0xFF, 0xF8, 0xE1)
SOFT_PURPLE= RGBColor(0xF3, 0xE5, 0xF5)

prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)
W = prs.slide_width
H = prs.slide_height


# ── helpers ─────────────────────────────────────────────────────
def _set_bg(slide, color):
    bg = slide.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = color


def _add_text(slide, left, top, width, height, text, size=18,
              color=WHITE, bold=False, align=PP_ALIGN.LEFT, font_name="Calibri"):
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top),
                                      Inches(width), Inches(height))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font_name
    p.alignment = align
    return txBox


def _add_para(text_frame, text, size=16, color=WHITE, bold=False,
              space_before=Pt(6), space_after=Pt(2), align=PP_ALIGN.LEFT,
              font_name="Calibri"):
    p = text_frame.add_paragraph()
    p.text = text
    p.font.size = Pt(size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font_name
    p.space_before = space_before
    p.space_after = space_after
    p.alignment = align
    return p


def _rounded_rect(slide, left, top, width, height, fill_color,
                  text="", text_color=WHITE, text_size=14, bold=False,
                  line_color=None, line_width=Pt(0)):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if line_color:
        shape.line.color.rgb = line_color
        shape.line.width = line_width
    else:
        shape.line.fill.background()
    if text:
        tf = shape.text_frame
        tf.word_wrap = True
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        tf.paragraphs[0].text = text
        tf.paragraphs[0].font.size = Pt(text_size)
        tf.paragraphs[0].font.color.rgb = text_color
        tf.paragraphs[0].font.bold = bold
        tf.paragraphs[0].font.name = "Calibri"
        shape.text_frame.paragraphs[0].space_before = Pt(0)
        shape.text_frame.paragraphs[0].space_after = Pt(0)
        # vertical center
        shape.text_frame.auto_size = None
        try:
            shape.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
        except:
            pass
    return shape


def _arrow_right(slide, left, top, width, height, color=ACCENT1):
    arrow = slide.shapes.add_shape(
        MSO_SHAPE.RIGHT_ARROW,
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    arrow.fill.solid()
    arrow.fill.fore_color.rgb = color
    arrow.line.fill.background()
    return arrow


def _circle(slide, left, top, diameter, fill_color, text="",
            text_color=WHITE, text_size=12, bold=True):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.OVAL,
        Inches(left), Inches(top), Inches(diameter), Inches(diameter)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.fill.background()
    if text:
        tf = shape.text_frame
        tf.word_wrap = True
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        tf.paragraphs[0].text = text
        tf.paragraphs[0].font.size = Pt(text_size)
        tf.paragraphs[0].font.color.rgb = text_color
        tf.paragraphs[0].font.bold = bold
        tf.paragraphs[0].font.name = "Calibri"
    return shape


def _diamond(slide, left, top, size, fill_color, text="",
             text_color=WHITE, text_size=11):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.DIAMOND,
        Inches(left), Inches(top), Inches(size), Inches(size)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.fill.background()
    if text:
        tf = shape.text_frame
        tf.word_wrap = True
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        tf.paragraphs[0].text = text
        tf.paragraphs[0].font.size = Pt(text_size)
        tf.paragraphs[0].font.color.rgb = text_color
        tf.paragraphs[0].font.bold = True
        tf.paragraphs[0].font.name = "Calibri"
    return shape


def _line(slide, x1, y1, x2, y2, color=ACCENT1, width=Pt(2)):
    connector = slide.shapes.add_connector(
        1,  # straight connector
        Inches(x1), Inches(y1), Inches(x2), Inches(y2)
    )
    connector.line.color.rgb = color
    connector.line.width = width
    return connector


def _hexagon(slide, left, top, width, height, fill_color, text="",
             text_color=WHITE, text_size=12, bold=True):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.HEXAGON,
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.fill.background()
    if text:
        tf = shape.text_frame
        tf.word_wrap = True
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        tf.paragraphs[0].text = text
        tf.paragraphs[0].font.size = Pt(text_size)
        tf.paragraphs[0].font.color.rgb = text_color
        tf.paragraphs[0].font.bold = bold
        tf.paragraphs[0].font.name = "Calibri"
    return shape


# ================================================================
#  VERSION 1 — "The Big Picture" (dark, pipeline flow with boxes)
# ================================================================
slide1 = prs.slides.add_slide(prs.slide_layouts[6])  # blank
_set_bg(slide1, DARK_BG)

# Title
_add_text(slide1, 0.5, 0.2, 12, 0.7,
          "VERSION 1 — The Big Picture", size=14, color=MED_GRAY)
_add_text(slide1, 0.5, 0.6, 12, 0.9,
          "OpenEvolve: Teaching AI to Write Better Code\nThrough Evolutionary Trial and Error",
          size=32, color=WHITE, bold=True)

# Subtitle
_add_text(slide1, 0.5, 1.6, 10, 0.5,
          "An open-source framework inspired by Google DeepMind's AlphaEvolve",
          size=16, color=ACCENT2)

# ── flow diagram: 5 boxes with arrows ──
box_y = 2.8
box_h = 1.2
box_w = 2.0
gap = 0.55
start_x = 0.7

steps = [
    ("1. Seed Code", "Start with your\ninitial program", ACCENT1),
    ("2. LLM Mutates", "AI suggests\ncode changes", ACCENT5),
    ("3. Evaluate", "Test the new\ncode automatically", ACCENT3),
    ("4. Select Best", "Keep winners,\ndrop losers", ACCENT4),
    ("5. Repeat", "Evolve over\n1000s of rounds", ACCENT2),
]

for i, (title, desc, clr) in enumerate(steps):
    x = start_x + i * (box_w + gap)
    _rounded_rect(slide1, x, box_y, box_w, box_h, clr,
                  text=title, text_color=WHITE, text_size=16, bold=True)
    _add_text(slide1, x, box_y + box_h + 0.1, box_w, 0.7,
              desc, size=13, color=LIGHT_GRAY, align=PP_ALIGN.CENTER)

    if i < len(steps) - 1:
        ax = x + box_w + 0.05
        _arrow_right(slide1, ax, box_y + box_h/2 - 0.15, 0.4, 0.3, clr)

# Loop-back arrow hint
_add_text(slide1, start_x + 4*(box_w+gap) + box_w + 0.2, box_y + 0.3, 1.5, 0.6,
          "loop back\nto step 2", size=12, color=MED_GRAY, align=PP_ALIGN.LEFT)

# ── Bottom: key value props ──
prop_y = 5.3
props = [
    ("Any Language", "Python, Rust, R, Go..."),
    ("Parallel Evolution", "Many programs tested at once"),
    ("Smart Diversity", "Explores many solutions, not just one"),
    ("Auto-Improving", "Gets better over time, no hand-tuning"),
]
for i, (title, desc) in enumerate(props):
    x = 0.7 + i * 3.15
    _rounded_rect(slide1, x, prop_y, 2.9, 0.5, RGBColor(0x2A, 0x2A, 0x4E),
                  text=title, text_color=ACCENT2, text_size=14, bold=True,
                  line_color=ACCENT2, line_width=Pt(1))
    _add_text(slide1, x, prop_y + 0.55, 2.9, 0.4,
              desc, size=12, color=MED_GRAY, align=PP_ALIGN.CENTER)

# ── tagline ──
_add_text(slide1, 0.5, 6.5, 12, 0.5,
          "Think of it as \"survival of the fittest\" — but for code.",
          size=18, color=ACCENT4, bold=True, align=PP_ALIGN.CENTER)


# ================================================================
#  VERSION 2 — "The Recipe Card" (light, clean, numbered steps)
# ================================================================
slide2 = prs.slides.add_slide(prs.slide_layouts[6])
_set_bg(slide2, CLEAN_BG)

_add_text(slide2, 0.5, 0.2, 12, 0.5,
          "VERSION 2 — The Recipe Card", size=14, color=MED_GRAY)
_add_text(slide2, 0.5, 0.5, 12, 0.8,
          "OpenEvolve in 60 Seconds",
          size=36, color=NAVY, bold=True)
_add_text(slide2, 0.5, 1.2, 10, 0.5,
          "An evolutionary coding agent that uses LLMs to make your code better — automatically.",
          size=18, color=RGBColor(0x55, 0x55, 0x55))

# Left column: "What You Provide"
_rounded_rect(slide2, 0.5, 2.0, 3.8, 4.5, WHITE,
              line_color=ACCENT1, line_width=Pt(2))
_add_text(slide2, 0.7, 2.1, 3.4, 0.5,
          "What You Provide", size=20, color=ACCENT1, bold=True)

inputs = [
    ("Your code", "The starting program to improve"),
    ("An evaluator", "A script that scores how good the code is"),
    ("A config", "Settings: which LLMs to use, how many rounds"),
]
for i, (title, desc) in enumerate(inputs):
    y = 2.7 + i * 0.85
    _circle(slide2, 0.8, y, 0.45, ACCENT1, str(i+1), WHITE, 16)
    _add_text(slide2, 1.4, y, 2.7, 0.25, title, size=16, color=NAVY, bold=True)
    _add_text(slide2, 1.4, y + 0.28, 2.7, 0.25, desc, size=12, color=MED_GRAY)

# Middle: arrow
_arrow_right(slide2, 4.5, 3.8, 0.6, 0.5, ACCENT1)

# Center column: "What OpenEvolve Does"
_rounded_rect(slide2, 5.3, 2.0, 3.8, 4.5, WHITE,
              line_color=ACCENT5, line_width=Pt(2))
_add_text(slide2, 5.5, 2.1, 3.4, 0.5,
          "What OpenEvolve Does", size=20, color=ACCENT5, bold=True)

process = [
    ("Picks parents", "Selects promising code from the population"),
    ("Asks LLMs", "Multiple AI models suggest improvements"),
    ("Tests changes", "Runs your evaluator in a 3-stage cascade"),
    ("Keeps the best", "Winners enter the population, losers are dropped"),
    ("Repeats 1000x", "Evolves through many generations"),
]
for i, (title, desc) in enumerate(process):
    y = 2.65 + i * 0.7
    _circle(slide2, 5.5, y, 0.4, ACCENT5, str(i+1), WHITE, 14)
    _add_text(slide2, 6.05, y, 2.8, 0.22, title, size=15, color=NAVY, bold=True)
    _add_text(slide2, 6.05, y + 0.24, 2.8, 0.22, desc, size=11, color=MED_GRAY)

# Right arrow
_arrow_right(slide2, 9.3, 3.8, 0.6, 0.5, ACCENT2)

# Right column: "What You Get"
_rounded_rect(slide2, 10.1, 2.0, 2.8, 4.5, WHITE,
              line_color=ACCENT2, line_width=Pt(2))
_add_text(slide2, 10.3, 2.1, 2.4, 0.5,
          "What You Get", size=20, color=ACCENT2, bold=True)

outputs = [
    ("Better code", "Optimized program"),
    ("Metrics", "Performance scores"),
    ("Diversity", "Multiple good solutions"),
    ("Checkpoints", "Resume anytime"),
]
for i, (title, desc) in enumerate(outputs):
    y = 2.7 + i * 0.85
    _circle(slide2, 10.3, y, 0.4, ACCENT2, str(i+1), WHITE, 14)
    _add_text(slide2, 10.85, y, 1.9, 0.22, title, size=15, color=NAVY, bold=True)
    _add_text(slide2, 10.85, y + 0.25, 1.9, 0.22, desc, size=12, color=MED_GRAY)

# Bottom tagline
_add_text(slide2, 0.5, 6.7, 12, 0.5,
          "Like having a tireless team of programmers who keep improving your code — powered by LLMs.",
          size=16, color=ACCENT5, bold=True, align=PP_ALIGN.CENTER)


# ================================================================
#  VERSION 3 — "Biology Analogy" (nature metaphor, dark green)
# ================================================================
slide3 = prs.slides.add_slide(prs.slide_layouts[6])
_set_bg(slide3, RGBColor(0x0D, 0x1B, 0x0D))

_add_text(slide3, 0.5, 0.2, 12, 0.5,
          "VERSION 3 — The Biology Analogy", size=14, color=MED_GRAY)
_add_text(slide3, 0.5, 0.5, 12, 0.8,
          "OpenEvolve: Natural Selection for Code",
          size=36, color=GREEN, bold=True)
_add_text(slide3, 0.5, 1.3, 12, 0.5,
          "The same evolutionary process that created life on Earth — now applied to software.",
          size=18, color=RGBColor(0xA0, 0xD0, 0xA0))

# Two-column comparison
# Left: nature
nature_x = 0.7
tech_x = 6.9
col_w = 5.5
row_start = 2.3

_rounded_rect(slide3, nature_x, 2.0, col_w, 0.6,
              RGBColor(0x1A, 0x3A, 0x1A),
              text="In Nature", text_color=GREEN, text_size=22, bold=True,
              line_color=GREEN, line_width=Pt(2))
_rounded_rect(slide3, tech_x, 2.0, col_w, 0.6,
              RGBColor(0x1A, 0x1A, 0x3A),
              text="In OpenEvolve", text_color=ACCENT1, text_size=22, bold=True,
              line_color=ACCENT1, line_width=Pt(2))

analogies = [
    ("Organism",            "A Program",            "Each code version is a 'creature'"),
    ("DNA / Genes",         "Source Code",           "The instructions that define behaviour"),
    ("Mutation",            "LLM-Generated Edits",   "AI models suggest random improvements"),
    ("Natural Selection",   "Evaluation Cascade",    "Test in stages — fail fast, keep winners"),
    ("Population",          "MAP-Elites Database",   "A diverse pool of candidate programs"),
    ("Islands",             "Island Populations",    "Separate groups evolve independently"),
    ("Migration",           "Best-Program Sharing",  "Top performers spread across islands"),
    ("Survival of Fittest", "Highest Score Wins",    "Better programs replace weaker ones"),
]

for i, (nature, tech, explanation) in enumerate(analogies):
    y = 2.85 + i * 0.52
    # Nature side
    _rounded_rect(slide3, nature_x, y, 2.2, 0.42,
                  RGBColor(0x1A, 0x3A, 0x1A),
                  text=nature, text_color=GREEN, text_size=14, bold=True)
    # arrow
    _add_text(slide3, nature_x + 2.3, y + 0.02, 0.4, 0.35,
              "=", size=20, color=MED_GRAY, bold=True, align=PP_ALIGN.CENTER)
    # Tech side
    _rounded_rect(slide3, tech_x, y, 2.4, 0.42,
                  RGBColor(0x1A, 0x1A, 0x3A),
                  text=tech, text_color=ACCENT1, text_size=14, bold=True)
    # Explanation
    _add_text(slide3, tech_x + 2.6, y + 0.02, 3.2, 0.4,
              explanation, size=13, color=LIGHT_GRAY)

# Bottom
_add_text(slide3, 0.5, 6.6, 12, 0.5,
          "Result: After thousands of generations, your code evolves into something far better than the original.",
          size=17, color=ACCENT4, bold=True, align=PP_ALIGN.CENTER)


# ================================================================
#  VERSION 4 — "Under the Hood" (technical diagram, 3-layer)
# ================================================================
slide4 = prs.slides.add_slide(prs.slide_layouts[6])
_set_bg(slide4, DARK_BG2)

_add_text(slide4, 0.5, 0.2, 12, 0.5,
          "VERSION 4 — Under the Hood", size=14, color=MED_GRAY)
_add_text(slide4, 0.5, 0.5, 12, 0.8,
          "How OpenEvolve Works: The Architecture",
          size=34, color=WHITE, bold=True)

# ── Layer 1: Core Loop (center) ──
# Central cycle: Sample → Mutate → Evaluate → Store
center_y = 2.2
_add_text(slide4, 0.5, center_y - 0.3, 12, 0.4,
          "EVOLUTION LOOP  (runs 1000s of times in parallel)", size=16, color=ACCENT4, bold=True, align=PP_ALIGN.CENTER)

# Four boxes in a cycle
cycle_boxes = [
    (2.2, center_y + 0.3, "Sample\nParent", ACCENT1, "Pick a promising\nprogram from the\npopulation"),
    (5.3, center_y + 0.3, "LLM\nMutate", ACCENT5, "AI models suggest\ncode edits\n(diff or rewrite)"),
    (8.4, center_y + 0.3, "Evaluate\n(3 stages)", ACCENT3, "Quick check\nPerformance test\nFull benchmark"),
    (5.3, center_y + 2.3, "Store in\nDatabase", ACCENT2, "MAP-Elites grid\nkeeps diverse\nsolutions"),
]

for x, y, label, clr, desc in cycle_boxes:
    _rounded_rect(slide4, x, y, 2.0, 1.2, clr,
                  text=label, text_color=WHITE, text_size=16, bold=True)
    # desc below or beside
    if y == center_y + 0.3:
        _add_text(slide4, x, y + 1.25, 2.0, 0.7,
                  desc, size=11, color=LIGHT_GRAY, align=PP_ALIGN.CENTER)
    else:
        _add_text(slide4, x, y + 1.25, 2.0, 0.7,
                  desc, size=11, color=LIGHT_GRAY, align=PP_ALIGN.CENTER)

# Arrows between cycle boxes
_arrow_right(slide4, 4.35, center_y + 0.7, 0.7, 0.3, ACCENT1)  # sample→mutate
_arrow_right(slide4, 7.45, center_y + 0.7, 0.7, 0.3, ACCENT5)  # mutate→evaluate

# Down arrow (evaluate → store) — use a text arrow
_add_text(slide4, 8.9, center_y + 1.55, 0.5, 0.5, "v", size=28, color=ACCENT3, bold=True, align=PP_ALIGN.CENTER)
_line(slide4, 9.15, center_y + 1.6, 7.4, center_y + 2.7, ACCENT3, Pt(2))

# Left arrow (store → sample) — loop back
_add_text(slide4, 3.7, center_y + 2.6, 1.4, 0.4, "<---", size=20, color=ACCENT2, bold=True, align=PP_ALIGN.CENTER)
_line(slide4, 5.2, center_y + 2.9, 4.3, center_y + 2.9, ACCENT2, Pt(2))
_line(slide4, 4.3, center_y + 2.9, 3.2, center_y + 1.0, ACCENT2, Pt(2))

# ── Right side: key concepts ──
concepts_x = 10.5
_add_text(slide4, concepts_x, center_y - 0.3, 2.5, 0.4,
          "KEY CONCEPTS", size=16, color=ACCENT4, bold=True)

concepts = [
    ("LLM Ensemble", "Multiple AI models\n(GPT-4, Claude, etc.)\nvote on best changes", ACCENT5),
    ("MAP-Elites", "Grid of solutions:\neach cell holds the\nbest for that niche", ACCENT2),
    ("Islands", "4 separate populations\nevolve independently,\nshare winners", ACCENT1),
    ("Cascade Eval", "Stage 1: syntax check\nStage 2: basic test\nStage 3: full suite", ACCENT3),
]

for i, (title, desc, clr) in enumerate(concepts):
    y = center_y + 0.3 + i * 1.1
    _rounded_rect(slide4, concepts_x, y, 2.5, 0.35, clr,
                  text=title, text_color=WHITE, text_size=13, bold=True)
    _add_text(slide4, concepts_x, y + 0.38, 2.5, 0.65,
              desc, size=11, color=LIGHT_GRAY)

# Bottom
_add_text(slide4, 0.5, 6.7, 12, 0.5,
          "All of this runs in parallel worker processes — each iteration is independent and fast.",
          size=15, color=ACCENT4, align=PP_ALIGN.CENTER)


# ================================================================
#  VERSION 5 — "The Promise" (storytelling: problem → solution → impact)
# ================================================================
slide5 = prs.slides.add_slide(prs.slide_layouts[6])
_set_bg(slide5, NAVY)

_add_text(slide5, 0.5, 0.2, 12, 0.5,
          "VERSION 5 — The Promise", size=14, color=MED_GRAY)
_add_text(slide5, 0.5, 0.5, 12, 0.8,
          "OpenEvolve: From Good Code to Great Code",
          size=36, color=WHITE, bold=True)

# Three columns: Problem | Solution | Impact
col_w = 3.8
col_gap = 0.3
start_x = 0.6

sections = [
    ("THE PROBLEM", ACCENT3,
     [
         ("Manual optimization is slow",
          "Engineers spend weeks tuning algorithms by hand."),
         ("Local maxima trap",
          "Humans get stuck on one approach and stop exploring alternatives."),
         ("Can't try 1000 ideas",
          "People can only test a handful of variations — not thousands."),
         ("Language-specific expertise",
          "Optimizing Rust kernels requires different skills than Python ML code."),
     ]),
    ("THE SOLUTION", ACCENT1,
     [
         ("LLMs generate variations",
          "AI proposes code changes — diffs or full rewrites — at scale."),
         ("Diverse population (MAP-Elites)",
          "Maintains many different solutions, not just one — avoids local maxima."),
         ("Automated evaluation cascade",
          "Fast 3-stage testing: quick check → performance test → full benchmark."),
         ("Language-agnostic",
          "Works with Python, Rust, R, Go — any language with an evaluator."),
     ]),
    ("THE IMPACT", ACCENT2,
     [
         ("Superhuman optimization",
          "Discovers solutions humans wouldn't think of — like AlphaGo's Move 37."),
         ("Hands-free improvement",
          "Set it running overnight — wake up to better code."),
         ("Reproducible & checkpointed",
          "Every step is saved. Resume, inspect, or roll back anytime."),
         ("Open source & extensible",
          "Built on OpenAI-compatible APIs. Plug in any LLM. MIT licensed."),
     ]),
]

for col_i, (header, header_clr, items) in enumerate(sections):
    x = start_x + col_i * (col_w + col_gap)
    # Header bar
    _rounded_rect(slide5, x, 1.8, col_w, 0.6, header_clr,
                  text=header, text_color=WHITE, text_size=20, bold=True)

    for j, (title, desc) in enumerate(items):
        y = 2.6 + j * 1.1
        _rounded_rect(slide5, x, y, col_w, 0.95,
                      RGBColor(0x12, 0x2A, 0x5E),
                      line_color=header_clr, line_width=Pt(1))
        _add_text(slide5, x + 0.15, y + 0.08, col_w - 0.3, 0.3,
                  title, size=15, color=header_clr, bold=True)
        _add_text(slide5, x + 0.15, y + 0.42, col_w - 0.3, 0.5,
                  desc, size=13, color=LIGHT_GRAY)

    # Arrow between columns
    if col_i < 2:
        ax = x + col_w + 0.02
        _arrow_right(slide5, ax, 3.5, 0.25, 0.3, header_clr)

# Bottom tagline
_add_text(slide5, 0.5, 6.7, 12, 0.5,
          "OpenEvolve = evolutionary pressure + LLM creativity + automated testing, running at machine speed.",
          size=16, color=ACCENT4, bold=True, align=PP_ALIGN.CENTER)


# ── Save ────────────────────────────────────────────────────────
out_path = "openevolve_explainer_5_versions.pptx"
prs.save(out_path)
print(f"Saved to {out_path}")
