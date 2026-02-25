#!/usr/bin/env python3
"""Generate PowerPoint figures for the BLIS Router + OpenEvolve pipeline.

Focused on clarity: WHO does what, WHEN, and HOW hypotheses flow.
"""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
import math

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLACK = RGBColor(0x00, 0x00, 0x00)
DARK = RGBColor(0x2B, 0x2B, 0x2B)
MID = RGBColor(0x66, 0x66, 0x66)
LIGHT_BG = RGBColor(0xF7, 0xF7, 0xF7)
BORDER = RGBColor(0xCC, 0xCC, 0xCC)

BLUE_D = RGBColor(0x1B, 0x3A, 0x5C)
BLUE_M = RGBColor(0x2D, 0x6A, 0x9F)
BLUE_L = RGBColor(0xD6, 0xEA, 0xF8)

GREEN_D = RGBColor(0x1B, 0x5E, 0x20)
GREEN_M = RGBColor(0x2E, 0x7D, 0x32)
GREEN_L = RGBColor(0xE8, 0xF5, 0xE9)

ORANGE_D = RGBColor(0xE6, 0x5C, 0x00)
ORANGE_L = RGBColor(0xFF, 0xF3, 0xE0)

RED_D = RGBColor(0xC6, 0x28, 0x28)
RED_L = RGBColor(0xFF, 0xEB, 0xEE)

PURPLE_D = RGBColor(0x4A, 0x14, 0x8C)
PURPLE_L = RGBColor(0xF3, 0xE5, 0xF5)

TEAL_D = RGBColor(0x00, 0x69, 0x5C)
TEAL_L = RGBColor(0xE0, 0xF2, 0xF1)

AMBER_D = RGBColor(0xD4, 0xA0, 0x17)
AMBER_L = RGBColor(0xFD, 0xF6, 0xE3)
AMBER_TEXT = RGBColor(0x8B, 0x6B, 0x00)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _bg(slide, color):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def box(slide, l, t, w, h, fill, border=None, bw=Pt(1.5), radius=0.06):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, t, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if border:
        s.line.color.rgb = border
        s.line.width = bw
    else:
        s.line.fill.background()
    s.adjustments[0] = radius
    return s


def txt(shape, text, sz=10, bold=False, color=DARK, align=PP_ALIGN.LEFT):
    tf = shape.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(sz)
    p.font.bold = bold
    p.font.color.rgb = color
    p.font.name = "Calibri"
    p.alignment = align
    return tf


def para(tf, text, sz=10, bold=False, color=DARK, align=PP_ALIGN.LEFT,
         before=Pt(2)):
    p = tf.add_paragraph()
    p.text = text
    p.font.size = Pt(sz)
    p.font.bold = bold
    p.font.color.rgb = color
    p.font.name = "Calibri"
    p.alignment = align
    p.space_before = before
    p.space_after = Pt(0)
    return p


