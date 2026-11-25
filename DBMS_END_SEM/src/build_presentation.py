"""Build the 8-slide Executive Presentation for Mobile Game Analytics (Deliverables 1-4).

Generates dark-navy consulting-grade matplotlib charts and assembles an 8-slide
16:9 widescreen PowerPoint deck at:
    presentation/Mobile_Game_Analytics_Executive_Readout.pptx
All numbers are strictly sourced from the audited Deliverable 1-4 outputs.
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

# ---------------------------------------------------------------------------
# Paths & Theme Constants
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
CHART_DIR = ROOT / ".tmp" / "pres_charts"
CHART_DIR.mkdir(parents=True, exist_ok=True)
OUT_PPTX = ROOT / "presentation" / "Mobile_Game_Analytics_Executive_Readout.pptx"
OUT_PPTX.parent.mkdir(parents=True, exist_ok=True)

# Palette (McKinsey/BCG Dark Navy Tech Executive Theme)
BG_HEX = "#0B132B"
CARD_HEX = "#141F3D"
BORDER_HEX = "#24345C"
TEXT_HEX = "#F8FAFC"
MUTED_HEX = "#94A3B8"
CYAN_HEX = "#22D3EE"       # Organic / Highlight
BLUE_HEX = "#3B82F6"       # Paid Social / Primary Accent
VIOLET_HEX = "#A855F7"     # Paid Video
EMERALD_HEX = "#10B981"    # Positive / Improvement
CORAL_HEX = "#F43F5E"      # Negative / Risk / Wasted
AMBER_HEX = "#F59E0B"      # Caution / Assumption

C_BG = RGBColor(0x0B, 0x13, 0x2B)
C_CARD = RGBColor(0x14, 0x1F, 0x3D)
C_CARD_HI = RGBColor(0x18, 0x28, 0x4E)
C_BORDER = RGBColor(0x24, 0x34, 0x5C)
C_WHITE = RGBColor(0xF8, 0xFA, 0xFC)
C_SLATE = RGBColor(0xCB, 0xD5, 0xE1)
C_MUTED = RGBColor(0x94, 0xA3, 0xB8)
C_CYAN = RGBColor(0x22, 0xD3, 0xEE)
C_BLUE = RGBColor(0x3B, 0x82, 0xF6)
C_VIOLET = RGBColor(0xA8, 0x55, 0xF7)
C_EMERALD = RGBColor(0x10, 0xB9, 0x81)
C_CORAL = RGBColor(0xF4, 0x3F, 0x5E)
C_AMBER = RGBColor(0xF5, 0x9E, 0x0B)

FONT_NAME = "Segoe UI"

plt.rcParams.update({
    "figure.facecolor": CARD_HEX,
    "axes.facecolor": CARD_HEX,
    "axes.edgecolor": BORDER_HEX,
    "axes.labelcolor": TEXT_HEX,
    "xtick.color": "#CBD5E1",
    "ytick.color": "#CBD5E1",
    "text.color": TEXT_HEX,
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
    "grid.color": "#1E2D52",
    "grid.linestyle": "--",
    "grid.linewidth": 0.7,
})


# ---------------------------------------------------------------------------
# 1. Generate High-DPI Dark-Mode Charts
# ---------------------------------------------------------------------------
def make_charts() -> dict[str, Path]:
    paths: dict[str, Path] = {}

    # --- Slide 3A: Retention Funnel ---
    fig, ax = plt.subplots(figsize=(5.7, 3.35), dpi=300)
    days = ["Day 1", "Day 7", "Day 14", "Day 30"]
    vals = [47.68, 25.48, 19.50, 13.91]
    cols = [CYAN_HEX, BLUE_HEX, "#6366F1", VIOLET_HEX]
    bars = ax.bar(days, vals, width=0.52, color=cols, edgecolor="none", zorder=3)
    ax.grid(axis="y", zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_ylim(0, 58)
    ax.set_ylabel("Cohort Retained (%)", fontsize=10, fontweight="bold")
    ax.set_title("Mature Cohort Retention Funnel (Jan–Apr 2026)", fontsize=11.5, fontweight="bold", pad=12, color=TEXT_HEX)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.4, f"{v:.2f}%", ha="center", va="bottom",
                fontsize=10.5, fontweight="bold", color=TEXT_HEX)
    ax.annotate("Steep early drop:\n-22.2 pp by Day 7", xy=(1, 25.48), xytext=(1.75, 41),
                arrowprops=dict(arrowstyle="->", color=CYAN_HEX, lw=1.3),
                fontsize=9, fontweight="bold", color=CYAN_HEX,
                bbox=dict(boxstyle="round,pad=0.35", fc="#0B132B", ec=CYAN_HEX, lw=0.9))
    fig.tight_layout()
    p = CHART_DIR / "s3_retention.png"
    fig.savefig(p, dpi=300, facecolor=CARD_HEX)
    plt.close(fig)
    paths["s3_retention"] = p

    # --- Slide 3B: Platform DAU vs Net Revenue + Payer Concentration ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(5.8, 3.35), dpi=300, gridspec_kw={"width_ratios": [1.05, 1]})
    plats = ["Android", "iOS"]
    dau = [3821.5, 1740.5]
    bars1 = ax1.bar(plats, dau, width=0.48, color=[BLUE_HEX, CYAN_HEX], zorder=3)
    ax1.grid(axis="y", zorder=0)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.set_ylim(0, 4700)
    ax1.set_ylabel("Average DAU", fontsize=9.5, fontweight="bold")
    ax1.set_title("Avg DAU by Platform", fontsize=10.5, fontweight="bold", pad=10)
    for b, v in zip(bars1, dau):
        ax1.text(b.get_x() + b.get_width() / 2, v + 110, f"{v:,.1f}", ha="center", fontsize=10, fontweight="bold")

    # Right subplot: Gross Revenue Concentration among Paying Players (n=11,054)
    tiers = ["Top 1%\nPayers", "Top 10%\nPayers", "Top 50%\nPayers"]
    shares = [9.39, 47.79, 89.96]
    bars2 = ax2.bar(tiers, shares, width=0.5, color=[AMBER_HEX, CYAN_HEX, BLUE_HEX], zorder=3)
    ax2.grid(axis="y", zorder=0)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.set_ylim(0, 108)
    ax2.set_ylabel("Share of Gross Revenue (%)", fontsize=9.5, fontweight="bold")
    ax2.set_title("Revenue Concentration\n(Among 13.77% Who Pay)", fontsize=10, fontweight="bold", pad=8)
    for b, v in zip(bars2, shares):
        ax2.text(b.get_x() + b.get_width() / 2, v + 2.2, f"{v:.2f}%", ha="center", fontsize=9.5, fontweight="bold")
    fig.tight_layout(w_pad=2.0)
    p = CHART_DIR / "s3_plat_conc.png"
    fig.savefig(p, dpi=300, facecolor=CARD_HEX)
    plt.close(fig)
    paths["s3_plat_conc"] = p

    # --- Slide 4A: Tier ARPDAU Change vs Tier 4 Mix Shift ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.2, 3.35), dpi=300, gridspec_kw={"width_ratios": [1.35, 1]})
    t_lbls = ["Tier 1", "Tier 2", "Tier 3", "Tier 4", "Blended\nOverall"]
    pct_chg = [7.03, 8.50, 13.50, 1.97, -16.32]
    b_cols = [EMERALD_HEX, EMERALD_HEX, EMERALD_HEX, EMERALD_HEX, CORAL_HEX]
    bars = ax1.bar(t_lbls, pct_chg, width=0.52, color=b_cols, zorder=3)
    ax1.axhline(0, color="#CBD5E1", lw=1.0, zorder=2)
    ax1.grid(axis="y", zorder=0)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.set_ylim(-23, 19)
    ax1.set_ylabel("Gross ARPDAU Change (%)", fontsize=9.5, fontweight="bold")
    ax1.set_title("Jan vs. Apr ARPDAU % Change", fontsize=10.5, fontweight="bold", pad=10)
    ax1.tick_params(axis="x", labelsize=8.5)
    for b, v in zip(bars, pct_chg):
        y_pos = v + 0.8 if v >= 0 else v - 2.3
        ax1.text(b.get_x() + b.get_width() / 2, y_pos, f"{v:+.2f}%", ha="center", fontsize=8.5, fontweight="bold",
                 color=EMERALD_HEX if v >= 0 else CORAL_HEX)

    # Right: Tier 4 Share of Player-Days
    periods = ["Jan 1–30\n(82,381)", "Apr 1–30\n(282,781)"]
    t4_share = [17.65, 45.99]
    other_share = [82.35, 54.01]
    ax2.bar(periods, t4_share, width=0.5, color=VIOLET_HEX, label="Tier 4", zorder=3)
    ax2.bar(periods, other_share, bottom=t4_share, width=0.5, color="#2D3E6B", label="Tiers 1–3", zorder=3)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.set_ylim(0, 114)
    ax2.set_ylabel("Share of Active Player-Days (%)", fontsize=9, fontweight="bold")
    ax2.set_title("Tier 4 Mix Surge", fontsize=10.5, fontweight="bold", pad=10)
    ax2.tick_params(axis="x", labelsize=8.5)
    for i, v in enumerate(t4_share):
        ax2.text(i, v / 2, f"{v:.2f}%", ha="center", va="center", fontsize=10, fontweight="bold", color=TEXT_HEX)
    ax2.legend(loc="upper center", frameon=False, ncol=2, fontsize=8)
    fig.tight_layout(w_pad=1.6)
    p = CHART_DIR / "s4_tiers_mix.png"
    fig.savefig(p, dpi=300, facecolor=CARD_HEX)
    plt.close(fig)
    paths["s4_tiers_mix"] = p

    # --- Slide 4B: Kitagawa Decomposition Waterfall ---
    fig, ax = plt.subplots(figsize=(5.3, 3.35), dpi=300)
    steps = ["Jan 1–30\nARPDAU", "Within-Tier\nEffect", "Player-Mix\nShift", "Apr 1–30\nARPDAU"]
    bottoms = [0.0, 0.3567, 0.2985, 0.0]
    heights = [0.3567, 0.0240, 0.0822, 0.2985]
    w_cols = [BLUE_HEX, EMERALD_HEX, CORAL_HEX, CYAN_HEX]
    bars = ax.bar(steps, heights, bottom=bottoms, width=0.52, color=w_cols, zorder=3)
    ax.grid(axis="y", zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_ylim(0, 0.44)
    ax.set_ylabel("Weighted Gross ARPDAU ($)", fontsize=9.5, fontweight="bold")
    ax.set_title("Mathematical Decomposition (-$0.0582 Total)", fontsize=10.5, fontweight="bold", pad=10)
    ax.tick_params(axis="x", labelsize=8.8)
    labels = ["$0.3567", "+$0.0240", "-$0.0822", "$0.2985"]
    y_lbls = [0.3567 + 0.01, 0.3567 + 0.0240 + 0.01, 0.3807 + 0.01, 0.2985 + 0.01]
    lbl_cols = [TEXT_HEX, EMERALD_HEX, CORAL_HEX, CYAN_HEX]
    for x_i, (lbl, y_l, lc) in enumerate(zip(labels, y_lbls, lbl_cols)):
        ax.text(x_i, y_l, lbl, ha="center", va="bottom", fontsize=10, fontweight="bold", color=lc)
    # Connector dashed lines
    ax.plot([0.26, 0.74], [0.3567, 0.3567], color=MUTED_HEX, ls=":", lw=1.0)
    ax.plot([1.26, 1.74], [0.3807, 0.3807], color=MUTED_HEX, ls=":", lw=1.0)
    ax.plot([2.26, 2.74], [0.2985, 0.2985], color=MUTED_HEX, ls=":", lw=1.0)
    fig.tight_layout()
    p = CHART_DIR / "s4_waterfall.png"
    fig.savefig(p, dpi=300, facecolor=CARD_HEX)
    plt.close(fig)
    paths["s4_waterfall"] = p

    # --- Slide 5: Raw vs Adjusted 30-Day Gross ARPU (Confounding Illustration) ---
    fig, ax = plt.subplots(figsize=(5.7, 3.65), dpi=300)
    channels = ["Organic", "Paid Social", "Paid Video"]
    raw_arpu = [2.50, 2.25, 1.55]
    adj_arpu = [2.17, 1.99, 2.06]
    ch_cols = [CYAN_HEX, BLUE_HEX, VIOLET_HEX]
    x = np.arange(len(channels))
    w = 0.34
    b1 = ax.bar(x - w / 2, raw_arpu, width=w, color=["#164E63", "#1E3A8A", "#4C1D95"],
                edgecolor=ch_cols, linewidth=1.4, label="Raw (Unadjusted)", zorder=3)
    b2 = ax.bar(x + w / 2, adj_arpu, width=w, color=ch_cols, label="Tier × Platform Adjusted", zorder=3)
    ax.grid(axis="y", zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xticks(x)
    ax.set_xticklabels(channels, fontsize=10, fontweight="bold")
    ax.set_ylim(0, 3.35)
    ax.set_ylabel("30-Day Gross ARPU ($)", fontsize=9.5, fontweight="bold")
    ax.set_title("Raw vs. Adjusted 30-Day Gross ARPU (Jan–Mar, n=37,489)", fontsize=10.2, fontweight="bold", pad=22)
    for b, v in zip(b1, raw_arpu):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.06, f"${v:.2f}", ha="center", fontsize=9, color="#CBD5E1", fontweight="bold")
    for b, v in zip(b2, adj_arpu):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.06, f"${v:.2f}", ha="center", fontsize=9.5, color=TEXT_HEX, fontweight="bold")
    ax.annotate("Paid Video jumps +33%\nafter removing Tier 4 &\nAndroid mix bias",
                xy=(2 + w / 2, 2.15), xytext=(1.22, 2.66),
                arrowprops=dict(arrowstyle="->", color=VIOLET_HEX, lw=1.3),
                fontsize=8.3, fontweight="bold", color="#E9D5FF",
                bbox=dict(boxstyle="round,pad=0.35", fc="#0B132B", ec=VIOLET_HEX, lw=0.9))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.09), frameon=False, ncol=2, fontsize=8.5)
    fig.tight_layout()
    p = CHART_DIR / "s5_channel_arpu.png"
    fig.savefig(p, dpi=300, facecolor=CARD_HEX)
    plt.close(fig)
    paths["s5_channel_arpu"] = p

    # --- Slide 6: Model Comparison (ROC-AUC & PR-AUC) ---
    fig, ax = plt.subplots(figsize=(6.1, 3.85), dpi=300)
    models = [
        "Prior Dummy",
        "Recency Only",
        "Decision Tree (d=5)",
        "LogReg (Balanced)",
        "LogReg (C=1.0) [Selected]",
        "HistGradientBoost",
    ]
    roc = [0.5000, 0.5680, 0.7330, 0.7468, 0.7467, 0.7580]
    pr = [0.1873, 0.2180, 0.3711, 0.3810, 0.3830, 0.4121]
    y = np.arange(len(models))
    h = 0.36
    b_roc = ax.barh(y + h / 2, roc, height=h, color=[MUTED_HEX, MUTED_HEX, "#6366F1", BLUE_HEX, CYAN_HEX, VIOLET_HEX],
                    label="ROC-AUC", zorder=3)
    b_pr = ax.barh(y - h / 2, pr, height=h, color=["#334155", "#334155", "#312E81", "#1D4ED8", "#0891B2", "#6D28D9"],
                   label="PR-AUC (Prevalence = 0.1873)", zorder=3)
    ax.grid(axis="x", zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_yticks(y)
    ax.set_yticklabels(models, fontsize=8.8, fontweight="bold")
    ax.set_xlim(0, 0.92)
    ax.set_xlabel("Test Score (n = 38,644; 7,238 Churners)", fontsize=9.5, fontweight="bold")
    ax.set_title("Out-of-Time Test Performance: Ranking & Precision-Recall", fontsize=10.3, fontweight="bold", pad=22)
    for b, v in zip(b_roc, roc):
        ax.text(v + 0.012, b.get_y() + b.get_height() / 2, f"{v:.4f}", va="center", fontsize=8.3, fontweight="bold", color=TEXT_HEX)
    for b, v in zip(b_pr, pr):
        ax.text(v + 0.012, b.get_y() + b.get_height() / 2, f"{v:.4f}", va="center", fontsize=8.3, color="#CBD5E1")
    ax.legend(loc="upper center", bbox_to_anchor=(0.48, 1.09), frameon=False, ncol=2, fontsize=8.3)
    fig.tight_layout()
    p = CHART_DIR / "s6_models.png"
    fig.savefig(p, dpi=300, facecolor=CARD_HEX)
    plt.close(fig)
    paths["s6_models"] = p

    # --- Slide 7: Targeting Trade-offs (Precision, Recall, Wasted Offers) ---
    fig, ax = plt.subplots(figsize=(6.35, 3.85), dpi=300)
    tiers = ["Top 5%\n(1,933)", "Top 10%\n(3,865)", "Top 20% (Rec.)\n(7,729)", "Top 30%\n(11,593)", "Everyone\n(38,644)"]
    prec = [48.16, 44.89, 39.73, 36.28, 18.73]
    rec = [12.86, 23.97, 42.43, 58.11, 100.00]
    wasted = [51.84, 55.11, 60.27, 63.72, 81.27]
    x = np.arange(len(tiers))
    w = 0.265
    b1 = ax.bar(x - w, prec, width=w, color=EMERALD_HEX, label="Precision % (True Churners)", zorder=3)
    b2 = ax.bar(x, rec, width=w, color=CYAN_HEX, label="Recall % (Churners Caught)", zorder=3)
    b3 = ax.bar(x + w, wasted, width=w, color=CORAL_HEX, label="Wasted Offers % (Non-Churners)", zorder=3)
    # Highlight Top 20% column band
    ax.axvspan(2 - 0.44, 2 + 0.44, color=BLUE_HEX, alpha=0.14, zorder=1)
    ax.grid(axis="y", zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xticks(x)
    ax.set_xticklabels(tiers, fontsize=8.5, fontweight="bold")
    ax.set_ylim(0, 116)
    ax.set_ylabel("Percentage (%)", fontsize=9.5, fontweight="bold")
    ax.set_title("Targeting Trade-Offs Across Risk Tiers (Test n = 38,644)", fontsize=10.5, fontweight="bold", pad=10)
    for bars, col, dy in [(b1, EMERALD_HEX, 1.4), (b2, CYAN_HEX, 2.2), (b3, CORAL_HEX, 1.4)]:
        for idx_b, b in enumerate(bars):
            v = b.get_height()
            extra = 3.2 if (idx_b == 2 and col == CYAN_HEX) else dy
            ax.text(b.get_x() + b.get_width() / 2, v + extra, f"{v:.1f}%", ha="center", fontsize=6.9, fontweight="bold", color=col)
    ax.legend(loc="upper left", frameon=True, facecolor="#0B132B", edgecolor=BORDER_HEX, fontsize=8)
    fig.tight_layout()
    p = CHART_DIR / "s7_targeting.png"
    fig.savefig(p, dpi=300, facecolor=CARD_HEX)
    plt.close(fig)
    paths["s7_targeting"] = p

    return paths


# ---------------------------------------------------------------------------
# 2. PowerPoint Builder Helpers
# ---------------------------------------------------------------------------
def set_slide_bg(slide, color=C_BG):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_rect(slide, left, top, width, height, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.0, rounded=False):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    shp = slide.shapes.add_shape(shape_type, Inches(left), Inches(top), Inches(width), Inches(height))
    if rounded:
        shp.adjustments[0] = 0.04
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill_color
    if line_color is not None:
        shp.line.color.rgb = line_color
        shp.line.width = Pt(line_pt)
    else:
        shp.line.fill.background()
    return shp


def add_textbox(slide, left, top, width, height, text="", font_size=12, bold=False, color=C_WHITE,
                align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP, line_spacing=1.15):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = valign
    tf.margin_left = Inches(0.04)
    tf.margin_right = Inches(0.04)
    tf.margin_top = Inches(0.02)
    tf.margin_bottom = Inches(0.02)
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = line_spacing
    run = p.add_run()
    run.text = text
    run.font.name = FONT_NAME
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = color
    return tb


def add_rich_bullets(slide, left, top, width, height, items, font_size=11.5, space_after=6):
    """items: list of list-of-(text, bold, color) tuples per paragraph."""
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.04)
    tf.margin_right = Inches(0.04)
    tf.margin_top = Inches(0.02)
    tf.margin_bottom = Inches(0.02)
    for idx, spans in enumerate(items):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.space_after = Pt(space_after)
        p.line_spacing = 1.15
        for txt, bld, col in spans:
            r = p.add_run()
            r.text = txt
            r.font.name = FONT_NAME
            r.font.size = Pt(font_size)
            r.font.bold = bld
            r.font.color.rgb = col
    return tb


def add_header(slide, kicker: str, title: str, takeaway: str, slide_num: int):
    # Top accent bar
    add_rect(slide, 0.0, 0.0, 13.333, 0.06, fill_color=C_CYAN, line_color=None)
    add_textbox(slide, 0.55, 0.22, 9.0, 0.28, kicker.upper(), font_size=10, bold=True, color=C_CYAN)
    add_textbox(slide, 0.55, 0.45, 11.8, 0.45, title, font_size=22, bold=True, color=C_WHITE)
    add_textbox(slide, 0.55, 0.90, 12.2, 0.36, takeaway, font_size=11.5, bold=False, color=C_SLATE)
    add_rect(slide, 0.55, 1.30, 12.23, 0.015, fill_color=C_BORDER, line_color=None)
    # Slide number pill top-right
    add_textbox(slide, 12.1, 0.22, 0.7, 0.28, f"{slide_num} / 8", font_size=10, bold=True, color=C_MUTED, align=PP_ALIGN.RIGHT)


def add_footer(slide, text: str):
    add_rect(slide, 0.55, 7.06, 12.23, 0.012, fill_color=C_BORDER, line_color=None)
    add_textbox(slide, 0.55, 7.11, 12.23, 0.28, text, font_size=8.8, color=C_MUTED)


def add_kpi_card(slide, left, top, width, height, value: str, label: str, sub: str = "", accent=C_CYAN):
    add_rect(slide, left, top, width, height, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.0, rounded=True)
    add_rect(slide, left, top, width, 0.055, fill_color=accent, line_color=None)
    add_textbox(slide, left + 0.14, top + 0.12, width - 0.28, 0.42, value, font_size=22, bold=True, color=accent)
    add_textbox(slide, left + 0.14, top + 0.53, width - 0.28, 0.28, label, font_size=10.5, bold=True, color=C_WHITE)
    if sub:
        add_textbox(slide, left + 0.14, top + 0.78, width - 0.28, 0.32, sub, font_size=8.8, color=C_MUTED)


def style_table(tbl, headers, rows, col_widths, font_size=10, highlight_row=None, col_colors=None):
    for j, w in enumerate(col_widths):
        tbl.columns[j].width = Inches(w)
    # Header
    for j, h in enumerate(headers):
        cell = tbl.cell(0, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = RGBColor(0x1B, 0x2B, 0x54)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.RIGHT
        r = p.add_run()
        r.text = h
        r.font.name = FONT_NAME
        r.font.size = Pt(font_size)
        r.font.bold = True
        r.font.color.rgb = C_CYAN
    # Body
    for i, row in enumerate(rows):
        is_hi = (highlight_row is not None and i == highlight_row)
        bg_c = RGBColor(0x1E, 0x35, 0x66) if is_hi else (C_CARD if i % 2 == 0 else RGBColor(0x10, 0x1A, 0x34))
        for j, val in enumerate(row):
            cell = tbl.cell(i + 1, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg_c
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.RIGHT
            r = p.add_run()
            r.text = val
            r.font.name = FONT_NAME
            r.font.size = Pt(font_size)
            r.font.bold = is_hi or (j == 0)
            if col_colors and j in col_colors:
                r.font.color.rgb = col_colors[j]
            else:
                r.font.color.rgb = C_WHITE if is_hi or j == 0 else C_SLATE


# ---------------------------------------------------------------------------
# 3. Build 8 Slides
# ---------------------------------------------------------------------------
def build_deck():
    charts = make_charts()
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # =======================================================================
    # SLIDE 1 — Executive Opening
    # =======================================================================
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s1)
    add_rect(s1, 0.0, 0.0, 13.333, 0.08, fill_color=C_CYAN, line_color=None)
    add_rect(s1, 0.0, 0.08, 0.12, 7.42, fill_color=C_BLUE, line_color=None)

    # Left Hero Content
    add_textbox(s1, 0.75, 0.72, 7.2, 0.35, "EXECUTIVE ANALYTICS READOUT  |  QUARTERLY PLANNING BRIEF",
                font_size=11, bold=True, color=C_CYAN)
    add_textbox(s1, 0.75, 1.18, 7.4, 1.55,
                "Mobile Game Analytics:\nFrom Player Behaviour to\nPredictive Intelligence",
                font_size=34, bold=True, color=C_WHITE, line_spacing=1.10)
    add_textbox(s1, 0.75, 2.98, 7.3, 0.75,
                "A Data-Driven Investigation of Engagement, Monetisation, Acquisition Channels, and Player Churn.",
                font_size=14.5, color=C_SLATE, line_spacing=1.25)

    # Central Business Question Box
    add_rect(s1, 0.75, 3.95, 7.3, 1.25, fill_color=C_CARD_HI, line_color=C_BLUE, line_pt=1.5, rounded=True)
    add_rect(s1, 0.75, 3.95, 0.08, 1.25, fill_color=C_CYAN, line_color=None)
    add_textbox(s1, 1.0, 4.07, 6.9, 0.28, "CENTRAL BUSINESS QUESTION", font_size=10, bold=True, color=C_CYAN)
    add_textbox(s1, 1.0, 4.38, 6.85, 0.72,
                "How can the studio grow revenue without increasing marketing spend — by separating true monetisation health from player-mix illusions and targeting churn risk efficiently?",
                font_size=12, bold=True, color=C_WHITE, line_spacing=1.22)

    # Bottom Metadata Strip
    add_textbox(s1, 0.75, 5.55, 7.3, 0.3, "AUDIENCE", font_size=9.5, bold=True, color=C_MUTED)
    add_textbox(s1, 0.75, 5.82, 7.3, 0.35, "Product Director, Head of Product, Growth Team, and Business Leadership",
                font_size=11.5, bold=True, color=C_SLATE)
    add_textbox(s1, 0.75, 6.28, 7.3, 0.3,
                "Telemetry Scope: 80,295 Players  •  667,435 Active Player-Days  •  Jan 1 – Apr 30, 2026 (120 Days)",
                font_size=10.5, color=C_CYAN, bold=True)

    # Right Analytical Journey Visual Stack
    add_rect(s1, 8.45, 0.72, 4.35, 6.0, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.2, rounded=True)
    add_textbox(s1, 8.75, 0.96, 3.8, 0.32, "FOUR AUDITED DELIVERABLES", font_size=10.5, bold=True, color=C_CYAN)
    journey = [
        ("01", "Player Behaviour & Funnel", "667,435 player-days, $216,159.30 net revenue, 13.91% D30 retention", C_CYAN),
        ("02", "The ARPDAU Paradox", "ARPDAU -16.32% vs. Revenue +187.25% explained by Tier 4 mix shift", C_EMERALD),
        ("03", "Channel Effectiveness", "Confounding removed: Paid Social & Paid Video converge on LTV", C_BLUE),
        ("04", "Churn Prediction & Targeting", "Logistic Regression (AUC 0.7467) → Top 20% A/B test strategy", C_VIOLET),
    ]
    for idx, (num, j_t, j_d, acc) in enumerate(journey):
        y0 = 1.48 + idx * 1.26
        add_rect(s1, 8.72, y0, 3.82, 1.06, fill_color=C_BG, line_color=C_BORDER, line_pt=1.0, rounded=True)
        add_rect(s1, 8.72, y0, 0.08, 1.06, fill_color=acc, line_color=None)
        add_textbox(s1, 8.92, y0 + 0.12, 0.5, 0.35, num, font_size=16, bold=True, color=acc)
        add_textbox(s1, 9.42, y0 + 0.12, 3.0, 0.30, j_t, font_size=12, bold=True, color=C_WHITE)
        add_textbox(s1, 9.42, y0 + 0.44, 3.0, 0.55, j_d, font_size=9.8, color=C_SLATE, line_spacing=1.18)

    add_footer(s1, "Source: Production player telemetry (SQL / DuckDB & Python) — all 4 deliverables independently audited against raw CSVs.")

    # =======================================================================
    # SLIDE 2 — Executive Summary
    # =======================================================================
    s2 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s2)
    add_header(s2, "Executive Summary", "Four Critical Discoveries Across the Player Lifecycle",
               "Separating player-mix illusions from real behaviour reveals healthy monetisation, channel parity, and actionable churn targeting.", 2)

    cards = [
        ("01", "DELIVERABLE 1  •  BEHAVIOUR", "Revenue Is Highly Concentrated", C_CYAN,
         "47.79%", "of gross revenue from Top 10% of payers",
         [
             [("• ", True, C_CYAN), ("86.23%", True, C_WHITE), (" of 80,295 players never purchase.", False, C_SLATE)],
             [("• ", True, C_CYAN), ("Retention drops from ", False, C_SLATE), ("47.68%", True, C_WHITE), (" (D1) to ", False, C_SLATE), ("13.91%", True, C_WHITE), (" (D30).", False, C_SLATE)],
             [("• ", True, C_CYAN), ("Ad cap-hit rate is only ", False, C_SLATE), ("0.9604%", True, C_WHITE), (".", False, C_SLATE)],
         ]),
        ("02", "DELIVERABLE 2  •  MONETISATION", "Blended ARPDAU Misleads Leadership", C_EMERALD,
         "-16.32%", "gross ARPDAU despite +187.25% revenue",
         [
             [("• ", True, C_EMERALD), ("All 4 country tiers ", False, C_SLATE), ("improved", True, C_EMERALD), (" ARPDAU (+$0.0240 effect).", False, C_SLATE)],
             [("• ", True, C_EMERALD), ("Tier 4 share surged ", False, C_SLATE), ("17.65% → 45.99%", True, C_WHITE), (" (-$0.0822 mix).", False, C_SLATE)],
             [("• ", True, C_EMERALD), ("Classic ", False, C_SLATE), ("Simpson's Paradox", True, C_WHITE), (" — stratify reporting.", False, C_SLATE)],
         ]),
        ("03", "DELIVERABLE 3  •  ACQUISITION", "Paid Channels Are Statistically Tied", C_BLUE,
         "$2.06 vs $1.99", "adjusted 30d Gross ARPU (Video vs Social)",
         [
             [("• ", True, C_BLUE), ("Paid Video's low raw ARPU ($1.55) is a ", False, C_SLATE), ("Tier 4/Android bias", True, C_WHITE), (".", False, C_SLATE)],
             [("• ", True, C_BLUE), ("Organic has small engagement edge (", False, C_SLATE), ("7.079", True, C_WHITE), (" active days).", False, C_SLATE)],
             [("• ", True, C_BLUE), ("Hold budget shifts until ", False, C_SLATE), ("CPI + ad LTV", True, C_AMBER), (" are added.", False, C_SLATE)],
         ]),
        ("04", "DELIVERABLE 4  •  CHURN", "Model Doubles Targeting Precision", C_VIOLET,
         "39.73%", "precision at Top 20% (vs. 18.73% random)",
         [
             [("• ", True, C_VIOLET), ("Logistic Regression (", False, C_SLATE), ("ROC-AUC 0.7467", True, C_WHITE), (", PR 0.3830).", False, C_SLATE)],
             [("• ", True, C_VIOLET), ("Top 20% catches ", False, C_SLATE), ("3,071 / 7,238", True, C_WHITE), (" churners (42.43% recall).", False, C_SLATE)],
             [("• ", True, C_VIOLET), ("Run ", False, C_SLATE), ("A/B holdout", True, C_AMBER), (" before scaling — model scores risk, not lift.", False, C_SLATE)],
         ]),
    ]

    for idx, (num, tag, h_t, acc, big_v, big_sub, buls) in enumerate(cards):
        x0 = 0.55 + idx * 3.10
        add_rect(s2, x0, 1.48, 2.95, 4.25, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.0, rounded=True)
        add_rect(s2, x0, 1.48, 2.95, 0.06, fill_color=acc, line_color=None)
        add_textbox(s2, x0 + 0.16, 1.62, 2.6, 0.25, tag, font_size=8.8, bold=True, color=acc)
        add_textbox(s2, x0 + 0.16, 1.87, 2.65, 0.50, h_t, font_size=13.5, bold=True, color=C_WHITE, line_spacing=1.12)
        add_rect(s2, x0 + 0.16, 2.45, 2.63, 0.92, fill_color=C_BG, line_color=C_BORDER, line_pt=0.8, rounded=True)
        add_textbox(s2, x0 + 0.26, 2.52, 2.43, 0.44, big_v, font_size=21, bold=True, color=acc)
        add_textbox(s2, x0 + 0.26, 2.97, 2.43, 0.34, big_sub, font_size=8.8, color=C_SLATE)
        add_rich_bullets(s2, x0 + 0.14, 3.52, 2.68, 2.1, buls, font_size=10.3, space_after=8)

    # Bottom Analytical Journey Strip
    add_rect(s2, 0.55, 5.92, 12.23, 0.96, fill_color=C_CARD_HI, line_color=C_BLUE, line_pt=1.2, rounded=True)
    add_textbox(s2, 0.78, 6.03, 2.2, 0.28, "STRATEGIC SYNTHESIS", font_size=10, bold=True, color=C_CYAN)
    add_textbox(s2, 0.78, 6.30, 11.75, 0.50,
                "Core game monetisation is healthy (+187% gross revenue), Paid Video is NOT broken once adjusted for Tier 4 mix, and targeted Top-20% retention offers provide a disciplined lever — provided leadership fixes blended metrics and validates causal ROI via controlled experiments.",
                font_size=11, bold=False, color=C_WHITE, line_spacing=1.2)

    add_footer(s2, "Note: All figures cover Jan 1–Apr 30, 2026 unless noted (Deliverable 3 cohort: Jan 1–Mar 31, n=37,489; Deliverable 4 Test: Apr 16, n=38,644).")

    # =======================================================================
    # SLIDE 3 — Understanding Players and Revenue (Deliverable 1)
    # =======================================================================
    s3 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s3)
    add_header(s3, "Deliverable 1  •  Player Behaviour & Monetisation",
               "Understanding Players, Retention, and Revenue Concentration",
               "Most players never spend real money (86.23%), making early retention and top-payer stewardship critical to total revenue.", 3)

    add_kpi_card(s3, 0.55, 1.46, 2.92, 1.15, "667,435", "Active Player-Days (120d)", "Android 3,821.5  |  iOS 1,740.5 avg DAU", C_CYAN)
    add_kpi_card(s3, 3.65, 1.46, 2.92, 1.15, "$216,159.30", "Net Raw Revenue", "Gross $219,434.02  |  Refunds -$3,274.72", C_EMERALD)
    add_kpi_card(s3, 6.75, 1.46, 2.92, 1.15, "86.23%", "Players Never Purchased", "69,241 of 80,295 accounts spent $0", C_AMBER)
    add_kpi_card(s3, 9.85, 1.46, 2.93, 1.15, "0.9604%", "Rewarded-Ad Cap-Hit Rate", "Rarely constrained across 647,623 ad events", C_BLUE)

    # Left Chart: Retention Funnel
    add_rect(s3, 0.55, 2.78, 5.95, 3.55, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.0, rounded=True)
    s3.shapes.add_picture(str(charts["s3_retention"]), Inches(0.65), Inches(2.86), width=Inches(5.75))

    # Right Chart: Platform DAU & Revenue Concentration
    add_rect(s3, 6.68, 2.78, 6.10, 3.55, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.0, rounded=True)
    s3.shapes.add_picture(str(charts["s3_plat_conc"]), Inches(6.78), Inches(2.86), width=Inches(5.90))

    # Bottom Takeaway Strip
    add_rect(s3, 0.55, 6.45, 12.23, 0.50, fill_color=C_CARD_HI, line_color=C_CYAN, line_pt=1.0, rounded=True)
    add_textbox(s3, 0.75, 6.55, 11.8, 0.30,
                "Key Insight: Because 13.77% of players carry 100% of IAP revenue (and Top 10% of payers drive 47.79%), engagement, retention, and monetisation must be tracked separately.",
                font_size=10.8, bold=True, color=C_WHITE)

    add_footer(s3, "Source: sql/task_1a..1d. Retention excludes right-censored cohorts per milestone. Payer concentration ranked among 11,054 paying device_ids.")

    # =======================================================================
    # SLIDE 4 — The ARPDAU Paradox (Deliverable 2)
    # =======================================================================
    s4 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s4)
    add_header(s4, "Deliverable 2  •  ARPDAU Deep Dive (Jan 1–30 vs. Apr 1–30, 2026)",
               "The ARPDAU Paradox: Revenue Nearly Tripled While ARPDAU Fell 16.32%",
               "Every country tier improved monetisation; blended ARPDAU dropped solely because Tier 4's activity share more than doubled (Simpson's Paradox).", 4)

    add_kpi_card(s4, 0.55, 1.46, 2.92, 1.12, "+243.26%", "Active Player-Days Growth", "82,381 (Jan) → 282,781 (Apr)", C_CYAN)
    add_kpi_card(s4, 3.65, 1.46, 2.92, 1.12, "+187.25%", "Gross Revenue Growth", "$29,383.67 → $84,404.41 (Net +186.67%)", C_EMERALD)
    add_kpi_card(s4, 6.75, 1.46, 2.92, 1.12, "-16.32%", "Weighted Gross ARPDAU", "$0.3567 → $0.2985 (Net -$0.0579 / -16.49%)", C_CORAL)
    add_kpi_card(s4, 9.85, 1.46, 2.93, 1.12, "17.65% → 45.99%", "Tier 4 Player-Day Share", "Driven primarily by Paid Video scaling", C_VIOLET)

    # Charts
    add_rect(s4, 0.55, 2.74, 6.45, 3.58, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.0, rounded=True)
    s4.shapes.add_picture(str(charts["s4_tiers_mix"]), Inches(0.65), Inches(2.82), width=Inches(6.25))

    add_rect(s4, 7.18, 2.74, 5.60, 3.58, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.0, rounded=True)
    s4.shapes.add_picture(str(charts["s4_waterfall"]), Inches(7.28), Inches(2.82), width=Inches(5.40))

    # Bottom Recommendation Banner
    add_rect(s4, 0.55, 6.44, 12.23, 0.52, fill_color=C_CARD_HI, line_color=C_EMERALD, line_pt=1.0, rounded=True)
    add_textbox(s4, 0.75, 6.55, 11.8, 0.30,
                "Decision: Nothing broke in monetisation (+$0.0240 within-tier gain vs. -$0.0822 mix shift). Replace blended ARPDAU with tier-stratified ARPDAU reporting.",
                font_size=10.8, bold=True, color=C_WHITE)

    add_footer(s4, "Source: sql/task_2_arpdau_deep_dive.sql. Symmetric Kitagawa decomposition: Within-Tier (+$0.0240) + Mix Shift (-$0.0822) = -$0.0582 exact.")

    # =======================================================================
    # SLIDE 5 — Acquisition Channel Effectiveness (Deliverable 3)
    # =======================================================================
    s5 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s5)
    add_header(s5, "Deliverable 3  •  Acquisition Channel Comparison (Jan 1–Mar 31 Clean Cohort, n = 37,489)",
               "Channel Quality Converges After Controlling for Tier & Platform",
               "Paid Video's raw revenue deficit is a Tier 4/Android composition artefact; adjusted Paid Social and Paid Video performance is statistically indistinguishable.", 5)

    # Left: Chart Raw vs Adjusted ARPU
    add_rect(s5, 0.55, 1.46, 5.95, 3.85, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.0, rounded=True)
    s5.shapes.add_picture(str(charts["s5_channel_arpu"]), Inches(0.65), Inches(1.56), width=Inches(5.75))

    # Right Top: Adjusted Channel Metrics Table
    add_rect(s5, 6.68, 1.46, 6.10, 2.52, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.0, rounded=True)
    add_textbox(s5, 6.86, 1.56, 5.7, 0.28, "VALIDATED TIER × PLATFORM ADJUSTED METRICS (30D COHORT)",
                font_size=9.5, bold=True, color=C_CYAN)
    tbl_shape = s5.shapes.add_table(6, 4, Inches(6.86), Inches(1.90), Inches(5.74), Inches(1.92))
    style_table(
        tbl_shape.table,
        headers=["Metric", "Organic", "Paid Social", "Paid Video"],
        rows=[
            ["Active Days (30d)", "7.079", "6.865", "6.774"],
            ["Day 7 Retention", "25.86%", "25.34%", "24.52%"],
            ["Day 30 Retention", "13.72%", "14.42%", "13.82%"],
            ["30-Day Gross ARPU", "$2.17", "$1.99", "$2.06"],
            ["30-Day Net ARPU", "$2.13", "$1.97", "$2.04"],
        ],
        col_widths=[2.14, 1.20, 1.20, 1.20],
        font_size=10,
        col_colors={1: C_CYAN, 2: C_BLUE, 3: C_VIOLET},
    )

    # Right Bottom: Statistical Findings Card
    add_rect(s5, 6.68, 4.12, 6.10, 2.18, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.0, rounded=True)
    add_rect(s5, 6.68, 4.12, 0.07, 2.18, fill_color=C_BLUE, line_color=None)
    add_textbox(s5, 6.88, 4.22, 5.7, 0.26, "STATISTICAL & CAUSAL INTERPRETATION", font_size=9.5, bold=True, color=C_CYAN)
    add_rich_bullets(s5, 6.86, 4.52, 5.75, 1.70, [
        [("• Engagement: ", True, C_CYAN), ("Organic holds a real but small edge (+0.21 to +0.31 active days, p < 0.0001) — too small to shift budget alone.", False, C_SLATE)],
        [("• Paid Parity: ", True, C_VIOLET), ("Adjusted Paid Social vs. Paid Video ARPU ($1.99 vs. $2.06) is statistically indistinguishable.", False, C_SLATE)],
        [("• Inconclusive Revenue: ", True, C_BLUE), ("Organic vs. Paid Social adjusted revenue difference is inconclusive (Holm-adjusted p = 0.4497).", False, C_SLATE)],
    ], font_size=10, space_after=6)

    # Left Bottom: Confounding Note
    add_rect(s5, 0.55, 5.44, 5.95, 0.86, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.0, rounded=True)
    add_textbox(s5, 0.72, 5.54, 5.65, 0.68,
                "Why Raw Numbers Mislead: Paid Video scaled in Tier 4 (71.1%) and Android (81.4%) with 54.5% April installs right-censored at D30 — pulling raw ARPU down to $1.55.",
                font_size=9.8, color=C_SLATE, line_spacing=1.2)

    # Bottom Recommendation Banner
    add_rect(s5, 0.55, 6.44, 12.23, 0.52, fill_color=C_CARD_HI, line_color=C_AMBER, line_pt=1.0, rounded=True)
    add_textbox(s5, 0.75, 6.55, 11.8, 0.30,
                "Recommendation: Do NOT cut Paid Video or reallocate UA budget on player quality alone. Missing CPI, ad spend & ad revenue require an LTV vs. CPI experiment.",
                font_size=10.6, bold=True, color=C_WHITE)

    add_footer(s5, "Source: sql/task_3_acquisition_analysis.sql & src/task_3_analysis.py. Clean 30d cohort excludes April installs to prevent right-censoring.")

    # =======================================================================
    # SLIDE 6 — Predicting Player Churn (Deliverable 4)
    # =======================================================================
    s6 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s6)
    add_header(s6, "Deliverable 4  •  Predictive Churn Modelling (Test Cohort: Apr 16, n = 38,644)",
               "Predicting 14-Day Churn with Calibrated, Interpretable Logistic Regression",
               "Using strictly past behaviour (<= T), Logistic Regression achieves 0.7467 ROC-AUC and 2.04x random PR-AUC while remaining transparent to live-ops.", 6)

    # Top KPIs
    add_kpi_card(s6, 0.55, 1.46, 2.92, 1.08, "38,644", "Test Active-7d Players", "7,238 churners (18.73% prevalence)", C_CYAN)
    add_kpi_card(s6, 3.65, 1.46, 2.92, 1.08, "0.7467", "Test ROC-AUC (LogReg)", "0.7852 on 20,129 unseen players", C_BLUE)
    add_kpi_card(s6, 6.75, 1.46, 2.92, 1.08, "0.3830", "Test PR-AUC (LogReg)", "2.04× random baseline (0.1873)", C_EMERALD)
    add_kpi_card(s6, 9.85, 1.46, 2.93, 1.08, "0.1366", "Test Brier Calibration", "Vs. 0.2091 for Balanced LogReg", C_VIOLET)

    # Left: Model Comparison Chart
    add_rect(s6, 0.55, 2.70, 6.35, 4.18, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.0, rounded=True)
    s6.shapes.add_picture(str(charts["s6_models"]), Inches(0.65), Inches(2.80), width=Inches(6.15))

    # Right Top: Executive Explanation & Setup
    add_rect(s6, 7.08, 2.70, 5.70, 2.15, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.0, rounded=True)
    add_rect(s6, 7.08, 2.70, 0.07, 2.15, fill_color=C_CYAN, line_color=None)
    add_textbox(s6, 7.28, 2.80, 5.3, 0.26, "LEAK-FREE SETUP & EXECUTIVE INTUITION", font_size=9.5, bold=True, color=C_CYAN)
    add_rich_bullets(s6, 7.26, 3.10, 5.35, 1.70, [
        [("• Who & What: ", True, C_WHITE), ("Players active in past 7 days → predict ", False, C_SLATE), ("0 active days in next 14 days", True, C_CYAN), (".", False, C_SLATE)],
        [("• Time Splits: ", True, C_WHITE), ("Train Mar 02 (20,025) → Val Mar 23 (26,886) → Test Apr 16 (38,644).", False, C_SLATE)],
        [("• Why LogReg (C=1.0): ", True, C_WHITE), ("Beats Decision Tree (0.7330), matches Balanced LR ranking without breaking probability calibration, and trails HistGB by only 0.011 AUC.", False, C_SLATE)],
    ], font_size=10, space_after=6)

    # Right Bottom: Drivers & Honest Limitations
    add_rect(s6, 7.08, 4.98, 5.70, 1.90, fill_color=C_CARD, line_color=C_AMBER, line_pt=1.0, rounded=True)
    add_textbox(s6, 7.28, 5.08, 5.3, 0.26, "KEY DRIVERS & MODEL LIMITATIONS", font_size=9.5, bold=True, color=C_AMBER)
    add_rich_bullets(s6, 7.26, 5.36, 5.35, 1.45, [
        [("• Lower Risk: ", True, C_EMERALD), ("Higher 30d sessions, playtime, recent active days & ad views.", False, C_SLATE)],
        [("• Higher Risk: ", True, C_CORAL), ("Longer install age (veteran active players lapse at 36.56% vs. 4.46% new).", False, C_SLATE)],
        [("• Known Weakness: ", True, C_AMBER), ("Discrimination weakens for ", False, C_SLATE), ("91+ day players", True, C_WHITE), (" (AUC 0.6241); requires ongoing validation.", False, C_SLATE)],
    ], font_size=9.8, space_after=5)

    add_footer(s6, "Source: sql/task_4_churn_analysis.sql & src/task_4_churn_analysis.py. Zero future telemetry leakage verified across all 32 features.")

    # =======================================================================
    # SLIDE 7 — Turning Predictions into Business Decisions
    # =======================================================================
    s7 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s7)
    add_header(s7, "Deliverable 4  •  Live-Ops Targeting & Economic Trade-Offs",
               "Turning Risk Scores into Targeted Retention Decisions",
               "Top 20% targeting catches 42.43% of churners at 39.73% precision — doubling efficiency over random outreach while containing wasted offers.", 7)

    # Left: Trade-off Chart
    add_rect(s7, 0.55, 1.46, 6.25, 3.92, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.0, rounded=True)
    s7.shapes.add_picture(str(charts["s7_targeting"]), Inches(0.65), Inches(1.54), width=Inches(6.05))

    # Right Top: Targeting Table
    add_rect(s7, 6.98, 1.46, 5.80, 2.38, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.0, rounded=True)
    add_textbox(s7, 7.14, 1.54, 5.45, 0.25, "TEST SET TARGETING TIERS (N = 38,644; 7,238 CHURNERS)",
                font_size=9.2, bold=True, color=C_CYAN)
    t_shp = s7.shapes.add_table(5, 5, Inches(7.14), Inches(1.84), Inches(5.48), Inches(1.86))
    style_table(
        t_shp.table,
        headers=["Target Group", "Targeted", "Caught", "Precision", "Recall"],
        rows=[
            ["Top 5%", "1,933", "931", "48.16%", "12.86%"],
            ["Top 10%", "3,865", "1,735", "44.89%", "23.97%"],
            ["Top 20% ★", "7,729", "3,071", "39.73%", "42.43%"],
            ["Top 30%", "11,593", "4,206", "36.28%", "58.11%"],
        ],
        col_widths=[1.40, 1.02, 0.96, 1.05, 1.05],
        font_size=9.8,
        highlight_row=2,
    )

    # Right Bottom: Top 20% Rationale & Economics
    add_rect(s7, 6.98, 3.96, 5.80, 2.36, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.0, rounded=True)
    add_rect(s7, 6.98, 3.96, 0.07, 2.36, fill_color=C_EMERALD, line_color=None)
    add_textbox(s7, 7.18, 4.06, 5.4, 0.26, "WHY TOP 20% IS THE RECOMMENDED STARTING POINT", font_size=9.5, bold=True, color=C_EMERALD)
    add_rich_bullets(s7, 7.16, 4.34, 5.45, 1.90, [
        [("• Balanced Reach & Waste: ", True, C_WHITE), ("Catches ", False, C_SLATE), ("3,071", True, C_CYAN), (" churners while avoiding 26,748 wasted offers vs. mass-sending (60.27% vs. 81.27% waste).", False, C_SLATE)],
        [("• Risk ≠ Causal Lift: ", True, C_AMBER), ("The model identifies who will lapse — it does ", False, C_SLATE), ("not prove", True, C_AMBER), (" an offer prevents churn.", False, C_SLATE)],
        [("• Assumptions vs. Facts: ", True, C_AMBER), ("Offer cost, save rate, and retained LTV are ", False, C_SLATE), ("unobserved assumptions", True, C_WHITE), (" (e.g., break-even only holds if retained value × save rate exceeds cost / precision).", False, C_SLATE)],
    ], font_size=9.6, space_after=5)

    # Left Bottom Callout: Experimental Design
    add_rect(s7, 0.55, 5.50, 6.25, 0.82, fill_color=C_CARD, line_color=C_BLUE, line_pt=1.0, rounded=True)
    add_textbox(s7, 0.72, 5.59, 5.95, 0.65,
                "Required Validation: Randomize Top 20% (7,729 high-risk players) into Treatment (Offer) vs. Control (No Offer) to measure true incremental save rate and net campaign ROI.",
                font_size=9.8, bold=True, color=C_SLATE, line_spacing=1.2)

    # Bottom Banner
    add_rect(s7, 0.55, 6.44, 12.23, 0.52, fill_color=C_CARD_HI, line_color=C_CYAN, line_pt=1.0, rounded=True)
    add_textbox(s7, 0.75, 6.55, 11.8, 0.30,
                "Rule of Thumb: Tighten to Top 5%–10% for high-cost offers; expand to Top 30% only if A/B tests confirm positive incremental margin.",
                font_size=10.8, bold=True, color=C_WHITE)

    add_footer(s7, "Source: outputs/tables/task_4_threshold_analysis.csv. Wasted offers = False Positives (players who would remain active without an offer).")

    # =======================================================================
    # SLIDE 8 — Final Recommendations and Next Steps
    # =======================================================================
    s8 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s8)
    add_header(s8, "Action Plan  •  Prioritised Roadmap",
               "Six Prioritised Recommendations for Product, Growth, and Live-Ops",
               "Move from misleading blended averages and unvalidated assumptions to stratified reporting and controlled experimentation.", 8)

    actions = [
        ("01", "MONITOR BY SEGMENT", "Segment Engagement & Retention",
         "Track DAU, retention (D1/D7/D14/D30), and payer behaviour by country tier, platform, and channel rather than global totals.",
         "Immediate  •  Product Analytics", C_CYAN),
        ("02", "FIX MONETISATION METRICS", "Replace Blended ARPDAU",
         "Deploy tier-stratified ARPDAU on executive dashboards so Tier 4 mix shifts never disguise true within-tier monetisation gains.",
         "Immediate  •  BI & Leadership", C_EMERALD),
        ("03", "UNBLOCK UA DECISIONS", "Evaluate Channels on CPI + LTV",
         "Combine telemetry with missing marketing CPI, ad spend, and rewarded-ad revenue before shifting budget between Paid Social and Paid Video.",
         "Near-Term  •  Growth & Finance", C_BLUE),
        ("04", "TEST BEFORE SCALING", "Run Randomized Churn A/B Test",
         "Randomize the Top 20% riskiest cohort (39.73% precision, 42.43% recall) into offer vs. holdout control to measure true causal lift.",
         "Near-Term  •  Live-Ops", C_VIOLET),
        ("05", "PROVE UNIT ECONOMICS", "Measure Net Campaign Profit",
         "Quantify actual save rate, incremental IAP + ad revenue, and offer cannibalization cost to calibrate the optimal targeting cutoff.",
         "Post-Test  •  Live-Ops & Finance", C_AMBER),
        ("06", "UPGRADE MODELLING", "Improve 91+ Day Veteran Churn",
         "Add progression-wall, social/guild, and non-linear features (e.g., calibrated gradient boosting) where Logistic Regression weakens (AUC 0.6241).",
         "Next Iteration  •  Data Science", C_CORAL),
    ]

    for idx, (num, tag, title_a, desc_a, owner, acc) in enumerate(actions):
        col = idx % 3
        row = idx // 3
        x0 = 0.55 + col * 4.14
        y0 = 1.48 + row * 2.26
        add_rect(s8, x0, y0, 3.95, 2.08, fill_color=C_CARD, line_color=C_BORDER, line_pt=1.0, rounded=True)
        add_rect(s8, x0, y0, 3.95, 0.055, fill_color=acc, line_color=None)
        add_textbox(s8, x0 + 0.16, y0 + 0.14, 0.55, 0.34, num, font_size=16, bold=True, color=acc)
        add_textbox(s8, x0 + 0.68, y0 + 0.19, 3.1, 0.24, tag, font_size=8.8, bold=True, color=acc)
        add_textbox(s8, x0 + 0.16, y0 + 0.50, 3.63, 0.34, title_a, font_size=13, bold=True, color=C_WHITE)
        add_textbox(s8, x0 + 0.16, y0 + 0.86, 3.63, 0.84, desc_a, font_size=9.8, color=C_SLATE, line_spacing=1.18)
        add_textbox(s8, x0 + 0.16, y0 + 1.74, 3.63, 0.24, owner, font_size=8.8, bold=True, color=C_MUTED)

    # Executive Takeaway Footer Banner
    add_rect(s8, 0.55, 6.08, 12.23, 0.86, fill_color=C_CARD_HI, line_color=C_CYAN, line_pt=1.5, rounded=True)
    add_rect(s8, 0.55, 6.08, 0.09, 0.86, fill_color=C_CYAN, line_color=None)
    add_textbox(s8, 0.80, 6.17, 11.75, 0.24, "EXECUTIVE TAKEAWAY", font_size=9.5, bold=True, color=C_CYAN)
    add_textbox(s8, 0.80, 6.43, 11.75, 0.42,
                "Better product decisions require understanding player composition, engagement, monetisation, acquisition quality, and churn risk together.",
                font_size=12.5, bold=True, color=C_WHITE)

    add_footer(s8, "Deliverables 1–4 audited & reproducible in SQL/Python. Next milestone: integrate Finance CPI / ad revenue and launch Top-20% holdout A/B test.")

    prs.save(str(OUT_PPTX))
    print(f"Presentation saved successfully to: {OUT_PPTX}")


if __name__ == "__main__":
    build_deck()
