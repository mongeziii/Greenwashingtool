"""
Greenwashing Risk Detection Tool
APFA802 Major Project — Beyond the Report
Standalone analytical artefact (Phase 5, solution option 3)

Scores potential greenwashing-pattern risk from THREE disclosed-data signals:
  1. Target Follow-Through Risk   (targets.csv)
  2. Disclosure Quality Gap       (reporting_quality.csv)
  3. High-Stakes Assurance Gap    (reporting_quality.csv)
...plus a supplementary, non-scored text-mining scan of materiality.csv for
vague/promotional sustainability language.

This is a SCREENING TOOL based on disclosure patterns. It does not, and cannot,
prove that a company is greenwashing — see the Methodology & Limitations
section for what it does and does not show.

Run with:
    pip install -r requirements.txt
    streamlit run app.py
"""

import re
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# ---------------------------------------------------------------------------
# PAGE CONFIG + THEME
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Greenwashing Risk Detection Tool",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = Path(__file__).parent / "data"
ASSETS_DIR = Path(__file__).parent / "assets"

INK, PANEL, PANEL_ALT, HAIRLINE = "#0F1512", "#161D18", "#1D2620", "#2B362F"
PAPER, MUTE = "#EDEAE0", "#93A499"
GRAIN, SAGE, RUST, AMBER, SLATE = "#C9A227", "#7A9E85", "#C1553F", "#D98F4E", "#5C7A99"

COMPANY_COLORS = {
    "AVI Limited": GRAIN,
    "Tiger Brands Limited": RUST,
    "Astral Foods Limited": SAGE,
    "RCL Foods Limited": AMBER,
    "Libstar Holdings Limited": SLATE,
}


def inject_css():
    css_path = ASSETS_DIR / "theme.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


def style_fig(fig, height=420):
    fig.update_layout(
        height=height, paper_bgcolor=INK, plot_bgcolor=INK,
        font=dict(family="Inter, sans-serif", color=PAPER, size=13),
        title_font=dict(family="Fraunces, serif", color=PAPER, size=18),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=PAPER)),
        margin=dict(t=50, l=10, r=10, b=10),
        hoverlabel=dict(bgcolor=PANEL_ALT, font=dict(color=PAPER, family="Inter")),
    )
    fig.update_xaxes(gridcolor=HAIRLINE, zerolinecolor=HAIRLINE, color=MUTE, linecolor=HAIRLINE)
    fig.update_yaxes(gridcolor=HAIRLINE, zerolinecolor=HAIRLINE, color=MUTE, linecolor=HAIRLINE)
    return fig


def hero(eyebrow, title, sub=""):
    st.markdown(
        f"""<div class="hero"><p class="hero-eyebrow">{eyebrow}</p>
             <p class="hero-title">{title}</p><p class="hero-sub">{sub}</p></div>""",
        unsafe_allow_html=True,
    )


def tier_badge(tier):
    cls = {"Elevated": "badge-not-achieved", "Moderate": "badge-progress", "Lower": "badge-achieved"}.get(tier, "badge-unknown")
    return f'<span class="badge {cls}">{tier} risk pattern</span>'


# ---------------------------------------------------------------------------
# DATA
# ---------------------------------------------------------------------------
@st.cache_data
def load_data():
    esg = pd.read_csv(DATA_DIR / "esg.csv")
    rq = pd.read_csv(DATA_DIR / "reporting_quality.csv")
    targets = pd.read_csv(DATA_DIR / "targets.csv")
    mat = pd.read_csv(DATA_DIR / "materiality.csv")
    mat = mat[mat.Company != "Unknown"].copy()
    rq["high_stakes"] = (rq["Target Linked"] == 1) | (rq["Financial Linked"] == 1)
    return esg, rq, targets, mat


esg, rq, targets, mat = load_data()
inject_css()

ALL_COMPANIES = sorted(esg["Company"].dropna().unique().tolist())


def color_for(company):
    return COMPANY_COLORS.get(company, "#7f7f7f")


# ---------------------------------------------------------------------------
# SCORING ENGINE
# ---------------------------------------------------------------------------
VAGUE_TERMS = [
    "industry-leading", "industry leading", "world-class", "world class",
    "best-in-class", "best in class", "sustainable future", "net zero",
    "net-zero", "carbon neutral", "environmentally friendly", "eco-friendly",
    "responsible business", "best practice", "strive to", "proud to",
    "award-winning", "pioneering", "cutting-edge", "committed to sustainability",
    "leading the way", "at the forefront",
]


