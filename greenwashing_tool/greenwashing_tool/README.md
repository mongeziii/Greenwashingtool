# Greenwashing Risk Detection Tool

A standalone Streamlit artefact implementing Phase 5, solution option 3 from the
APFA802 brief: *"A scoring or warning system identifying potential inconsistencies
between sustainability claims, targets and actual performance."*

This is a **companion** artefact to the ESG-to-Financial Decision Intelligence
Dashboard — same underlying six-sheet dataset, same visual language, different job.

## Setup

```bash
cd greenwashing_tool
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## What it does

Computes a **Composite Greenwashing Risk Score (0–100)** per company from three
disclosed-data signals:

1. **Target Follow-Through Risk (40%)** — from `targets.csv`. Flags targets marked
   *not achieved* / *worsened*, or whose progress *cannot be calculated* from what
   was disclosed.
2. **Disclosure Quality Gap (35%)** — from `reporting_quality.csv`. The inverse of
   the average Reporting Quality Index (0–8) per company.
3. **High-Stakes Assurance Gap (25%)** — from `reporting_quality.csv`. Share of
   indicators that are linked to a stated target or to financial/operational
   narrative, but not externally assured.

Plus a **supplementary, non-scored** keyword scan of `materiality.csv` for vague or
promotional sustainability language (content analysis / text mining), shown as a
manual-review starting point rather than a scored input.

## Pages

- **Overview** — composite score bar chart with risk-tier lines, per-company summary
  cards, and a component breakdown chart.
- **Company drill-down** — pick one company and see exactly which targets, which
  weakly-scored indicators, which unassured high-stakes indicators, and which
  flagged excerpts drive its score.
- **Flag log** — every individual flag across all companies in one filterable,
  downloadable table (CSV export) — useful as a report appendix.
- **Methodology & limitations** — the full scoring formula, weights, risk-tier
  thresholds, and an explicit list of what this tool does *not* show.

## Important: what this tool is and isn't

This is a **screening tool based on disclosure patterns** — it does not and cannot
prove that a company is greenwashing. A high score can also reflect early-stage
ESG reporting maturity, a small number of disclosed targets, or a sector-wide
pattern (e.g. low third-party assurance rates across the whole industry, not one
company). Every page carries this disclaimer and every score is traceable back to
the specific target, indicator, or excerpt (with source report and page) behind it.
Use it to direct attention for manual review — always read the original report
before drawing a conclusion about a specific company.

## Extending it

- Swap or extend `VAGUE_TERMS` in `app.py` to tune the text-scan lexicon.
- Adjust the three component weights (currently 40/35/25) or the risk-tier
  thresholds (Lower <40, Moderate 40–69, Elevated ≥70) — both are documented,
  editable modelling choices, not fixed constants.
- To combine this with the main dashboard into one app, the two share the same
  `assets/theme.css` and `.streamlit/config.toml`, so pages could be merged behind
  a single top-level nav if you'd rather submit one artefact.