def label(slide, l, t, w, h, text, sz=10, bold=False, color=DARK,
          align=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(sz)
    p.font.bold = bold
    p.font.color.rgb = color
    p.font.name = "Calibri"
    p.alignment = align
    return tb


def arrow(slide, x1, y1, x2, y2, color=MID, w=Pt(2)):
    c = slide.shapes.add_connector(1, x1, y1, x2, y2)
    c.line.color.rgb = color
    c.line.width = w
    c.end_style = "arrow"
    return c


def big_arrow(slide, x1, y1, x2, y2, color=MID):
    return arrow(slide, x1, y1, x2, y2, color, Pt(3))


# ---------------------------------------------------------------------------
# SLIDE 1: The Big Picture — Who Does What
# ---------------------------------------------------------------------------
def slide_big_picture(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _bg(s, WHITE)

    # Title
    label(s, Inches(0.3), Inches(0.15), Inches(12.7), Inches(0.55),
          "Hypothesis-Driven Algorithm Discovery on OpenEvolve",
          sz=26, bold=True, color=BLUE_D, align=PP_ALIGN.CENTER)
    label(s, Inches(0.3), Inches(0.65), Inches(12.7), Inches(0.3),
          "Three actors, one loop, no human in the loop during evolution",
          sz=13, color=MID, align=PP_ALIGN.CENTER)

    # ── Three actor boxes ──
    actors = [
        {
            "who": "THE LLM  (Claude)",
            "role": "Scientist",
            "does": [
                "Reads what worked / failed before",
                "  (the \"knowledge base\")",
                "Proposes a new hypothesis:",
                "  \"If I route small requests by load,",
                "    cache_warmup should drop below 5000 ms\"",
                "Writes the code that implements it",
                "Embeds the hypothesis as a comment",
                "  right inside the code",
            ],
            "when": "Every iteration (called by OpenEvolve)",
            "fill": PURPLE_L, "border": PURPLE_D,
        },
        {
            "who": "THE EVALUATOR  (simulator)",
            "role": "Experimentalist",
            "does": [
                "Takes the LLM's code",
                "Compiles it into a Go binary",
                "Runs 3 experiments (workloads):",
                "  cache_warmup, load_spikes, multiturn",
                "Measures latency on each",
                "Checks: did the hypothesis come true?",
                "  (actual vs. predicted threshold)",
                "Records verdict: CONFIRMED or REFUTED",
            ],
            "when": "Every iteration (called by OpenEvolve)",
            "fill": RED_L, "border": RED_D,
        },
        {
            "who": "OPENEVOLVE  (framework)",
            "role": "Lab Manager",
            "does": [
                "Picks which program to improve next",
                "Hands the LLM the right context:",
                "  best programs, past results,",
                "  accumulated knowledge base",
                "Calls the LLM, then the evaluator",
                "Stores results in a population DB",
                "Keeps 3 independent \"islands\" of",
                "  programs to avoid getting stuck",
            ],
            "when": "Runs the loop: 100 iterations, fully automated",
            "fill": BLUE_L, "border": BLUE_M,
        },
    ]

    aw = Inches(3.95)
    ah = Inches(4.05)
    gap = Inches(0.2)
    aleft = Inches(0.45)
    atop = Inches(1.2)

    for i, a in enumerate(actors):
        al = aleft + i * (aw + gap)
        b = box(s, al, atop, aw, ah, a["fill"], a["border"], Pt(2))
        # WHO
        tf = txt(b, a["who"], 14, True, a["border"], PP_ALIGN.CENTER)
        para(tf, a["role"], 11, True, MID, PP_ALIGN.CENTER, Pt(1))
        para(tf, "", 4)
        # WHAT
        para(tf, "What it does:", 10, True, a["border"], PP_ALIGN.LEFT, Pt(6))
        for line in a["does"]:
            para(tf, line, 9, False, DARK, PP_ALIGN.LEFT, Pt(2))
        # WHEN
        para(tf, "", 6)
        para(tf, "When:", 10, True, a["border"], PP_ALIGN.LEFT, Pt(4))
        para(tf, a["when"], 9, False, MID, PP_ALIGN.LEFT, Pt(2))

    # ── Flow arrow at bottom ──
    flow_top = Inches(5.5)
    flow_box = box(s, Inches(0.45), flow_top, Inches(12.4), Inches(1.75),
                   LIGHT_BG, BORDER, Pt(1))
    tf = txt(flow_box, "  How one iteration flows (repeated 100 times, fully automated):",
             12, True, BLUE_D, PP_ALIGN.LEFT)
    para(tf, "", 6)

    # Step labels with WHO tags
    steps = [
        ("OpenEvolve", "picks a parent program from the population", BLUE_M),
        ("OpenEvolve", "assembles a prompt: parent + best programs + knowledge base of past hypotheses", BLUE_M),
        ("LLM (Claude)", "reads the prompt, writes new code + a hypothesis predicting what will improve", PURPLE_D),
        ("Evaluator", "compiles the code, runs 3 workloads, measures latency", RED_D),
        ("Evaluator", "checks hypothesis: did the prediction come true?  Records CONFIRMED or REFUTED", RED_D),
        ("OpenEvolve", "stores the program + results; updates the knowledge base for the next iteration", BLUE_M),
    ]
    for i, (who, what, color) in enumerate(steps):
        step_text = f"  {i+1}. {who}: {what}"
        para(tf, step_text, 10, False, color, PP_ALIGN.LEFT, Pt(3))


# ---------------------------------------------------------------------------
# SLIDE 2: One Iteration — Step by Step
# ---------------------------------------------------------------------------
def slide_one_iteration(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _bg(s, WHITE)

    label(s, Inches(0.3), Inches(0.15), Inches(12.7), Inches(0.5),
          "One Iteration  \u2014  What Happens Each Cycle",
          sz=24, bold=True, color=BLUE_D, align=PP_ALIGN.CENTER)
    label(s, Inches(0.3), Inches(0.6), Inches(12.7), Inches(0.3),
          "Each step is labeled with WHO does it. No human is involved during the loop.",
          sz=12, color=MID, align=PP_ALIGN.CENTER)

    # 4 main columns (combining sample+prompt, LLM, evaluate, store)
    cols = [
        {
            "num": "1",
            "title": "ASSEMBLE CONTEXT",
            "who": "OpenEvolve does this",
            "fill": BLUE_L, "border": BLUE_M, "tc": BLUE_D,
            "lines": [
                "Pick a parent program",
                "from the population",
                "",
                "Gather the 3 best programs",
                "and 2 diverse ones",
                "",
                "Include the knowledge base:",
                "a summary of ALL past",
                "hypotheses and whether",
                "they were confirmed or",
                "refuted",
                "",
                "Package it all into a",
                "prompt for the LLM",
            ],
        },
        {
            "num": "2",
            "title": "PROPOSE + CODE",
            "who": "The LLM does this",
            "fill": PURPLE_L, "border": PURPLE_D, "tc": PURPLE_D,
            "lines": [
                "Read the prompt:",
                " - what strategies worked",
                " - what strategies failed",
                " - best code so far",
                "",
                "Form a NEW hypothesis:",
                " \"If I route by load for",
                "  small inputs, latency",
                "  will drop below X ms\"",
                "",
                "Write the Go code that",
                "implements this idea",
                "",
                "Embed the hypothesis as",
                "a structured comment",
            ],
        },
        {
            "num": "3",
            "title": "RUN EXPERIMENTS",
            "who": "The evaluator does this",
            "fill": RED_L, "border": RED_D, "tc": RED_D,
            "lines": [
                "Compile the new code",
                "into a Go binary",
                "",
                "Run 3 simulation workloads:",
                " cache_warmup  (5 sec)",
                " load_spikes   (5 sec)",
                " multiturn     (10 sec)",
                "",
                "Measure actual latency",
                "on each workload",
                "",
                "Check the hypothesis:",
                " predicted < 5000 ms?",
                " actual = 4923 ms",
                " \u2192 CONFIRMED",
            ],
        },
        {
            "num": "4",
            "title": "LEARN + STORE",
            "who": "OpenEvolve does this",
            "fill": GREEN_L, "border": GREEN_M, "tc": GREEN_D,
            "lines": [
                "Record the verdict in",
                "the hypothesis ledger",
                "(a persistent JSON file)",
                "",
                "Regenerate the",
                "knowledge base from",
                "ALL past results:",
                "",
                " CONFIRMED strategies:",
                "  input-length routing",
                "  (4/4, avg \u22125.4%)",
                "",
                " REFUTED strategies:",
                "  load-only for all",
                "  (0/2, avg +5.5%)",
                "",
                "Store program in the",
                "population database",
            ],
        },
    ]

    cw = Inches(3.0)
    ch = Inches(5.3)
    cgap = Inches(0.2)
    cleft = Inches(0.35)
    ctop = Inches(1.1)

    for i, c in enumerate(cols):
        cl = cleft + i * (cw + cgap)
        b = box(s, cl, ctop, cw, ch, c["fill"], c["border"], Pt(2))

        # Number circle
        circ = s.shapes.add_shape(MSO_SHAPE.OVAL,
                                  cl + cw - Inches(0.45), ctop + Inches(0.08),
                                  Inches(0.35), Inches(0.35))
        circ.fill.solid()
        circ.fill.fore_color.rgb = c["border"]
        circ.line.fill.background()
        txt(circ, c["num"], 14, True, WHITE, PP_ALIGN.CENTER)

        # Title + who
        tf = txt(b, c["title"], 13, True, c["tc"], PP_ALIGN.CENTER)
        para(tf, c["who"], 9, True, MID, PP_ALIGN.CENTER, Pt(1))
        para(tf, "", 4)

        # Content
        for line in c["lines"]:
            if line == "":
                para(tf, "", 4)
            else:
                para(tf, line, 9, False, DARK, PP_ALIGN.LEFT, Pt(1))

        # Arrow to next
        if i < len(cols) - 1:
            ax = cl + cw
            ay = ctop + ch / 2
            big_arrow(s, ax + Inches(0.02), ay, ax + cgap - Inches(0.02), ay,
                      c["border"])

    # Return arrow
    ry = ctop + ch + Inches(0.15)
    right_x = cleft + 3 * (cw + cgap) + cw / 2
    left_x = cleft + cw / 2
    big_arrow(s, right_x, ry, left_x, ry, BLUE_M)
    label(s, Inches(4.0), ry - Inches(0.2), Inches(5), Inches(0.25),
          "repeat  \u2192  knowledge base grows every iteration  \u2192  LLM gets smarter",
          sz=10, bold=True, color=BLUE_D, align=PP_ALIGN.CENTER)

    # Key takeaway
    kt = ctop + ch + Inches(0.4)
    kb = box(s, Inches(0.35), kt, Inches(12.6), Inches(0.55),
             AMBER_L, AMBER_D, Pt(2))
    tf = txt(kb, "  KEY: The LLM generates a new hypothesis EVERY iteration. "
             "It's not a one-time thing. The knowledge base grows, "
             "so the LLM's hypotheses get better over time.",
             11, True, AMBER_TEXT, PP_ALIGN.LEFT)


# ---------------------------------------------------------------------------
# SLIDE 3: The Hypothesis Feedback Loop
# ---------------------------------------------------------------------------
def slide_hypothesis_loop(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _bg(s, WHITE)

    label(s, Inches(0.3), Inches(0.15), Inches(12.7), Inches(0.5),
          "How Hypotheses Drive the Search",
          sz=24, bold=True, color=BLUE_D, align=PP_ALIGN.CENTER)
    label(s, Inches(0.3), Inches(0.6), Inches(12.7), Inches(0.3),
          "Each iteration: the LLM proposes a hypothesis, the simulator tests it, "
          "the result feeds back to the LLM",
          sz=12, color=MID, align=PP_ALIGN.CENTER)

    # ── Circular diagram with 4 nodes ──
    cx, cy = Inches(3.6), Inches(3.85)
    r = Inches(1.9)
    nw, nh = Inches(2.5), Inches(1.6)

    nodes = [
        ("KNOWLEDGE BASE\n(what we know so far)",
         "Confirmed: input-length routing\nRefuted: load-only for all\nInconclusive: SLO-aware routing",
         AMBER_L, AMBER_D, AMBER_TEXT),
        ("LLM PROPOSES\n(every iteration)",
         "Reads the knowledge base\nPicks a strategy to try or refine\nWrites code + hypothesis comment",
         PURPLE_L, PURPLE_D, PURPLE_D),
        ("SIMULATOR TESTS\n(automatic, no human)",
         "Compiles code, runs 3 workloads\nMeasures actual latency\nCompares against prediction",
         RED_L, RED_D, RED_D),
        ("VERDICT RECORDED\n(grows the knowledge)",
         "CONFIRMED or REFUTED\nStored in persistent ledger\nKnowledge base regenerated",
         GREEN_L, GREEN_M, GREEN_D),
    ]

    # Place at top, right, bottom, left
    angles = [math.pi/2, 0, -math.pi/2, math.pi]
    positions = []

    for i, (angle, (title, desc, fill, border, tc)) in enumerate(zip(angles, nodes)):
        nx = cx + r * math.cos(angle) - nw / 2
        ny = cy - r * math.sin(angle) - nh / 2
        positions.append((nx + nw/2, ny + nh/2))

        b = box(s, nx, ny, nw, nh, fill, border, Pt(2))
        tf = txt(b, title, 10, True, tc, PP_ALIGN.CENTER)
        para(tf, "", 3)
        for line in desc.split("\n"):
            para(tf, line, 8, False, DARK, PP_ALIGN.CENTER, Pt(2))

    # Arrows between nodes (clockwise: top→right→bottom→left→top)
    arrow_colors = [PURPLE_D, RED_D, GREEN_M, AMBER_D]
    for i in range(4):
        j = (i + 1) % 4
        x1, y1 = positions[i]
        x2, y2 = positions[j]
        dx, dy = x2 - x1, y2 - y1
        dist = math.sqrt(dx*dx + dy*dy)
        off = Inches(0.85)
        if dist > 0:
            sx = int(x1 + dx/dist * off)
            sy = int(y1 + dy/dist * off)
            ex = int(x2 - dx/dist * off)
            ey = int(y2 - dy/dist * off)
            big_arrow(s, sx, sy, ex, ey, arrow_colors[i])

    # Center label
    cb = box(s, cx - Inches(0.85), cy - Inches(0.35),
             Inches(1.7), Inches(0.7), WHITE, BLUE_M, Pt(2))
    tf = txt(cb, "LEARNING", 12, True, BLUE_D, PP_ALIGN.CENTER)
    para(tf, "LOOP", 12, True, BLUE_D, PP_ALIGN.CENTER)

    # ── Right side: concrete example ──
    ex_l = Inches(6.4)
    ex_t = Inches(1.1)
    ex_w = Inches(6.5)

    label(s, ex_l, ex_t, ex_w, Inches(0.3),
          "Concrete Example: 3 Iterations",
          sz=14, bold=True, color=BLUE_D, align=PP_ALIGN.LEFT)

    # Iteration 1
    it1 = box(s, ex_l, ex_t + Inches(0.4), ex_w, Inches(1.55),
              PURPLE_L, PURPLE_D, Pt(1.5))
    tf = txt(it1, "  Iteration 1 \u2014 First try (no prior knowledge)", 11, True, PURPLE_D)
    para(tf, "", 3)
    para(tf, "  LLM proposes:  \"Route small inputs (<1000 tokens) by load-balance\"", 9, False, DARK, before=Pt(2))
    para(tf, "  LLM writes:    // HYPOTHESIS-1: Input-length routing reduces cache_warmup", 9, False, PURPLE_D, before=Pt(2))
    para(tf, "                 // EXPECT-1: cache_warmup_e2e_ms < 5000", 9, False, PURPLE_D, before=Pt(1))
    para(tf, "  Simulator:     actual = 4923 ms  \u2192  CONFIRMED  (delta = \u22125.9% vs baseline)", 9, False, GREEN_D, before=Pt(4))
    para(tf, "  Ledger:        input-length routing: 1/1 confirmed", 9, False, TEAL_D, before=Pt(2))

    # Iteration 5
    it5 = box(s, ex_l, ex_t + Inches(2.15), ex_w, Inches(1.55),
              ORANGE_L, ORANGE_D, Pt(1.5))
    tf = txt(it5, "  Iteration 5 \u2014 Tries a different idea", 11, True, ORANGE_D)
    para(tf, "", 3)
    para(tf, "  LLM proposes:  \"Use load-balance for ALL requests, not just small ones\"", 9, False, DARK, before=Pt(2))
    para(tf, "  LLM writes:    // HYPOTHESIS-1: Load-only routing is universally better", 9, False, ORANGE_D, before=Pt(2))
    para(tf, "                 // EXPECT-1: multiturn_e2e_ms < 2100", 9, False, ORANGE_D, before=Pt(1))
    para(tf, "  Simulator:     actual = 2265 ms  \u2192  REFUTED  (delta = +5.5% vs baseline)", 9, False, RED_D, before=Pt(4))
    para(tf, "  Ledger:        load-only for all: 0/1 confirmed \u2014 bouncing sessions hurts!", 9, False, RED_D, before=Pt(2))

    # Iteration 15
    it15 = box(s, ex_l, ex_t + Inches(3.9), ex_w, Inches(1.55),
               GREEN_L, GREEN_M, Pt(1.5))
    tf = txt(it15, "  Iteration 15 \u2014 Builds on confirmed, avoids refuted", 11, True, GREEN_D)
    para(tf, "", 3)
    para(tf, "  Knowledge base says:  input-length routing confirmed 4/4;  load-only refuted 0/2", 9, False, AMBER_TEXT, before=Pt(2))
    para(tf, "  LLM proposes:  \"Combine input-length routing with CacheHitRate for even better results\"", 9, False, DARK, before=Pt(3))
    para(tf, "  LLM writes:    // HYPOTHESIS-1: Adding CacheHitRate to input-length routing", 9, False, GREEN_D, before=Pt(2))
    para(tf, "                 // EXPECT-1: avg_e2e_ms < 3800", 9, False, GREEN_D, before=Pt(1))
    para(tf, "  Simulator:     actual = 3750 ms  \u2192  CONFIRMED  (new best!)", 9, False, GREEN_D, before=Pt(4))

    # Bottom takeaway
    tk = box(s, ex_l, ex_t + Inches(5.65), ex_w, Inches(0.55),
             AMBER_L, AMBER_D, Pt(2))
    tf = txt(tk, "  The LLM learns from its own experiments. Confirmed ideas get refined. "
             "Refuted ideas get avoided.", 10, True, AMBER_TEXT)


# ---------------------------------------------------------------------------
# SLIDE 4: The 3 Workloads
# ---------------------------------------------------------------------------
def slide_workloads(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _bg(s, WHITE)

    label(s, Inches(0.3), Inches(0.15), Inches(12.7), Inches(0.5),
          "The 3 Experiments  \u2014  Why No Static Strategy Wins",
          sz=24, bold=True, color=BLUE_D, align=PP_ALIGN.CENTER)
    label(s, Inches(0.3), Inches(0.6), Inches(12.7), Inches(0.3),
          "Each candidate router is tested on 3 workloads that pull in different directions",
          sz=12, color=MID, align=PP_ALIGN.CENTER)

    workloads = [
        {
            "name": "cache_warmup",
            "fill": GREEN_L, "border": GREEN_M, "tc": GREEN_D,
            "setup": "1000 req/s for 5 seconds",
            "what": [
                "Small requests (< 1000 tokens)",
                "3 prefix groups + no-prefix batch",
            ],
            "trap": "Prefix-affinity maps 3 groups to\n3 instances \u2192 GPU 3 sits idle",
            "win": "Load-balance for small inputs\n(\u221926% latency)",
        },
        {
            "name": "load_spikes",
            "fill": ORANGE_L, "border": ORANGE_D, "tc": ORANGE_D,
            "setup": "1000 req/s for 5 seconds",
            "what": [
                "50% share one big prefix (bursty)",
                "25% realtime + 25% other prefix",
            ],
            "trap": "Prefix-affinity sends 50% of\ntraffic to ONE instance (+113%!)",
            "win": "Spread heavy-hitter traffic\nacross instances",
        },
        {
            "name": "multiturn",
            "fill": PURPLE_L, "border": PURPLE_D, "tc": PURPLE_D,
            "setup": "150 req/s for 10 seconds",
            "what": [
                "Multi-turn sessions with big prefixes",
                "40% coding, 25% chat, 15% QA",
            ],
            "trap": "Load-balance bounces sessions\n\u2192 loses KV cache (72 ms penalty)",
            "win": "Keep sessions pinned to their\ncached instance (prefix-affinity)",
        },
    ]

    ww = Inches(3.95)
    wh = Inches(4.6)
    wgap = Inches(0.2)
    wleft = Inches(0.45)
    wtop = Inches(1.1)

    for i, w in enumerate(workloads):
        wl = wleft + i * (ww + wgap)

        b = box(s, wl, wtop, ww, wh, w["fill"], w["border"], Pt(2))
        tf = txt(b, w["name"], 16, True, w["tc"], PP_ALIGN.CENTER)
        para(tf, w["setup"], 9, False, MID, PP_ALIGN.CENTER, Pt(1))
        para(tf, "", 6)

        para(tf, "What it runs:", 10, True, w["tc"], before=Pt(4))
        for line in w["what"]:
            para(tf, "  " + line, 9, False, DARK, before=Pt(2))

        para(tf, "", 6)
        # Trap sub-box
        trap_y = wtop + Inches(2.15)
        tb = box(s, wl + Inches(0.15), trap_y, ww - Inches(0.3), Inches(0.85),
                 RED_L, RED_D, Pt(1))
        ttf = txt(tb, "  The trap:", 9, True, RED_D)
        for line in w["trap"].split("\n"):
            para(ttf, "  " + line, 9, False, DARK, before=Pt(1))

        # Win sub-box
        win_y = trap_y + Inches(1.0)
        wb = box(s, wl + Inches(0.15), win_y, ww - Inches(0.3), Inches(0.85),
                 GREEN_L, GREEN_M, Pt(1))
        wtf = txt(wb, "  What works:", 9, True, GREEN_D)
        for line in w["win"].split("\n"):
            para(wtf, "  " + line, 9, False, DARK, before=Pt(1))

    # Bottom insight
    ins_top = Inches(5.9)
    ib = box(s, Inches(0.45), ins_top, Inches(12.4), Inches(1.3),
             AMBER_L, AMBER_D, Pt(2))
    tf = txt(ib, "  The insight:", 13, True, AMBER_TEXT)
    para(tf, "", 4)
    para(tf, "  cache_warmup wants load-balance.  multiturn wants prefix-affinity.  "
         "load_spikes punishes prefix-affinity.", 11, False, DARK, before=Pt(2))
    para(tf, "  No single fixed strategy works.  The router must be ADAPTIVE \u2014 "
         "choose a strategy based on the request.", 11, True, AMBER_TEXT, before=Pt(6))
    para(tf, "  A hand-crafted oracle proves 28% improvement is possible.  "
         "We let OpenEvolve discover this automatically.", 10, False, MID, before=Pt(6))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    slide_big_picture(prs)
    slide_one_iteration(prs)
    slide_hypothesis_loop(prs)
    slide_workloads(prs)

    out = "examples/blis_router/openevolve_blis_figures.pptx"
    prs.save(out)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