def target_flags(company):
    t = targets[targets.Company == company].copy()
    if t.empty:
        return t, None

    def flag(row):
        s, p = str(row.Status).lower(), str(row.Progress).lower()
        if "not achiev" in s or "worsen" in s:
            return "Target not achieved / performance worsened vs baseline"
        if "cannot be calculated" in p or p.strip() == "nd" or "insufficient" in p:
            return "Progress cannot be calculated from disclosed information"
        return None

    t["Flag reason"] = t.apply(flag, axis=1)
    flagged = t[t["Flag reason"].notna()]
    score = len(flagged) / len(t) * 100
    return t, score


def assurance_flags(company):
    sub = rq[(rq.Company == company) & (rq.high_stakes)]
    if sub.empty:
        return sub, None
    flagged = sub[sub["Assured"] == 0]
    score = len(flagged) / len(sub) * 100
    return flagged, score


def disclosure_gap(company):
    r = rq[rq.Company == company]
    if r.empty:
        return None, None
    avg = r["Total Score"].mean()
    return avg, (8 - avg) / 8 * 100


def low_quality_indicators(company, threshold=2):
    r = rq[(rq.Company == company) & (rq["Total Score"] <= threshold)]
    return r


def vague_language_hits(company):
    m = mat[mat.Company == company].copy()
    if m.empty:
        return m

    def hits(text):
        if pd.isna(text):
            return []
        t = str(text).lower()
        return [term for term in VAGUE_TERMS if term in t]

    m["Matched terms"] = m["Materiality Evidence"].apply(hits)
    m["n_hits"] = m["Matched terms"].apply(len)
    return m[m.n_hits > 0]


@st.cache_data
def compute_all_scores():
    rows = []
    for c in ALL_COMPANIES:
        _, tr = target_flags(c)
        _, ag = assurance_flags(c)
        avg_rqi, dg = disclosure_gap(c)
        comps = [(tr, 0.40, "Target Follow-Through Risk"),
                 (dg, 0.35, "Disclosure Quality Gap"),
                 (ag, 0.25, "High-Stakes Assurance Gap")]
        valid = [(v, w) for v, w, _ in comps if v is not None]
        wsum = sum(w for v, w in valid)
        composite = sum(v * w for v, w in valid) / wsum if wsum else None
        rows.append({
            "Company": c, "Target Follow-Through Risk": tr,
            "Disclosure Quality Gap": dg, "Avg Reporting Quality Index": avg_rqi,
            "High-Stakes Assurance Gap": ag, "Composite Score": composite,
        })
    return pd.DataFrame(rows)


def risk_tier(score):
    if score is None or pd.isna(score):
        return "Unknown"
    if score >= 70:
        return "Elevated"
    if score >= 40:
        return "Moderate"
    return "Lower"


scores_df = compute_all_scores()
scores_df["Risk tier"] = scores_df["Composite Score"].apply(risk_tier)

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
st.sidebar.markdown(
    """<div style="border-bottom:1px solid #2B362F; padding-bottom:14px; margin-bottom:10px;">
         <p style="font-family:'Fraunces',serif; font-size:1.4rem; font-weight:600;
                   color:#EDEAE0; margin:0; line-height:1.15;">🔥 Greenwashing Risk<br>Detection Tool</p>
         <p style="color:#93A499; font-size:0.8rem; margin-top:4px;">
            Disclosure-pattern screening · not a verdict</p>
       </div>""",
    unsafe_allow_html=True,
)
section = st.sidebar.radio(
    "Section",
    ["Overview", "Company drill-down", "Flag log", "Methodology & limitations"],
    label_visibility="collapsed",
)
st.sidebar.markdown('<hr style="margin:16px 0 10px 0;">', unsafe_allow_html=True)
st.sidebar.markdown(
    '<p style="font-size:0.82rem; color:#93A499; line-height:1.5;">'
    "Companion artefact to the ESG-to-Financial Decision Intelligence Dashboard. "
    "Built from the same six-sheet dataset."
    "</p>", unsafe_allow_html=True,
)
st.sidebar.markdown('<hr style="margin:10px 0;">', unsafe_allow_html=True)
chips = "".join(
    f'<span class="company-chip"><span class="company-dot" style="background:{c}"></span>{n.replace(" Limited","").replace(" Holdings","")}</span>'
    for n, c in COMPANY_COLORS.items()
)
st.sidebar.markdown(f'<div style="line-height:2.2;">{chips}</div>', unsafe_allow_html=True)

