# Real-World Data Cleaning & EDA — Online Retail

**Week 1 bootcamp project #2.** While most practice datasets are clean, this
one is genuinely messy: the UCI *Online Retail* dataset is a real UK online
gift retailer's 2010–2011 transaction log with real duplicates, missing IDs,
cancellations, and corrupted prices. The point of this repo is **documented
cleaning decisions**, not just charts.

## What was wrong with the data (audit)

| Problem | Rows | What we did |
|---|---|---|
| Exact duplicate rows | 5,268 | Dropped |
| Cancellation invoices (prefix "C") | 9,251 | Kept, flagged `is_cancellation` |
| Negative quantity without C invoice | 1,336 | Kept, flagged `is_adjustment` (damaged stock etc.) |
| Zero/negative unit price | 2,512 | Dropped (fee/adjustment lines, not sales) |
| Non-product codes (POST, DOT, M, ...) | 2,957 | Dropped (postage, manuals, bank charges) |
| Missing Description | 1,454 raw | Filled `"Unknown"` (mostly gone after price filter) |
| **Missing CustomerID** | **131,516 (25%)** | **Kept as NA** — dropping them would erase a quarter of revenue; customer analyses use the non-null subset, revenue analyses use all rows |

Every step is logged to `outputs/cleaning_report.json` with row counts and the
reasoning — the same discipline as a production pipeline.

## Key findings (cleaned data)

- Net revenue **$9.77M** across **23,195 orders** ($421/order), 3,914 products, 4,362 identified customers, 38 countries
- UK customers drive **85%** of revenue; Netherlands, EIRE, Germany and France follow
- Cancellations cost **$476K**, about 4.6% of gross revenue
- Revenue grows through 2011 with strong seasonality into November
- Top product: *REGENCY CAKESTAND 3 TIER*

## RFM customer segmentation

Using the identified-customer subset (4,334 customers after cleaning), customers were
scored on Recency, Frequency and Monetary value (quintiles, snapshot 2011-12-10) and
mapped to standard RFM segments (`src/rfm.py`, outputs in `rfm_segments.csv` / `5_rfm_segments.png`):

| Segment | Customers | Revenue | Share of revenue |
|---|---|---|---|
| Champions | 956 (22%) | $5.71M | **65.3%** |
| Loyal customers | 768 (18%) | $1.36M | 15.5% |
| At risk (was loyal) | 637 (15%) | $0.78M | 9.0% |
| Promising / new | 964 (22%) | $0.45M | 5.1% |
| Hibernating | 669 (15%) | $0.31M | 3.6% |
| Potential loyalists | 340 (8%) | $0.13M | 1.5% |

Business takeaway: a fifth of the customers generate two-thirds of revenue, and
another $0.78M sits with recently lapsed loyal buyers, the retailer's most
recoverable revenue pool.

## Charts

**What cleaning accomplished** — raw (dashed, with duplicates & fee lines) vs cleaned monthly net revenue:

![](outputs/4_raw_vs_clean.png)

**RFM: a small champion core drives revenue** — bars = revenue, line = share of customers:

![](outputs/5_rfm_segments.png)

## Repo layout

```
├── README.md
├── src/
│   ├── clean.py        # audit -> 7 documented cleaning steps -> clean CSV
│   ├── analyze.py     # EDA charts on the cleaned data
│   └── rfm.py         # RFM segmentation: scores, segments, chart, KPIs
├── data/
│   └── Online Retail.xlsx   # UCI source (not in git; see .gitignore)
└── outputs/
    ├── cleaning_report.json # step-by-step provenance
    ├── 1_monthly_revenue.png      # trend + cancellation value
    ├── 2_top_products.png        # top 10 products
    ├── 3_revenue_by_country.png  # log-scale country revenue
    └── 4_raw_vs_clean.png        # effect of cleaning on the trend
```

## Reproduce

```bash
# download Online Retail.xlsx from UCI (https://archive.ics.uci.edu/dataset/352/online+retail)
# into data/, then:
pip install -r ../superstore-sales-analysis/requirements.txt
python src/clean.py && python src/analyze.py && python src/rfm.py
```

## Why this matters

A quarter of all rows are unidentifiable customers. The lazy fix is
`dropna()` — and it silently deletes 25% of the business's revenue. The real
fix is deciding *per analysis*: revenue questions use all rows, customer
questions use identified ones. That decision, made explicitly and logged, is
what separates data cleaning from data deleting.

## Data source

UCI Machine Learning Repository — *Online Retail* dataset (Daqing Chen et al.,
2012). Intended for education and portfolio use.
