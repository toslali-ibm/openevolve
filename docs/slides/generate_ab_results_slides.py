#!/usr/bin/env python3
"""Generate a single 5-slide deck — each slide is a different version of hypothesis A/B results."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import os

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(OUT_DIR, "..", ".."))

# Colors
DARK_BLUE = RGBColor(0x00, 0x2D, 0x5E)
MID_BLUE = RGBColor(0x00, 0x53, 0xA0)
LIGHT_BLUE = RGBColor(0x41, 0x78, 0xBE)
ACCENT_GREEN = RGBColor(0x24, 0xA1, 0x48)
ACCENT_RED = RGBColor(0xDA, 0x1E, 0x28)
ACCENT_ORANGE = RGBColor(0xFF, 0x83, 0x2B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF4, 0xF4, 0xF4)
DARK_GRAY = RGBColor(0x39, 0x39, 0x39)
BLACK = RGBColor(0x00, 0x00, 0x00)
WARM_WHITE = RGBColor(0xFA, 0xFA, 0xF7)


def set_slide_bg(slide, color):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_textbox(slide, left, top, width, height, text, font_size=18,
                color=BLACK, bold=False, alignment=PP_ALIGN.LEFT, font_name="Arial"):
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


def add_rich_textbox(slide, left, top, width, height, lines, font_size=14,
                     color=BLACK, font_name="Arial", line_spacing=1.15):
    """lines: list of (text, bold, color_override_or_None)"""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, (text, bold, col) in enumerate(lines):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = text
        p.font.size = Pt(font_size)
        p.font.color.rgb = col if col else color
        p.font.bold = bold
        p.font.name = font_name
        p.space_after = Pt(font_size * (line_spacing - 1) + 2)
    return txBox


def add_image_safe(slide, img_path, left, top, width, height):
    full = os.path.join(REPO_ROOT, img_path)
    if os.path.exists(full):
        slide.shapes.add_picture(full, left, top, width, height)
    else:
        add_textbox(slide, left, top, width, height,
                    f"[Image not found: {img_path}]", font_size=10, color=ACCENT_RED)


def add_table(slide, left, top, width, height, rows, col_widths=None):
    """rows: list of lists. First row is header."""
    n_rows = len(rows)
    n_cols = len(rows[0])
    table_shape = slide.shapes.add_table(n_rows, n_cols, left, top, width, height)
    table = table_shape.table

    if col_widths:
        for i, w in enumerate(col_widths):
            table.columns[i].width = w

    for r_idx, row in enumerate(rows):
        for c_idx, cell_text in enumerate(row):
            cell = table.cell(r_idx, c_idx)
            cell.text = str(cell_text)
            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.size = Pt(11)
                paragraph.font.name = "Arial"
                if r_idx == 0:
                    paragraph.font.bold = True
                    paragraph.font.color.rgb = WHITE
            if r_idx == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = DARK_BLUE
            elif r_idx % 2 == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = LIGHT_GRAY
    return table_shape


# ─── Slide 1: Executive Summary ──────────────────────────────────────────────

def slide1_executive(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    set_slide_bg(slide, WARM_WHITE)

    add_textbox(slide, Inches(0.5), Inches(0.2), Inches(9), Inches(0.6),
                "V1: Executive Summary — Hypothesis A/B Results",
                font_size=24, color=DARK_BLUE, bold=True)

    add_textbox(slide, Inches(0.5), Inches(0.7), Inches(9), Inches(0.4),
                "Does structured scientific reasoning (HYPOTHESIS → RESULT) improve LLM code evolution?",
                font_size=13, color=DARK_GRAY)

    # Results table
    rows = [
        ["Experiment", "Models", "Metrics", "Delta", "Winner"],
        ["Web Scraper", "GPT-4o + Sonnet 4.5", "4 (acc, comp, robust, parse)", "+12.4%", "TREATMENT"],
        ["BLIS Router", "Opus 4.5 + Sonnet 4.5", "5+ (latency, throughput, SLO)", "+4.6%", "TREATMENT"],
        ["Rust Sort", "GPT-5.2 + Opus 4.6", "5 (perf, adapt, correct)", "+0.0005%", "Tie"],
        ["Circle Packing", "GPT-5.2 + Opus 4.6", "1 (sum_radii)", "-0.76%", "CONTROL"],
        ["Func Minimization", "Gemini Flash", "1 (combined)", "-0.76%", "CONTROL"],
    ]
    tbl = add_table(slide, Inches(0.5), Inches(1.15), Inches(9), Inches(2.0), rows)

    # Key finding
    add_rich_textbox(slide, Inches(0.5), Inches(3.3), Inches(4.2), Inches(2.0), [
        ("When Hypotheses Help:", True, DARK_BLUE),
        ("1. Multi-metric feedback (tradeoffs to reason about)", False, None),
        ("2. Problem hard enough (not solved in <5 iterations)", False, None),
        ("3. Capable model (inject rate >40%)", False, None),
        ("", False, None),
        ("When They Hurt:", True, ACCENT_RED),
        ("• Single scalar metric — nothing to reason about", False, None),
        ("• Weak model — can't follow hypothesis format", False, None),
        ("• Too easy — ceiling reached before reasoning helps", False, None),
    ], font_size=12)

    # Convergence images - winners
    add_image_safe(slide, "experiments/ab_webscraper_gpt4o_30iter_20260302_1253/plots/convergence_curves.png",
                   Inches(5.0), Inches(3.2), Inches(2.3), Inches(1.7))
    add_textbox(slide, Inches(5.0), Inches(4.85), Inches(2.3), Inches(0.3),
                "Web Scraper (+12.4%)", font_size=9, color=ACCENT_GREEN, bold=True,
                alignment=PP_ALIGN.CENTER)

    add_image_safe(slide, "experiments/ab_blis_30iter_20260227_1349/plots/convergence_curves.png",
                   Inches(7.4), Inches(3.2), Inches(2.3), Inches(1.7))
    add_textbox(slide, Inches(7.4), Inches(4.85), Inches(2.3), Inches(0.3),
                "BLIS Router (+4.6%)", font_size=9, color=ACCENT_GREEN, bold=True,
                alignment=PP_ALIGN.CENTER)


# ─── Slide 2: By Outcome ─────────────────────────────────────────────────────

def slide2_by_outcome(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WARM_WHITE)

    add_textbox(slide, Inches(0.5), Inches(0.2), Inches(9), Inches(0.5),
                "V2: Results by Outcome — Helped / Marginal / Hurt",
                font_size=24, color=DARK_BLUE, bold=True)

    # LEFT: Helped
    add_textbox(slide, Inches(0.3), Inches(0.8), Inches(3.0), Inches(0.35),
                "HELPED", font_size=16, color=ACCENT_GREEN, bold=True)

    add_rich_textbox(slide, Inches(0.3), Inches(1.15), Inches(3.0), Inches(1.4), [
        ("Web Scraper: +12.4%", True, ACCENT_GREEN),
        ("GPT-4o + Sonnet 4.5 | 4 metrics", False, DARK_GRAY),
        ("Treatment 0.805 vs Control 0.716", False, None),
        ("Control seed=501 stuck at initial score", False, None),
    ], font_size=11)

    add_image_safe(slide, "experiments/ab_webscraper_gpt4o_30iter_20260302_1253/plots/convergence_curves.png",
                   Inches(0.3), Inches(2.6), Inches(2.9), Inches(2.1))

    add_rich_textbox(slide, Inches(0.3), Inches(4.75), Inches(3.0), Inches(1.0), [
        ("BLIS Router: +4.6%", True, ACCENT_GREEN),
        ("Opus + Sonnet | 5+ metrics", False, DARK_GRAY),
        ("Treatment -3876 vs Control -4053", False, None),
        ("13x lower variance (IQR 27 vs 341)", False, None),
    ], font_size=11)

    # MIDDLE: Marginal
    add_textbox(slide, Inches(3.5), Inches(0.8), Inches(3.0), Inches(0.35),
                "MARGINAL", font_size=16, color=ACCENT_ORANGE, bold=True)

    add_rich_textbox(slide, Inches(3.5), Inches(1.15), Inches(3.0), Inches(1.2), [
        ("Rust Sort: +0.0005%", True, ACCENT_ORANGE),
        ("GPT-5.2 + Opus 4.6 | 5 metrics", False, DARK_GRAY),
        ("Both reach 0.9998 — problem too easy", False, None),
        ("Treatment converges 5 iters faster", False, None),
    ], font_size=11)

    add_image_safe(slide, "experiments/ab_rustsort_gpt52_30iter_20260302_1149/plots/convergence_curves.png",
                   Inches(3.5), Inches(2.4), Inches(2.9), Inches(2.1))

    # RIGHT: Hurt
    add_textbox(slide, Inches(6.8), Inches(0.8), Inches(3.0), Inches(0.35),
                "HURT", font_size=16, color=ACCENT_RED, bold=True)

    add_rich_textbox(slide, Inches(6.8), Inches(1.15), Inches(3.0), Inches(1.2), [
        ("Circle Packing: -0.76%", True, ACCENT_RED),
        ("GPT-5.2 + Opus | 1 metric", False, DARK_GRAY),
        ("Single scalar — no tradeoffs to reason about", False, None),
    ], font_size=11)

    add_image_safe(slide, "experiments/ab_circle_gpt52_30iter_20260302_0927/plots/convergence_curves.png",
                   Inches(6.8), Inches(2.4), Inches(2.9), Inches(2.1))

    add_rich_textbox(slide, Inches(6.8), Inches(4.55), Inches(3.0), Inches(1.0), [
        ("Func Min: -0.76%", True, ACCENT_RED),
        ("Gemini Flash | 1 metric", False, DARK_GRAY),
        ("Weak model: inject rate only 30-37%", False, None),
        ("Can't follow structured hypothesis format", False, None),
    ], font_size=11)

    add_image_safe(slide, "experiments/ab_funcmin_gemini_30iter_20260227_1510/plots/convergence_curves.png",
                   Inches(6.8), Inches(5.4), Inches(2.2), Inches(1.6))


# ─── Slide 3: Convergence Deep-Dive ──────────────────────────────────────────

def slide3_convergence(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WARM_WHITE)

    add_textbox(slide, Inches(0.5), Inches(0.2), Inches(9), Inches(0.5),
                "V3: Convergence Analysis — How Treatment vs Control Evolve Over Time",
                font_size=24, color=DARK_BLUE, bold=True)

    # 5 plots in a grid: 3 on top, 2 on bottom
    plots = [
        ("experiments/ab_webscraper_gpt4o_30iter_20260302_1253/plots/convergence_curves.png",
         "Web Scraper (+12.4%)", ACCENT_GREEN, "Treatment leads from iter 5, gap widens"),
        ("experiments/ab_blis_30iter_20260227_1349/plots/convergence_curves.png",
         "BLIS Router (+4.6%)", ACCENT_GREEN, "Steady treatment advantage, low variance"),
        ("experiments/ab_rustsort_gpt52_30iter_20260302_1149/plots/convergence_curves.png",
         "Rust Sort (tie)", ACCENT_ORANGE, "Treatment faster to ceiling, control catches up"),
        ("experiments/ab_circle_gpt52_30iter_20260302_0927/plots/convergence_curves.png",
         "Circle Packing (-0.76%)", ACCENT_RED, "Control leads throughout"),
        ("experiments/ab_funcmin_gemini_30iter_20260227_1510/plots/convergence_curves.png",
         "Func Min (-0.76%)", ACCENT_RED, "Control slightly better, both near-optimal"),
    ]

    positions = [
        (Inches(0.2), Inches(0.85)),
        (Inches(3.4), Inches(0.85)),
        (Inches(6.6), Inches(0.85)),
        (Inches(1.0), Inches(3.55)),
        (Inches(5.5), Inches(3.55)),
    ]

    img_w, img_h = Inches(3.1), Inches(2.2)

    for i, (path, title, color, note) in enumerate(plots):
        x, y = positions[i]
        add_image_safe(slide, path, x, y, img_w, img_h)
        add_textbox(slide, x, y + img_h, img_w, Inches(0.25),
                    title, font_size=11, color=color, bold=True, alignment=PP_ALIGN.CENTER)
        add_textbox(slide, x, y + img_h + Inches(0.22), img_w, Inches(0.25),
                    note, font_size=9, color=DARK_GRAY, alignment=PP_ALIGN.CENTER)

    # Bottom insight
    add_textbox(slide, Inches(0.5), Inches(6.3), Inches(9), Inches(0.4),
                "Pattern: 4/5 experiments show treatment converging faster. On hard problems, the gap persists. On easy problems, control catches up.",
                font_size=12, color=DARK_BLUE, bold=True, alignment=PP_ALIGN.CENTER)


# ─── Slide 4: Model & Pipeline Analysis ──────────────────────────────────────

def slide4_model_analysis(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WARM_WHITE)

    add_textbox(slide, Inches(0.5), Inches(0.2), Inches(9), Inches(0.5),
                "V4: Model Strength & Hypothesis Pipeline Health",
                font_size=24, color=DARK_BLUE, bold=True)

    # Pipeline health table
    rows = [
        ["Model Tier", "Hypos/iter", "Persist", "Inject", "Inherit", "Hypo Benefit?"],
        ["Claude Opus/Sonnet", "3.2–4.2", "54–72%", "88–100%", "67–83%", "Yes (BLIS +4.6%)"],
        ["GPT-5.2 + Opus", "3.1–4.2", "54–63%", "97–100%", "70–79%", "Marginal (too easy)"],
        ["GPT-4o + Sonnet", "3.2–3.8", "72%", "47–53%", "76–83%", "Yes (Web +12.4%)"],
        ["Gemini Flash", "2.8–3.1", "45–52%", "30–37%", "48–55%", "No (broken pipeline)"],
    ]
    add_table(slide, Inches(0.3), Inches(0.8), Inches(9.2), Inches(1.7), rows)

    # 2x2 Matrix
    add_textbox(slide, Inches(0.3), Inches(2.7), Inches(4.5), Inches(0.35),
                "Problem Type × Model Strength Matrix", font_size=15, color=DARK_BLUE, bold=True)

    matrix_rows = [
        ["", "Single Metric", "Multi-Metric"],
        ["Strong (GPT-5.2)", "Circle Pack: CONTROL wins", "Rust Sort: TIE"],
        ["Mid (GPT-4o, Sonnet)", "—", "Web Scraper: TREATMENT +12%"],
        ["Mid-Strong (Opus+Sonnet)", "—", "BLIS Router: TREATMENT +5%"],
        ["Weak (Gemini Flash)", "Func Min: CONTROL wins", "—"],
    ]
    add_table(slide, Inches(0.3), Inches(3.1), Inches(5.5), Inches(2.0), matrix_rows)

    # Right side: insights
    add_rich_textbox(slide, Inches(6.0), Inches(2.7), Inches(3.8), Inches(3.5), [
        ("Key Findings:", True, DARK_BLUE),
        ("", False, None),
        ("Inject rate is the critical metric:", True, None),
        (">85%: Pipeline works well (Claude, GPT-5.2)", False, ACCENT_GREEN),
        ("47-53%: Still beneficial if problem has room (GPT-4o)", False, ACCENT_ORANGE),
        ("<40%: Pipeline too broken to help (Gemini Flash)", False, ACCENT_RED),
        ("", False, None),
        ("The Goldilocks Zone:", True, None),
        ("Mid-tier model + multi-metric + hard problem", False, ACCENT_GREEN),
        ("= maximum hypothesis benefit", False, ACCENT_GREEN),
        ("", False, None),
        ("Recommendation:", True, None),
        ("Monitor inject rate in first 5 iterations.", False, None),
        ("If <40%, disable hypotheses to avoid overhead.", False, None),
    ], font_size=11)

    # Bottom
    add_textbox(slide, Inches(0.3), Inches(5.4), Inches(9.2), Inches(0.6),
                "Hypotheses succeed in the multi-metric column — where there are genuine tradeoffs to reason about. "
                "Model strength matters less than feedback richness.",
                font_size=12, color=DARK_BLUE, bold=True, alignment=PP_ALIGN.CENTER)


# ─── Slide 5: Bugs Found + Practical Takeaways ───────────────────────────────

def slide5_practical(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, WARM_WHITE)

    add_textbox(slide, Inches(0.5), Inches(0.2), Inches(9), Inches(0.5),
                "V5: Bugs Found, Fixes & Practical Recommendations",
                font_size=24, color=DARK_BLUE, bold=True)

    # Bugs section
    add_textbox(slide, Inches(0.3), Inches(0.8), Inches(4.5), Inches(0.3),
                "Bugs Discovered During Experiments", font_size=15, color=ACCENT_RED, bold=True)

    add_rich_textbox(slide, Inches(0.3), Inches(1.15), Inches(4.5), Inches(2.5), [
        ("1. Comment syntax for non-Python languages", True, None),
        ("Template showed # (Python) but Rust needs //", False, DARK_GRAY),
        ("Caused ~2% compilation failures in Rust programs", False, DARK_GRAY),
        ("Fix: Language-aware template + ASCII-only rule", False, ACCENT_GREEN),
        ("", False, None),
        ("2. Fitness tracking used wrong metric name", True, None),
        ("Evaluator returned 'score' not 'combined_score'", False, DARK_GRAY),
        ("Fallback averaged ALL metrics including avg_time", False, DARK_GRAY),
        ("Lower avg_time = lower fitness (backwards!)", False, DARK_GRAY),
        ("Initial program appeared 'best' for 30 iterations", False, DARK_GRAY),
        ("Fix: Renamed to combined_score in evaluator", False, ACCENT_GREEN),
        ("", False, None),
        ("3. Convergence CSV overwritten by sequential runs", True, None),
        ("Each run_experiment.py call overwrote the CSV", False, DARK_GRAY),
        ("Fix: Rebuild CSVs from checkpoint data", False, ACCENT_GREEN),
    ], font_size=11)

    # Recommendations
    add_textbox(slide, Inches(5.2), Inches(0.8), Inches(4.5), Inches(0.3),
                "Practical Recommendations", font_size=15, color=DARK_BLUE, bold=True)

    add_rich_textbox(slide, Inches(5.2), Inches(1.15), Inches(4.5), Inches(2.5), [
        ("Enable hypotheses when:", True, ACCENT_GREEN),
        ("• Multi-metric problem with genuine tradeoffs", False, None),
        ("• Model inject rate > 40% (check in first 5 iters)", False, None),
        ("• Problem not solvable in < 5 iterations", False, None),
        ("", False, None),
        ("Skip hypotheses when:", True, ACCENT_RED),
        ("• Single scalar metric optimization", False, None),
        ("• Weak model (Gemini Flash, GPT-5-nano)", False, None),
        ("• Problem trivially easy for the chosen model", False, None),
        ("", False, None),
        ("Best model pairing:", True, MID_BLUE),
        ("• Primary: mid-tier (GPT-4o, Sonnet) — benefits most", False, None),
        ("• Secondary: strong (Opus) — provides diversity", False, None),
        ("• Avoid: frontier models on easy problems (waste)", False, None),
    ], font_size=11)

    # Summary box at bottom
    rows = [
        ["Experiment", "Result", "Key Takeaway"],
        ["Web Scraper", "+12.4%", "Multi-metric + mid-tier model = best combo"],
        ["BLIS Router", "+4.6%", "Hard problem + rich feedback = sustained advantage"],
        ["Rust Sort", "Tie", "Faster convergence but ceiling too low"],
        ["Circle Packing", "-0.76%", "Single metric — nothing to reason about"],
        ["Func Minimization", "-0.76%", "Weak model breaks hypothesis pipeline"],
    ]
    add_table(slide, Inches(0.3), Inches(4.0), Inches(9.2), Inches(2.1), rows)

    add_textbox(slide, Inches(0.3), Inches(6.3), Inches(9.2), Inches(0.4),
                "Bottom line: Hypothesis-driven evolution is not universally better — it shines on multi-metric problems with capable models.",
                font_size=13, color=DARK_BLUE, bold=True, alignment=PP_ALIGN.CENTER)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.0)

    slide1_executive(prs)
    slide2_by_outcome(prs)
    slide3_convergence(prs)
    slide4_model_analysis(prs)
    slide5_practical(prs)

    out_path = os.path.join(OUT_DIR, "hypothesis_ab_results.pptx")
    prs.save(out_path)
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