DISCLAIMER = (
    "🔶 This score reflects **patterns in disclosed data** — unmet or vaguely-progressed "
    "targets, low disclosure-quality scores, and ESG claims linked to targets or financial "
    "narrative without independent assurance. It is a **screening indicator, not proof of "
    "greenwashing**. A high score can also reflect early-stage ESG reporting maturity, "
    "conservative target-setting, or a small sample of disclosed targets. Always verify "
    "against the original report before drawing conclusions about a specific company."
)

# ===========================================================================
# OVERVIEW
# ===========================================================================
if section == "Overview":
    hero("Screening tool · disclosure patterns", "Greenwashing Risk Indicator",
         "Composite score built from three disclosed-data signals across five JSE food companies.")
    st.warning(DISCLAIMER)

    st.markdown("### Composite score by company (0–100, higher = more risk-pattern signals)")
    plot_df = scores_df.sort_values("Composite Score", ascending=False)
    fig = px.bar(plot_df, x="Company", y="Composite Score", color="Company",
                 color_discrete_map=COMPANY_COLORS, range_y=[0, 100], text_auto=".1f")
    fig.add_hline(y=70, line_dash="dot", line_color=RUST, annotation_text="Elevated ≥ 70", annotation_font_color=MUTE)
    fig.add_hline(y=40, line_dash="dot", line_color=GRAIN, annotation_text="Moderate ≥ 40", annotation_font_color=MUTE)
    fig.update_layout(showlegend=False)
    st.plotly_chart(style_fig(fig, height=440), use_container_width=True)

    st.markdown("### Company summary")
    cols = st.columns(len(ALL_COMPANIES))
    for col, (_, row) in zip(cols, scores_df.sort_values("Composite Score", ascending=False).iterrows()):
        with col:
            st.markdown(
                f"""<div style="border-top:3px solid {color_for(row.Company)}; padding-top:8px;">
                      <div style="font-family:'Fraunces',serif; font-size:1.6rem; color:{PAPER};">
                        {row['Composite Score']:.0f}</div>
                      <div style="font-size:0.85rem; color:{MUTE}; margin-bottom:6px;">{row.Company}</div>
                      {tier_badge(row['Risk tier'])}
                    </div>""",
                unsafe_allow_html=True,
            )

    st.markdown("### Component breakdown")
    comp_melt = scores_df.melt(
        id_vars="Company",
        value_vars=["Target Follow-Through Risk", "Disclosure Quality Gap", "High-Stakes Assurance Gap"],
        var_name="Signal", value_name="Score",
    )
    fig2 = px.bar(comp_melt, x="Signal", y="Score", color="Company", barmode="group",
                  color_discrete_map=COMPANY_COLORS, range_y=[0, 100])
    fig2.update_layout(xaxis_tickangle=-10)
    st.plotly_chart(style_fig(fig2, height=420), use_container_width=True)
    st.caption(
        "High-Stakes Assurance Gap is elevated across **all** companies in this sample — "
        "independent (third-party) assurance of target- or financial-linked ESG indicators "
        "is rare sector-wide, not a weakness unique to any one company."
    )

# ===========================================================================
# COMPANY DRILL-DOWN
# ===========================================================================
elif section == "Company drill-down":
    company = st.selectbox("Company", ALL_COMPANIES, key="dd_company")
    row = scores_df[scores_df.Company == company].iloc[0]

    hero("Company drill-down", company, f"Composite score {row['Composite Score']:.0f}/100 — {row['Risk tier']} risk pattern")
    st.markdown(tier_badge(row["Risk tier"]), unsafe_allow_html=True)
    st.warning(DISCLAIMER)

    k1, k2, k3 = st.columns(3)
    k1.metric("Target Follow-Through Risk", f"{row['Target Follow-Through Risk']:.0f}" if pd.notna(row['Target Follow-Through Risk']) else "N/D")
    k2.metric("Disclosure Quality Gap", f"{row['Disclosure Quality Gap']:.0f}" if pd.notna(row['Disclosure Quality Gap']) else "N/D",
              help=f"Average Reporting Quality Index: {row['Avg Reporting Quality Index']:.2f} / 8")
    k3.metric("High-Stakes Assurance Gap", f"{row['High-Stakes Assurance Gap']:.0f}" if pd.notna(row['High-Stakes Assurance Gap']) else "N/D")

    st.markdown("### 1 · Targets — follow-through evidence")
    t, _ = target_flags(company)
    if t.empty:
        st.info("No sustainability targets disclosed for this company.")
    else:
        for _, r in t.iterrows():
            flagged = pd.notna(r["Flag reason"])
            border = RUST if flagged else SAGE
            st.markdown(
                f"""<div class="target-row" style="border-left-color:{border};">
                      <strong>{r.Indicator}</strong> — {r.Target}<br>
                      <span style="color:{MUTE}; font-size:0.88rem;">
                        Status: {r.Status} · Progress: {r.Progress}</span><br>
                      {'<span class="badge badge-not-achieved">' + r["Flag reason"] + '</span>' if flagged else '<span class="badge badge-achieved">No follow-through flag</span>'}
                      <div class="section-note" style="border-top:none; padding-top:4px;">Source: {r.Source}, page {r.Page}</div>
                    </div>""",
                unsafe_allow_html=True,
            )

    st.markdown("### 2 · Reporting quality — weakest-scored indicators")
    low_q = low_quality_indicators(company)
    if low_q.empty:
        st.info("No indicators scored ≤2/8 for this company.")
    else:
        st.caption("Indicators scoring 2 or less out of 8 on the Reporting Quality Index (see companion dashboard, Page 7).")
        st.dataframe(low_q[["Year", "Indicator", "Total Score", "Disclosed", "Definition Clear",
                             "Unit Clear", "Comparable", "Assured"]], use_container_width=True, hide_index=True)

    st.markdown("### 3 · High-stakes indicators without independent assurance")
    af, _ = assurance_flags(company)
    if af.empty:
        st.info("No target- or financial-linked indicators found for this company.")
    else:
        st.caption("Indicators that are linked to a stated target or to financial/operational narrative, but not externally assured.")
        st.dataframe(af[["Year", "Indicator", "Target Linked", "Financial Linked", "Assured"]],
                     use_container_width=True, hide_index=True, height=280)

    st.markdown("### 4 · Supplementary text scan — vague / promotional language")
    st.caption(
        "Non-scored. A simple keyword scan of the raw materiality disclosure text for "
        "promotional phrasing. Source text is extracted report content and may include "
        "boilerplate — treat as a starting point for manual review, not a finding on its own."
    )
    vh = vague_language_hits(company)
    if vh.empty:
        st.info("No matches from this lexicon in the materiality excerpts for this company.")
    else:
        for _, r in vh.iterrows():
            terms = ", ".join(f"“{t}”" for t in r["Matched terms"])
            st.markdown(
                f"""<div class="target-row" style="border-left-color:{GRAIN};">
                      <span class="badge badge-progress">Matched: {terms}</span>
                      <p style="margin-top:8px; color:{MUTE}; font-size:0.88rem;">
                        {str(r['Materiality Evidence'])[:280]}…</p>
                      <div class="section-note" style="border-top:none; padding-top:4px;">Source: {r.Source}, page {r.Page}</div>
                    </div>""",
                unsafe_allow_html=True,
            )

# ===========================================================================
# FLAG LOG
# ===========================================================================
elif section == "Flag log":
    hero("Appendix", "Flag Log", "Every individual flag behind the composite scores, in one exportable table.")
    st.warning(DISCLAIMER)

    companies_sel = st.multiselect("Companies", ALL_COMPANIES, default=ALL_COMPANIES, key="log_companies")

    log_rows = []
    for c in companies_sel:
        t, _ = target_flags(c)
        for _, r in t[t["Flag reason"].notna()].iterrows() if not t.empty else []:
            log_rows.append({"Company": c, "Flag type": "Target follow-through", "Detail": r["Flag reason"],
                              "Indicator": r.Indicator, "Source": r.Source, "Page": r.Page})
        low_q = low_quality_indicators(c)
        for _, r in low_q.iterrows():
            log_rows.append({"Company": c, "Flag type": "Low disclosure quality",
                              "Detail": f"Reporting Quality Index {r['Total Score']}/8",
                              "Indicator": r.Indicator, "Source": "", "Page": ""})
        af, _ = assurance_flags(c)
        for _, r in af.iterrows():
            log_rows.append({"Company": c, "Flag type": "Unassured high-stakes indicator",
                              "Detail": "Linked to target or financial narrative, no independent assurance",
                              "Indicator": r.Indicator, "Source": "", "Page": ""})
        vh = vague_language_hits(c)
        for _, r in vh.iterrows():
            log_rows.append({"Company": c, "Flag type": "Vague language (supplementary)",
                              "Detail": ", ".join(r["Matched terms"]),
                              "Indicator": r["ESG Category"], "Source": r.Source, "Page": r.Page})

    log_df = pd.DataFrame(log_rows)
    if log_df.empty:
        st.info("No flags for this selection.")
    else:
        flag_type_sel = st.multiselect("Flag type", sorted(log_df["Flag type"].unique()),
                                        default=sorted(log_df["Flag type"].unique()))
        st.dataframe(log_df[log_df["Flag type"].isin(flag_type_sel)], use_container_width=True,
                     hide_index=True, height=500)
        st.download_button("⬇ Download flag log (CSV)", log_df.to_csv(index=False).encode("utf-8"),
                            "greenwashing_flag_log.csv", "text/csv")

# ===========================================================================
# METHODOLOGY
# ===========================================================================
elif section == "Methodology & limitations":
    hero("How this tool works", "Methodology & Limitations", "")

    st.markdown("""
### Composite score

A weighted average of three signals, each 0–100 (higher = more risk-pattern signal),
computed per company from your existing dataset:

| Signal | Weight | Source | What it measures |
|---|---|---|---|
| Target Follow-Through Risk | 40% | `targets.csv` | Share of disclosed targets marked *not achieved* / *worsened*, or whose progress *cannot be calculated* from disclosed information |
| Disclosure Quality Gap | 35% | `reporting_quality.csv` | `(8 − average Reporting Quality Index) ÷ 8 × 100` |
| High-Stakes Assurance Gap | 25% | `reporting_quality.csv` | Share of indicators that are *target-linked or financial-linked* but **not** externally assured |

If a company has no disclosed targets, that component is dropped and the remaining
two are re-weighted proportionally (never treated as zero risk or maximum risk).

**Risk tiers** (applied to the composite): Lower < 40 · Moderate 40–69 · Elevated ≥ 70.
These thresholds are a modelling choice for this project, not an industry standard.

### Supplementary text scan

A fixed lexicon of common promotional/vague sustainability phrases (e.g. *"industry-leading"*,
*"net zero"*, *"best practice"*, *"committed to sustainability"*) is matched, case-insensitively,
against the `Materiality Evidence` excerpts in `materiality.csv`. This is simple keyword
matching (content analysis), **not** natural-language understanding — it does not weigh
context, negation, or tone, and is **not included in the composite score**. It is shown as a
manual-review starting point only.

### Limitations

- **Small samples.** Some companies have as few as one disclosed target; a single flagged
  target can swing that company's Target Follow-Through Risk to 100%. Always check `n` before
  interpreting.
- **Assurance gap is sample-wide.** Independent assurance of target/financial-linked ESG
  indicators is rare across *all five* companies in this dataset — a high score on this
  component reflects a sector pattern, not necessarily a company-specific failing.
- **Extracted text, not curated claims.** `materiality.csv` excerpts come from automated
  extraction of report PDFs and may include boilerplate (tables of contents, financial
  statement text) alongside genuine narrative — the text-scan hit rate is deliberately not
  scored for this reason.
- **This tool detects disclosure *patterns*, not intent.** A high score does not mean a
  company is deliberately misleading stakeholders; a low score does not certify that a
  company's ESG claims are accurate. It is designed to direct a human reviewer's attention,
  as part of a wider assessment that should include reading the original reports.
- **Same underlying dataset as the companion dashboard** — data quality issues there
  (restatements, unit inconsistencies, ND vs 0 coding) apply here too.
""")

    with st.expander("🔎 Full per-company score table"):
        st.dataframe(scores_df.round(1), use_container_width=True, hide_index=True)
